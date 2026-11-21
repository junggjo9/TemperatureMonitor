#!/bin/bash

source /home/user/TemperatureMonitoring/python_env/bin/activate
cd /home/user/TemperatureMonitoring/

now=$(python -c "from datetime import datetime; print(datetime.now().strftime('%d%m%y_%H%M'))")
log_file="/var/www/html/temperature_flat/logs/json_${now}.log"
echo ${log_file}

python read_sensor.py > ${log_file} 2>&1

result=$?
if [ ${result} -ne 0 ];then
    head ../compile.log
    exit 1
fi


#### Update the data records
cp  /var/www/html/temperature_flat/records/*.json /home/user/TemperatureMonitoring/data_records/

#### Push to git
git pull
git commit -am "Update of the data records ${now}" >> ${log_file} 2>&1
git push

python copy_from_json.py  >> ${log_file} 2>&1
