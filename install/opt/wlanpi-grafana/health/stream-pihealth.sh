#!/bin/bash

/opt/wlanpi-grafana/check-token.sh

while true; do ./pihealth.sh | /opt/wlanpi-grafana/to-grafana.sh pihealth; sleep 60; done
