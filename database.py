#/env/python
from enum import Enum
import logging, string, random, json
from datetime import datetime, timedelta

from dbConnection import QueryOrder, ColumnDef, DbConnection, DataTypes, Order
from time import sleep
logging.basicConfig(format='%(levelname)s : %(message)s', level=logging.INFO)


def id_generator(size=45, chars=string.ascii_letters + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))




class VariableDataType(Enum):
    NUMERIC = 0
    ENUM = 1
    SWITCH = 2
    BITMASK = 3
    STRING = 4

class DeviceVariable(object):
    def __init__(self, variable_record):
        self.__id = variable_record[0]
        self.__name = variable_record[1]
        self.__type = variable_record[2]
        self.__unit = variable_record[3]
        self.__min = variable_record[4]
        self.__max = variable_record[5]
        self.__discrete = variable_record[6]
        self.__conversion = variable_record[7]

        if isinstance(self.__discrete, str):
            self.__discrete = self.__discrete.split(",")

        if self.__type == "Integer":
            self.__type = VariableDataType.NUMERIC
        elif self.__type == "Enum":
            self.__type = VariableDataType.ENUM
        elif self.__type == "Boolean":
            self.__type = VariableDataType.SWITCH
        elif self.__type == "Bitmap":
            self.__type = VariableDataType.BITMASK
        elif self.__type == "String":
            self.__type = VariableDataType.STRING
        else:
            raise RuntimeError(f"DeviceVariable() - data type {self.__type} cannot be decoded. Setup of {self.name} failed.")

        if not self.__conversion and self.dataType == VariableDataType.NUMERIC: self.__conversion = 1.
    
    @property
    def id(self): return self.__id
    @property
    def name(self): return self.__name
    @property
    def dataType(self): return self.__type
    @property
    def choices(self): return self.__discrete
    @property
    def conversion(self): return self.__conversion
    @property
    def unit(self): return self.__unit


