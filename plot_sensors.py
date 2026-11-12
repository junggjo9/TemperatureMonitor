#/env/python
from sync_database import setupSmartDevices
from curve_analysis import fillAuxiliaryPoints, calcMeanObservable
from datetime import datetime, timedelta
from os import system
from os.path import exists
import logging


def setupArgParser():
    from sync_database import setupArgParser as argParserBase
    parser = argParserBase()
    parser.add_argument("--curve", help="Which curve to plot",
                        choices=["temperature", "humidity"], default="temperature")
    parser.add_argument("--plotPeriod" , help="Maximum period to show on the temperature curves in days",
                        type=int, default=7)
    parser.add_argument("--outFolder", help="Folder where the output plots will be stored",
                        default="plots/")
    return parser

if __name__== "__main__":
    parser = setupArgParser()
    args = setupArgParser().parse_args()

    devices = setupSmartDevices(db_file = args.dataBase)
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from scipy.ndimage import gaussian_filter1d

    fig, ax = plt.subplots(figsize=(10, 6))

    unit = None
    now = datetime.now()
    start_day = None

    db = devices[0].dbConnection

    system(f"mkdir -p {args.outFolder}/daily/")
    for d_field in db.loadVariables():      
        if d_field.name.find(args.curve) == -1: continue
        unit = d_field.unit
  
        for dev in devices:
            if dev.name == "Outside": continue
            if start_day is None or dev.earliestRecord < start_day: 
                start_day = dev.earliestRecord
            time_series = fillAuxiliaryPoints(dev.payload(data_field=d_field, 
                                                          start_time=now - timedelta(days=args.plotPeriod),
                                                          end_time = now))
            if len(time_series) == 0: continue
            x = [t for t, _ in time_series]
            y = [x  for _, x in time_series]
            ### Define the legend
            mean, stdDev = calcMeanObservable([x for x in time_series if x[0] > now - timedelta(days=1)])
            ax.plot(x, y, label="{name} room (Average last 24h: {mean:.1f} $\\pm$ {stdDev:.1f} {unit})".format(name = dev.name,
                            mean=mean, stdDev=stdDev, unit=d_field.unit))

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m - %H:%M'))
        fig.autofmt_xdate()  
        ax.set_title(f"{args.curve} evolution in G503 - last update {now.strftime('%d.%m.%y %H:%M')}")
        ax.set_xlabel("time")
        ax.set_ylabel(f"{args.curve} [{unit}]")
        ax.legend() #plot the legend
        ax.grid(True)

        plt.tight_layout()
        plt.savefig(f"{args.outFolder}/{d_field.name}.pdf", dpi=300)
        plt.close(fig)
  
        ### Next plot curves per date
        start_day = start_day.replace(hour=0, minute=0, second =1, microsecond=0)
        end_day = now.replace(hour=23, minute=59, second=59, microsecond=99)
        logging.info(f"Temperatur record ranges from {start_day.strftime('%d.%m.%y')} to {end_day.strftime('%d.%m.%y')}")
        while start_day < end_day:
            figure_name =f"{args.outFolder}/daily/{d_field.name}_{start_day.strftime('%y-%m-%d')}"
            if exists(f"{figure_name}.pdf") and (start_day.day != now.day or start_day.month != now.month):
                logging.info(f"Do not recreate plot for {d_field.name} recorded @ {start_day.strftime('%d.%m.%y')}")
                start_day = start_day + timedelta(days=1)
                continue

            fig, ax = plt.subplots(figsize=(10, 6))

            filled = False
            for dev in devices:
                if dev.name == "Outside": continue
                date = int(start_day.timestamp())
                stored_avg = dev.sqlDB.fetchFromTable(tableName="average_values",
                                                        columns=["mean", "stdDev"],
                                                        conditions=[f"device={dev.device_id}",
                                                                    f"variable={d_field.id}",
                                                                    f"date={date}"])
                if len(stored_avg) == 0:
                    logging.debug(f"The {dev.name} has no {d_field.name} data stored for {start_day.strftime('%d.%m.%y')}")
                    continue
                mean, stdDev = stored_avg[0]

                time_series = fillAuxiliaryPoints(dev.payload(d_field, 
                                                              start_time= start_day,
                                                              end_time = min(start_day + timedelta(days=1), now)))
                x = [t for t, _ in time_series]
                y = [x  for _, x in time_series]
                ### Define the legend
                ax.plot(x, y, label="{name} room (Average: {mean:.1f} $\\pm$ {stdDev:.1f} {unit})".format(
                                        name = dev.name, mean=mean, stdDev = stdDev, unit=d_field.unit))
                filled = True              
            
            ax.set_title(f"{d_field.name} evolution in G503 - Record: {start_day.strftime('%d.%m.%y')}")
            start_day = start_day + timedelta(days=1)
            if not filled:
               plt.close(fig)
               continue
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.set_xlabel("time")
            ax.set_ylabel(f"{d_field.name} [{unit}]")
            ax.legend()  # Zeigt die Legende für die verschiedenen Kurven an
            ax.grid(True)
            plt.tight_layout()
            plt.savefig(f"{figure_name}.pdf", dpi=300)
            plt.close(fig)
           
        ##### Last but not least create the daily summary plot
        fig, ax = plt.subplots(figsize=(10, 6))
        for dev in devices:
            if dev.name == "Outside": continue

            time_series = dev.sqlDB.fetchFromTable(tableName="average_values",
                                                   columns=["date", "mean", "stdDev"],
                                                  conditions=[f"device={dev.device_id}",
                                                              f"variable={d_field.id}"])

            if len(time_series) == 0: continue
            x = [datetime.fromtimestamp(t) for t, _ ,__ in time_series]
            y = [x  for _, x,__ in time_series]
            e = [e  for _,__, e in time_series]
        	### Define the legend
            ax.errorbar(x, y, yerr=e, xerr=timedelta(hours=12), fmt="^", markersize=10, label="{name} room".format(name = dev.name))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.set_title(f"{args.curve} evolution in G503 - Daily average last update {now.strftime('%d.%m.%y %H:%M')}")
        ax.set_xlabel("time")
        ax.set_ylabel(f"{args.curve} [{unit}]")
        ax.legend()  
        ax.grid(True)

        plt.tight_layout()
        figure_name =f"{args.outFolder}/average_{d_field.name}" 
        plt.savefig(f"{figure_name}.pdf", dpi=300)
        plt.close(fig)








