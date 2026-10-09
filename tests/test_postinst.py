import os
import subprocess
from pathlib import Path

import pytest

POSTINST = Path(__file__).resolve().parent.parent / "debian" / "postinst"
# Every command postinst uses to change the system, so a run can't touch the host.
STUBS = ("wget", "curl", "gpg", "sudo", "tee", "ln", "mv", "chgrp", "chmod", "chown")


def grafana_running():
    try:
        cmd = ["systemctl", "is-active", "--quiet", "grafana-server.service"]
        return subprocess.run(cmd, check=False).returncode == 0
    except FileNotFoundError:
        return False


def run_postinst(tmp_path, *args):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls"
    for name in (*STUBS, "grafana"):
        stub = bin_dir / name
        stub.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n')
        stub.chmod(0o755)
    result = subprocess.run(
        ["bash", str(POSTINST), *args],
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        check=False,
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return result, calls


@pytest.mark.parametrize(
    "args",
    [
        ("triggered", "/usr/bin/python3"),
        ("triggered", "dh-virtualenv-interpreter-update"),
        ("abort-upgrade", "1.1.3"),
        ("abort-remove",),
        ("abort-deconfigure", "in-favour", "x", "1"),
    ],
)
def test_only_configure_sets_up(tmp_path, args):
    result, calls = run_postinst(tmp_path, *args)
    assert result.returncode == 0
    assert result.stdout == ""
    assert calls == []


# configure stops and restarts grafana-server through /bin/systemctl.
@pytest.mark.skipif(grafana_running(), reason="would restart the host's Grafana")
def test_configure_installs_plugins(tmp_path):
    result, calls = run_postinst(tmp_path, "configure", "1.1.3")
    assert "Installing Grafana plugins" in result.stdout
    assert "grafana cli plugins install ae3e-plotly-panel" in calls
    assert "grafana cli plugins install innius-video-panel" in calls
