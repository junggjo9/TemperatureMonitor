#/env/python
from enum import Enum
from os.path import exists
import sqlite3, logging, string, random
logging.basicConfig(format='%(levelname)s : %(message)s', level=logging.INFO)



class DataTypes(Enum):
    INT_TYPE = 0 #
    REAL_TYPE = 1
    TEXT_TYPE = 2

class Order(Enum):
    ASC = 0
    DESC = 1

#### Object to define a database column
class ColumnDef(object):
    ## Constructor
    ## @param name: The name of the column
    ## @param type: The data type of the column
    ## @param primary: Is the column the primary column identifiying a record
    ## @param notNull: Is the column allowed to be filled without value
    ## @param ref_table: Establish a refernce to another table (together ith ref_column)
    ## @param ref_column: Etablish a reference to the column from an other table
    def __init__(self, name: str, 
                       d_type: DataTypes,
                       primary:bool = False, 
                       notNull:bool = False,
                       ref_table:str = "",
                       ref_column: str = ""):
        self.__name = name
        self.__type = d_type
        self.__primary = primary
        self.__notNull = notNull
        self.__ref_table = ref_table
        self.__ref_column = ref_column
        if (len(ref_table) == 0) != (len(ref_column) == 0):
            raise RuntimeError(f"The reference table: '{ref_table}' or the '{ref_column}' are empty but not both")
    @property
    def column_name(self): return self.__name
    @property
    def data_type(self): return self.__type
    @property
    def primary(self): return self.__primary
    @property
    def not_null(self): return self.__notNull
    @property
    def reference_table(self): return self.__ref_table
    @property
    def reference_column(self): return self.__ref_column
    ### Print the ColumnDefinition
    def __repr__(self):
        ret_str =f"{self.column_name} "
        if self.data_type == DataTypes.INT_TYPE: ret_str+="INTEGER"
        elif self.data_type == DataTypes.REAL_TYPE: ret_str+="REAL"
        elif self.data_type == DataTypes.TEXT_TYPE: ret_str+="TEXT"
        else: raise RuntimeError(f"Unkown data type {self.data_type}")
        if self.primary: ret_str+=" PRIMARY KEY"
        if self.not_null: ret_str+=" NOT NULL"
        if len(self.reference_table): 
            ret_str+=f" REFERENCES {self.reference_table}({self.reference_column})"
        return ret_str
### Helper struct to specify how the gathered dataset is 
### orderd by the queried columns
class QueryOrder(object):
    ### @param name: The name of the column by which the query is ordered
    ### @param order: Apply an ascending or descending order
    def __init__(self, name: str, order: Order):
        self.__name = name
        self.__order = order
    @property
    def column_name(self): return self.__name
    @property
    def order_direction(self) : return self.__order
    def __repr__(self):
        return "{col_name} {direct}".format(col_name=self.column_name,
                                            direct="ASC" if Order.ASC else "DESC" )



class DbConnection(object):
    def __init__(self, database_path):
        self.__path = database_path
        ### Database pointer
        self.__db = sqlite3.connect(self.__path)
        ### Internal dictionary to cache which tables are held
        self.__tables = {}

    @property 
    def path(self): return self.__path
    @property
    def instance(self): return self.__db
    ### Create a new table in the sqlite
    def createTable(self, 
                    tableName: str, 
                    columns: list):
        if tableName in self.__tables.keys():
            raise RuntimeError(f"Cannot create the table {tableName} twice in {self.path}")
        query="CREATE TABLE {tableName} ({columns})".format(tableName=tableName,
                    columns=", ".join([f"{c}" for c in columns]))
        logging.info(query)
        cursor = self.instance.execute(query)
        self.__tables[tableName] = columns

    def insertRecord(self, 
                     tableName: str, 
                     columns: tuple,
                     record: tuple):
        if tableName not in self.__tables.keys():
            raise RuntimeError(f"insertRecord() - The table {tableName} does not exist")

        if len(columns) != len(record):
            raise RuntimeError(f"insertRecord() - Inconsistent number of columns ({len(columns)}) and records {len(record)}")
        if len(columns) == 0:
            raise RuntimeError(f"insertRecord() - The number of passed colmuns must not be zero")
        d_types =[] 
        for col_name in columns:
            for db_col in self.__tables[tableName]:
                if db_col.column_name == col_name:
                    d_types.append(db_col.data_type)
                    break
        if len(d_types) != len(columns):
            raise RuntimeError(f"insertRecord() - At least one column is not part of the table {tableName}")
        
        value_str = ""
        for i in range(len(record)):
            if i > 0: value_str+=", "
            if d_types[i] == DataTypes.TEXT_TYPE: value_str+=f"\"{record[i]}\""
            else: value_str+=f"{record[i]}"
        query = "INSERT INTO {tableName} ({cols}) VALUES ({values})".format(tableName=tableName,
                cols = ", ".join([f"'{c}'" for c in columns]),
                values=value_str)
        logging.info(query)
        cursor = self.instance.cursor()
        cursor.execute(query)
        


    #### Fetch entries from the table
    def fetchFromTable(self, tableName:str, 
                             columnNames:tuple = [],
                             conditions: list =[],
                             order: list =[],
                             limit:int = -1,
                             start: int =0):
        cols = "*" if len(columnNames) == 0 else ", ".join([f"'{c}'" for c in columnNames])
        sel = "" if len(conditions)  == 0 else "WHERE {l_cond}".format(
                        l_cond=", ".join([f"{c}" for c in conditions]))
        sort = "" if len(order) == 0 else "ORDER BY {ord_seq}".format(ord_seq = ", ".join([
                f"{o}" for o in order]))
        
        range_str = "" if limit < 1 else f"LIMIT {start} {limit}"
       
        query = f"SELECT {cols} FROM {tableName} {sel} {sort} {range_str}"
        cursor = self.instance.cursor()
        cursor.execute(query)
        return cursor.fetchall()
        #return 

