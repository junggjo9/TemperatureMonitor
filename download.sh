#!/bin/bash

source /home/user/TemperatureMonitoring/python_env/bin/activate
cd /home/user/TemperatureMonitoring/
python read_sensor.py

#### Update the data records
cp  /var/www/html/temperature_flat/*.json /home/user/TemperatureMonitoring/data_records/

#exit
now=`date`
#### Push to git
git pull
git commit -am "Update of the data records ${now}"
git push
exit
python plot_sensors.py --curve humidity
python plot_sensors.py --curve temperature

### Temporarily add the git fetch

