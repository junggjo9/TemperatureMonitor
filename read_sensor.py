import json
import os
from os.path import exists
from os import system
from datetime import datetime, timedelta
from time import sleep
import random
import logging

logging.basicConfig(format="%(asctime)s (%(levelname)s) : %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    level=logging.INFO)
                    
### Tuya cloud error codes, see https://developer.tuya.com/en/docs/iot/error-code?id=K989ruxx88swc
TUYA_RETRY_CODES = {500,    # system error / API time out
                    1110,   # concurrent request over limit
                    1111,   # system is busy, please retry later
                    1113,   # do not repeat the operation in a short time
                    1199}   # your requests are too frequent
TUYA_TOKEN_CODES = {1010,   # token is expired
                    1011,   # token invalid
                    1400}   # token invalid




class DataFormat(object):
    def __repr__(self):
        return f"Sensor data {self.name} of type {self.data_type} "
    def __init__(self, name:str,
                       d_type: str,
                       d_range: dict):
        self.__name = name
        self.__data_type = d_type

        self.__min = d_range["min"] if isinstance(d_range, dict) and "min" in d_range.keys() else 0
        self.__max = d_range["max"] if isinstance(d_range, dict) and "max" in d_range.keys() else 0
        self.__unit =  d_range["unit"] if isinstance(d_range, dict) and "unit" in d_range.keys() else "Undefined"
        self.__allowed = d_range["range"] if isinstance(d_range, dict) and "range" in d_range.keys() else []
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
                       key: str,
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
        ### The authorization key
        self.__key = key
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

        self.__lock_file = ""

    def __del__(self): 
        if exists(self.__lock_file): system(f"rm {self.__lock_file}")
    @property
    def local_key(self): return self.__key
    @property
    def ip(self): return  deviceIP(self.mac_address) if len(self.mac_address) else "255.255.255.3"
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
    def uuid(self): return self.__uuid
    @property
    def serial_number(self): return self.__serial_number
    @property
    def first_record_time(self): return self.__time_first
    @property
    def latest_record_time(self): return self.__time_last
    @property
    def data_fields(self): return self.__data_types
    #### Return the data payload for a field read by the sensor
    #### @param field: The field to be returned
    #### @param ealiest: The first data point should not been recorded before
    #### @param latest: The last data point shoud not have been recorded after
    #### @param calibrator: Optional calibrator to apply 
    def data_payload(self, 
                     field: DataFormat,
                     earliest = datetime.fromtimestamp(0),
                     latest = None,
                     calibrator = None):
        if len([0 for x in self.data_fields if field.name == x.name]) == 0:
            logging.warning(f"Data field {field} is unknown")
            return []
        if latest is None: latest = datetime.now()
        if not calibrator:
            calibrator = lambda x: x
        values = [ (datetime.fromtimestamp(stamp / 1000), calibrator(value)) \
                    for stamp, value in self.__data[field.name]
                if stamp >= earliest.timestamp() * 1000 and stamp <= latest.timestamp() * 1000]
        values.sort(key=lambda x: x[0].timestamp())
        return values
    
    ###
    def load_local_db(self, db_folder, time_out: timedelta = timedelta(minutes = 15)):
        ### Check whether a device file is stored in the directory
        self.__db_file = f"{db_folder}/{self.name}.json"
        if not os.path.exists(self.__db_file):
            logging.debug(f"No data has been stored for {self.name}")
            return 0

        start_time = datetime.now()
        lock_file = f"{db_folder}/.{self.name}.lock"
        while exists(lock_file) and len(self.__lock_file) == 0:
            logging.info(f"Cannot open {self.__db_file} as it's still open by another process")
            sleep(15)
            if datetime.now() -  time_out > start_time:
                raise RuntimeError("Time out reached")
        self.__lock_file = lock_file
        with open(self.__lock_file, 'w') as f: f.write(self.__db_file) 
        loaded = 0
        with open(self.__db_file, "r") as f:
            for key, payload in json.load(f)["data"].items():
                for time_stamp, value in payload:
                    loaded+= self._append_point(d_type = key,
                                                time_stamp = time_stamp,
                                                value = value)
        return loaded

    def _append_point(self, 
                      d_type:str, 
                      time_stamp: int,
                      value: str,
                      log = False):
        ### first find out which data point is to be appended
        type_id = -1
        for idx in range(0, len(self.__data_types)):
            if self.__data_types[idx].name == d_type:
                type_id = idx
                break
        if type_id == -1:
            logging.debug(f"Do not store data of {d_type} with value {value} evaluated at {time_stamp}")
            return False
        ### Check if the value can be converted to an integer
        if self.__data_types[idx].data_type == "Integer":
            value = int(value)
        before = len(self.__data[d_type])
        self.__data[d_type].add((time_stamp, value))
        
        if len(self.__data[d_type]) == before:
            return False
        data_time = datetime.fromtimestamp(time_stamp /1000)
        if log:
            logging.info(f"Append data point recorded @{data_time.strftime("%d.%m.%y %H:%M")} to {d_type} with {value}")
        
        if self.__time_last.timestamp()* 1000 < time_stamp:
            self.__time_last = data_time

        if self.__time_first.timestamp()* 1000 > time_stamp:
            self.__time_first = data_time
        self.__empty = False
        return True

    #### Query the data from the online logs
    def fetch_from_cloud(self, cloud_stream, days = 14):
        logging.info("fetch_from_cloud() - Device {dev_name} has data from {start} until {end}".format(
            dev_name = self.name, 
            start = self.first_record_time.strftime('%d.%m.%y %H:%M'),
            end = self.latest_record_time.strftime('%d.%m.%y %H:%M')))

        ### If no data is present we need to download the entire log stream
 
        #### Start first with the most recent data
        end_cursor = datetime.now()
        if self.__empty:
            # First run — fetch full history
            start_cursor = end_cursor - timedelta(days=days)
            logging.info(f"fetch_from_cloud() - No local data, fetching {days} days")
        else:
            # Incremental — only fetch since last known record
            start_cursor = self.__time_last - timedelta(minutes = 10)
            logging.info(f"fetch_from_cloud() - Incremental fetch from {start_cursor.strftime('%d.%m.%y %H:%M')}")
        
        downloaded = self._download_data(cloud_stream = cloud_stream, 
                                          start_time = start_cursor, 
                                          end_time = end_cursor)
        logging.info(f"Loaded {downloaded} new entries from cloud.")
        return downloaded

    @staticmethod
    def _cloud_error_code(result):
        """Returns None if the cloud request succeeded, otherwise the Tuya error code
           (-1 if tinytuya itself failed, e.g. the token could not be renewed)."""
        if not isinstance(result, dict):
            return -1
        if result.get("success") == True and "result" in result:
            return None
        try:
            return int(result.get("code", -1))
        except (TypeError, ValueError):
            return -1

    def _download_data(self, cloud_stream, start_time, end_time, page_size = 100,
                       max_retries = 60, base_delay = 1., max_delay = 60.):

        logging.info("Fetch new data from the cloud for sensor {name} for the time span from {start} until {end}".format(
                name = self.name, start = start_time.strftime('%d.%m.%y %H:%M'), 
                end = end_time.strftime('%d.%m.%y %H:%M')))
        start_timestamp = int(start_time.timestamp())
        end_timestamp = int(end_time.timestamp())

        added = 0
        n_pages = 0
        row_key = None
        retries = 0
        token_renewed = False
        last_entry = 0
        earliest_entry = datetime.now().timestamp()
        while True:
            ### Fetch exactly one page per call, such that the error code of every page
            ### is visible. Without max_fetches = 1 tinytuya stops silently on a failed page.
            result = cloud_stream.getdevicelog(self.tuya_id, start_timestamp, end_timestamp, 
                                               evtype=7, size=page_size, max_fetches=1,
                                               start_row_key=row_key)
            err_code = self._cloud_error_code(result)
            if err_code is not None:
                if err_code in TUYA_TOKEN_CODES and not token_renewed:
                    ### tinytuya only renews on 'token invalid', not on 1010 'token is expired'
                    logging.info(f"Cloud token expired/invalid ({err_code}), renew it")
                    token_renewed = True
                    cloud_stream.token = None
                    cloud_stream._gettoken()
                    continue
                if err_code in TUYA_RETRY_CODES and retries < max_retries:
                    ### Exponential back off with jitter. Only wait if the cloud asks for it
                    delay = min(max_delay, base_delay * 2**retries) * random.uniform(1., 1.5)
                    retries += 1
                    logging.info(f"Cloud busy / rate limited ({err_code}). Retry {retries}/{max_retries} in {delay:.1f}s")
                    sleep(delay)
                    continue
                logging.warning(f"Failed to retrieve data from cloud after {n_pages} pages: {result}")
                break
            retries = 0
            token_renewed = False
            n_pages += 1

            page = result["result"]
            logs = page.get("logs", [])
            logging.debug(f"Fetched {len(logs)} entries from the database (page {n_pages})")
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
                if self._append_point(d_type, d_time, d_value, log = True):
                   added+=1
                earliest_entry = min(d_time /1000, earliest_entry)
                last_entry     = max(d_time / 1000, last_entry)

            next_key = page.get("next_row_key")
            if not page.get("has_next") or not next_key or next_key == row_key:
                break
            row_key = next_key

        if last_entry > 0:
            logging.debug(f"Records span the period {datetime.fromtimestamp(earliest_entry).strftime('%d.%m.%y %H:%M')} until {datetime.fromtimestamp(last_entry).strftime('%d.%m.%y %H:%M')}")
        return added


    def update_db(self):
        if len(self.__db_file) == 0:
            logging.warning(f"No external database defined to store data of {self.name}")
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

def loadSensorsFromJSON(json_config, restrict=[]):
    if not os.path.exists(json_config):
        logging.error(f"The device JSON configuration file {json_config} does not exist")
        exit(1)
    devices = []
    nRestricted = 0
    if len(restrict) > 0:
        logging.info("Only setup the devices {dev}".format(dev=", ".join(restrict)))
    with open(json_config, 'r') as f:
         for entry in json.load(f):
            dev_name = entry['name']
            if len(restrict) > 0:
                if dev_name not in restrict:
                    logging.debug(f"Skip instantiation of {dev_name}")
                    continue
                nRestricted+=1
            logging.debug(f"Instantiate new device {dev_name}")
            newDevice = DeviceData( name = dev_name,
                                    id = entry["id"],
                                    mac = entry["mac"],
                                    uuid = entry["uuid"],
                                    sn = "",# entry["sn"],
                                    prod_name = entry["product_name"],
                                    icon = entry["icon"],
                                    key = entry["key"],
                                    mapping_data = entry["mapping"])
            devices.append(newDevice)
    if nRestricted != len(restrict):
        logging.error(f"Only {nRestricted} out of the {len(restrict)} selected devices were found. please check input")
        exit(1)
    return devices

def deviceIP(mac:str, 
             leases = ["/var/lib/kea/kea-leases4.csv",
                       "/var/lib/kea/kea-leases4.csv.2"]):
    logging.debug(f"Look up IP assigned to '{mac}'")
    for l_file in leases:
        with open(l_file, 'r') as f:
            for line in f:
                tokens = line.split(",")
                dev_ip= tokens[0]
                dev_mac = tokens[1]
                logging.debug(f"deviceIP() - IP {dev_ip} is assigned to MAC {dev_mac}")
                if dev_mac == mac:
                    return dev_ip
    raise RuntimeError(f"Failed to find the IP address assigned to {mac}")

def pingIP(ip):
    return system(f"ping -c 1 {ip} > /dev/null 2>&1") ==0
    

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
                        default="/var/www/html/temperature_flat/records/")
    parser.add_argument("--downloadOnly", default=[], nargs="+",
                        help="Download data only for the listed devices.")
    return parser
if __name__ =="__main__":
    import tinytuya

    args = setupArgParser().parse_args()

    if not os.path.exists(args.dbFolder):
        logging.debug(f" Create database directory {args.dbFolder}")
        if not os.mkdir(args.dbFolder):
            logging.warning("Failed to create database directory")
    else:
        logging.debug(f"Search for databases from {args.dbFolder}")

    devices = loadSensorsFromJSON(args.deviceJSON, args.downloadOnly)

    try:
        cloud = tinytuya.Cloud()
    except Exception as e:
        logging.error(f"Failed to initialize cloud connection {e}")
        exit(1)

    now = datetime.now()
    for dev in range(len(devices)):
        devices[dev].load_local_db(args.dbFolder)
        logging.info(f" Try the tuya device API for {devices[dev].name}, IP: {devices[dev].ip} PING: {pingIP(devices[dev].ip)}, Internet: {pingIP('spiegel.de')}")
        if (now - devices[dev].latest_record_time).total_seconds() > 30 * 60 and devices[dev].fetch_from_cloud(cloud) >0 :
            devices[dev].update_db()
        devices[dev] = None
