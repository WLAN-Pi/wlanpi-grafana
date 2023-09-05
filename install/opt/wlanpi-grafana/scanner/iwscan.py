#!/usr/bin/env python3
import sys
import json

data = json.load(sys.stdin)

for d in data:
    if 'ssid' in d:
        try:
            d['ssid'] = d['ssid'].replace(" ", "\ ")
            print(f'wlanpi,name={d["ssid"]}\ {d["bssid"]},ssid={d["ssid"]},bssid={d["bssid"]},channel={d["primary_channel"]},freq={d["freq"]} rssi={d["signal_dbm"]},channel={d["primary_channel"]},freq={d["freq"]}')
        except AttributeError:
            pass
    else:
        print(f'wlanpi,name={d["bssid"]},bssid={d["bssid"]},channel={d["primary_channel"]},freq={d["freq"]} rssi={d["signal_dbm"]},channel={d["primary_channel"]},freq={d["freq"]}')

