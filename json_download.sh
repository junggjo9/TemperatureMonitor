#!/bin/bash

source /home/user/TemperatureMonitoring/python_env/bin/activate
cd /home/user/TemperatureMonitoring/
python read_sensor.py

#### Update the data records
cp  /var/www/html/temperature_flat/*.json /home/user/TemperatureMonitoring/data_records/

now=`date`
#### Push to git
git pull
git commit -am "Update of the data records ${now}"
git push

### Temporarily add the git fetch
python copy_from_json.py
