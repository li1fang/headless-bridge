"""Internal process gate: start the child only after supervision is established."""
import json
import subprocess
import sys

if __name__ == "__main__":
    payload = json.load(sys.stdin)
    try:
        completed = subprocess.run(payload["command"], input=payload["prompt"].encode("utf-8"))
        sys.exit(completed.returncode if completed.returncode >= 0 else 1)
    except OSError:
        print("executor could not be started", file=sys.stderr)
        sys.exit(127)
