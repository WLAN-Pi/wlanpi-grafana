#!/bin/bash
# stream-scanner.sh <interface>: scan <interface> with nlscan-lp and stream the results to Grafana Live.

iface=$1
dir=$(dirname "$(readlink -f "$0")")
net=${SYS_CLASS_NET:-/sys/class/net}
raised=
paused=()

is_up() { (($(cat "$net/$1/flags") & 1)); }

# True if a capture (a packet socket) is bound to any of the given interfaces,
# or if ss can't tell.
captured() {
    local socks mon
    socks=$(ss -0 -a -n -H) || return 0
    for mon; do
        awk '{ sub(/.*:/, "", $5); print $5 }' <<< "$socks" | grep -qx "$mon" && return 0
    done
    return 1
}

resume_monitors() {
    for mon in "${paused[@]}"; do ip link set "$mon" up; done
    paused=()
}

restore() {
    # Leave the interface alone if it was replaced meanwhile, as activating
    # a wlanpi-core network profile does.
    if [ -n "$raised" ] && [ "$(cat "$net/$iface/ifindex" 2>/dev/null)" = "$raised" ]; then
        ip link set "$iface" down
    fi
    resume_monitors
}
trap restore EXIT
trap 'exit 0' TERM INT

# Intel iwlwifi firmware (BE200) crashes when an interface scans while a
# monitor on the same radio is up (WLAN-Pi/wlanpi-core#314), so keep those
# monitors down while the scanner runs, unless a capture is using one.
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
    if [ ${#mons[@]} -gt 0 ] && captured "${mons[@]}"; then
        echo "Not scanning on $iface: a capture is using ${mons[*]} on the same Intel radio"
        return 1
    fi
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
            ip link set "$iface" up && raised=$(cat "$net/$iface/ifindex")
        fi
        "$dir/nlscan-lp" "$iface" > >("$dir/../to-grafana.sh" nlscan) &
        scan=$!
        # A capture that starts on a paused monitor ends the scan and gets
        # the monitor back. ponytail: a tool that raises the monitor itself
        # overlaps the scan for up to one poll; core's own scan risks 3-5 s.
        while sleep 2 && kill -0 "$scan" 2> /dev/null; do
            if [ ${#paused[@]} -gt 0 ] && captured "${paused[@]}"; then
                echo "Stopping the scan on $iface: a capture started on ${paused[*]}"
                kill "$scan"
                resume_monitors
            fi
        done
        wait "$scan"
    fi
    # nlscan-lp scans until it fails. Without a pause a down interface fails
    # hundreds of times a second.
    sleep 5
done
