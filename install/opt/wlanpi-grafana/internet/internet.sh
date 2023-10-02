#!/bin/bash

default_gateway=$(ip route | grep "default" | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}" | head -n1)

primary_dns_server=$(grep -m1 "nameserver" /etc/resolv.conf | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
dns1_res_time_google=$(dig +time=2 +tries=1 @"$primary_dns_server" NS google.com | grep "Query time:" | cut -d ' ' -f4)
if [ -z "$dns1_res_time_google" ]; then dns1_res_time_google="-1"; fi
dns1_res_time_apple=$(dig +time=2 +tries=1 @"$primary_dns_server" NS apple.com | grep "Query time:" | cut -d ' ' -f4)
if [ -z "$dns1_res_time_apple" ]; then dns1_res_time_apple="-1"; fi
dns1_res_time_akamai=$(dig +time=2 +tries=1 @"$primary_dns_server" NS akamai.com | grep "Query time:" | cut -d ' ' -f4)
if [ -z "$dns1_res_time_akamai" ]; then dns1_res_time_akamai="-1"; fi

hostname=$(hostname)
speedtest_result=$(speedtest-cli --secure --json)
rtt_speedtest=$(echo "$speedtest_result" | jq -r ".ping")
rtt_google=$(ping -c1 google.com | grep "rtt" | cut -d"/" -f5)
rtt_gateway=$(ping -c1 "$default_gateway" | grep "rtt" | cut -d"/" -f5)
download=$(echo "$speedtest_result" | jq -r ".download")
upload=$(echo "$speedtest_result" | jq -r ".upload")

echo "internet,hostname=$hostname rtt_speedtest=$rtt_speedtest,rtt_google=$rtt_google,rtt_gateway=$rtt_gateway,download=$download,upload=$upload,dns1_res_time_google=$dns1_res_time_google,dns1_res_time_apple=$dns1_res_time_apple,dns1_res_time_akamai=$dns1_res_time_akamai"