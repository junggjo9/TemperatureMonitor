
from datetime import datetime, timedelta
import logging
logging.basicConfig(format='%(levelname)s : %(message)s', level=logging.INFO)



def setupArgParser():
    from sync_database import setupArgParser as argParserBase
    parser = argParserBase()
    parser.add_argument("--averageVars", nargs="+", default = ["va_humidity", "va_temperature"])
    parser.add_argument("--reDoAll", help="Update all entries in the summary table again", default=True,
                        action='store_false')
    return parser


def fillAuxiliaryPoints(time_series:list, max_dt:timedelta = timedelta(minutes = 5)) :
    series_copy = [ p for p in time_series]
    before = len(time_series)
    for p in range(1, before):
        prev_time = time_series[p-1]
        now_time = time_series[p]
        # if prev_time > now_time: raise RuntimeError(f"Ordering issue {p-1} --> {p}  {prev_time} vs {now_time}")
        ### If the two data points are close by don't do anything
        while (now_time[0] - prev_time[0]) > max_dt:
            new_time = [x for x in prev_time]
            new_time[0] = new_time[0] + max_dt
            series_copy.append(tuple(x for x in new_time))
            prev_time = new_time
    series_copy.sort(key=lambda x: x[0])
    #for p in range(1,len(series_copy)):
    #    prev_time = series_copy[p-1]
    #    now_time = series_copy[p]
    #    if prev_time > now_time: raise RuntimeError(f"Ordering issue {p-1} --> {p}  {prev_time} vs {now_time}")
    #    if (now_time[0] - prev_time[0]) > max_dt: raise RuntimeError("Padding issue")
  
    return series_copy

def calcMeanObservable(time_series):
    interval = time_series[-1][0].timestamp() - time_series[0][0].timestamp()
    x = [t.timestamp() for t, _ in time_series]
    y = [x  for _, x in time_series]
    from scipy import integrate
    from math import sqrt
    mean = integrate.trapezoid(y, x=x) / interval
    return mean, sqrt(integrate.trapezoid( [ v**2 for v in y], x=x)/ interval -mean**2) 


def calcDailyAverage(device, field, ignorePastDays = True):
    logging.info(f"calcDailyAverage() - Calculate the {field.name}'s daily average recorded by {device.name}")
    start_day = device.earliestRecord.replace(hour=0, minute=0, second =1, microsecond=0)
    end_day = device.latestRecord.replace(hour=23, minute=59, second=59, microsecond=99)
    now =datetime.now()
    while start_day < end_day:
        date = int(start_day.timestamp())
        record_id = [x[0] for x in device.sqlDB.fetchFromTable(tableName="average_values",
                                    columns=[device.primaryKey("average_values")],
                                    conditions=[f"device={device.device_id}",
                                                f"variable={field.id}",
                                                f"date={date}"])]
                
        if len(record_id) > 0 and (now - start_day).days > 1 and ignorePastDays:
            start_day = start_day + timedelta(days=1)
            continue
        
        record = device.payload(data_field = field,
                                start_time = start_day,
                                end_time = start_day + timedelta(days =1))
        logging.debug(f"calcDailyAverage() - Fetched {len(record)} records for day {start_day.strftime('%d.%m.%y')}")

        start_day = start_day + timedelta(days=1)
        if len(record) < 2:
            logging.debug("calcDailyAverage() - Too little records")        
            continue
        mean, stdDev = calcMeanObservable(fillAuxiliaryPoints(record))
        logging.debug(f"Calculated mean {mean} +- {stdDev}")
        if len(record_id) == 0:
            device.sqlDB.insertRecord(tableName="average_values",
                                       columns=["device", "variable", "mean", "stdDev" , "date" , "nPoints"],
                                       record=[device.device_id, field.id, mean, stdDev, date, len(record)])
        else:
            device.sqlDB.updateRecord(tableName="average_values",
                                       columns=[ "mean", "stdDev" ,"nPoints"],
                                       record=[mean, stdDev, len(record)],
                                       entry_id=record_id[0])


