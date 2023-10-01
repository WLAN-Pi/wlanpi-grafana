#!/bin/bash

/opt/wlanpi-grafana/check-token.sh

while true; do ./internet.sh | /opt/wlanpi-grafana/to-grafana.sh internet; sleep 300; done
