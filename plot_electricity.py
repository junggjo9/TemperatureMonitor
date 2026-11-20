#/env/python
from sync_database import setupSmartDevices
from plot_sensors import Histogram, PlotContent, latestPerDay, drawPlots
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging


def setupArgParser():
    from sync_database import setupArgParser as argParserBase
    parser = argParserBase()
    parser.add_argument("--outFolder", help="Folder where the output plots will be stored",
                        default="./temperature_flat/")
    parser.add_argument("--variable", help="Name of the variable whose daily consumption & costs are stored",
                        default="add_ele")
    return parser


if __name__ == "__main__":
    args = setupArgParser().parse_args()
    devices = setupSmartDevices(db_file=args.dataBase)
    db = devices[0].dbConnection

    now = datetime.now()
    plots = []

    for d_field in db.loadVariables():
        if d_field.name != args.variable: continue

        ### Only consider the devices that have consumption summaries stored (mean = kWh, stdDev = costs)
        dev_records = {}
        start_day = None
        for dev in devices:
            records = latestPerDay(dev.sqlDB.fetchFromTable(tableName="average_values",
                                                            columns=["date", "mean", "stdDev", "lastUpdate"],
                                                            conditions=[f"device={dev.device_id}",
                                                                        f"variable={d_field.id}"]))
            if len(records) == 0: continue
            dev_records[dev] = records
            first = datetime.fromtimestamp(records[0][0])
            if start_day is None or first < start_day: start_day = first
        if start_day is None:
            logging.warning(f"No consumption summaries stored for {d_field.name}")
            continue

        ### One plot per month for the consumption and one for the costs
        start_month = start_day.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_start = start_month
        while month_start <= now:
            month_end = month_start + relativedelta(months=1)
            tag = month_start.strftime('%b%y')
            consumptionPlot = PlotContent(plot_path=f"{args.outFolder}/electricity/consumption_{tag}.pdf",
                                          title=f"Electricity consumption {month_start.strftime('%B %Y')} - last update {now.strftime('%d.%m.%y %H:%M')}",
                                          xLabel="date", yLabel="daily consumption [kWh]", xDateFormat="%d.%m.%y")
            costPlot = PlotContent(plot_path=f"{args.outFolder}/electricity/costs_{tag}.pdf",
                                   title=f"Electricity costs {month_start.strftime('%B %Y')} - last update {now.strftime('%d.%m.%y %H:%M')}",
                                   xLabel="date", yLabel="daily costs [€]", xDateFormat="%d.%m.%y")

            for dev, records in dev_records.items():
                in_month = [r for r in records
                            if month_start <= datetime.fromtimestamp(r[0]) < month_end]
                if len(in_month) == 0: continue
                times = [datetime.fromtimestamp(t).replace(hour=12, minute=0, second=0) for t, _, __ in in_month]
                xerr = [timedelta(hours=12)] * len(in_month)
                consumption = [kWh for _, kWh, __ in in_month]
                costs = [c for _, __, c in in_month]
                consumptionPlot.addHisto(Histogram(times=times, values=consumption, xerr=xerr,
                                                   label=f"{dev.name} (total: {sum(consumption):.1f} kWh)"))
                costPlot.addHisto(Histogram(times=times, values=costs, xerr=xerr,
                                            label=f"{dev.name} (total: {sum(costs):.2f} €)"))

            if consumptionPlot.nHistos: plots.append(consumptionPlot)
            if costPlot.nHistos: plots.append(costPlot)
            month_start = month_end

    drawPlots(plots)
