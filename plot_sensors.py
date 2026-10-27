#/env/python

from read_sensor import DeviceData, setupArgParser, loadSensorsFromJSON
from datetime import datetime, timedelta


def getMean24Hours(device, variable, scale_factor):
    mean = 0.
    now = datetime.now()
    yesterday = now - timedelta(days=1)

    time_series = dev.data_payload(d_type,
                                   earliest = yesterday,
                                   latest = now)
    interval = time_series[-1][0].timestamp() - time_series[0][0].timestamp()
    x = [t.timestamp() for t, _ in time_series]
    y = [scale_factor*x  for _, x in time_series]
    from scipy import integrate
    return integrate.trapezoid(y, x=x) / interval


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

    for dev in devices:
        dev.load_local_db(args.dbFolder)
        for d_type in dev.data_fields:
            if d_type.name != f"va_{args.curve}":
                continue
            unit = d_type.unit
            time_series = dev.data_payload(d_type)
            x = [t for t, _ in time_series] + [datetime.now()]
            y = [scale_factor*x  for _, x in time_series]
            y.append(y[-1])
            # y = gaussian_filter1d(y, sigma = 3)

            # print("Legend ",da)
            ### Define the legend
            ax.plot(x, y, label="{name} room (Average last 24h: {mean:.1f} {unit})".format(name = dev.name,
                                  mean=getMean24Hours(dev, d_type, scale_factor),
                                  unit=d_type.unit))

            # 3. Datumsformatierung für die X-Achse optimieren
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    fig.autofmt_xdate()  #Dreht die Datumsbeschriftungen leicht, damit sie lesbar sind

    ax.set_title(f"{args.curve} evolution in G503 - last update {datetime.now().strftime('%d.%m.%y %H:%M')}")
    ax.set_xlabel("time")
    ax.set_ylabel(f"{args.curve} [{unit}]")
    ax.legend()  # Zeigt die Legende für die verschiedenen Kurven an
    ax.grid(True)

    # 5. Diagramm als PNG speichern und Layout anpassen
    plt.tight_layout()
    plt.savefig(f"{args.dbFolder}/{args.curve}.png", dpi=300)
    plt.savefig(f"{args.dbFolder}/{args.curve}.pdf", dpi=300)
    plt.close(fig)  # Schließt die Figure, um Speicher freizugeben
    print (f"Loaded {len(devices)} temperature sensors")

   





