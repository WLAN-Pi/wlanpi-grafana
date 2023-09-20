#!/bin/bash

/opt/wlanpi-grafana/check-token.sh

while true; do ./internet.sh | ./tografana.sh internet; sleep 300; done
