#!/bin/bash

source /home/user/TemperatureMonitoring/python_env/bin/activate
cd /home/user/TemperatureMonitoring/
python sync_database.py

python curve_analysis.py

exit
