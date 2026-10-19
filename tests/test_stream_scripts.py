import os
import subprocess
from pathlib import Path

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
            "bash",
            "-c",
            f'{defs}exec bash "$0" "${{@}}"',
            str(SCRIPTS / script),
            "scanner",
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
        "Grafana Live push to scanner failed: HTTP 000",
        "Grafana Live push to scanner failed: HTTP 401",
        "Grafana Live push to scanner failed: HTTP 000",
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


def internet_sample(tmp_path, ping, dig, speedtest):
    environment = tmp_path / "environment"
    environment.write_text("")
    stubs = {
        "ip": "echo default via 192.0.2.1 dev eth0",
        "hostname": "echo wlanpi-test",
        "ping": ping,
        "dig": dig,
        "librespeed-cli": speedtest,
    }
    rc, out, _ = run("internet/internet.sh", stubs, environment)
    assert rc == 0
    return dict(field.split("=") for field in out.split()[1].split(","))


def test_internet_pings_google_over_ipv4(tmp_path):
    # IPv6 is broken: only an IPv4 ping gets a reply.
    ping = (
        'case "$*" in *-4*|*192.0.2.1*) '
        "echo rtt min/avg/max/mdev = 1/14.8/1/0 ms ;; *) return 1 ;; esac"
    )

    sample = internet_sample(
        tmp_path,
        ping,
        dig="echo ';; Query time: 8 msec'",
        speedtest='echo \'[{"ping": 19.4, "download": 862.8, "upload": 586.5}]\'',
    )

    assert sample["rtt_google"] == "14.8"
    assert sample["rtt_gateway"] == "14.8"
    assert sample["download"] == "862.8"


def test_internet_reports_failed_measurements_as_minus_one(tmp_path):
    sample = internet_sample(
        tmp_path, ping="return 1", dig="return 1", speedtest="echo '[]'"
    )

    assert sample == {
        "rtt_speedtest": "-1",
        "rtt_google": "-1",
        "rtt_gateway": "-1",
        "download": "-1",
        "upload": "-1",
        "dns1_res_time_google": "-1",
        "dns1_res_time_apple": "-1",
        "dns1_res_time_aws": "-1",
        "internet_status": "0",
        "speedtest_tool": "0",
    }
