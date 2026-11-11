"""Deterministic local process fixture. No model, credential, or network access."""
import json
import os
import subprocess
import sys
import time

scenario = sys.argv[1]
sys.stdin.read()
if scenario in {"child", "orphan"}:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    print(json.dumps({"fixture": True, "child_pid": child.pid}), flush=True)
    if scenario == "child":
        time.sleep(60)
elif scenario == "timeout":
    print(json.dumps({"fixture": True, "event": "waiting"}), flush=True)
    time.sleep(60)
elif scenario == "slow":
    time.sleep(1)
elif scenario == "large_output":
    sys.stdout.write("X" * 100000)
    sys.stderr.write("Y" * 100000)
if scenario == "failure":
    print("fixture: deliberate nonzero exit", file=sys.stderr)
    sys.exit(7)
print(json.dumps({"fixture": True, "scenario": scenario, "result": "completed"}), flush=True)