class Database(object):
    def __init__(self, database_path):
        self.__db = DbConnection(database_path = database_path)
        self._setupTables()
    @property
    def sqlDB(self) : return self.__db
    ####
    def _setupTables(self):
        ### Table to store the device information
        #### name: The name of the device as stored in the app
        ### mac_address: The MAC address for lock-up of the local IP address
        ### tuya_id: Identifier within the tuya system
        ### product_name: Name of the device from the vendor
        ### uuid: Universal unique identifier
        ### icon: The url to show the icon
        ### battery_state: The current state of the device battery
        if "devices" not in self.sqlDB.tableNames:
            self.sqlDB.createTable("devices",             
                [ColumnDef(name="id", d_type = DataTypes.INT_TYPE, primary=True),
                 ColumnDef(name="uuid", d_type = DataTypes.TEXT_TYPE, notNull=True),
                 ColumnDef(name="name", d_type = DataTypes.TEXT_TYPE, notNull=True),
                 ColumnDef(name="mac_address", d_type = DataTypes.TEXT_TYPE, notNull=False),
                 ColumnDef(name="tuya_id", d_type = DataTypes.TEXT_TYPE, notNull=True),
                 ColumnDef(name="tuya_key", d_type = DataTypes.TEXT_TYPE, notNull= True),
                 ColumnDef(name="product_name", d_type = DataTypes.TEXT_TYPE, notNull=True),
                 ColumnDef(name="icon", d_type = DataTypes.TEXT_TYPE, notNull=False),
                 ColumnDef(name="battery_state", d_type = DataTypes.INT_TYPE, notNull = False)])
        #### Table to store the variables held by a sensor
        #### id: The number of the entry within the table
        #### name: Name of the variable 
        #### type: Data type of the variable
        #### unit: In which units is the variable given
        #### min: Minimum value of the variable
        #### max: Maximum value of he variable
        #### discrete: Allowed values (Used for enum)
        if "record_variables" not in self.sqlDB.tableNames:
            self.sqlDB.createTable("record_variables",             
            [ColumnDef(name="id", d_type = DataTypes.INT_TYPE, primary=True),
            ColumnDef(name="name", d_type = DataTypes.TEXT_TYPE, notNull=True),
            ColumnDef(name="type", d_type = DataTypes.TEXT_TYPE, notNull=True),
            ColumnDef(name="unit", d_type = DataTypes.TEXT_TYPE, notNull=False),
            ColumnDef(name="min", d_type = DataTypes.REAL_TYPE, notNull=False),
            ColumnDef(name="max", d_type = DataTypes.REAL_TYPE, notNull=False),
            ColumnDef(name="conversion", d_type= DataTypes.REAL_TYPE, notNull=False),
            ColumnDef(name="discrete", d_type = DataTypes.TEXT_TYPE, notNull= False)])
        #### Actual data held by the device
        # data_records - id, variable, device, value, record_time, insert_time
        ### id: The number of the entry within the table
        ### variable: The identifier to the type of record
        ### device: The identifier of the sensor that has stored the datapoint
        ### value: The recorded value of the data point
        ### record_time: The time stamp when the data point has been recorded
        ### insert_time: The time stamp when the data point has been put into the table
        if "data_records" not in self.sqlDB.tableNames:
            self.sqlDB.createTable("data_records",
                    [ColumnDef(name="id", d_type = DataTypes.INT_TYPE, primary=True),
                    ColumnDef(name="variable", d_type = DataTypes.INT_TYPE, notNull=True,
                              ref_table="record_variables", ref_column="id"),
                    ColumnDef(name="device", d_type = DataTypes.INT_TYPE, notNull=True,
                              ref_table="devices", ref_column="id"),
                    ColumnDef(name="value", d_type = DataTypes.INT_TYPE, notNull=True),
                    ColumnDef(name="record_time", d_type = DataTypes.INT_TYPE, notNull=True),
                    ColumnDef(name="insert_time", d_type = DataTypes.INT_TYPE, notNull=True)])
        #### Reference table to which record types are storeable by a given sensor
        ### id: The number of the entry within the table
        ### variable: The identifier to the type of record
        ### device: The identifier of the sensor that has stored the datapoint
        if "device_variables" not in self.sqlDB.tableNames:
            self.sqlDB.createTable("device_variables",
                    [ColumnDef(name="id", d_type = DataTypes.INT_TYPE, primary=True),
                     ColumnDef(name="variable", d_type = DataTypes.INT_TYPE, notNull=True,
                               ref_table="record_variables", ref_column="id"),
                     ColumnDef(name="device", d_type = DataTypes.INT_TYPE, notNull=True,
                               ref_table="devices", ref_column="id")])
        ##### Daily average of the content
        ### id: The number of the entry within the table
        ### variable: The identifier to the type of record
        ### device: The identifier of the sensor that has stored the datapoint
        ### date: The date for which the average is calculated
        ### mean: The mean value
        ### stdDev: The standard deviation
        ### n_points: The number of data points
        if "average_values" not in self.sqlDB.tableNames:
            self.sqlDB.createTable("average_values",
                    [ColumnDef(name="id", d_type = DataTypes.INT_TYPE, primary=True),
                     ColumnDef(name="variable", d_type = DataTypes.INT_TYPE, notNull=True,
                               ref_table="record_variables", ref_column="id"),
                     ColumnDef(name="device", d_type = DataTypes.INT_TYPE, notNull=True,
                               ref_table="devices", ref_column="id"),
                     ColumnDef(name="mean", d_type = DataTypes.REAL_TYPE, notNull = True),
                     ColumnDef(name="stdDev", d_type = DataTypes.REAL_TYPE, notNull = True),
                     ColumnDef(name="date", d_type = DataTypes.REAL_TYPE, notNull = True),
                     ColumnDef(name="nPoints", d_type = DataTypes.INT_TYPE, notNull = True),
                     ColumnDef(name="lastUpdate", d_type = DataTypes.INT_TYPE, notNull = True)])
    
    
    
    def device_name(self, device_id: int):
        prim_col =self.sqlDB.primaryKey('devices').column_name
        return self.sqlDB.fetchFromTable(
                tableName="devices", columns=["name"],
                conditions=[f"{prim_col}={device_id}"])[0][0]

    def variable_name(self, variable_id: int):
        prim_col =self.sqlDB.primaryKey('record_variables').column_name
        return self.sqlDB.fetchFromTable(
                tableName="record_variables", columns=["name"],
                conditions=[f"{prim_col}={variable_id}"])[0][0]
        
    ### Insert a new data record from a device into the database
    ### device: The identifier of the device which is the value of the correspoding entry's primary key
    ### variable: The variable (or variable) for which the record will be stored
    ### record_time: When has the data poin been recorded
    ### value: The actual value of the data point    
    def insertDataRecord(self,
                      device:int,
                      variable:int,
                      record_time:datetime,
                      value):
        ### First check whether the record has already been stored in the database
        record_stamp = int(record_time.timestamp())
        record_exists = self.sqlDB.fetchFromTable(
                                        tableName="data_records",  
                                         columns=["value", "insert_time" ],
                                         conditions=[f"\"variable\"={variable}",
                                                     f"\"device\"={device}",
                                                     f"\"record_time\"={record_stamp}"] )
        if len(record_exists) > 0:
            if f"{record_exists[0][0]}" != f"{value}":
                logging.warning(f"insertDataRecord() - At {record_time}, {self.variable_name(variable)} of device {self.device_name(device)} has already recorded a value {record_exists[0][0]}.")
                logging.warning(f"insertDataRecord() - It was inserted at {datetime.fromtimestamp(record_exists[0][1])}. Cannot insert {value}.")
            return False
        insert_time = int(datetime.now().timestamp())
        logging.debug(f"storeRecord() - Append new record {self.variable_name(variable)} to {self.device_name(device)} with value {value} recored at {record_time}")

        self.sqlDB.insertRecord(tableName="data_records",
                                columns=["device", "variable", "record_time", "insert_time", "value"],
                                record=[device, variable,record_stamp, insert_time, value])
        return True
 
    def updateBattery(self, device_id: int, battery_state):
        logging.debug("updateBattery() - Update battery status of device {device_id} to {battery_state}")
        self.sqlDB.updateRecord(tableName="devices",
                                   columns = ["battery_state"],
                                   record = [battery_state],
                                   entry_id = device_id)
    
    def defineConversion(self, variable_name:str, conversion=1.):
        dev_id = [ x[0] for x in self.sqlDB.fetchFromTable( tableName="record_variables",
                                                            columns=[self.sqlDB.primaryKey("record_variables").column_name],
                                                            conditions=[f"\"name\"=\"{variable_name}\"",
                                                                        "\"type\"=\"Integer\""])]
        if len(dev_id) != 1:
            raise RuntimeError(f"defineConversionFactor() - '{variable_name}' is either unknown or not an integer ({len(dev_id)})")
        self.sqlDB.updateRecord(tableName="record_variables",
                                columns=["conversion"],
                                record=[conversion],
                                entry_id=dev_id[0])
    #### Load the devices from the tuya json file into the database and
    #### also store the record_mapping 
    ### jsoin_file: The path to the json file from which the devices will be cached 
    def loadDevices(self, json_file = "devices.json"):
        payload = []
        from os.path import exists
        if exists(json_file):
            with open(json_file, 'r') as f:
                payload = json.load(f)

        for entry in payload:
            uuid = entry["uuid"]
            name = entry["name"]
            ### Check whether there exists an entry in the database whch matched
            ### the universal unique identifier
            n_records = len(self.sqlDB.fetchFromTable(tableName = "devices", 
                                    columns=[self.sqlDB.primaryKey("devices").column_name],
                                    conditions=[f"\"uuid\"=\"{uuid}\""]) )
            #### The sensor is already stored in the database -> check the mapping?
            if n_records > 1:
                raise RuntimeError(f"loadDevices() - The sensor {name} is twice in the database")
            if n_records > 0:
                logging.debug(f"loadDevices() - The sensor {name} is already in the database")
                continue
            ### Setup a new record in the database
            new_record = [name, uuid, entry["id"], entry["key"], entry["icon"], 
                          entry["product_name"],]
            columns = ["name", "uuid", "tuya_id" , "tuya_key", "icon", "product_name"]
            if len(entry["mac"]) > 0: 
                new_record+=[entry["mac"]]
                columns+=["mac_address"]
            ### use the new record to define the mappings
            self._check_record_variables(device = self.sqlDB.insertRecord(tableName="devices",
                                                                         columns= columns,
                                                                         record = new_record),
                                     mapping = entry["mapping"])

        return [x[0] for x in self.sqlDB.fetchFromTable(tableName="devices", 
                                                        columns=[self.sqlDB.primaryKey("devices").column_name])]

    def _check_record_variables(self, device, mapping):
        ### First check whether the record type is in the database
        for _, variable in mapping.items():
            record_name = variable["code"]
            d_type = variable["type"]
            n_records = len(self.sqlDB.fetchFromTable(tableName = "record_variables",
                                                  columns=[self.sqlDB.primaryKey("record_variables").column_name],
                                                  conditions=[f"name=\"{record_name}\"",
                                                           f"type=\"{d_type}\""]))
            if n_records > 1:
                raise RuntimeError(f"_check_record_variables() - The record {record_name} is twice in the database")
            if n_records > 0:
                logging.debug(f"_check_record_variables() - The record {record_name} is already in the database")
                continue  
            new_record = [record_name, d_type]
            columns = ["name", "type"]
            if isinstance(variable["values"], dict):     
                for x in ["unit", "min", "max"]:
                    if x in variable["values"].keys():
                        new_record+=[variable["values"][x]]
                        columns+=[x]

                for x in ["label", "range"]:
                    if x in variable["values"].keys():
                        new_record+=[",".join(variable["values"][x])]
                        columns+=["discrete"]
            self.sqlDB.insertRecord(tableName = "record_variables",
                              columns=columns,
                              record=new_record)
        #### 
        for _, variable in mapping.items():
            record_name = variable["code"]
            d_type = variable["type"]
            record_id = self.sqlDB.fetchFromTable(tableName = "record_variables",
                                                  columns=[self.sqlDB.primaryKey("record_variables").column_name],
                                                  conditions=[f"name=\"{record_name}\"",
                                                           f"type=\"{d_type}\""])[0][0]
            conn_record = len(self.sqlDB.fetchFromTable(tableName = "device_variables",
                                                 columns =[self.sqlDB.primaryKey("device_variables").column_name],
                                                 conditions=[f"\"variable\"={record_id}",
                                                             f"\"device\"={device}"]))
            if conn_record > 1:
                raise RuntimeError(f"_check_record_variables() - The record {record_name} is connected twice to sensor {device}")
            if conn_record > 0:
                logging.debug(f"_check_record_variables() - The record {record_name} is already connected to sensor {device}")
            self.sqlDB.insertRecord(tableName = "device_variables",
                                    columns=["variable", "device"],
                                    record =[record_id, device])
    
    def loadVariables(self, variable_ids=[]):
        
        conditions = [" OR ".join([f"{self.sqlDB.primaryKey('record_variables').column_name}={id}" for id in variable_ids])] if len(variable_ids) else []
        variable_record = self.sqlDB.fetchFromTable(tableName="record_variables",
                                                  columns=["id", "name", "type", "unit", "min", "max", "discrete", "conversion"],
                                                  conditions=conditions)
        if len(variable_ids) > 0 and len(variable_record) != len(variable_ids):
            raise RuntimeError("SmartHomeDevice() - Cannot retrieve the associated variables")  
        variables = []
        for record in variable_record:
            variables.append(DeviceVariable(record))
        return variables
    
    def fetchRecords(self, 
                    device:int,
                    variable:int,
                    start_time = None,
                    end_time = None):
        conditions=[f"\"variable\"={variable}",
                     f"\"device\"={device}"]
        if isinstance(start_time, datetime):
            conditions+=[f"\"record_time\">={int(start_time.timestamp())}"]
        if isinstance(end_time, datetime):
            conditions+=[f"\"record_time\" <= {int(end_time.timestamp())}"]
        return [ (datetime.fromtimestamp(x[0]), x[1]) for x in self.sqlDB.fetchFromTable(tableName="data_records",
                                                                            columns=["record_time", "value"],
                                                                            conditions = conditions,
                                                                            order = [QueryOrder(column="record_time",
                                                                                                order=Order.ASC)])]