## 0.1479 
## 0.1018 (14h30 - 17) (1h30 - 7)

class CostSlot(object):
    def __init__(self, 
                 start:datetime, 
                 pricePerkWh= 0.):
        self.__start = start
        self.__price = pricePerkWh
    @property
    def start(self): return self.__start
    @property
    def kWhPrice(self): return self.__price
    def check(self, time):
        check_time = time.relpace(hour= self.start.hour, 
                                  minute = self.start.minute,
                                  second= self.start.second)
        return time - check_time > 0

class CostTable(object):
    def __init__(self, slots = []):
        self.__slots=[]


    def _timeSlotNo(self, time):
        for i in range(len(self.__slots)):
            if self.__slots[i].check(time): return i
        return len(self.__slots)



def electricityPrice(time_point: datetime):
    if (time_point.hour == 14 and time_point.minute >=30) or \
       (time_point.hour >= 15 and time_point.hour < 17) or \
       (time_point.hour == 1 and time_point.minute >=30) or \
       (time_point.hour == 2 and time_point.hour < 7): return 0.1018
    return 0.1479


def calcCosts(device, field, ignorePastDays = True):
    logging.info(f"calcCosts() - Calculate the consumpion and costs recorded by {device.name}")
    start_day = device.earliestRecord.replace(hour=0, minute=0, second =1, microsecond=0)
    end_day = device.latestRecord.replace(hour=23, minute=59, second=59, microsecond=99)
    now =datetime.now()
    total_costs =0.
    while start_day < end_day:
        date = int(start_day.timestamp())

        record_id = [x[0] for x in device.sqlDB.fetchFromTable(tableName="average_values",
                                    columns=[device.primaryKey("average_values")],
                                    conditions=[f"device={device.device_id}",
                                                f"variable={field.id}",
                                                f"date={date}"])]
                
        if len(record_id) > 0 and (now - start_day).days > 1 and ignorePastDays:
            start_day = start_day + timedelta(days=1)
            continue

        record = device.payload(data_field = field,
                                start_time = start_day,
                                end_time = start_day + timedelta(days =1))

        if len(record) < 2:
            logging.debug("calcCosts() - Too little records")  
            start_day = start_day + timedelta(days=1)
            continue

        consumption = 0.
        costs = 0.
        last_time = record[0][0]
        for time, consumed in record:
            if electricityPrice(last_time) == electricityPrice(time):
                costs += consumed * electricityPrice(last_time)
            else: ### To be refined
                costs+=consumed *max(electricityPrice(last_time), electricityPrice(time))
            consumption+=consumed
        logging.info(f"calcCosts() - Fetched {len(record)} records for day {start_day.strftime('%d.%m.%y')}. Consumed {consumption:.3f} kWh --> Costs: {costs:.2f}")
        start_day = start_day + timedelta(days=1)

        if len(record_id) == 0:
            device.sqlDB.insertRecord(tableName="average_values",
                                       columns=["device", "variable", "mean", "stdDev" , "date" , "nPoints"],
                                       record=[device.device_id, field.id, consumption, costs, date, len(record)])
        else:
            device.sqlDB.updateRecord(tableName="average_values",
                                       columns=[ "mean", "stdDev" ,"nPoints"],
                                       record=[consumption, costs, len(record)],
                                       entry_id=record_id[0])

if __name__=="__main__":
    from sync_database import setupSmartDevices

    args = setupArgParser().parse_args()

    for device in setupSmartDevices(db_file = args.dataBase):
        logging.debug(f"Analyze device {device.name} that stores data {device.earliestRecord.strftime('%d.%m.%y %H:%M')} until {device.latestRecord.strftime('%d.%m.%y %H:%M')}")
        for var in device.dataFields:
            if var.name in args.averageVars: 
                calcDailyAverage(device = device, field = var, ignorePastDays=args.reDoAll)
            elif var.name == "add_ele":
                calcCosts(device = device, field = var, ignorePastDays=args.reDoAll)
               

