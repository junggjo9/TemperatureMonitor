#!/bin/bash


source /home/user/TemperatureMonitoring/python_env/bin/activate
cd /home/user/TemperatureMonitoring/
python plot_sensors.py --curve temperature
python plot_sensors.py --curve humidity

python plot_sensors.py --curve temperature --singleCurves
python plot_sensors.py --curve humidity --singleCurves
