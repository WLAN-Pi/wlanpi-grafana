#!/bin/bash
/opt/wlanpi-grafana/check-token.sh

spectool_raw -r 2 2> /dev/null | spectool-client-parser > /dev/null
