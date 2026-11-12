import logging
logging.basicConfig(format='%(levelname)s : %(message)s', level=logging.INFO)




def copyFromJSONtoSqlite(json_dev, sqlite_dev):
    copied = 0
    for json_var in json_dev.data_fields:
        logging.info(f"JSON {json_var.name}")
        for sqlite_var in sqlite_dev.dataFields:
            if sqlite_var.name != json_var.name: continue
            for time, record in json_dev.data_payload(field = json_var):
                copied += sqlite_dev.storeRecord( data_field = sqlite_var,
                                                  record_time = time,
                                                  value = record)
    logging.info(f"Copied {copied} records from json to sqlite for {sqlite_dev.name}")                   

if __name__ == "__main__":
    from sync_database import setupSmartDevices, setupArgParser
    args = setupArgParser().parse_args()
    sqlite_dev = setupSmartDevices(db_file=args.dataBase)

    from read_sensor import loadSensorsFromJSON

    json_dev = loadSensorsFromJSON(args.deviceJSON)

    for dev in json_dev:
        dev.load_local_db("data_records/")
        for sql in sqlite_dev:
            if sql.tuya_id != dev.tuya_id: continue
            copyFromJSONtoSqlite(json_dev = dev, sqlite_dev = sql)



