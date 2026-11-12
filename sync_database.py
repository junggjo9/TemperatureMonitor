from database import Database, DeviceVariable, VariableDataType
from dbConnection import QueryOrder, Order
from datetime import datetime, timedelta
from time import sleep
import logging
logging.basicConfig(format='%(levelname)s : %(message)s', level=logging.INFO)




### Class to represent the smart home devices (Read mode)
class SmartHomeDevice(object):
    def __init__(self,
                 db: Database, 
                 device_id: int):
        self.__id = device_id
        self.__db = db
        device_record = self.sqlDB.fetchFromTable(tableName="devices", 
                                                columns=["tuya_id", "name", "mac_address", "product_name", 
                                                         "battery_state", "icon"],                            
                                                conditions=[f"\"{self.primaryKey('devices')}\"={device_id}"])[0]
        self.__tuya_id = device_record[0]
        self.__name = device_record[1]
        self.__mac_address = device_record[2]
        self.__product_name = device_record[3]
        self.__battery_state = device_record[4]
        self.__icon = device_record[5]
        
        self.__variables = self.dbConnection.loadVariables(variable_ids = 
                [x[0] for x in db.sqlDB.fetchFromTable(tableName="device_variables",
                                                       columns=["variable"],
                                                       conditions=[f"\"device\"={device_id}"])])
        ### first data time stamp
        self.__time_first = datetime.now() 
        ### last data time stamp
        self.__time_last = datetime.fromtimestamp(0)
        ### Empty dataset
        self.__empty = True

        first_record = [x[0] for x in self.sqlDB.fetchFromTable(tableName="data_records", columns=["record_time"],
                                               conditions=[f"\"device\"={self.device_id}"],
                                               order=[QueryOrder(column="record_time", order=Order.ASC)],
                                               limit = 1)]
        if len(first_record) == 0:
            logging.debug(f"SmartHomeDevice() - No record has been stored for {self.name}")
            return

        self.__time_first = datetime.fromtimestamp(first_record[0])

        last_record = [x[0] for x in self.sqlDB.fetchFromTable(tableName="data_records", columns=["record_time"],
                                               conditions=[f"\"device\"={self.device_id}"],
                                               order=[QueryOrder(column="record_time", order=Order.DESC)],
                                               limit = 1)]
        
        self.__time_last = datetime.fromtimestamp(last_record[0])

    @property
    def empty(self): return self.__empty
    @property
    def tuya_id(self): return self.__tuya_id
    @property
    def device_id(self) : return self.__id
    @property
    def name(self): return self.__name
    @property
    def dbConnection(self): return self.__db
    @property
    def sqlDB(self): return self.dbConnection.sqlDB
    @property
    def dataFields(self): return self.__variables
    @property
    def earliestRecord(self): return self.__time_first
    @property
    def latestRecord(self): return self.__time_last
    
    def primaryKey(self, tableName):
        return self.sqlDB.primaryKey(tableName).column_name

    def dataField(self, field_name: str):
        for f in self.dataFields:
            if f.name == field_name: return f
        return None
    def storeRecord(self,
                    data_field: DeviceVariable,
                    record_time: datetime,
                    value):
        if data_field.name not in ["va_temperature", "va_humidity", "battery_percentage" , "battery_state"
                                ## Radiator power consumption
                                   "cur_current", "cur_voltage", "cur_power", "add_ele",
                                    ### Radiator calibration
                                    "power_coe", "electricity_coe", "electric_coe", 
                                   ]: return 0
        
        if data_field.dataType == VariableDataType.STRING:
            logging.debug(f"storeRecord() - String storage is not yet supported. Cannot store field {data_field.name}")
            return False
        elif data_field.dataType == VariableDataType.ENUM:
            logging.debug(f"storeRecord() - Find enum value field {data_field.name} for {value} in {data_field.choices}")
            value = data_field.choices.index(value)
        elif data_field.dataType == VariableDataType.SWITCH:
            value = 0 if value.lower() == "false" else 1

        if data_field.name.find("battery") != -1:
            if self.__battery_state != value:
                self.dbConnection.updateBattery(device_id = self.device_id, battery_state = value)
                self.__battery_state = value
                return True
            return False
        
        if not self.dbConnection.insertDataRecord(device = self.device_id,
                        variable = data_field.id, record_time = record_time,
                        value = value):
            return False

        if self.__time_last < record_time or self.empty:
            self.__time_last = record_time

        if self.__time_first  > record_time or self.empty:
            self.__time_first = record_time
        self.__empty = False

        return True
    
    def payload(self, 
                data_field: DeviceVariable,
                start_time = datetime.fromtimestamp(0),
                end_time = datetime.now()):
        records =  self.dbConnection.fetchRecords(device = self.device_id,
                                                  variable = data_field.id,
                                                  start_time = start_time,
                                                  end_time = end_time)
        if len(records) == 0: return records
        if self.earliestRecord < start_time:
            records.insert(0, [start_time, records[0][1]]) 

        if self.latestRecord < end_time:
            records.append([end_time, records[-1][1]]) 

        if data_field.dataType == VariableDataType.NUMERIC and data_field.conversion != 1.:
            return [ (x[0], x[1] * data_field.conversion) for x in records]
        return records

    #### Query the data from the online logs
    def downloadFromCloud(self, 
                          cloud_stream, 
                          download_all = False):
        logging.info("downloadFromCloud() - Device {dev_name} has data from {start} until {end}".format(
            dev_name = self.name, 
            start = self.earliestRecord.strftime('%d.%m.%y %H:%M'),
            end = self.latestRecord.strftime('%d.%m.%y %H:%M')))

        ### If no data is present we need to download the entire log stream
        downloaded = 0
  
        start_time = datetime.now() - timedelta(days =1)
        #### Start first with the most recent data
        for iter in range(50):
            fetched = self._downloadData(cloud_stream = cloud_stream, 
                                         start_time = start_time, 
                                         end_time = start_time + timedelta(hours = 12))
            downloaded +=fetched
            logging.info(f"Downloaded {fetched} new data points")
            start_time += timedelta(hours=11)
            if start_time > datetime.now(): break
            sleep(20 + iter % 20)
        return downloaded

    def _downloadData(self, cloud_stream, start_time, end_time):
        logging.info("_downloadData() - Fetch new data from the cloud for sensor {name} for the time span from {start} unil {end}".format(
                      name = self.name, start = start_time.strftime('%d.%m.%y %H:%M'), 
                      end = end_time.strftime('%d.%m.%y %H:%M')))
        start_timestamp = int(start_time.timestamp())
        end_timestamp = int(end_time.timestamp())
        result = cloud.getdevicelog(self.tuya_id, start_timestamp, end_timestamp, size=1000)
 
        if not result["success"] == True:
            logging.error(f"Failed to retrieve data from cloud {result}")
            exit(1)
        logs = result['result']["logs"]
        added = 0
        for entry in logs:
            if not "code" in entry.keys():
                continue
            d_type = entry["code"]
            d_time = int(entry["event_time"])
            d_status = int(entry["status"])
            if d_status != 1:
                logging.warning(f"Skip data point {entry}")
                continue

            d_value = entry["value"]

            field = self.dataField(field_name = d_type)
            if field is None: continue

            if self.storeRecord(data_field = field, 
                                record_time = datetime.fromtimestamp(d_time/ 1000), 
                                value = d_value):
               added+=1
        return added

