import json
import os
from datetime import datetime, timedelta
from time import sleep



class DataFormat(object):
    def __repr__(self):
        return f"Sensor data {self.name} of type {self.data_type} "
    def __init__(self, name:str, 
                       d_type: str, 
                       d_range: dict):
        self.__name = name
        self.__data_type = d_type
        self.__min = d_range["min"] if "min" in d_range.keys() else 0
        self.__max = d_range["max"] if "max" in d_range.keys() else 0
        self.__unit =  d_range["unit"] if "unit" in d_range.keys() else "Undefined"
        self.__allowed = d_range["range"] if "range" in d_range.keys() else []
    @property
    def minimum(self): return self.__min
    @property 
    def maximum(self): return self.__max
    @property
    def name(self): return self.__name
    @property 
    def unit(self): return self.__unit
    @property
    def data_type(self): return self.__data_type
    @property 
    def json_dict(self): 
        result = {
            "code": self.name,
            "type": self.data_type,
            "values": {
                "min": self.minimum,
                "max": self.maximum,
                "unit": self.unit,
            }
        }
        return result

### Basic class to describe a temperature sensor device
class DeviceData(object):
    ### Overload to dump the class to a string
    def __init__(self, name:str, 
                       id: str,
                       mac: str,
                       uuid: str,
                       sn: str,
                       prod_name: str,
                       icon: str,
                       mapping_data: dict):
        ### Name of the device as assigned by the App
        self.__name = name
        ### Identifier of the device assigned by the TUYA system
        self.__id = id
        #### The MAC address of the device
        self.__mac = mac 
        ### The UUID of the device
        self.__uuid = uuid
        ### The serial number of the device
        self.__serial_number = sn
        #### The product_name of the device
        self.__product_name = prod_name
        ### URL of the ICON
        self.__icon = icon
        ### 
        self.__data_types = []
        #### 
        self.__data = {}
        ##### Load the mapping data from the device
        for key, values in mapping_data.items():
            new_format = DataFormat(name = values["code"],
                                    d_type = values["type"],
                                    d_range = values["values"])
            self.__data_types.append(new_format)
            self.__data[new_format.name] = set()
        ### Output data file name
        self.__db_file = ""
        ### first data time stamp
        self.__time_first =  datetime.now() 
        ### last data time stamp
        self.__time_last = datetime.fromtimestamp(0)
        ### Empty dataset
        self.__empty = True

    @property
    def empty(self): return self.__empty
    @property
    def name(self): return self.__name
    @property
    def tuya_id(self): return self.__id
    @property
    def product_name(self): return self.__product_name
    @property
    def mac_address(self): return self.__mac
    @property
    def uuid(self): return self.__uid
    @property
    def serial_number(self): return self.__serial_number
    @property
    def earliest_data(self): return self.__time_first
    @property
    def latest_data(self): return self.__time_last
    @property
    def data_fields(self): return self.__data_types

    def data_payload(self, 
                     field: DataFormat,
                     earliest = datetime.fromtimestamp(0),
                     latest = datetime.now()):
        if len([0 for x in self.data_fields if field.name == x.name]) == 0:
            print(f"Data field {field} unknown")
            return []
        values = [ (datetime.fromtimestamp(stamp / 1000), value) for stamp, value in self.__data[field.name]
                if stamp >= earliest.timestamp() * 1000 and stamp <= latest.timestamp() * 1000]
        values.sort(key=lambda x: x[0].timestamp())
        return values
    ###
    def load_local_db(self, db_folder):
        ### Check whether a device file is stored in the directory
        self.__db_file = f"{db_folder}/{self.name}.json"
        if not os.path.exists(self.__db_file):
            print (f"No data has been stored for {self}")
            return

        with open(self.__db_file, "r") as f:
            for key, payload in json.load(f)["data"].items():
                for time_stamp, value in payload:
                    self._append_point(d_type = key,
                                       time_stamp = time_stamp,
                                       value = value)

    def _append_point(self, 
                      d_type:str, 
                      time_stamp: int,
                      value: str):
        ### first find out which data point is to be appended
        type_id = -1
        for idx in range(0, len(self.__data_types)):
            if self.__data_types[idx].name == d_type:
                type_id = idx
                break
        if type_id == -1:
            print (f" Do not store data of {d_type} with value {value} evaluated at {time_stamp}")
            return False
        ### Check if the value can be converted to an integer
        if self.__data_types[idx].data_type == "Integer":
            value = int(value)
        before = len(self.__data[d_type])
        self.__data[d_type].add((time_stamp, value))
        if len(self.__data[d_type]) == before:
            return False
        data_time = datetime.fromtimestamp(time_stamp /1000)

        #print ( f" Append data point {(data_time.strftime("%d.%m.%y  %H:%M"), value)}")
        if self.__time_last.timestamp()* 1000 < time_stamp:
            self.__time_last = data_time

        if self.__time_first.timestamp()* 1000 > time_stamp:
            self.__time_first = data_time
        self.__empty = False
        return True

    #### Query the data from the online logs
    def fetch_from_cloud(self, cloud_stream):
        print ("Device {dev_name} has data from {start} until {end}".format(
            dev_name = self.name, 
            start = self.earliest_data.strftime('%d.%m.%y %H:%M'),
            end = self.latest_data.strftime('%d.%m.%y %H:%M')))

        ### If no data is present we need to download the entire log stream
        is_empty = self.empty
        iter = 0

        downloaded = 0
        #### Start first with the most recent data
        while iter < 50:
            fetched = self._download_data(cloud_stream = cloud_stream, 
                                          start_time = self.latest_data, 
                                          end_time = datetime.now())
            downloaded +=fetched
            if fetched == 0: break
            ++iter
            sleep(5)
        #### The data has been queried before no need to try again
        if not is_empty:
            return downloaded
        while iter < 100:
            fetched = self._download_data(cloud_stream = cloud_stream, 
                                          start_time = datetime.fromtimestamp(0), 
                                          end_time = self.earliest_data)
            downloaded +=fetched
            if fetched == 0: break
            ++iter
            sleep(5)
        return downloaded

    def _download_data(self, cloud_stream, start_time, end_time):

        print ("Fetch new data from the cloud for sensor {name} for the time span from {start} unil {end}".format(
                name = self.name, start = start_time.strftime('%d.%m.%y %H:%M'), 
                end = end_time.strftime('%d.%m.%y %H:%M')))
        start_timestamp = int(start_time.timestamp())
        end_timestamp = int(end_time.timestamp())
        result = cloud.getdevicelog(self.tuya_id, start_timestamp, end_timestamp, size=1000)
 
        if not result["success"] == True:
            print(f"Failed to retrieve data from cloud")
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
                print(f"Skip data point {entry}")
                continue

            d_value = entry["value"]
            if self._append_point(d_type, d_time, d_value):
               added+=1
        return added

    def update_db(self):
        if len(self.__db_file) == 0:
            print(f"No external database defined to store data of {self.name}")
            return
        persitify = {}
        persitify["data"] = {}

        for d_type, payload in self.__data.items():
            persitify["data"][d_type] = [ (time_stamp, value) for time_stamp, value in payload]
            persitify["data"][d_type].sort(key = lambda x: x[0])

        persitify["data_types"] = {}
        for x in range(len(self.data_fields)):
            persitify["data_types"][x] = self.data_fields[x].json_dict
        persitify["name"] = self.name
        # persitify["tuya_id"] = self.tuya_id
        persitify["mac_address"] = self.mac_address

        with open(self.__db_file, 'w') as f:
            json.dump(persitify, f, indent=2)

