#!/bin/bash
/opt/wlanpi-grafana/check-token.sh

spectool_raw -r 0 2> /dev/null | spectool-client-parser | /opt/wlanpi-grafana/to-grafana.sh wispy > /dev/null