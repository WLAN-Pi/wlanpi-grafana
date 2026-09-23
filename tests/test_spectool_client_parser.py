import io
import re

from wispy.spectool_client_parser import main

SPECTOOL_RAW = """\
Found 1 devices...
Initializing WiSPY device Wi-Spy DBx3 id 1
Configured device 1 (Wi-Spy DBx3 1)
    2400MHz-2403MHz @ 1000.00KHz, 3 samples
Wi-Spy DBx3 1: -90 -80 -70 
Wi-Spy DBx3 1: -91 -81 -71 
"""


def test_main_emits_influx_line_per_sweep(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(SPECTOOL_RAW))
    main()
    lines = capsys.readouterr().out.splitlines()
    assert [re.sub(r" \d{19}$", " <ts>", line) for line in lines] == [
        "wispy2 2400.0=-90,2401.0=-80,2402.0=-70 <ts>",
        "wispy2 2400.0=-91,2401.0=-81,2402.0=-71 <ts>",
    ]
