#!/bin/bash


source /home/user/TemperatureMonitoring/python_env/bin/activate
cd /home/user/TemperatureMonitoring/

python plot_sensors.py --curve temperature --singleCurves
python plot_sensors.py --curve humidity --singleCurves
python plot_electricity.py