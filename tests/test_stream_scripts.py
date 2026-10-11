import os
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "install" / "opt" / "wlanpi-grafana"


def run(script, stubs, stdin="", env=None):
    """Run a script with commands replaced by exported bash functions.

    Functions win over PATH, and the scripts source /etc/environment, which can
    reset PATH on the host running the tests.
    """
    defs = "".join(
        f"{name}() {{ {body}; }}; export -f {name}; " for name, body in stubs.items()
    )
    return subprocess.run(
        [
            "bash",
            "-c",
            f'{defs}exec bash "$0" "${{@}}"',
            str(SCRIPTS / script),
            "nlscan",
        ],
        input=stdin,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def test_to_grafana_logs_each_failure_once(tmp_path):
    codes = tmp_path / "codes"
    codes.write_text("000\n000\n200\n401\n401\n204\n000\n")
    curl = f'head -1 "{codes}"; sed -i 1d "{codes}"'

    result = run("to-grafana.sh", {"curl": curl}, stdin="a\nb\nc\nd\ne\nf\ng\n")

    assert result.returncode == 0
    assert result.stderr.splitlines() == [
        "Grafana Live push to nlscan failed: HTTP 000",
        "Grafana Live push to nlscan failed: HTTP 401",
        "Grafana Live push to nlscan failed: HTTP 000",
    ]


def test_check_token_waits_for_grafana(tmp_path):
    calls = tmp_path / "calls"
    # grafana-server is inactive for the first two checks.
    systemctl = f'echo >> "{calls}"; [ "$(wc -l < "{calls}")" -gt 2 ]'

    result = run(
        "check-token.sh",
        {"systemctl": systemctl, "sleep": ":"},
        env={"GRAFANA_TOKEN": "x" * 40},
    )

    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "Waiting for the Grafana service to start",
        "Existing Grafana API token found in environmental variable",
    ]
    assert len(calls.read_text().splitlines()) == 3
