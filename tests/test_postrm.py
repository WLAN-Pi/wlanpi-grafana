import os
import subprocess
from pathlib import Path

import pytest

POSTRM = Path(__file__).resolve().parent.parent / "debian" / "postrm"
OUR_CONF = "/etc/wlanpi-grafana/grafana.ini"


def run_postrm(root, action):
    subprocess.run(
        ["sh", str(POSTRM), action],
        env={**os.environ, "DPKG_ROOT": str(root)},
        check=True,
    )


@pytest.fixture()
def etc(tmp_path):
    path = tmp_path / "etc" / "grafana"
    path.mkdir(parents=True)
    return path


def test_purge_restores_newest_backup(tmp_path, etc):
    (etc / "grafana.ini").symlink_to(OUR_CONF)
    (etc / "grafana.ini.1791492169").write_text("older")
    (etc / "grafana.ini.1791493359").write_text("newer")
    run_postrm(tmp_path, "purge")
    conf = etc / "grafana.ini"
    assert not conf.is_symlink()
    assert conf.read_text() == "newer"
    assert (etc / "grafana.ini.1791492169").read_text() == "older"
    assert not (etc / "grafana.ini.1791493359").exists()


def test_purge_without_backup_removes_link(tmp_path, etc):
    (etc / "grafana.ini").symlink_to(OUR_CONF)
    run_postrm(tmp_path, "purge")
    assert not os.path.lexists(etc / "grafana.ini")


@pytest.mark.parametrize("action", ["remove", "upgrade"])
def test_only_purge_touches_the_link(tmp_path, etc, action):
    (etc / "grafana.ini").symlink_to(OUR_CONF)
    (etc / "grafana.ini.1791492169").write_text("backup")
    run_postrm(tmp_path, action)
    assert os.readlink(etc / "grafana.ini") == OUR_CONF


def test_purge_leaves_other_configs(tmp_path, etc):
    (etc / "grafana.ini").symlink_to("/srv/my-grafana.ini")
    (etc / "grafana.ini.1791492169").write_text("backup")
    run_postrm(tmp_path, "purge")
    assert os.readlink(etc / "grafana.ini") == "/srv/my-grafana.ini"
    assert (etc / "grafana.ini.1791492169").exists()
