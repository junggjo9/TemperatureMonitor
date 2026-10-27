#!/bin/bash
source /home/user/TemperatureMonitoring/python_env/bin/activate
cd /home/user/TemperatureMonitoring/
python read_sensor.py

python plot_sensors.py --curve humidity
python plot_sensors.py --curve temperature