#!/bin/bash

source /home/user/TemperatureMonitoring/python_env/bin/activate
cd /home/user/TemperatureMonitoring/

git pull

now=$(python -c "from datetime import datetime; print(datetime.now().strftime('%d%m%y_%H%M'))")
log_file="/var/www/html/temperature_flat/logs/sqlite_${now}.log"
echo ${log_file}


#python sync_database.py >${log_file} 2>&1
result=$?
if [ ${result} -ne 0 ];then
    head ../compile.log
    exit 1
fi
python curve_analysis.py >> ${log_file} 2>&1
