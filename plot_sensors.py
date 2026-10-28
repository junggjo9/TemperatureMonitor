#/env/python

from read_sensor import DeviceData, setupArgParser, loadSensorsFromJSON
from datetime import datetime, timedelta



def fillAuxiliaryPoints(time_series:list, max_interval:int = 10) :
    series_copy = [ p for p in time_series]
    max_dt = timedelta(minutes = max_interval)
    from copy import deepcopy
    before = len(time_series)
    for p in range(1, before):
        prev_time = time_series[p-1]
        now_time = time_series[p]
        ### If the two data points are close by don't do anything
        while (now_time[0] - prev_time[0]) > max_dt:
            new_time = [x for x in prev_time]
            new_time[0] = new_time[0] + max_dt
            series_copy.append(tuple(x for x in new_time))
            prev_time = new_time
    series_copy.sort(key=lambda x: x[0])
    return series_copy


def getMean24Hours(device, 
                   variable, 
                   scale_factor,
                   now= datetime.now()):
    return calcMeanObservable(fillAuxiliaryPoints(dev.data_payload(d_type,
                                                       earliest = now - timedelta(days=1),
                                                       latest = now,
                                                       calibrator= lambda x: scale_factor * x)))
def calcMeanObservable(time_series):
    interval = time_series[-1][0].timestamp() - time_series[0][0].timestamp()
    x = [t.timestamp() for t, _ in time_series]
    y = [x  for _, x in time_series]
    from scipy import integrate
    return integrate.trapezoid(y, x=x) / interval

def findField(device, variable_name):
    for field in device.data_fields:
        if field.name == f"va_{variable_name}":
            return field
    print("Warning the field {variable_name} does not exist")
    return None

if __name__== "__main__":
    parser = setupArgParser()
    parser.add_argument("--curve", help="Which curve to plot",
                        choices=["temperature", "humidity"], default="temperature")
    args = parser.parse_args()

    devices = loadSensorsFromJSON(args.deviceJSON)
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from scipy.ndimage import gaussian_filter1d

    fig, ax = plt.subplots(figsize=(10, 6))

    scale_factor = 1.
    if args.curve == "temperature": scale_factor = 0.1
    elif args.curve == "humidity": scale_factor = 1.
    unit = None
    now = datetime.now()
    start_day = None

    for dev in devices:
        if not start_day or dev.first_record_time.timestamp() < start_day.timestamp():
            start_day = dev.first_record_time
        dev.load_local_db(args.dbFolder)
        
        d_field = findField(dev, args.curve)
        if not d_field: continue
        unit = d_type.unit
        time_series = fillAuxiliaryPoints(dev.data_payload(d_field, calibrator = lambda x: scale_factor*x))
        x = [t for t, _ in time_series]
        y = [x  for _, x in time_series]
        ### Define the legend
        ax.plot(x, y, label="{name} room (Average last 24h: {mean:.1f} {unit})".format(name = dev.name,
                        mean=getMean24Hours(dev, d_field, scale_factor),
                        unit=d_field.unit))

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m - %H:%M'))
    fig.autofmt_xdate()  
    ax.set_title(f"{args.curve} evolution in G503 - last update {now.strftime('%d.%m.%y %H:%M')}")
    ax.set_xlabel("time")
    ax.set_ylabel(f"{args.curve} [{unit}]")
    ax.legend() #plot the legend
    ax.grid(True)

    plt.tight_layout()
    # plt.savefig(f"{args.dbFolder}/{args.curve}.png", dpi=300)
    plt.savefig(f"{args.dbFolder}/{args.curve}.pdf", dpi=300)
    plt.close(fig)

    ### Next plot curves per date
    start_day = datetime.fromisoformat(start.strftime("%d.%m.%y 00:00:01"))
    end_day = datetime.fromisoformat(now.strftime("%d.%m.%y 23:59:59"))
    print ("Temperatur record ranges from {start_day} to {end_day}")
    day_average = {}

    ### Create the daily average
    while start_day < end_day:
        fig, ax = plt.subplots(figsize=(10, 6))
        for dev in devices:
            d_field = findField(dev, args.curve)
            if not d_field: continue
            time_series = fillAuxiliaryPoints(dev.data_payload(d_type, 
                                              earliest = start_day,
                                              latest = start_day + timedelta(days=1),
                                              calibrator = lambda x: scale_factor*x))

            mean = calcMeanObservable(time_series)
            if not dev.name in day_average.keys():
                day_average[dev.name] = []

            x = [t for t, _ in time_series]
            y = [x  for _, x in time_series]
            ### Define the legend
            ax.plot(x, y, label="{name} room (Average: {mean:.1f} {unit})".format(name = dev.name,
                                                                                  mean=mean,
                                                                                  unit=d_field.unit))
           
            day_average[dev.name].append(start_day, mean)

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.set_title(f"{args.curve} evolution in G503 - Record: {start_day.strftime('%d.%m.%y')}")
        ax.set_xlabel("time")
        ax.set_ylabel(f"{args.curve} [{unit}]")
        ax.legend()  # Zeigt die Legende für die verschiedenen Kurven an
        ax.grid(True)

        plt.tight_layout()
        figure_name =f"{args.dbFolder}/daily/{args.curve}_{start_day.strftime('%y-%m-%d')}" 
        # plt.savefig(f"{figure_name}.png", dpi=300)
        plt.savefig(f"{figure_name}.pdf", dpi=300)
        plt.close(fig)

        start_day = end_day + timedelta(days=1)
    ##### Last but not least create the daily summary plot
    for dev, time_series in day_average.items():
        x = [t for t, _ in time_series]
        y = [x  for _, x in time_series]
        ### Define the legend
        ax.plot(x, y, label="{name} room".format(name = dev))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax.set_title(f"{args.curve} evolution in G503 - Daily average")
    ax.set_xlabel("time")
    ax.set_ylabel(f"{args.curve} [{unit}]")
    ax.legend()  # Zeigt die Legende für die verschiedenen Kurven an
    ax.grid(True)

    plt.tight_layout()
    figure_name =f"{args.dbFolder}/average_{args.curve}" 
    # plt.savefig(f"{figure_name}.png", dpi=300)
    plt.savefig(f"{figure_name}.pdf", dpi=300)
    plt.close(fig)








