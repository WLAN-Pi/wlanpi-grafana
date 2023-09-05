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

    # Sleep is required for Grafana service to start. It has to be sleep for fixed amount of time. Otherwise installation fails during image build process.
    echo "Waiting for 15 seconds for Grafana service to start"
    sleep 15

    # Create wlanpi service account
    echo "Creating Grafana service account wlanpi"
    SA_RESPONSE=$(curl -s --insecure -X POST https://admin:admin@127.0.0.1/app/grafana/api/serviceaccounts -H "Accept: application/json" -H "Content-Type: application/json" -d '{"name": "wlanpi", "role": "Admin", "isDisabled": false}' -w " StatusCode:%{http_code}")

    # Generate API token for wlanpi service account. Service account must use name wlanpi and ID 2. Otherwise following command fails.
    echo "Generating Grafana API token for service account wlanpi"
    NEW_GRAFANA_TOKEN=$(curl -s --insecure -X POST https://admin:admin@127.0.0.1/app/grafana/api/serviceaccounts/2/tokens -H "Accept: application/json" -H "Content-Type: application/json" -d '{"name": "wlanpi", "role": "Admin"}' | jq -r '.key')

    if [ ${#NEW_GRAFANA_TOKEN} -gt 40 ]; then
        # Save API token to env variable
        echo "Successfully generated Grafana API token"
        echo "Saving Grafana API token to environmental variable"
        echo "GRAFANA_TOKEN=$NEW_GRAFANA_TOKEN" | sudo tee -a /etc/environment
        set -a; source /etc/environment; set +a
    else
        echo "Error: Failed to create Grafana API token"
        exit 1
    fi
else
    echo "Existing Grafana API token found in environmental variable"
    echo "GRAFANA_TOKEN=$GRAFANA_TOKEN"
fi
