import asyncio
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest

import httpx
import uvicorn

from core.config import Settings
from core.runner import Runner
from core.server import create_app


@contextmanager
def serving(settings):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(settings), log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(.01)
    if not server.started:
        server.should_exit = True
        sock.close()
        raise RuntimeError("test server did not start")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        if thread.is_alive():
            raise RuntimeError("test server did not stop")


def is_alive(pid):
    if os.name == "nt":
        import ctypes as c
        kernel = c.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [c.c_ulong, c.c_int, c.c_ulong]
        kernel.OpenProcess.restype = c.c_void_p
        kernel.WaitForSingleObject.argtypes = [c.c_void_p, c.c_ulong]
        kernel.CloseHandle.argtypes = [c.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle(handle)
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists() and stat.read_text().split(") ", 1)[1].startswith("Z"):
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings(workspace_root=Path(self.temp.name), codex_timeout=1.5,
                                 output_limit=512, backend="fixture", max_concurrency=1)
        self.context = serving(self.settings)
        self.url = self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])
        self.temp.cleanup()

    def request(self, scenario="success"):
        return {"contract_id": "test-contract", "failure_details": "fixture only",
                "scenario": scenario}

    async def post(self, scenario):
        async with httpx.AsyncClient(base_url=self.url, timeout=10, trust_env=False) as client:
            return await client.post("/run_codex_session", json=self.request(scenario))

    async def test_success_and_nonzero_preserve_identity(self):
        for scenario, reason, code in [("success", "completed", 0), ("failure", "nonzero_exit", 7)]:
            response = await self.post(scenario)
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertEqual(result["reason"], reason)
            self.assertEqual(result["exit_code"], code)
            self.assertEqual(result["meta"], {"contract_id": "test-contract", "backend": "fixture", "fixture": True})
            self.assertTrue(result["run_id"])
            self.assertGreater(result["duration_ms"], 0)

    async def test_timeout_is_explicit(self):
        response = await self.post("timeout")
        self.assertEqual(response.status_code, 504)
        result = response.json()
        self.assertEqual(result["reason"], "timeout")
        self.assertIsNone(result["exit_code"])
        self.assertEqual(result["meta"]["contract_id"], "test-contract")
        self.assertIn("waiting", result["output"])

    async def test_health_remains_live_and_capacity_is_enforced(self):
        async with httpx.AsyncClient(base_url=self.url, timeout=10, trust_env=False) as client:
            slow = asyncio.create_task(client.post("/run_codex_session", json=self.request("slow")))
            for _ in range(50):
                health = await client.get("/health")
                if health.json()["active_runs"] == 1:
                    break
                await asyncio.sleep(.01)
            self.assertEqual(health.json()["active_runs"], 1)
            started = time.monotonic()
            health = await client.get("/health?deep=true")
            self.assertLess(time.monotonic() - started, .75)
            self.assertEqual(health.status_code, 200)
            self.assertFalse(slow.done())
            busy = await client.post("/run_codex_session", json=self.request())
            self.assertEqual(busy.status_code, 429)
            self.assertEqual(busy.json()["reason"], "busy")
            self.assertEqual(busy.json()["meta"]["contract_id"], "test-contract")
            self.assertEqual((await slow).json()["reason"], "completed")
            self.assertEqual((await client.get("/health")).json()["active_runs"], 0)

    async def test_both_output_streams_are_bounded_and_drained(self):
        result = (await self.post("large_output")).json()
        self.assertEqual(result["reason"], "completed")
        self.assertTrue(result["output_truncated"])
        self.assertLessEqual(len(result["output"].encode()), 512)
        self.assertLessEqual(len(result["logs"].encode()), 512)

    async def test_descendants_are_removed_on_timeout_and_normal_exit(self):
        for scenario in ("child", "orphan"):
            result = (await self.post(scenario)).json()
            pid = json.loads(result["output"].splitlines()[0])["child_pid"]
            self.assertEqual(result["reason"], "timeout" if scenario == "child" else "completed")
            deadline = time.monotonic() + 2
            while is_alive(pid) and time.monotonic() < deadline:
                await asyncio.sleep(.02)
            self.assertFalse(is_alive(pid), f"fixture child {pid} survived")

    async def test_request_cannot_choose_executable(self):
        async with httpx.AsyncClient(base_url=self.url, trust_env=False) as client:
            response = await client.post("/run_codex_session", json={**self.request(), "command": "arbitrary"})
            self.assertEqual(response.status_code, 422)


class ConfigurationTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_real_executor_and_health(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(backend="codex", codex_binary="headless-bridge-nonexistent-executable",
                                auth_file=Path(directory) / "absent", workspace_root=Path(directory))
            with serving(settings) as url:
                async with httpx.AsyncClient(base_url=url, trust_env=False) as client:
                    self.assertEqual((await client.get("/health?deep=1")).status_code, 503)
                    response = await client.post("/run_codex_session", json={
                        "contract_id": "missing", "failure_details": "fixture"})
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json()["reason"], "executor_unavailable")
                    rejected = await client.post("/run_codex_session", json={
                        "contract_id": "missing", "failure_details": "fixture", "scenario": "failure"})
                    self.assertEqual(rejected.status_code, 422)

    async def test_cancelled_caller_does_not_release_running_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = Runner(Settings(workspace_root=Path(directory), backend="fixture", codex_timeout=2))
            task = asyncio.create_task(runner.run("fixture", "slow", "cancel", "contract"))
            await asyncio.sleep(.1)
            task.cancel()
            await asyncio.sleep(.02)
            self.assertEqual(runner.active, 1)
            self.assertEqual((await runner.run("fixture", "success", "other", "contract"))["reason"], "busy")
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(runner.active, 0)


if __name__ == "__main__":
    unittest.main()
