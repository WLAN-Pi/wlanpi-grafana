import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCANNER = (
    Path(__file__).resolve().parent.parent
    / "install/opt/wlanpi-grafana/scanner/stream-scanner.sh"
)
MANAGED, MONITOR = "1", "803"


def fake_interface(net, name, phy, driver, kind, up, ifindex=3):
    """Add /sys/class/net/<name> with the links and files the scanner reads."""
    root = net.parent
    (root / "phys" / phy).mkdir(parents=True, exist_ok=True)
    (root / "drivers" / driver).mkdir(parents=True, exist_ok=True)
    device = root / "devices" / phy
    device.mkdir(parents=True, exist_ok=True)
    if not (device / "driver").exists():
        (device / "driver").symlink_to(root / "drivers" / driver)
    iface = net / name
    iface.mkdir(parents=True)
    (iface / "phy80211").symlink_to(root / "phys" / phy)
    (iface / "device").symlink_to(device)
    (iface / "type").write_text(kind + "\n")
    (iface / "flags").write_text("0x1003\n" if up else "0x1002\n")
    (iface / "ifindex").write_text(f"{ifindex}\n")


def run_scanner(tmp_path, captures="", captures_once_scanning="", on_scan="", polls=1):
    """Run stream-scanner.sh wlan0 until its `polls`-th sleep, then stop it
    the way systemd does: SIGTERM to every process in the group.

    Returns the result and the ip and nlscan-lp calls in order.
    """
    opt = tmp_path / "opt"
    (opt / "scanner").mkdir(parents=True)
    shutil.copy(SCANNER, opt / "scanner")
    log, scanning = tmp_path / "log", tmp_path / "scanning"
    stubs = {
        opt / "check-token.sh": "",
        opt / "to-grafana.sh": "cat > /dev/null",
        opt / "scanner" / "nlscan-lp": (
            f'echo "nlscan-lp $*" >> "{log}"; {on_scan}\ntouch "{scanning}"; exec sleep 30'
        ),
    }
    for path, body in stubs.items():
        path.write_text(f"#!/bin/bash\n{body}\n")
        path.chmod(0o755)
    # Functions win over PATH, so these replace the real commands. The poll
    # sleep (2 s) waits until nlscan-lp is running so the calls keep their order.
    defs = (
        f'ip() {{ echo "ip $*" >> "{log}"; }}; '
        f"ss() {{ printf '%s' '{captures}'; "
        f"[ -e \"{scanning}\" ] && printf '%s' '{captures_once_scanning}'; return 0; }}; "
        "sleep() { "
        f'  if [ "$1" = 2 ]; then until [ -e "{scanning}" ]; do command sleep 0.02; done; fi; '
        f"  _sleeps=$((_sleeps + 1)); [ $_sleeps -lt {polls} ] || kill -TERM 0; "
        "}; "
        "export -f ip ss sleep; "
    )
    result = subprocess.run(
        [
            "bash",
            "-c",
            defs + 'exec "$0" wlan0',
            str(opt / "scanner/stream-scanner.sh"),
        ],
        env={**os.environ, "SYS_CLASS_NET": str(tmp_path / "net")},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        start_new_session=True,
    )
    return result, log.read_text().splitlines() if log.exists() else []


@pytest.mark.parametrize("driver", ["mt76x2u", "brcmfmac"])
def test_brings_a_down_interface_up_and_restores_it(tmp_path, driver):
    net = tmp_path / "net"
    fake_interface(net, "wlan0", "phy0", driver, MANAGED, up=False)
    fake_interface(net, "wlanpi0", "phy0", driver, MONITOR, up=True, ifindex=4)

    result, calls = run_scanner(tmp_path)

    assert result.returncode == 0
    assert calls == [
        "ip link set wlan0 up",
        "nlscan-lp wlan0",
        "ip link set wlan0 down",
    ]


def test_leaves_an_up_interface_up(tmp_path):
    fake_interface(tmp_path / "net", "wlan0", "phy0", "mt76x2u", MANAGED, up=True)

    result, calls = run_scanner(tmp_path)

    assert result.returncode == 0
    assert calls == ["nlscan-lp wlan0"]


def test_leaves_a_replaced_interface_up(tmp_path):
    net = tmp_path / "net"
    fake_interface(net, "wlan0", "phy0", "mt76x2u", MANAGED, up=False)
    # wlanpi-core recreates the interface when it activates a profile on it.
    recreate = f'echo 9 > "{net}/wlan0/ifindex"'

    result, calls = run_scanner(tmp_path, on_scan=recreate)

    assert result.returncode == 0
    assert calls == ["ip link set wlan0 up", "nlscan-lp wlan0"]


def test_pauses_monitors_on_the_same_intel_radio(tmp_path):
    net = tmp_path / "net"
    fake_interface(net, "wlan0", "phy0", "iwlwifi", MANAGED, up=False)
    fake_interface(net, "wlanpi0", "phy0", "iwlwifi", MONITOR, up=True, ifindex=4)
    fake_interface(net, "wlan1", "phy1", "iwlwifi", MANAGED, up=False, ifindex=5)
    fake_interface(net, "wlanpi1", "phy1", "iwlwifi", MONITOR, up=True, ifindex=6)

    result, calls = run_scanner(tmp_path, captures="p_raw UNCONN 0 0 *:wlanpi1 *\n")

    assert result.returncode == 0
    assert calls == [
        "ip link set wlanpi0 down",
        "ip link set wlan0 up",
        "nlscan-lp wlan0",
        "ip link set wlan0 down",
        "ip link set wlanpi0 up",
    ]


def test_does_not_scan_while_a_capture_uses_the_intel_monitor(tmp_path):
    net = tmp_path / "net"
    fake_interface(net, "wlan0", "phy0", "iwlwifi", MANAGED, up=False)
    fake_interface(net, "wlanpi0", "phy0", "iwlwifi", MONITOR, up=True, ifindex=4)

    result, calls = run_scanner(tmp_path, captures="p_raw UNCONN 0 0 *:wlanpi0 *\n")

    assert result.returncode == 0
    assert "a capture is using wlanpi0" in result.stdout
    assert calls == []


def test_stops_scanning_when_a_capture_starts_on_a_paused_monitor(tmp_path):
    net = tmp_path / "net"
    fake_interface(net, "wlan0", "phy0", "iwlwifi", MANAGED, up=False)
    fake_interface(net, "wlanpi0", "phy0", "iwlwifi", MONITOR, up=True, ifindex=4)

    result, calls = run_scanner(
        tmp_path, captures_once_scanning="p_raw UNCONN 0 0 *:wlanpi0 *\n", polls=2
    )

    assert result.returncode == 0
    assert "a capture started on wlanpi0" in result.stdout
    assert calls == [
        "ip link set wlanpi0 down",
        "ip link set wlan0 up",
        "nlscan-lp wlan0",
        "ip link set wlanpi0 up",
        "ip link set wlan0 down",
    ]


def test_waits_for_a_missing_interface(tmp_path):
    (tmp_path / "net").mkdir()

    result, calls = run_scanner(tmp_path)

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["wlan0 not found"]
    assert calls == []
