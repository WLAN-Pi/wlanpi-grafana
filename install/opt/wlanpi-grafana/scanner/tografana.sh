#!/bin/bash

source /etc/environment

while IFS= read -r line; do
  curl --insecure -X POST -H "Authorization: Bearer $GRAFANA_TOKEN" -d "$line" https://localhost/app/grafana/api/live/push/$1
done
