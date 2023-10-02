#!/bin/bash

default_gateway=$(ip route | grep "default" | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}" | head -n1)

hostname=$(hostname)
speedtest_result=$(speedtest-cli --secure --json)
rtt_speedtest=$(echo "$speedtest_result" | jq -r ".ping")
rtt_google=$(ping -c1 google.com | grep "rtt" | cut -d"/" -f5)
rtt_gateway=$(ping -c1 "$default_gateway" | grep "rtt" | cut -d"/" -f5)
download=$(echo "$speedtest_result" | jq -r ".download")
upload=$(echo "$speedtest_result" | jq -r ".upload")

echo "internet,hostname=$hostname rtt_speedtest=$rtt_speedtest,rtt_google=$rtt_google,rtt_gateway=$rtt_gateway,download=$download,upload=$upload"
