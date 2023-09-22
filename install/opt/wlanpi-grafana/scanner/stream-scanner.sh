#!/bin/bash
/opt/wlanpi-grafana/check-token.sh

while true; do ./nlscan-lp wlan0 | ./tografana.sh scan; done
