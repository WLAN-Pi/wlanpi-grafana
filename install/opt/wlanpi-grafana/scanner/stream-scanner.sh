#!/bin/bash
/opt/wlanpi-grafana/check-token.sh

while true; do ./nlscan-lp $1 | /opt/wlanpi-grafana/to-grafana.sh nlscan; done
