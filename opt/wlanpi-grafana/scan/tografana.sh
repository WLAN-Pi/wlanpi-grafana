#!/bin/bash

while IFS= read -r line; do
  curl -X POST -H "Authorization: Bearer $GRAFANA_TOKEN" -d "$line" http://localhost:3000/api/live/push/$1
done