if __name__ == "__main__":
    from os import system
    #system("rm test.db")
    test_db = Database("test.db")
    test_db.loadDevices()


    test_time = datetime.now() - timedelta(hours=2)
    test_db.insertDataRecord(device = 1, 
                             variable = 2, 
                             record_time = test_time,
                             value=666.)
    sleep(10)
    test_db.insertDataRecord(device = 1, 
                             variable = 2, 
                             record_time = test_time,
                             value=667.)
    
    exit(1)
    test_injects = ["ship", "heater", "plant", "die CASSY!!!", "TV"]

    records = [(test_injects[i % len(test_injects)], id_generator(12), id_generator(24), "test_device", id_generator(12)) for i in range (100)]

    for i in range(len(records)):
        test_db.sqlDB.insertRecord(tableName ="devices", 
            columns= ("name", "mac_address", "tuya_id" , "product_name", "uuid"), 
            record = records[i])
    
    fetch_back = test_db.sqlDB.fetchFromTable(tableName = "devices", 
                                              columns = ("name", "mac_address", "tuya_id" , "product_name", "uuid"))

    logging.info(f"Fetched datasets {len(fetch_back)}")
    if len(fetch_back) != len(records):
        logging.error("Did no retrieve back the same amount of datasets")
        exit(1)
    for i in range(len(fetch_back)):
        insert_block = records[i]
        read_block = fetch_back[i]
        if len(insert_block) != len(read_block):
            logging.error(f"Retrieved table content has different numb of columns {len(insert_block)} vs. {len(read_block)}.")
            exit(1)
        for j in range(len(insert_block)):
            if insert_block[j] != read_block[j]:
                logging.error(f"Database content differs {insert_block[j]} vs. {read_block[j]}")
                exit(1)
    #### Now we update the product_name to other names
    new_devices = ["coffee machine", "heater", "green house"]
    for i in range(len(records)):
        test_db.sqlDB.updateRecord(tableName="devices",
                                   columns = ["product_name"],
                                   record = [new_devices[i % len(new_devices)]],
                                   entry_id = i+1)

                                   
