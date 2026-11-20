#/env/python
from sync_database import setupSmartDevices
from curve_analysis import fillAuxiliaryPoints, calcMeanObservable, periodBelowThreshold
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from os import system
from os.path import exists
import logging


class Histogram(object):
    def __init__(self, times=[], values=[], xerr=[], yerr=[],  label=""):
        self.__time = times
        self.__y = values
        self.__yerr = yerr if len(yerr) == len(values) else None
        self.__xerr = xerr if len(xerr) == len(values) else None
        self.__label = label

    @property
    def time(self): return self.__time
    @property
    def values(self): return self.__y
    @property
    def label(self): return self.__label
    @property
    def yaxis_erros(self): return self.__yerr
    @property
    def xaxis_erros(self): return self.__xerr
    

class PlotContent(object):
    def __init__(self, plot_path ="", title="", showLegend = True,
                 xLabel="time", yLabel="", xDateFormat="%d.%m %H:%M",
                 countThreshold=None, countLabel=""):
        self.__path = plot_path
        self.__title = title
        self.__legend = showLegend
        self.__xLabel = xLabel
        self.__yLabel = yLabel
        self.__xDateFormat = xDateFormat
        ### If set, count the time points where at least one histogram exceeds the threshold
        self.__countThreshold = countThreshold
        self.__countLabel = countLabel
        self.__histos = []

    def addHisto(self, histo: Histogram):
        self.__histos.append(histo)
    @property
    def nHistos(self): return len(self.__histos)
    @property
    def plotPath(self): return self.__path
    @property
    def title(self): return self.__title
    @property
    def showLegend(self): return self.__legend
    @property
    def histos(self): return self.__histos
    @property
    def xLabel(self): return self.__xLabel
    @property
    def yLabel(self): return self.__yLabel
    @property
    def xDateFormat(self): return self.__xDateFormat
    @property
    def countThreshold(self): return self.__countThreshold
    @property
    def countLabel(self): return self.__countLabel


def latestPerDay(rows):
    """Rows are (date, ..., lastUpdate). The average_values table may contain several entries
       for the same calendar day (e.g. stored at 00:00:00 and 00:00:01 by different runs).
       Keep only the most recently updated one per day and drop the lastUpdate column."""
    per_day = {}
    for row in rows:
        day = datetime.fromtimestamp(row[0]).date()
        if day not in per_day or row[-1] > per_day[day][-1]:
            per_day[day] = row
    return [per_day[day][:-1] for day in sorted(per_day)]


