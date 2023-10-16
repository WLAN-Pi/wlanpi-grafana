#!/bin/bash
# This script collects data for Internet Monitoring Grafana dashboard

# Sample outputs of this script
# internet,hostname=wlanpi-ed8 rtt_speedtest=9.329,rtt_google=9.430,rtt_gateway=0.555,speedtest_tool=Speedtest.net,download=879,upload=836,dns1_res_time_google=19,dns1_res_time_apple=11,dns1_res_time_aws=11,internet_status=1
# internet,hostname=wlanpi-ed8 rtt_speedtest=9,rtt_google=10.721,rtt_gateway=0.549,speedtest_tool=LibreSpeed,download=857.79,upload=509.97,dns1_res_time_google=19,dns1_res_time_apple=11,dns1_res_time_aws=11,internet_status=1

# To use Speedtest.net instead of LibreSpeed add this line to /etc/environment file: USE_SPEEDTEST_NET=1
# Make sure Ookla's speedtest CLI tool is installed
# Execute "speedtest" manually and accept EULA license at its very first start

# Load $USE_SPEEDTEST_NET environmental variable
source /etc/environment

if [[ ! -v USE_SPEEDTEST_NET || "$USE_SPEEDTEST_NET" -eq 0 ]]; then
    USE_SPEEDTEST_NET=0
    speedtest_tool="LibreSpeed"
else
    speedtest_tool="Speedtest.net"
fi

internet_status=0
default_gateway=$(ip route | grep "default" | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}" | head -n1)

# No default gateway detected, WLAN Pi has no internet connection
if [ -z "$default_gateway" ]; then
cat <<-____HERE
internet,hostname=$(hostname) \
rtt_speedtest=-1,\
rtt_google=-1,\
rtt_gateway=-1,\
speedtest_tool=$speedtest_tool,\
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
rtt_google=$(ping -c1 google.com | grep "rtt" | cut -d"/" -f5)
rtt_gateway=$(ping -c1 "$default_gateway" | grep "rtt" | cut -d"/" -f5)

# Use LibreSpeed by default to measure throughput
if [ "$USE_SPEEDTEST_NET" -eq 0 ]; then
    speedtest_result=$(librespeed-cli --json)
    # Sample output
    # [{"timestamp":"2023-10-16T07:57:21.667623717-05:00","server":{"name":"London, England (Clouvider)","url":"http://lon.speedtest.clouvider.net/backend"},"client":{"ip":"","hostname":"","city":"","region":"","country":"","loc":"","org":"","postal":"","timezone":""},"bytes_sent":991330304,"bytes_received":1761691176,"ping":9,"jitter":0.25,"upload":508.29,"download":903.39,"share":""}]
    rtt_speedtest=$(echo "$speedtest_result" | jq -r '.[0].ping')
    download=$(echo "$speedtest_result" | jq -r '.[0].download')
    upload=$(echo "$speedtest_result" | jq -r '.[0].upload')
else
    # Use Ookla Speedtest.net to measure throughput
    speedtest_result=$(speedtest -f json)
    # Sample output
    # {"type":"result","timestamp":"2023-10-16T15:51:29Z","ping":{"jitter":0.824,"latency":8.928,"low":7.549,"high":9.718},"download":{"bandwidth":109643056,"bytes":996186976,"elapsed":9209,"latency":{"iqm":9.719,"low":7.923,"high":230.024,"jitter":3.306}},"upload":{"bandwidth":103091745,"bytes":1065890503,"elapsed":10503,"latency":{"iqm":16.415,"low":8.524,"high":26.067,"jitter":1.687}},"packetLoss":0,"isp":"Zen Internet Ltd","interface":{"internalIp":"192.168.199.1","name":"eth0","macAddr":"EE:55:11:AA:BB:CC","isVpn":false,"externalIp":"80.70.20.200"},"server":{"id":40788,"host":"speedtest02a.web.zen.net.uk","port":8080,"name":"Zen Internet","location":"London","country":"United Kingdom","ip":"51.148.82.21"},"result":{"id":"85adc2c1-xxxx-yyyy-bf4a-a54878dd50ec","url":"https://www.speedtest.net/result/c/85adc2c1-xxxx-yyyy-bf4a-a54878dd50ec","persisted":true}}
    rtt_speedtest=$(echo "$speedtest_result" | jq -r '.ping.latency')
    download=$(echo "$speedtest_result" | jq -r '.download.bandwidth')
    # Convert to Mbps
    download=$((download * 8 / 1000000))
    upload=$(echo "$speedtest_result" | jq -r '.upload.bandwidth')
    # Convert to Mbps
    upload=$((upload * 8 / 1000000))
fi

# Generate final output
cat <<-____HERE
internet,hostname=$(hostname) \
rtt_speedtest=$rtt_speedtest,\
rtt_google=$rtt_google,\
rtt_gateway=$rtt_gateway,\
speedtest_tool=$speedtest_tool,\
download=$download,\
upload=$upload,\
dns1_res_time_google=$dns1_res_time_google,\
dns1_res_time_apple=$dns1_res_time_apple,\
dns1_res_time_aws=$dns1_res_time_aws,\
internet_status=$internet_status
____HERE
