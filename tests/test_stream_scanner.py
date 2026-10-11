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


def fake_interface(net, name, phy, driver, kind, up):
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


def run_scanner(tmp_path, captures=""):
    """Run one pass of the scan loop; the sleep after it stops the script."""
    opt = tmp_path / "opt"
    (opt / "scanner").mkdir(parents=True)
    shutil.copy(SCANNER, opt / "scanner")
    log = tmp_path / "log"
    stubs = {
        opt / "check-token.sh": "",
        opt / "to-grafana.sh": "cat > /dev/null",
        opt / "scanner" / "nlscan-lp": f'echo "nlscan-lp $*" >> "{log}"',
    }
    for path, body in stubs.items():
        path.write_text(f"#!/bin/bash\n{body}\n")
        path.chmod(0o755)
    # Functions win over PATH, so these replace the real commands.
    defs = (
        f'ip() {{ echo "ip $*" >> "{log}"; }}; '
        f"ss() {{ printf '%s' '{captures}'; }}; "
        "sleep() { kill -TERM $$; }; "
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
    )
    return result, log.read_text().splitlines() if log.exists() else []


@pytest.mark.parametrize("driver", ["mt76x2u", "brcmfmac"])
def test_brings_a_down_interface_up_and_restores_it(tmp_path, driver):
    net = tmp_path / "net"
    fake_interface(net, "wlan0", "phy0", driver, MANAGED, up=False)
    fake_interface(net, "wlanpi0", "phy0", driver, MONITOR, up=True)

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


def test_pauses_monitors_on_the_same_intel_radio(tmp_path):
    net = tmp_path / "net"
    fake_interface(net, "wlan0", "phy0", "iwlwifi", MANAGED, up=False)
    fake_interface(net, "wlanpi0", "phy0", "iwlwifi", MONITOR, up=True)
    fake_interface(net, "wlan1", "phy1", "iwlwifi", MANAGED, up=False)
    fake_interface(net, "wlanpi1", "phy1", "iwlwifi", MONITOR, up=True)

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
    fake_interface(net, "wlanpi0", "phy0", "iwlwifi", MONITOR, up=True)

    result, calls = run_scanner(tmp_path, captures="p_raw UNCONN 0 0 *:wlanpi0 *\n")

    assert result.returncode == 0
    assert "a capture is using wlanpi0" in result.stdout
    assert calls == []


def test_waits_for_a_missing_interface(tmp_path):
    (tmp_path / "net").mkdir()

    result, calls = run_scanner(tmp_path)

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["wlan0 not found"]
    assert calls == []
