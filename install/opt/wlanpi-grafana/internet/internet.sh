#!/bin/bash

hostname=$(hostname)
#rtt=$(ping -c1 google.com | grep "rtt" | cut -d"/" -f5)
speedtest_result=$(speedtest-cli --secure --csv)
rtt=$(echo "$speedtest_result" | cut -d"," -f6)
download=$(echo "$speedtest_result" | cut -d"," -f7)
upload=$(echo "$speedtest_result" | cut -d"," -f8)

echo "internet,hostname=$hostname rtt=$rtt,download=$download,upload=$upload"
