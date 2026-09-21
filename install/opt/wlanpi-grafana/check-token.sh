#!/bin/bash

# Check if Grafana service is running
if ! systemctl is-active --quiet grafana-server; then
    echo "Error: Grafana service is not running"
    exit 1
fi

# Check if Service Account and API token have been created. If not, create them.
set -a; source /etc/environment; set +a

if [ ${#GRAFANA_TOKEN} -lt 40 ]; then
    echo "No Grafana API token for service account found. Attempting to create one now."
    while true; do
        # If we get 502 or cannot connect, wait for Grafana to come up
        HTTP_CODE=$(curl --insecure --max-time 5 --write-out "%{http_code}" --silent --output /dev/null https://127.0.0.1:3000/app/grafana/)
        if [ "$HTTP_CODE" = "502" ] || [ "$HTTP_CODE" = "000" ]; then
            sleep 1
        else
            break
        fi
    done

    # Create wlanpi service account
    echo "Creating Grafana service account wlanpi"
    SA_RESPONSE=$(curl -s --insecure -X POST https://wlanpi:wlanpi@127.0.0.1:3000/app/grafana/api/serviceaccounts -H "Accept: application/json" -H "Content-Type: application/json" -d '{"name": "wlanpi", "role": "Admin", "isDisabled": false}' -w " StatusCode:%{http_code}")

    # Look up the service account ID by name. It is not guaranteed to be 2.
    SA_ID=$(curl -s --insecure https://wlanpi:wlanpi@127.0.0.1:3000/app/grafana/api/serviceaccounts/search?perpage=100\&page=1 | jq -r '.serviceAccounts[] | select(.name == "wlanpi") | .id' | head -1)

    if [ -z "$SA_ID" ]; then
        echo "Error: Failed to find Grafana service account wlanpi"
        exit 1
    fi

    # Delete any existing tokens so a fresh one can be created with a known name
    for TOKEN_ID in $(curl -s --insecure https://wlanpi:wlanpi@127.0.0.1:3000/app/grafana/api/serviceaccounts/"$SA_ID"/tokens | jq -r '.[].id' 2>/dev/null); do
        curl -s --insecure -X DELETE https://wlanpi:wlanpi@127.0.0.1:3000/app/grafana/api/serviceaccounts/"$SA_ID"/tokens/"$TOKEN_ID" > /dev/null
    done

    # Generate API token for wlanpi service account
    echo "Generating Grafana API token for service account wlanpi"
    NEW_GRAFANA_TOKEN=$(curl -s --insecure -X POST https://wlanpi:wlanpi@127.0.0.1:3000/app/grafana/api/serviceaccounts/"$SA_ID"/tokens -H "Accept: application/json" -H "Content-Type: application/json" -d '{"name": "wlanpi", "role": "Admin"}' | jq -r '.key')

    if [ ${#NEW_GRAFANA_TOKEN} -gt 40 ]; then
        # Save API token to env variable
        echo "Successfully generated Grafana API token"
        echo "Saving Grafana API token to environmental variable"
        echo "GRAFANA_TOKEN=$NEW_GRAFANA_TOKEN" | sudo tee -a /etc/environment > /dev/null
        set -a; source /etc/environment; set +a
    else
        echo "Error: Failed to create Grafana API token"
        exit 1
    fi
else
    echo "Existing Grafana API token found in environmental variable"
    #echo "GRAFANA_TOKEN=$GRAFANA_TOKEN"
fi