def drawPlots(plots):
    """Draw each PlotContent with matplotlib and save it to its plotPath"""
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from os import makedirs
    from os.path import dirname
    from itertools import cycle
    markers = ["^", "o", "s", "v", "D", "P", "X", "*", "<", ">", "h", "p"]
    for plot in plots:
        fig, ax = plt.subplots(figsize=(12, 6))
        exceeding_times = set()
        for histo, marker in zip(plot.histos, cycle(markers)):
            values = histo.values
            yerr = histo.yaxis_erros
            ### matplotlib cannot draw timedeltas on the y-axis -> convert to hours
            if len(values) and isinstance(values[0], timedelta):
                values = [v.total_seconds() / 3600. for v in values]
                if yerr is not None:
                    yerr = [e.total_seconds() / 3600. for e in yerr]
            if plot.countThreshold is not None:
                exceeding_times.update(t.date() for t, v in zip(histo.time, values) if v > plot.countThreshold)
            xerr = histo.xaxis_erros
            if xerr is not None or yerr is not None:
                ax.errorbar(histo.time, values, xerr=xerr, yerr=yerr,
                            fmt=marker, markersize=8, capsize=3, label=histo.label)
            else:
                ### Dense time series: only mark every n-th point to keep the curve readable
                ax.plot(histo.time, values, marker=marker, markersize=7,
                        markevery=max(1, len(values) // 20), label=histo.label)
        ax.xaxis.set_major_formatter(mdates.DateFormatter(plot.xDateFormat))
        fig.autofmt_xdate()
        if len(plot.title): ax.set_title(plot.title)
        if len(plot.xLabel): ax.set_xlabel(plot.xLabel)
        if len(plot.yLabel): ax.set_ylabel(plot.yLabel)
        if plot.countThreshold is not None:
            ax.axhline(plot.countThreshold, color="red", linestyle="--", linewidth=1)
            ### Place the counter above the axes (top right) so it never covers the data or the legend
            ax.text(1.0, 1.02, f"{plot.countLabel}: {len(exceeding_times)}", transform=ax.transAxes,
                    fontsize=14, horizontalalignment="right", verticalalignment="bottom",
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        ### Legend outside the axes on the right so it never hides data points
        if plot.showLegend: ax.legend(fontsize=14, markerscale=1.5, loc="upper left",
                                      bbox_to_anchor=(1.01, 1.0), borderaxespad=0.)
        ax.grid(True)
        fig.tight_layout()
        if len(dirname(plot.plotPath)): makedirs(dirname(plot.plotPath), exist_ok=True)
        fig.savefig(plot.plotPath, dpi=300, bbox_inches="tight")
        logging.info(f"Saved {plot.plotPath}")
        plt.close(fig)


def setupArgParser():
    from sync_database import setupArgParser as argParserBase
    parser = argParserBase()
    parser.add_argument("--curve", help="Which curve to plot",
                        choices=["temperature", "humidity"], default="temperature")
    parser.add_argument("--plotPeriod" , help="Maximum period to show on the temperature curves in days",
                        type=int, default=7)
    parser.add_argument("--outFolder", help="Folder where the output plots will be stored",
                        default="./temperature_flat/")
    parser.add_argument("--singleCurves", help="Switch to toggle whether the", default=False, 
                        action='store_true')
    parser.add_argument("--excludeFromSummary", help="Name of the devices to be exluded from the common plot",
                        nargs="+", default=["Outside", "Station"])
    return parser

if __name__== "__main__":
    args = setupArgParser().parse_args()
    devices = setupSmartDevices(db_file = args.dataBase)
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    now = datetime.now()
    start_day = None
    db = devices[0].dbConnection

    plots = []

    for d_field in db.loadVariables():
        if d_field.name.find(args.curve) == -1: continue

        yLabel = "{label} [{unit}]".format(label = args.curve if len(d_field.label) == 0 else d_field.label,
                                           unit = d_field.unit)
        summaryPlot = PlotContent(plot_path=f"{args.outFolder}/{d_field.name}.pdf", yLabel=yLabel,
                                  title= f"{args.curve} evolution in G503 - last update {now.strftime('%d.%m.%y %H:%M')}")

        for dev in devices:
            if not args.singleCurves and dev.name in args.excludeFromSummary: continue
           
            if start_day is None or dev.earliestRecord < start_day: 
                start_day = dev.earliestRecord
            time_series = fillAuxiliaryPoints(dev.payload(data_field=d_field, 
                                                          start_time=now - timedelta(days=args.plotPeriod),
                                                          end_time = now))
            if len(time_series) == 0: 
                continue
     
            ### Define the legend
            time_series24h = [x for x in time_series if x[0] > now - timedelta(days=1)]
            mean, stdDev = calcMeanObservable(time_series24h)
            coldTime = periodBelowThreshold(time_series24h) if args.curve == "temperature" else 0

            dev_histo = Histogram(times=[t for t, _ in time_series], values=[x  for _, x in time_series],  
                                  label="{name} room (Last 24h: {mean:.1f} $\\pm$ {stdDev:.1f} {unit}){extra}".format(
                                            name = dev.name, mean=mean, stdDev=stdDev, unit=d_field.unit,
                                            extra = f", too cold: {timedelta(seconds=coldTime)}" if args.curve == "temperature" and coldTime > 60*60*2 else "" ) )
            if not dev.name in args.excludeFromSummary: 
                summaryPlot.addHisto(dev_histo)
            if args.singleCurves:
                deviceCurve = PlotContent(plot_path=f"{args.outFolder}/devices/{dev.name}/{d_field.name}.pdf", yLabel=yLabel,
                                          title="{label} evolution in G503 ({sensor_name}) - Last 24h: {mean:.1f} $\\pm$ {stdDev:.1f} {unit}{extra} - {update_time} ".format(
                                                label = args.curve if len(d_field.label) == 0 else d_field.label,
                                                sensor_name = dev.name, mean=mean, stdDev=stdDev, unit=d_field.unit,
                                                extra = f" - too cold: {timedelta(seconds=coldTime)}" if args.curve == "temperature" and coldTime > 60*60*2 else "",
                                                update_time=now.strftime('%d.%m.%y %H:%M') ) 
                                          )
                deviceCurve.addHisto(dev_histo)
                plots.append(deviceCurve)
        if summaryPlot.nHistos > 0:
            plots.append(summaryPlot)
        ### Next plot curves per date
        start_day = start_day.replace(hour=0, minute=0, second =0, microsecond=0)
        end_day = now.replace(hour=23, minute=59, second=59, microsecond=99)
        logging.info(f"Record ranges from {start_day.strftime('%d.%m.%y')} to {end_day.strftime('%d.%m.%y')}")
        logging.info((end_day - start_day).days)

        for day in range((end_day - start_day).days +1):
            today = start_day + timedelta(days = day)
            summaryPlot = PlotContent(plot_path=f"{args.outFolder}/daily/{d_field.name}_{today.strftime('%y-%m-%d')}.pdf",
                                  yLabel=yLabel, xDateFormat="%H:%M",
                                  title= f"{args.curve} evolution in G503 - last update {now.strftime('%d.%m.%y %H:%M')}")
            ### Do not recreate the figure
            if exists(summaryPlot.plotPath) and (now - today).days > 1 and not args.singleCurves:
                logging.debug(f"Do not recreate plot for {d_field.name} recorded @ {today.strftime('%d.%m.%y')}")
                continue
            
            date = int(today.timestamp())
            logging.info(f"Check device records @ {today.strftime('%d.%m.%y')} ")
            for dev in devices:
                figure_name=f"{args.outFolder}/daily/{dev.name}/{d_field.name}_{today.strftime('%d.%m.%y')}.pdf"
                if args.singleCurves and exists(figure_name) and (now - today).days > 1 :
                    logging.debug(f"Do not recreate plot {figure_name}")
                    continue
                
                stored_avg = dev.sqlDB.fetchFromTable(tableName="average_values",
                                                        columns=["mean", "stdDev"] + (["alarmPeriod"] if args.curve == "temperature" else []),
                                                        conditions=[f"device={dev.device_id}",
                                                                    f"variable={d_field.id}",
                                                                    f"date={date}"])
                if len(stored_avg) == 0:
                    logging.debug(f"The {dev.name} has no {d_field.name} data stored for {today.strftime('%d.%m.%y')}")
                    continue
                mean= stored_avg[0][0]
                stdDev = stored_avg[0][1]
                coldTime = stored_avg[0][2] if len(stored_avg[0]) == 3 else None
              
                time_series = fillAuxiliaryPoints(dev.payload(d_field, 
                                                              start_time= today,
                                                              end_time = today + timedelta(days=1)))
                
                dev_histo = Histogram(times=[t for t, _ in time_series], values=[x  for _, x in time_series],  
                                        label="{name} room ({mean:.1f} $\\pm$ {stdDev:.1f} {unit}){extra}".format(
                                                name = dev.name, mean=mean, stdDev=stdDev, unit=d_field.unit,
                                                extra = f", too cold: {timedelta(seconds=coldTime)}" if coldTime is not None and coldTime > 60*60*2 else "" ) )

                if args.singleCurves:
                    deviceCurve = PlotContent(plot_path=figure_name, yLabel=yLabel, xDateFormat="%H:%M",
                                          title="{label} evolution in G503 ({sensor_name})".format(
                                                    label = args.curve if len(d_field.label) == 0 else d_field.label,
                                                    sensor_name = dev.name))
                    deviceCurve.addHisto(dev_histo)
                    plots.append(deviceCurve)    
                if not dev.name in args.excludeFromSummary: 
                    summaryPlot.addHisto(dev_histo)

            if summaryPlot.nHistos > 0: plots.append(summaryPlot)
           
        
        logging.info("Daily curves finished. Summary values")

        start_month = start_day.replace(day=1)
        for month in range (relativedelta(end_day, start_month).months +1):
            start_day = start_month + relativedelta(months = month)
            end_day = start_day + relativedelta(months=1)
            
            summaryPlot = PlotContent(plot_path=f"{args.outFolder}/average/{d_field.name}_{start_day.strftime('%b%y')}.pdf",
                                      xLabel="date", yLabel=f"daily average {yLabel}", xDateFormat="%d.%m.%y")
            tooColdPlot = PlotContent(plot_path=f"{args.outFolder}/average/low_temperature_{start_day.strftime('%b%y')}.pdf",
                                      xLabel="date", yLabel="time below 18 degrees [h]", xDateFormat="%d.%m.%y",
                                      countThreshold=6, countLabel="Days with > 6 h below 18 degrees")

            for dev in devices:
                if dev.name in args.excludeFromSummary: continue
                time_series = dev.sqlDB.fetchFromTable(tableName="average_values",
                                                       columns=["date", "mean", "stdDev", "lastUpdate"],
                                                       conditions=[f"device={dev.device_id}",
                                                                   f"variable={d_field.id}",
                                                                   f"date>={int(start_day.timestamp())}",
                                                                   f"date<{int(end_day.timestamp())}"])
                time_series = latestPerDay(time_series)
                if len(time_series) ==0: 
                    continue
                             
                dev_histo = Histogram(times=[datetime.fromtimestamp(t).replace(hour=12) for t, _ ,__ in time_series], 
                                      values= [x  for _, x,__ in time_series], 
                                      xerr=[timedelta(hours=12) for i in range(len(time_series))], 
                                      yerr=[e  for _,__, e in time_series],  label=dev.name)
                summaryPlot.addHisto(dev_histo)

                ### For the temperatures plot also the time where the flat is too cold
                if "temperature" not in d_field.name: continue

                time_series = dev.sqlDB.fetchFromTable(tableName="average_values",
                                                       columns=["date", "alarmPeriod", "lastUpdate"],
                                                       conditions=[f"device={dev.device_id}",
                                                                   f"variable={d_field.id}",
                                                                   f"date>={int(start_day.timestamp())}",
                                                                   f"date<{int(end_day.timestamp())}"])
                time_series = [(t, x) for t, x in latestPerDay(time_series) if x is not None]
                dev_histo = Histogram(times=[datetime.fromtimestamp(t).replace(hour=12) for t, _ in time_series], 
                                      values= [timedelta(seconds=x)  for _, x in time_series], 
                                      xerr=[timedelta(hours=12) for i in range(len(time_series))],  label=dev.name)
                tooColdPlot.addHisto(dev_histo)

            if tooColdPlot.nHistos: plots.append(tooColdPlot)
            if summaryPlot.nHistos: plots.append(summaryPlot)

    ### Draw all collected plots
    drawPlots(plots)
        
       

        #     if len(time_series) == 0: continue
        #     x = [datetime.fromtimestamp(t) for t, _ ,__ in time_series]
        #     y = [x  for _, x,__ in time_series]
        #     e = [e  for _,__, e in time_series]
        # 	### Define the legend
        #     ax.errorbar(x, y, yerr=e, xerr=timedelta(hours=12), fmt="^", markersize=10, label="{name} room".format(name = dev.name))
        #     ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        # ax.set_title(f"{args.curve} evolution in G503 - Daily average last update {now.strftime('%d.%m.%y %H:%M')}")
        # ax.set_xlabel("time")
        # ax.set_ylabel(f"{args.curve} [{unit}]")
        # ax.legend()  
        # ax.grid(True)

        # plt.tight_layout()
        # figure_name =f"{args.outFolder}/average_{d_field.name}" 
        # plt.savefig(f"{figure_name}.pdf", dpi=300)
        # logging.info(f"Saved {figure_name}.pdf")
        # plt.close(fig)
