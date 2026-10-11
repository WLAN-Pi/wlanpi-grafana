#!/bin/bash

source /etc/environment

last=
while IFS= read -r line; do
    code=$(curl -s -o /dev/null -w "%{http_code}" --insecure -X POST -H "Authorization: Bearer $GRAFANA_TOKEN" -d "$line" https://localhost:3000/app/grafana/api/live/push/$1)
    # One line per change, not per sample: the scanner pushes hundreds a second.
    if [ "$code" != "$last" ] && [ "${code:0:1}" != 2 ]; then
        echo "Grafana Live push to $1 failed: HTTP $code" >&2
    fi
    last=$code
done
