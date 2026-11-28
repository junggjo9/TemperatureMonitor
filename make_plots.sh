#!/bin/bash


source /home/user/TemperatureMonitoring/python_env/bin/activate
cd /home/user/TemperatureMonitoring/
exit

now=$(python -c "from datetime import datetime; print(datetime.now().strftime('%d%m%y_%H%M'))")
log_file="/var/www/html/temperature_flat/logs/plots_${now}.log"
echo ${log_file}
python plot_sensors.py --curve temperature --singleCurves >${log_file} 2>&1
python plot_sensors.py --curve humidity --singleCurves >>${log_file} 2>&1
python plot_sensors.py --curve voltage --singleCurves >>${log_file} 2>&1

python plot_electricity.py >>${log_file} 2>&1
