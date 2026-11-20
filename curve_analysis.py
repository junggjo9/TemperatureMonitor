
from datetime import datetime, timedelta, time
import logging
logging.basicConfig(format='%(levelname)s : %(message)s', level=logging.INFO)



class CostSlot(object):
    def __init__(self, 
                 start:datetime, 
                 end:datetime,
                 pricePerkWh= 0.):
        self.__start = start
        self.__end = end
        self.__price = pricePerkWh
    @property
    def start(self): return self.__start
    @property
    def end(self): return self.__end
    @property
    def kWhPrice(self): return self.__price
    @staticmethod
    def replaceClock(time, replaceW):
        return time.replace(hour= replaceW.hour, 
                            minute = replaceW.minute,
                            second= replaceW.second)
    def check(self, time):
        return time.timestamp() - self.replaceClock(time, self.start).timestamp() > 0 and \
              self.replaceClock(time, self.end).timestamp() - time.timestamp() >= 0

class CostTable(object):
    def __str__(self):
        out_str = ""
        for slot in self.__slots:
            out_str+=f"  -- {slot.start} - {slot.end}, price: {slot.kWhPrice}\n"
        return out_str
    def __init__(self):
        self.__slots=[CostSlot(start=time(hour = 0, minute= 00),
                               end=time(hour=1, minute=29, second=59),
                               pricePerkWh= 0.1479),
                      CostSlot(start=time(hour = 1, minute= 30),
                               end=time(hour=6, minute=59, second=59),
                               pricePerkWh= 0.1018),
                      CostSlot(start=time(hour = 7, minute= 0),
                               end=time(hour=14, minute=29, second=59),
                               pricePerkWh= 0.1479),
                      CostSlot(start=time(hour = 14, minute= 30),
                               end=time(hour=16, minute=59, second=59),
                               pricePerkWh= 0.1018),
                      CostSlot(start=time(hour = 17, minute= 00),
                               end=time(hour=23, minute=59, second=59),
                               pricePerkWh= 0.1479)]

    def _timeSlotNo(self, time):
        for i in range(self.nSlots):
            if self.__slots[i].check(time): return i
        return self.nSlots
    @property
    def nSlots(self): return len(self.__slots)
    def price(self, start_clock, end_clock, consumed_kwH):
        if start_clock > end_clock:
            raise RuntimeError(f"The start time cannot be after the end time")
        slot_a = self._timeSlotNo(start_clock)
        slot_b = self._timeSlotNo(end_clock)
        if slot_a == slot_b: return self.__slots[slot_a].kWhPrice * consumed_kwH
        if slot_b == 0: slot_b = self.nSlots
            
        interval = end_clock.timestamp() - start_clock.timestamp()
        logging.info(f"price evalation time interval: {timedelta(seconds=interval)},  electricity: {consumed_kwH},  {start_clock.strftime('%d.%m.%y %H:%M:%S')} ({slot_a}), {end_clock.strftime('%d.%m.%y %H:%M:%S')} ({slot_b})")
        calc_price = 0.
        for slot_no in range(slot_a, slot_b+1, 1):
            slot = self.__slots[slot_no % self.nSlots]
            duration = min(slot.replaceClock(end_clock, slot.end), end_clock) - \
                       max(slot.replaceClock(start_clock, slot.start), start_clock)
            slot_price = duration.seconds * consumed_kwH * slot.kWhPrice
            calc_price+= slot_price
            logging.info(f" interval duration: {duration}, {slot_price / interval:.2f}")
        return calc_price / interval


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
    return mean, sqrt(max(integrate.trapezoid( [ v**2 for v in y], x=x)/ interval -mean**2,0.)) 


def summaryUpdateNeeded(start_day, record_id, ignorePastDays = True):
    now = datetime.now()
    return not ignorePastDays or len(record_id) == 0 or (now - start_day).days <= 1  or \
             (datetime.fromtimestamp(record_id[0][1]) - start_day).days <= 1

def calcDailyAverage(device, field, ignorePastDays = True):
    logging.info(f"calcDailyAverage() - Calculate the {field.name}'s daily average recorded by {device.name}")
    start_day = device.earliestRecord.replace(hour=0, minute=0, second =1, microsecond=0)
    end_day = device.latestRecord.replace(hour=23, minute=59, second=59, microsecond=99)
    now =datetime.now()
    while start_day < end_day:
        date = int(start_day.timestamp())
        record_id = device.sqlDB.fetchFromTable(tableName="average_values",
                                    columns=[device.primaryKey("average_values"), "lastUpdate"],
                                    conditions=[f"device={device.device_id}",
                                                f"variable={field.id}",
                                                f"date={date}"])
                
        if not summaryUpdateNeeded(start_day, record_id, ignorePastDays):
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
                                       columns=["device", "variable", "mean", "stdDev" , "date" , "nPoints", "lastUpdate"],
                                       record=[device.device_id, field.id, mean, stdDev, date, len(record), int(datetime.now().timestamp())])
        else:
            device.sqlDB.updateRecord(tableName="average_values",
                                       columns=[ "mean", "stdDev" ,"nPoints", "lastUpdate"],
                                       record=[mean, stdDev, len(record), int(datetime.now().timestamp())],
                                       entry_id=record_id[0][0])

def calcCosts(device, field, ignorePastDays = True):
    logging.info(f"calcCosts() - Calculate the consumption and costs recorded by {device.name}")
    start_day = device.earliestRecord.replace(hour=0, minute=0, second =1, microsecond=0)
    end_day = device.latestRecord.replace(hour=23, minute=59, second=59, microsecond=99)
    now =datetime.now()
    total_costs =0.
    while start_day < end_day:
        logging.info(f"calcCosts() - {start_day} until {end_day}")
        date = int(start_day.timestamp())

        record_id =  device.sqlDB.fetchFromTable(tableName="average_values",
                                    columns=[device.primaryKey("average_values"), "lastUpdate"],
                                    conditions=[f"device={device.device_id}",
                                                f"variable={field.id}",
                                                f"date={date}"])
                
        if not summaryUpdateNeeded(start_day, record_id, ignorePastDays):
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
        electric_tarif = CostTable()
        logging.debug(f"calcCosts() - Cost table\n{electric_tarif}")
        for time, consumed in record:
            costs+= electric_tarif.price(start_clock = last_time, end_clock = time, consumed_kwH = consumed)
            consumption+=consumed
            last_time = time
        logging.debug(f"calcCosts() - Fetched {len(record)} records for day {start_day.strftime('%d.%m.%y')}. Consumed {consumption:.3f} kWh --> Costs: {costs:.2f}")

        start_day = start_day + timedelta(days=1)
        if len(record_id) == 0:
            device.sqlDB.insertRecord(tableName="average_values",
                                       columns=["device", "variable", "mean", "stdDev" , "date" , "nPoints", "lastUpdate"],
                                       record=[device.device_id, field.id, consumption, costs, date, len(record), int(datetime.now().timestamp())])
        else:
            device.sqlDB.updateRecord(tableName="average_values",
                                       columns=[ "mean", "stdDev" ,"nPoints", "lastUpdate"],
                                       record=[consumption, costs, len(record), int(datetime.now().timestamp())],
                                       entry_id=record_id[0][0])


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
               

