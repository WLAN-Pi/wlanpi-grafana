#!/bin/bash
# stream-scanner.sh <interface>: scan <interface> with nlscan-lp and stream the results to Grafana Live.

iface=$1
dir=$(dirname "$(readlink -f "$0")")
net=${SYS_CLASS_NET:-/sys/class/net}
raised=
paused=()

is_up() { (($(cat "$net/$1/flags") & 1)); }

restore() {
    [ -n "$raised" ] && ip link set "$iface" down
    for mon in "${paused[@]}"; do ip link set "$mon" up; done
}
trap restore EXIT
trap 'exit 0' TERM INT

# Intel iwlwifi firmware (BE200) crashes when an interface scans while a
# monitor on the same radio is up (WLAN-Pi/wlanpi-core#314), so keep those
# monitors down while the scanner runs, unless a capture is using one.
# ponytail: a capture that brings a paused monitor back up mid-scan isn't
# caught; wlanpi-core's own scan has the same window.
pause_monitors() {
    local phy dev mon mons=()
    [ "$(basename "$(readlink -f "$net/$iface/device/driver")")" = iwlwifi ] || return 0
    phy=$(readlink -f "$net/$iface/phy80211")
    for dev in "$net"/*; do
        mon=${dev##*/}
        if [ "$(readlink -f "$dev/phy80211")" = "$phy" ] && [ "$(cat "$dev/type")" = 803 ] && is_up "$mon"; then
            mons+=("$mon")
        fi
    done
    for mon in "${mons[@]}"; do
        if ss -0 -a -n -H | awk '{ sub(/.*:/, "", $5); print $5 }' | grep -qx "$mon"; then
            echo "Not scanning on $iface: a capture is using $mon on the same Intel radio"
            return 1
        fi
    done
    for mon in "${mons[@]}"; do
        ip link set "$mon" down && paused+=("$mon")
    done
}

"$dir/../check-token.sh"

while true; do
    if [ ! -e "$net/$iface" ]; then
        echo "$iface not found"
    elif pause_monitors; then
        # wlanpi-core leaves a managed interface down once it adds its monitor.
        if ! is_up "$iface"; then
            ip link set "$iface" up && raised=1
        fi
        "$dir/nlscan-lp" "$iface" | "$dir/../to-grafana.sh" nlscan
    fi
    # nlscan-lp scans until it fails. Without a pause a down interface fails
    # hundreds of times a second.
    sleep 5
done