class Database(object):
    def __init__(self, database_path):
        present = exists(database_path)
        self.__db = DbConnection(database_path = database_path)
        if not present:
            self._setupTables()
    @property
    def sqlDB(self) : return self.__db
    ####
    def _setupTables(self):
        ### Table to store the device information
        self.sqlDB.createTable("sensors",             
            [ColumnDef(name="id", d_type = DataTypes.INT_TYPE, primary=True),
            ColumnDef(name="device_name", d_type = DataTypes.TEXT_TYPE, notNull=True),
            ColumnDef(name="mac_address", d_type = DataTypes.TEXT_TYPE, notNull=True),
            ColumnDef(name="tuya_id", d_type = DataTypes.TEXT_TYPE, notNull=True),
            ColumnDef(name="product_name", d_type = DataTypes.TEXT_TYPE, notNull=True),
            ColumnDef(name="uuid", d_type = DataTypes.TEXT_TYPE, notNull=True),
            ColumnDef(name="icon", d_type = DataTypes.TEXT_TYPE, notNull=False) ])
        #### Table to store the variables held by a sensor
        #### id: The number of the entry within the table
        #### name: Name of the variable 
        #### type: Data type of the variable
        #### unit: In which units is the variable given
        #### min: Minimum value of the variable
        #### max: Maximum value of he variable
        #### discrete: Allowed values (Used for enum)
        self.sqlDB.createTable("record_types",             
            [ColumnDef(name="id", d_type = DataTypes.INT_TYPE, primary=True),
            ColumnDef(name="name", d_type = DataTypes.TEXT_TYPE, notNull=True),
            ColumnDef(name="type", d_type = DataTypes.TEXT_TYPE, notNull=True),
            ColumnDef(name="unit", d_type = DataTypes.TEXT_TYPE, notNull=False),
            ColumnDef(name="min", d_type = DataTypes.REAL_TYPE, notNull=False),
            ColumnDef(name="max", d_type = DataTypes.REAL_TYPE, notNull=False),
            ColumnDef(name="discrete", d_type = DataTypes.TEXT_TYPE, notNull= False)])
        #### Actual data held by the device
        # data_records - id, record_type, sensor_id, value, record_time, insert_time
        ### id: The number of the entry within the table
        ### record_type: The identifier to the type of record
        ### sensor_id: The identifier of the sensor that has stored the datapoint
        ### value: The recorded value of the data point
        ### record_time: The time stamp when the data point has been recorded
        ### insert_time: The time stamp when the data point has been put into the table
        self.sqlDB.createTable("data_records",
                    [ColumnDef(name="id", d_type = DataTypes.INT_TYPE, primary=True),
                    ColumnDef(name="record_type", d_type = DataTypes.INT_TYPE, notNull=True,
                              ref_table="record_types", ref_column="id"),
                    ColumnDef(name="sensor_id", d_type = DataTypes.INT_TYPE, notNull=True,
                              ref_table="sensors", ref_column="id"),
                    ColumnDef(name="value", d_type = DataTypes.REAL_TYPE, notNull=True),
                    ColumnDef(name="record_time", d_type = DataTypes.INT_TYPE, notNull=True),
                    ColumnDef(name="insert_time", d_type = DataTypes.INT_TYPE, notNull=True)])
        #### Reference table to which record types are storeable by a given sensor
        ### id: The number of the entry within the table
        ### record_type: The identifier to the type of record
        ### sensor_id: The identifier of the sensor that has stored the datapoint
        self.sqlDB.createTable("sensor_variables",
                    [ColumnDef(name="id", d_type = DataTypes.INT_TYPE, primary=True),
                     ColumnDef(name="record_type", d_type = DataTypes.INT_TYPE, notNull=True,
                               ref_table="record_types", ref_column="id"),
                     ColumnDef(name="sensor_id", d_type = DataTypes.INT_TYPE, notNull=True,
                               ref_table="sensors", ref_column="id")])
        ##### Daily average of the content
        ### id: The number of the entry within the table
        ### record_type: The identifier to the type of record
        ### sensor_id: The identifier of the sensor that has stored the datapoint
        ### date: The date for which the average is calculated
        ### mean: The mean value
        ### stdDev: The standard deviation
        ### n_points: The number of data points
        self.sqlDB.createTable("average_values",
                    [ColumnDef(name="id", d_type = DataTypes.INT_TYPE, primary=True),
                     ColumnDef(name="record_type", d_type = DataTypes.INT_TYPE, notNull=True,
                               ref_table="record_types", ref_column="id"),
                     ColumnDef(name="sensor_id", d_type = DataTypes.INT_TYPE, notNull=True,
                               ref_table="sensors", ref_column="id")])



def id_generator(size=45, chars=string.ascii_letters + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

if __name__ == "__main__":
    from os import system
    system("rm test.db")
    test_db = Database("test.db")

    test_injects = ["ship", "heater", "plant", "die CASSY!!!", "TV"]

    records = [(test_injects[i % len(test_injects)], id_generator(12), id_generator(24), "test_device", id_generator(12)) for i in range (10000)]

    for i in range(len(records)):
        test_db.sqlDB.insertRecord( "sensors", 
            ("device_name", "mac_address", "tuya_id" , "product_name", "uuid"), 
            records[i])
    
    fetch_back = test_db.sqlDB.fetchFromTable(tableName = "sensors", 
                                             columnNames = ("device_name", "mac_address", "tuya_id" , "product_name", "uuid"))

    print (f"Fetched datasets {len(fetch_back)}")
    if len(fetch_back) != len(records):
        print("DIE CASSY")