#!/bin/bash
/opt/wlanpi-grafana/check-token.sh
/opt/wlanpi-grafana/wipry/wipry-lp $1 | /opt/wlanpi-grafana/to-grafana.sh
