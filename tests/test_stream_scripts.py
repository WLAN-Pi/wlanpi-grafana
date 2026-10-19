import os
import subprocess
from pathlib import Path


BASH = (
    r"C:\Program Files\Git\bin\bash.exe"
    if Path(r"C:\Program Files\Git\bin\bash.exe").exists()
    else "bash"
)

SCRIPTS = Path(__file__).resolve().parent.parent / "install" / "opt" / "wlanpi-grafana"
TOKEN_FROM_GRAFANA = "glsa_" + "t" * 41


def start(script, stubs, environment, stdin=None):
    """Start a script with commands replaced by exported bash functions.

    Functions win over PATH and builtins, so `source` reads `environment`
    instead of the host's /etc/environment.
    """
    stubs = {"source": f'builtin source "{environment}"', **stubs}
    defs = "".join(
        f"{name}() {{ {body}; }}; export -f {name}; " for name, body in stubs.items()
    )
    env = {k: v for k, v in os.environ.items() if k != "GRAFANA_TOKEN"}
    return subprocess.Popen(
        [
            BASH,
            "-c",
            f'{defs}exec bash "$0" "${{@}}"',
            str(SCRIPTS / script),
            "nlscan",
        ],
        stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )


def run(script, stubs, environment, stdin=None):
    proc = start(script, stubs, environment, stdin)
    out, err = proc.communicate(stdin, timeout=30)
    return proc.returncode, out, err


def test_to_grafana_logs_each_failure_once(tmp_path):
    environment = tmp_path / "environment"
    environment.write_text("")
    codes = tmp_path / "codes"
    codes.write_text("000\n000\n200\n401\n401\n204\n000\n")
    curl = f'head -1 "{codes}"; sed -i 1d "{codes}"'

    rc, _, err = run(
        "to-grafana.sh", {"curl": curl}, environment, stdin="a\nb\nc\nd\ne\nf\ng\n"
    )

    assert rc == 0
    assert err.splitlines() == [
        "Grafana Live push to nlscan failed: HTTP 000",
        "Grafana Live push to nlscan failed: HTTP 401",
        "Grafana Live push to nlscan failed: HTTP 000",
    ]


def test_check_token_waits_for_grafana(tmp_path):
    environment = tmp_path / "environment"
    environment.write_text(f"GRAFANA_TOKEN={TOKEN_FROM_GRAFANA}\n")
    calls = tmp_path / "calls"
    # grafana-server is inactive for the first two checks.
    systemctl = f'echo "$*" >> "{calls}"; [ "$(wc -l < "{calls}")" -gt 2 ]'

    rc, out, _ = run(
        "check-token.sh", {"systemctl": systemctl, "sleep": ":"}, environment
    )

    assert rc == 0
    assert out.splitlines() == [
        "Waiting for the Grafana service to start",
        "Existing Grafana API token found in environmental variable",
    ]
    assert calls.read_text().splitlines() == ["is-active --quiet grafana-server"] * 3


def test_check_token_creates_one_token_for_streams_starting_together(tmp_path):
    environment = tmp_path / "environment"
    environment.write_text("")
    # Just enough of Grafana's API for check-token.sh. Creating a token is slow,
    # so without the lock both streams create one and the first is deleted.
    curl = (
        'case "$*" in '
        "*--write-out*) echo 200 ;; "
        "*/tokens*POST*|*POST*/tokens*) command sleep 0.5; "
        f"echo {TOKEN_FROM_GRAFANA}$BASHPID ;; "
        "esac"
    )
    jq = 'case "$*" in *serviceAccounts*) echo 2 ;; *.key*) cat ;; esac'
    stubs = {
        "systemctl": "return 0",
        "curl": curl,
        "jq": jq,
        "sudo": '"$@"',
        "tee": f'cat >> "{environment}"',
    }

    procs = [start("check-token.sh", stubs, environment) for _ in range(2)]
    outs = [proc.communicate(timeout=30)[0] for proc in procs]

    assert [proc.returncode for proc in procs] == [0, 0]
    assert environment.read_text().count("GRAFANA_TOKEN=") == 1
    assert sorted(
        "Successfully generated Grafana API token" in out for out in outs
    ) == [
        False,
        True,
    ]


def test_pihealth_reports_missing_mmcblk0_as_unknown(tmp_path):
    environment = tmp_path / "environment"
    environment.write_text("")
    stubs = {
        "cat": "case \"$1\" in /sys/*) echo 1000000 ;; *) command cat \"$@\" ;; esac",
        "vcgencmd": "case \"$1\" in measure_temp) echo \"temp=50.0'C\" ;; measure_volts) echo \"volt=1.2V\" ;; get_throttled) echo \"throttled=0x0\" ;; esac",
        "mpstat": 'echo \'{"sysstat":{"hosts":[{"statistics":[{"cpu-load":[{"idle":90}]}]}]}}\'',
        "free": "echo 'Mem: 100 50 50'",
        "df": "echo '/dev/root 100 50 50 50% /'",
        "iostat": "echo '{\"sysstat\":{}}'",
        "jq": "case \"$*\" in *kB_read*) echo null ;; *kB_wrtn*) echo null ;; *) command jq \"$@\" ;; esac",
    }

    rc, out, err = run("health/pihealth.sh", stubs, environment)

    assert rc == 0, err
    assert "sdcard_reads=-1,sdcard_writes=-1" in out
