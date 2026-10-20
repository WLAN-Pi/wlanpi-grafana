#!/bin/bash
# stream-scanner.sh <interface>: scan <interface> through wlanpi-core every 15 s and stream the results to Grafana Live.

iface=$1
dir=$(dirname "$(readlink -f "$0")")
scan_url=https://127.0.0.1:31415/api/v1/utils/wlan/scan
core_cert=/etc/nginx/ssl/self-signed-wlanpi.cert

# One line protocol line per network, in the format the Scanner dashboard reads.
# Grafana splits a stream's labels on "," and "=", and line protocol can't
# carry control characters or end a tag value in "\", so those are written as
# \xNN, the way iw writes SSID bytes it can't print.
lines='
def hex: "0123456789abcdef" as $h | (. / 16 | floor) as $hi
    | "\\x" + $h[$hi:$hi + 1] + $h[. % 16:. % 16 + 1];
def tag: explode
    | map(if . < 32 or . == 127 or . == 44 or . == 61 then hex
          elif . == 32 then "\\ "
          else [.] | implode end)
    | join("") | sub("\\\\$"; "\\x5c");
.networks[]
| (.bssid | gsub(":"; "")) as $bssid
| "scanner,ifname=\($ifname),bssid=\($bssid),freq=\(.freq)"
    + (if .primaryChannel then ",channel=\(.primaryChannel)" else "" end)
    + (if .ssid | test("^(\\\\x00)*$") then ",name=[\($bssid)]"
       else ",name=\("\(.ssid) [\($bssid)]" | tag),ssid=\(.ssid | tag)" end)
    + " rssi=\(.signal) \($ts)"
'

last=
fail() {
    [ "$1" = "$last" ] || echo "$1"
    last=$1
}

"$dir/../check-token.sh"
exec 3> >("$dir/../to-grafana.sh" scanner -z)

token=
while true; do
    if [ -z "$token" ]; then
        if out=$(getjwt wlanpi-grafana --export); then
            token=${out#export WLANPI_TOKEN=}
        else
            fail "Could not get a wlanpi-core token: $out"
        fi
    fi
    if [ -n "$token" ]; then
        # The header goes through a pipe: any local user can read curl's argv.
        response=$(curl -s --cacert "$core_cert" --max-time 30 -G --data-urlencode "iface=$iface" \
            -H @<(printf 'Authorization: Bearer %s\n' "$token") -w '\n%{http_code}' "$scan_url")
        code=${response##*$'\n'}
        body=${response%$'\n'*}
        case $code in
            200)
                out=$(jq -r --arg ifname "$iface" --arg ts "$(date +%s)000000000" "$lines" <<< "$body")
                [ -z "$out" ] || printf '%s\0' "$out" >&3
                last=
                ;;
            401)
                token=
                fail "wlanpi-core rejected its token; getting a new one"
                ;;
            *)
                error=$(jq -r '.error // empty' <<< "$body" 2> /dev/null)
                fail "Scan on $iface failed: HTTP $code${error:+ $error}"
                ;;
        esac
    fi
    # wlanpi-core's scan is a one-off snapshot; its docs ask for at least 15 s between scans.
    sleep 15
done
