#/env/python
from enum import Enum
from os.path import exists
import sqlite3



class DataTypes(Enum):
    INT_TYPE = 0 #
    REAL_TYPE = 1
    TEXT_TYPE = 2

#### Object to define a database column
class ColumnDef(object):
    ## Constructor
    ## @param name: The name of the column
    ## @param type: The data type of the column
    ## @param primary: Is the column the primary column identifiying a record
    ## @param notNull: Is the column allowed to be filled without value
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

###
##### Define the following tables wih columns

### sensors - id device_name, mac_address, tuya_id, product_name, uuid, icon

### record_types - id, variable_name, unit, min, max, values
### 
### data_records - id, record_type, sensor_id, value, record_time, insert_time


class DbConnection(object):
    def __init__(self, database_path):
        self.__path = database_path
        ### Database pointer
        self.__db = sqlite3.connect(self.__path)

    @property     
    def instance(self): return self.__db


    def createTable(self, tableName: str, columns: list):
        query="CREATE TABLE {tableName} ({columns})".format(tableName=tableName,
                    columns=",".join([f"{c}" for c in columns]))
        print(query)
        cursor = self.instance.execute(query)

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
        #### Table to store the variables held
        #### name: Name of the variable 
        #### type: Data type of the variable
        #### unit: In which units is the variable given
        #### min: Minimum value of the variable
        #### max: Maximum value of he variable
        #### values: Allowed values (Used for enum)
        self.sqlDB.createTable("record_types",             
            [ColumnDef(name="id", d_type = DataTypes.INT_TYPE, primary=True),
            ColumnDef(name="name", d_type = DataTypes.TEXT_TYPE, notNull=True),
            ColumnDef(name="type", d_type = DataTypes.TEXT_TYPE, notNull=True),
            ColumnDef(name="unit", d_type = DataTypes.TEXT_TYPE, notNull=False),
            ColumnDef(name="min", d_type = DataTypes.REAL, notNull=False),
            ColumnDef(name="max", d_type = DataTypes.REAL, notNull=False),
            ColumnDef(name="values", d_type = DataTypes.TEXT_TYPE, notNull= False)])
        #### Actual data held by the device
        # data_records - id, record_type, sensor_id, value, record_time, insert_time
        self.sqlDB.createTable("data_records",
                    [ColumnDef(name="id", d_type = DataTypes.INT_TYPE, primary=True),
                    ColumnDef(name="record_type", d_type = DataTypes.INT_TYPE, notNull=True,
                              ref_table="record_types", ref_column="id"),
                    ColumnDef(name="sensor_id", d_type = DataTypes.INT_TYPE, notNull=True,
                              ref_table="sensors", ref_column="id"),
                    ColumnDef(name="value", d_type = DataTypes.REAL, notNull=True),
                    ColumnDef(name="record_time", d_type = DataTypes.INT, notNull=True),
                    ColumnDef(name="insert_time", d_type = DataTypes.INT, notNull=True)])

if __name__ == "__main__":
    test_db = Database("test.db")
