#/env/python
from enum import Enum
from os.path import exists
import sqlite3, logging, string, random
logging.basicConfig(format='%(levelname)s : %(message)s', level=logging.INFO)


def id_generator(size=45, chars=string.ascii_letters + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

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
                                direct="ASC" if self.order_direction == Order.ASC else "DESC" )



class DbConnection(object):
    def __init__(self, database_path):
        self.__path = database_path
        ### Database pointer
        self.__db = sqlite3.connect(self.__path)
        ### Internal dictionary to cache which tables are held
        self.__tables = {}
        print(sqlite3.sqlite_version)
        self._loadTableInfo()

    def __del__(self):
        self.__db.close()
    
    def _loadTableInfo(self):
        query = "SELECT name FROM sqlite_master WHERE type ='table' AND name NOT LIKE 'sqlite_%';"
        logging.debug(f"_loadTableInfo() - Execute query {query}")
        cursor = self.instance.cursor()
        cursor.execute(query)
        #### Load all present tables 
        for table_row in cursor.fetchall():
            table_name = table_row[0]
            logging.debug(f"_loadTableInfo() - Found table {table_name}")
            self.__tables[table_name] = []
        #### Now load the columns types
        for table_name in self.__tables.keys():
            query = f"SELECT name, type, \"notnull\", pk from pragma_table_info('{table_name}');"
            logging.debug(f"_loadTableInfo() - Execute query {query}")
            cursor.execute(query)
            for column_def in cursor.fetchall():
                column_name = column_def[0]
                notNull = column_def[2] != 0
                primary = column_def[3] != 0
                d_type  = None
                if column_def[1] == "INTEGER": d_type = DataTypes.INT_TYPE
                elif column_def[1] == "REAL": d_type = DataTypes.REAL_TYPE
                elif column_def[1] == "TEXT": d_type = DataTypes.TEXT_TYPE
                else: raise RuntimeError(f"Column {column_name} has an unknown data type {column_def[1]}")
                self.__tables[table_name].append(ColumnDef(name= column_def, d_type = d_type, 
                                                           primary=primary, notNull = notNull))

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
        logging.debug(f"createTable() - Execute {query}")
        self.instance.execute(query)
        self.__tables[tableName] = columns

    def tableInfo(self, tableName: str):
        if tableName not in self.__tables.keys():
            raise RuntimeError(f"tableInfo() - The table {tableName} does not exist")
        return self.__tables[tableName]

    def primaryKey(self, tableName: str):
        for col in self.tableInfo(tableName):
            if col.primary: return col
        raise RuntimeError(f"There is no primary column for table {tableName}")

    def columnDataTypes(self, 
                        tableName: str, 
                        columns:tuple):
        d_types =[] 
        for col_name in columns:
            for db_col in self.tableInfo(tableName=tableName):
                if db_col.column_name == col_name:
                    d_types.append(db_col.data_type)
                    break
        return d_types

    def insertRecord(self, 
                     tableName: str, 
                     columns: tuple,
                     record: tuple):
        if len(columns) != len(record):
            raise RuntimeError(f"insertRecord() - Inconsistent number of columns ({len(columns)}) and records {len(record)}")
        if len(columns) == 0:
            raise RuntimeError(f"insertRecord() - The number of passed colmuns must not be zero")
        d_types = self.columnDataTypes(tableName=tableName, columns=columns)
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
        logging.debug(query)
        cursor = self.instance.cursor()
        cursor.execute(query)
        self.instance.commit()
        primary = self.primaryKey(tableName)
        return self.fetchFromTable(tableName = tableName,
                                   columns = [primary.column_name],
                                   order = [QueryOrder(name= primary.column_name, order =Order.DESC)],
                                   limit = 1)[0][0]

    #### Fetch entries from the table
    def fetchFromTable(self, tableName:str, 
                             columns:list = [],
                             conditions: list =[],
                             order: list =[],
                             limit:int = -1,
                             start: int =0):
        cols = "*" if len(columns) == 0 else ", ".join([f"\"{c}\"" for c in columns])
        sel = "" if len(conditions)  == 0 else "WHERE {l_cond}".format(
                        l_cond=", ".join([f"{c}" for c in conditions]))
        sort = "" if len(order) == 0 else "ORDER BY {ord_seq}".format(ord_seq = ", ".join([
                f"{o}" for o in order]))
        
        range_str = "" if limit < 1 else f"LIMIT {start}, {limit}"
       
        query = f"SELECT {cols} FROM {tableName} {sel} {sort} {range_str}"
        logging.debug(query)
        cursor = self.instance.cursor()
        cursor.execute(query)
        return cursor.fetchall()
    #### Update an entry from the table
    def updateRecord(self, tableName: str,
                           columns: tuple,
                           record: tuple,
                           entry_id):
        if len(columns) != len(record):
            raise RuntimeError(f"updateRecord() - Inconsistent number of columns ({len(columns)}) and records {len(record)}")
        if len(columns) == 0:
            raise RuntimeError(f"updateRecord() - The number of passed colmuns must not be zero")
        d_types = self.columnDataTypes(tableName=tableName, columns=columns)
        if len(d_types) != len(columns):
            raise RuntimeError(f"updateRecord() - At least one column is not part of the table {tableName}")

        value_str = ""
        for i in range(len(record)):
            if i > 0: value_str+=", "
            value_str+=f"\"{columns[i]}\"="
            if d_types[i] == DataTypes.TEXT_TYPE: value_str+=f"\"{record[i]}\""
            else: value_str+=f"{record[i]}"

        query = f"UPDATE {tableName} SET {value_str} WHERE \"{self.primaryKey(tableName).column_name}\"='{entry_id}'"
        cursor = self.instance.cursor()
        cursor.execute(query)
        self.instance.commit()

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

if __name__ == "__main__":
    from os import system
    #system("rm test.db")
    test_db = Database("test.db")
    exit(1)
    test_injects = ["ship", "heater", "plant", "die CASSY!!!", "TV"]

    records = [(test_injects[i % len(test_injects)], id_generator(12), id_generator(24), "test_device", id_generator(12)) for i in range (100)]

    for i in range(len(records)):
        test_db.sqlDB.insertRecord(tableName ="sensors", 
            columns= ("device_name", "mac_address", "tuya_id" , "product_name", "uuid"), 
            record = records[i])
    
    fetch_back = test_db.sqlDB.fetchFromTable(tableName = "sensors", 
                                              columns = ("device_name", "mac_address", "tuya_id" , "product_name", "uuid"))

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
        test_db.sqlDB.updateRecord(tableName="sensors",
                                   columns = ["product_name"],
                                   record = [new_devices[i % len(new_devices)]],
                                   entry_id = i+1)

                                   
