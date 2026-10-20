import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
SCANNER = ROOT / "install/opt/wlanpi-grafana/scanner/stream-scanner.sh"
DASHBOARD = ROOT / "install/var/lib/grafana/dashboards/scanner.json"
NOW = "1792440000"


def network(ssid, bssid="00:11:22:33:44:55", signal=-50, freq=2412, channel=1):
    return {
        "ssid": ssid,
        "bssid": bssid,
        "signal": signal,
        "freq": freq,
        "primaryChannel": channel,
    }


def scan(*networks):
    return 200, json.dumps(
        {"selectedAdapter": {"iface": "wlan0"}, "networks": networks}
    )


def error(code, name):
    return code, json.dumps({"error": name, "message": "..."})


def run_scanner(tmp_path, responses, tokens=("tok1",), cycles=None):
    """Run stream-scanner.sh wlan0 for `cycles` scan cycles (one per response
    by default), with wlanpi-core's scan API answering `responses` in order
    and getjwt handing out `tokens` in order (None: getjwt fails).

    Returns stdout, the channel and lines pushed to Grafana, and per scan
    the curl arguments and the headers curl read from files, and each sleep.
    """
    opt = tmp_path / "opt"
    (opt / "scanner").mkdir(parents=True)
    shutil.copy(SCANNER, opt / "scanner")
    for i, (code, body) in enumerate(responses, start=1):
        (tmp_path / f"{i}.code").write_text(str(code))
        (tmp_path / f"{i}.body").write_text(body)
    for i, token in enumerate(tokens, start=1):
        if token:
            (tmp_path / f"{i}.token").write_text(token)
    pushed, calls, headers = (
        tmp_path / name for name in ("pushed", "calls", "headers")
    )
    sleeps = tmp_path / "sleep_args"
    stubs = {
        opt / "check-token.sh": "",
        opt / "to-grafana.sh": f'echo "$1" > "{tmp_path}/channel"; cat >> "{pushed}"',
    }
    for path, body in stubs.items():
        path.write_text(f"#!/bin/bash\n{body}\n")
        path.chmod(0o755)
    # Functions win over PATH, so these replace the real commands. curl and
    # getjwt run in subshells, so they count their calls in files.
    defs = (
        'next() { n=$(($(cat "$1" 2>/dev/null) + 1)); echo $n > "$1"; echo $n; }; '
        f'curl() {{ printf "%s\\n" "$*" >> "{calls}"; '
        f'for a; do case $a in @*) cat "${{a#@}}" >> "{headers}" ;; esac; done; '
        f'n=$(next "{tmp_path}/curls"); '
        f'cat "{tmp_path}/$n.body"; printf "\\n%s" "$(cat "{tmp_path}/$n.code")"; }}; '
        f'getjwt() {{ n=$(next "{tmp_path}/getjwts"); '
        f'[ -e "{tmp_path}/$n.token" ] || {{ echo "API Error: connection refused"; return 1; }}; '
        f'echo "export WLANPI_TOKEN=$(cat "{tmp_path}/$n.token")"; }}; '
        f"date() {{ echo {NOW}; }}; "
        # Exiting closes the pipe to to-grafana.sh, which then pushes the rest.
        f'sleep() {{ echo "$*" >> "{sleeps}"; '
        f'[ "$(next "{tmp_path}/sleeps")" -lt {cycles or len(responses)} ] || exit 0; }}; '
        "export -f next curl getjwt date sleep; "
    )
    result = subprocess.run(
        [
            "bash",
            "-c",
            defs + 'exec "$0" wlan0',
            str(opt / "scanner/stream-scanner.sh"),
        ],
        env=os.environ,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    channel = tmp_path / "channel"

    def lines(path):
        return path.read_text().splitlines() if path.exists() else []

    return SimpleNamespace(
        out=result.stdout.splitlines(),
        channel=channel.read_text().strip() if channel.exists() else None,
        pushed=lines(pushed),
        calls=lines(calls),
        headers=lines(headers),
        sleeps=lines(sleeps),
    )


def test_pushes_each_network_in_the_scanner_format(tmp_path):
    response = scan(
        network("Office", bssid="9a:2a:6f:42:e4:79", signal=-38, freq=2462, channel=11),
        # Hidden networks: an empty SSID, or NULs that wlanpi-core prints as \x00.
        network("", bssid="94:2a:6f:42:e4:79"),
        network(r"\x00\x00", bssid="94:2a:6f:42:e4:7a"),
        network("Cafe Wifi", freq=5955, channel=None),
        # Grafana splits labels on "," and "="; line protocol can't carry a tab
        # or end a tag value in a backslash.
        network("Bob,Guest=1"),
        network("tab\tx"),
        network("back\\"),
        # wlanpi-core's own escapes and UTF-8 pass through.
        network(r"PoM-\x1a\x13"),
        network("Café"),
    )

    run = run_scanner(tmp_path, [response])

    def line(tags, rssi=-50):
        return f"scanner,ifname=wlan0,{tags} rssi={rssi} {NOW}000000000"

    tags = "bssid=001122334455,freq=2412,channel=1"
    assert run.out == []
    assert run.channel == "scanner"
    assert run.pushed == [
        line(
            r"bssid=9a2a6f42e479,freq=2462,channel=11,name=Office\ [9a2a6f42e479],ssid=Office",
            rssi=-38,
        ),
        line("bssid=942a6f42e479,freq=2412,channel=1,name=[942a6f42e479]"),
        line("bssid=942a6f42e47a,freq=2412,channel=1,name=[942a6f42e47a]"),
        line(
            r"bssid=001122334455,freq=5955,name=Cafe\ Wifi\ [001122334455],ssid=Cafe\ Wifi"
        ),
        line(rf"{tags},name=Bob\x2cGuest\x3d1\ [001122334455],ssid=Bob\x2cGuest\x3d1"),
        line(rf"{tags},name=tab\x09x\ [001122334455],ssid=tab\x09x"),
        line(rf"{tags},name=back\\ [001122334455],ssid=back\x5c"),
        line(rf"{tags},name=PoM-\x1a\x13\ [001122334455],ssid=PoM-\x1a\x13"),
        line(rf"{tags},name=Café\ [001122334455],ssid=Café"),
    ]


def test_logs_each_failure_once(tmp_path):
    responses = [
        error(409, "SCAN_IN_PROGRESS"),
        error(409, "SCAN_IN_PROGRESS"),
        error(409, "MONITOR_IN_USE"),
        error(422, "NO_SCAN_ADAPTER"),
        ("000", ""),  # curl couldn't reach wlanpi-core
        error(409, "SCAN_IN_PROGRESS"),
        scan(network("Office")),
        error(409, "SCAN_IN_PROGRESS"),
    ]

    run = run_scanner(tmp_path, responses)

    assert run.out == [
        "Scan on wlan0 failed: HTTP 409 SCAN_IN_PROGRESS",
        "Scan on wlan0 failed: HTTP 409 MONITOR_IN_USE",
        "Scan on wlan0 failed: HTTP 422 NO_SCAN_ADAPTER",
        "Scan on wlan0 failed: HTTP 000",
        "Scan on wlan0 failed: HTTP 409 SCAN_IN_PROGRESS",
        # A success in between: the same failure is news again.
        "Scan on wlan0 failed: HTTP 409 SCAN_IN_PROGRESS",
    ]
    assert len(run.pushed) == 1
    # wlanpi-core's scan guide asks for at least 15 s between scans.
    assert run.sleeps == ["15"] * len(responses)


def test_gets_a_new_core_token_when_core_rejects_one(tmp_path):
    responses = [scan(network("Office")), error(401, ""), scan(network("Office"))]

    run = run_scanner(tmp_path, responses, tokens=("tok1", "tok2"))

    assert run.out == ["wlanpi-core rejected its token; getting a new one"]
    assert run.headers == [
        f"Authorization: Bearer {t}" for t in ("tok1", "tok1", "tok2")
    ]
    assert len(run.pushed) == 2


def test_waits_for_core_to_issue_a_token(tmp_path):
    run = run_scanner(
        tmp_path, [scan(network("Office"))], tokens=(None, None, "tok1"), cycles=3
    )

    assert run.out == [
        "Could not get a wlanpi-core token: API Error: connection refused"
    ]
    assert len(run.calls) == 1
    assert len(run.pushed) == 1


def test_asks_core_for_one_interface_without_the_token_in_argv(tmp_path):
    run = run_scanner(tmp_path, [scan(network("Office"))])

    (args,) = run.calls
    assert args.startswith(
        "-s --cacert /etc/nginx/ssl/self-signed-wlanpi.cert --max-time 30"
    )
    assert "-G --data-urlencode iface=wlan0" in args
    assert args.endswith("https://127.0.0.1:31415/api/v1/utils/wlan/scan")
    # Any local user can read a process's argv.
    assert "tok1" not in args
    assert run.headers == ["Authorization: Bearer tok1"]


def test_dashboard_reads_the_channel_the_scanner_pushes_to(tmp_path):
    run = run_scanner(tmp_path, [scan(network("Office"))])
    measurement = run.pushed[0].split(",")[0]

    panels = json.loads(DASHBOARD.read_text())["panels"]
    channels = {
        t["channel"] for p in panels for t in p.get("targets", []) if "channel" in t
    }

    assert channels == {f"stream/{run.channel}/{measurement}"}
