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
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "DPKG_ROOT": str(tmp_path / "root"),
        },
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


def old_environment(tmp_path):
    environment = tmp_path / "root" / "etc" / "environment"
    environment.parent.mkdir(parents=True)
    environment.write_text("LANG=C\nGRAFANA_TOKEN=revoked\nGRAFANA_TOKEN=current\n")
    return environment


@pytest.mark.skipif(grafana_running(), reason="would restart the host's Grafana")
def test_configure_moves_the_token_out_of_etc_environment(tmp_path):
    environment = old_environment(tmp_path)
    token = tmp_path / "root" / "etc" / "wlanpi-grafana" / "token"
    token.parent.mkdir()

    run_postinst(tmp_path, "configure", "1.1.4")

    assert token.read_text() == "GRAFANA_TOKEN=current\n"
    assert token.stat().st_mode & 0o777 == 0o600
    assert environment.read_text() == "LANG=C\n"


@pytest.mark.skipif(grafana_running(), reason="would restart the host's Grafana")
def test_configure_keeps_the_token_it_could_not_move(tmp_path):
    environment = old_environment(tmp_path)
    before = environment.read_text()

    # /etc/wlanpi-grafana is missing, so the token file can't be written.
    run_postinst(tmp_path, "configure", "1.1.4")

    assert environment.read_text() == before