def setupSmartDevices(db_file: str, device_json: str = ""):
    dbObj = Database(db_file)
    devices = []
    for dev_id in dbObj.loadDevices(device_json):
        devices.append(SmartHomeDevice( db = dbObj, device_id = dev_id))
 
    ### Floating point values with one digit precision
    dbObj.defineConversion("va_temperature" , 0.1)
    dbObj.defineConversion("cur_voltage" , 0.1)
    ### Energy unit Wh -> kWh 
    dbObj.defineConversion("add_ele", 0.001)
    #### mA -> A 
    dbObj.defineConversion("cur_current", 0.001)
    ### W -> kW with one digit precision
    dbObj.defineConversion("cur_power", 0.0001)
    return devices

def setupArgParser():
    from argparse import ArgumentParser
    from os import getenv
    parser = ArgumentParser(
                    prog='ReadTemperatureSensors',
                    description='Python API to read the TUYA temperature sensor data from the cloud') 
    parser.add_argument("--deviceJSON", help="JSON file where the TUYA device data is stored",
                                        default="devices.json")
    parser.add_argument("--dataBase", help="Directory where the JSON database is stored",
                        default=f"{getenv('PWD')}/data_records/records.db")
    return parser


if __name__ == "__main__":
    args = setupArgParser().parse_args()
    devices = setupSmartDevices(db_file = args.dataBase, device_json = args.deviceJSON)
    import tinytuya
    try:
        cloud = tinytuya.Cloud()
    except Exception as e:
        logging.error(f"Failed to initialize cloud connection {e}")
        exit(1)

    for dev in devices:
        dev.downloadFromCloud(cloud_stream = cloud)


