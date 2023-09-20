#!/bin/bash

cpu_temp=$(( $(</sys/class/thermal/thermal_zone0/temp) / 1000 ))
gpu_temp=$(vcgencmd measure_temp | cut -d"=" -f2 | cut -d"'" -f1)
pmic_temp=$(vcgencmd measure_temp pmic | cut -d"'" -f1 | cut -d"=" -f2)
cpu_freq=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq)
cpu_volt=$(vcgencmd measure_volts | cut -d"=" -f2 | sed 's/V$//')
cpu_throttled=$(vcgencmd get_throttled | cut -d"x" -f2)
hostname=$(hostname)
cpu_util=$(mpstat -o JSON | jq '(100-(.sysstat.hosts[0].statistics[0]."cpu-load"[0].idle))')
mem_used=$(free | head -n2 | tail -n1 | awk '{print $3 / $2 * 100}')
sdcard_used=$(df | grep "/dev/root" | awk '{print $5}' | cut -d"%" -f1)
#gpu_util=0
#sda1_used=$(df | grep "/dev/sda1" | awk '{print $5}' | cut -d"%" -f1)
#sdb1_used=$(df | grep "/dev/sdb1" | awk '{print $5}' | cut -d"%" -f1)

echo "pihealth,hostname=$hostname cpu_temp=$cpu_temp,gpu_temp=$gpu_temp,cpu_util=$cpu_util,mem_used=$mem_used,sdcard_used=$sdcard_used,pmic_temp=$pmic_temp,cpu_freq=$cpu_freq,cpu_volt=$cpu_volt,cpu_throttled=$cpu_throttled"
