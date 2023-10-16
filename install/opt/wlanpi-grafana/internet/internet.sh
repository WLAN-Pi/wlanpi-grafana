#!/bin/bash
# This script collects data for Internet Monitoring Grafana dashboard

# Sample output
# internet,hostname=wlanpi-5a8 rtt_speedtest=55.02,rtt_google=70.912,rtt_gateway=0.447,download=20014469.101157937,upload=1906590.93800208,dns1_res_time_google=3,dns1_res_time_apple=3,dns1_res_time_aws=0,internet_status=1

internet_status=0
default_gateway=$(ip route | grep "default" | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}" | head -n1)

# No default gateway detected, WLAN Pi has no internet connection
if [ -z "$default_gateway" ]; then
cat <<-____HERE
internet,hostname=$(hostname) \
rtt_speedtest=-1,\
rtt_google=-1,\
rtt_gateway=-1,\
download=-1,\
upload=-1,\
dns1_res_time_google=-1,\
dns1_res_time_apple=-1,\
dns1_res_time_aws=-1,\
internet_status=$internet_status
____HERE
exit 1
fi

# Default gateway detected, continue
primary_dns_server=$(grep -m1 "nameserver" /etc/resolv.conf | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
dns1_res_time_google=$(dig +time=2 +tries=1 @"$primary_dns_server" NS google.com | grep "Query time:" | cut -d ' ' -f4)
if [ -z "$dns1_res_time_google" ]; then dns1_res_time_google="-1"; else internet_status=1; fi
dns1_res_time_apple=$(dig +time=2 +tries=1 @"$primary_dns_server" NS apple.com | grep "Query time:" | cut -d ' ' -f4)
if [ -z "$dns1_res_time_apple" ]; then dns1_res_time_apple="-1"; fi
dns1_res_time_aws=$(dig +time=2 +tries=1 @"$primary_dns_server" NS amazonaws.com | grep "Query time:" | cut -d ' ' -f4)
if [ -z "$dns1_res_time_aws" ]; then dns1_res_time_aws="-1"; fi

speedtest_result=$(librespeed-cli --json)
# Sample output of librespeed-cli --json
# [{"timestamp":"2023-10-16T07:57:21.667623717-05:00","server":{"name":"London, England (Clouvider)","url":"http://lon.speedtest.clouvider.net/backend"},"client":{"ip":"","hostname":"","city":"","region":"","country":"","loc":"","org":"","postal":"","timezone":""},"bytes_sent":991330304,"bytes_received":1761691176,"ping":9,"jitter":0.25,"upload":508.29,"download":903.39,"share":""}]

rtt_speedtest=$(echo "$speedtest_result" | jq -r '.[0].ping')
rtt_google=$(ping -c1 google.com | grep "rtt" | cut -d"/" -f5)
rtt_gateway=$(ping -c1 "$default_gateway" | grep "rtt" | cut -d"/" -f5)
download=$(echo "$speedtest_result" | jq -r '.[0].download')
upload=$(echo "$speedtest_result" | jq -r '.[0].upload')

# Generate final output
cat <<-____HERE
internet,hostname=$(hostname) \
rtt_speedtest=$rtt_speedtest,\
rtt_google=$rtt_google,\
rtt_gateway=$rtt_gateway,\
download=$download,\
upload=$upload,\
dns1_res_time_google=$dns1_res_time_google,\
dns1_res_time_apple=$dns1_res_time_apple,\
dns1_res_time_aws=$dns1_res_time_aws,\
internet_status=$internet_status
____HERE