def loadSensorsFromJSON(json_config):
    if not os.path.exists(json_config):
        print(f"The device JSON configuration file {json_config} does not exist")
        exit(1)
    devices = []
    with open('devices.json', 'r') as f:
         for entry in json.load(f):
            newDevice = DeviceData( name = entry["name"],
                                    id = entry["id"],
                                    mac = entry["mac"],
                                    uuid = entry["uuid"],
                                    sn = entry["sn"],
                                    prod_name = entry["product_name"],
                                    icon = entry["icon"],
                                    mapping_data = entry["mapping"])
            devices.append(newDevice)
    return devices

def setupArgParser():
    from argparse import ArgumentParser
    parser = ArgumentParser(
                    prog='ReadTemperatureSensors',
                    description='Python API to read the TUYA temperature sensor data from the cloud') 
    parser.add_argument("--deviceJSON", help="JSON file where the TUYA device data is stored",
                                        default="devices.json")
    parser.add_argument("--apiJSON", help="JSON file containing the API access secrets",
                        default="tinytuya.json")
    parser.add_argument("--dbFolder", help="Directory where the JSON database is stored",
                        default="/var/www/html/temperature_flat/")
    return parser
if __name__ =="__main__":
    import tinytuya

    args = setupArgParser().parse_args()

    if not os.path.exists(args.dbFolder):
        print(f" Create database directory {args.dbFolder}")
        if not os.mkdir(args.dbFolder):
            print("Failed to create database directory")
    else:
        print(f"Search for databases from {args.dbFolder}")

    devices = loadSensorsFromJSON(args.deviceJSON)

    try:
        cloud = tinytuya.Cloud()
    except Exception as e:
        print(f"Failed to initialize cloud connection {e}")
        exit(1)

    for device in devices:
        device.load_local_db(args.dbFolder)
        if device.fetch_from_cloud(cloud) >0 or True:
            device.update_db()
