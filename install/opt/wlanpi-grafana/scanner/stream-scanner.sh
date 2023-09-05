#!/bin/bash
/opt/wlanpi-grafana/check-token.sh

while true; do sudo jc iw dev wlan0 scan | ./iwscan.py | ./tografana.sh scan; done
