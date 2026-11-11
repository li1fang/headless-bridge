import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from core.process_tree import ProcessTree

ROOT = Path(__file__).resolve().parents[1]


class Capture:
    def __init__(self, pipe, limit):
        self.pipe, self.limit = pipe, limit
        self.data, self.total = bytearray(), 0
        self.thread = threading.Thread(target=self.read, daemon=True)

    def read(self):
        try:
            while chunk := self.pipe.read(4096):
                self.total += len(chunk)
                self.data.extend(chunk[:max(0, self.limit - len(self.data))])
        finally:
            self.pipe.close()


class Runner:
    def __init__(self, settings):
        self.settings, self.active = settings, 0
        self.tasks = set()

    def response(self, run_id, contract_id, reason, **extra):
        return {"status": "success" if reason == "completed" else "error",
                "reason": reason, "run_id": run_id, "logs": "", "output": "",
                "exit_code": None, "duration_ms": 0, "output_truncated": False,
                "meta": {"contract_id": contract_id, "backend": self.settings.backend,
                         "fixture": self.settings.backend == "fixture"}, **extra}

    async def run(self, prompt, scenario, run_id, contract_id):
        # Admission is atomic between awaits on this application's event loop.
        if self.active >= self.settings.max_concurrency:
            return self.response(run_id, contract_id, "busy")
        self.active += 1
        task = asyncio.create_task(asyncio.to_thread(
            self.execute, prompt, scenario, run_id, contract_id))
        self.tasks.add(task)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # A disconnected/cancelled caller must not free a still-running slot.
            await task
            raise
        finally:
            self.tasks.discard(task)
            self.active -= 1

    async def drain(self):
        if self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)

    def execute(self, prompt, scenario, run_id, contract_id):
        start = time.monotonic()
        result = self.response(run_id, contract_id, "execution_error")
        if self.settings.backend == "fixture":
            command = [sys.executable, str(ROOT / "examples/fixture_cli.py"), scenario]
        else:
            binary = shutil.which(self.settings.codex_binary)
            if not binary:
                return self.response(run_id, contract_id, "executor_unavailable")
            command = [binary, "exec", "--json", "--ephemeral", "--ignore-user-config", "--skip-git-repo-check",
                       "--sandbox", "read-only", "-"]
        process = tree = None
        captures = []
        try:
            self.settings.workspace_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=run_id + "-",
                                             dir=self.settings.workspace_root.resolve()) as cwd:
                process = subprocess.Popen(
                    [sys.executable, str(ROOT / "core/worker.py")],
                    cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, start_new_session=os.name != "nt",
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                try:
                    # The worker waits for input, so no target can start before assignment.
                    tree = ProcessTree(process)
                    captures = [Capture(process.stdout, self.settings.output_limit),
                                Capture(process.stderr, self.settings.output_limit)]
                    for capture in captures:
                        capture.thread.start()
                    process.stdin.write(json.dumps({"command": command, "prompt": prompt}).encode())
                    process.stdin.close()
                    try:
                        process.wait(timeout=self.settings.codex_timeout)
                        result["reason"] = "completed" if process.returncode == 0 else "nonzero_exit"
                    except subprocess.TimeoutExpired:
                        result["reason"] = "timeout"
                finally:
                    if tree:
                        tree.close()
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=5)
                    if process.stdin and not process.stdin.closed:
                        process.stdin.close()
                    for capture in captures:
                        capture.thread.join(timeout=5)
                    if not captures:
                        process.stdout.close()
                        process.stderr.close()
                result["exit_code"] = None if result["reason"] == "timeout" else process.returncode
                if any(c.thread.is_alive() for c in captures):
                    result["reason"] = "execution_error"
                if captures:
                    result["output"], result["logs"] = [
                        c.data.decode("utf-8", errors="replace") for c in captures]
                    result["output_truncated"] = any(c.total > c.limit for c in captures)
                result["status"] = "success" if result["reason"] == "completed" else "error"
        except OSError:
            result.update(status="error", reason="execution_error",
                          logs="Local executor setup or cleanup failed; inspect server configuration.")
        finally:
            result["duration_ms"] = round((time.monotonic() - start) * 1000)
        return result
