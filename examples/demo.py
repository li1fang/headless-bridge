"""Run a real local HTTP service and deterministic subprocesses; no credentials."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, ProxyHandler, Request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"

    def call(path, scenario=None):
        body = None if scenario is None else json.dumps({
            "contract_id": f"demo-{scenario}", "failure_details": "Local fixture demonstration",
            "scenario": scenario}).encode()
        req = Request(base + path, data=body, headers={"Content-Type": "application/json"})
        try:
            with build_opener(ProxyHandler({})).open(req, timeout=10) as res:
                return {"http_status": res.status, "body": json.load(res)}
        except HTTPError as res:
            try:
                return {"http_status": res.code, "body": json.load(res)}
            finally:
                res.close()

    with tempfile.TemporaryDirectory(prefix="headless-bridge-demo-") as work:
        env = {**os.environ, "HB_BACKEND": "fixture", "HB_CODEX_TIMEOUT": "1.5",
               "HB_MAX_CONCURRENCY": "1", "HB_OUTPUT_LIMIT": "1024", "HB_WORKSPACE_ROOT": work}
        child = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host",
                                  "127.0.0.1", "--port", str(port), "--log-level", "error"],
                                 cwd=root, env=env, stdout=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            deadline = time.monotonic() + 20
            while True:
                try:
                    call("/health")
                    break
                except (URLError, OSError):
                    if child.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError("demo service could not start")
                    time.sleep(.05)
            records = {scenario: call("/run_codex_session", scenario)
                       for scenario in ("success", "failure", "timeout", "large_output")}
            with ThreadPoolExecutor(max_workers=1) as pool:
                slow = pool.submit(call, "/run_codex_session", "slow")
                for _ in range(100):
                    if call("/health")["body"]["active_runs"] == 1:
                        break
                    time.sleep(.01)
                started = time.monotonic()
                records["health_during_run"] = call("/health")
                records["health_during_run"]["elapsed_ms"] = round((time.monotonic() - started) * 1000)
                records["busy"] = call("/run_codex_session", "success")
                records["slow"] = slow.result()
            assert records["success"]["body"]["reason"] == "completed"
            assert records["failure"]["body"]["exit_code"] == 7
            assert records["timeout"]["http_status"] == 504
            assert records["busy"]["http_status"] == 429
            assert records["health_during_run"]["body"]["active_runs"] == 1
            assert records["large_output"]["body"]["output_truncated"]
            assert not list(Path(work).iterdir())
            report = {"kind": "real HTTP + deterministic fixture processes; no model calls",
                      "recorded_at": datetime.now(timezone.utc).isoformat(),
                      "host_os": platform.system(), "python": platform.python_version(),
                      "results": records}
            rendered = json.dumps(report, indent=2) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(rendered, encoding="utf-8")
            print(rendered)
        finally:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


if __name__ == "__main__":
    main()
