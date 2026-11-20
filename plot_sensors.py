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
    def values(self): return self.__values
    @property
    def label(self): return self.__label
    @property
    def yaxis_erros(self): return self.__yerr
    @property
    def xaxis_erros(self): return self.__xerr
    

class PlotContent(object):
    def __init__(self, plot_path ="", title="", showLegend = True):
        self.__path = plot_path
        self.__title = title
        self.__legend = True
        self.__histos = []

    def addHisto(self, histo: Histogram):
        self.__histos.append(histo)
    @property
    def nHistos(self): return len(self.__histos)
    @property
    def plotPath(self): return self.__path




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
                        nargs="+", default=["Outside"])
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

        summaryPlot = PlotContent(plot_path=f"{args.outFolder}/{d_field.name}.pdf",
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
                deviceCurve = PlotContent(plot_path=f"{args.outFolder}/devices/{dev.name}/{d_field.name}.pdf",
                                          title="{label} evolution in G503 ({sensor_name}) - Last 24h: {mean:.1f} $\\pm$ {stdDev:.1f} {unit}{extra} - {update_time} ".format(
                                                label = args.curve if len(d_field.label) == 0 else d_field.label,
                                                sensor_name = dev.name, mean=mean, stdDev=stdDev, unit=d_field.unit,
                                                extra = f" - too cold: {timedelta(seconds=coldTime)}" if args.curve == "temperature" and coldTime > 60*60*2 else "" ) 
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
                                                              start_time= start_day,
                                                              end_time = min(start_day + timedelta(days=1), now)))
                
                dev_histo = Histogram(times=[t for t, _ in time_series], values=[x  for _, x in time_series],  
                                        label="{name} room ({mean:.1f} $\\pm$ {stdDev:.1f} {unit}){extra}".format(
                                                name = dev.name, mean=mean, stdDev=stdDev, unit=d_field.unit,
                                                extra = f", too cold: {timedelta(seconds=coldTime)}" if coldTime is not None and coldTime > 60*60*2 else "" ) )

                if args.singleCurves:
                    deviceCurve = PlotContent(plot_path=figure_name,
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
            
            summaryPlot = PlotContent(plot_path=f"{args.outFolder}/average/{d_field.name}_{start_day.strftime('%b%y')}.pdf")
            tooColdPlot = PlotContent(plot_path=f"{args.outFolder}/average/tooLowTemperatur_{start_day.strftime('%b%y')}.pdf")

            for dev in devices:
                if dev.name in args.excludeFromSummary: continue
                time_series = dev.sqlDB.fetchFromTable(tableName="average_values",
                                                       columns=["date", "mean", "stdDev"],
                                                       conditions=[f"device={dev.device_id}",
                                                                   f"variable={d_field.id}",
                                                                   f"date>={int(start_day.timestamp())}",
                                                                   f"date<{int(end_day.timestamp())}"])
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
                                                       columns=["date", "alarmPeriod"],
                                                       conditions=[f"device={dev.device_id}",
                                                                   f"variable={d_field.id}",
                                                                   f"date>={int(start_day.timestamp())}",
                                                                   f"date<{int(end_day.timestamp())}"])
                dev_histo = Histogram(times=[datetime.fromtimestamp(t).replace(hour=12) for t, _ ,__ in time_series], 
                                      values= [x  for _, x,__ in time_series], 
                                      xerr=[timedelta(hours=12) for i in range(len(time_series))],  label=dev.name)
                tooColdPlot.addHisto(dev_histo)

            if tooColdPlot.nHistos: plots.append(tooColdPlot)
            if summaryPlot.nHistos: plots.append(summaryPlot)
        
       

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
