# A short path from request to evidence

[← Overview](../README.md) · [Recorded local demo](demo-results.windows.json) · [Tests](../tests/test_service.py)

## Why this bridge exists

An HTTP caller needs more than a CLI's final text: it needs to know whether execution started, whether capacity was available, how the process ended, and which request a result belongs to. The bridge adds those service responsibilities around one execution path.

Codex already provides non-interactive execution and JSONL events. The real backend reuses those capabilities instead of building another agent harness. The fixture backend makes the service behavior independently inspectable.

## One request, four decisions

1. **Validate.** The API accepts a bounded request body schema. Callers cannot provide an executable or switch the backend. Backend and capacity are operator configuration.
2. **Admit.** An event-loop-local counter limits active executions; a full service returns `429 busy` immediately. Use one Uvicorn worker so the configured limit describes the whole instance.
3. **Supervise.** A worker thread creates an empty per-run directory, launches an internal Python worker, establishes process lifetime management, and only then releases the target command through stdin. The HTTP event loop remains free.
4. **Report.** Stdout and stderr are drained concurrently while only bounded prefixes are kept. The response separates completion, nonzero exit, timeout, busy and local startup failure. The workspace is removed after the process tree is closed.

Cancellation of the waiting request does not immediately release an occupied slot: the runner waits for its bounded execution to finish. Application shutdown drains admitted work. There is no persistent run queue; a server restart does not resume work.

## Process cleanup, precisely

On Windows, a Job Object has `KILL_ON_JOB_CLOSE` enabled. The initial worker blocks on stdin until it has joined that job, preventing the target from spawning descendants before supervision. On POSIX, the worker starts a new session and cleanup signals its process group.

Tests cover a sleeping descendant on timeout and a descendant left behind after a normal parent exit. This manages ordinary process lifetimes; it does not confine hostile programs. POSIX processes that deliberately leave the process group are outside this cleanup contract.

The deadline applies to execution waiting after startup; platform process creation and cleanup have their own overhead. Output is capped per stream in bytes and decoded as UTF-8 with replacement. Truncated JSONL can end mid-event; check `output_truncated` before consuming it as a complete event stream.

## API example

```json
{
  "contract_id": "demo-review",
  "failure_details": "Inspect the supplied issue context.",
  "scenario": "success"
}
```

Send this to `POST /run_codex_session`. In fixture mode, `scenario` may be `success`, `failure`, `slow`, `timeout`, `large_output`, `child` or `orphan`; the last two exercise descendant cleanup. These names select fixed demonstration behaviors, not arbitrary commands. Real Codex mode rejects fixture-only scenarios.

`repo_url`, `ak_url` and `ak_hash` are optional context fields retained from the older contract. They are JSON-quoted into the analysis prompt; the service does not download, verify or execute them. Existing clients depending on the previous download-and-run prompt must migrate explicitly.

Execution failures use the documented result envelope. Invalid request schemas use FastAPI's standard HTTP 422 validation response. `exit_code` is null for timeout or when execution has not started. Nonzero process exits retain HTTP 200 for compatibility with the earlier response envelope; inspect `status` and `reason`.

## Run modes and configuration

Configuration uses `HB_` environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `HB_BACKEND` | `fixture` | `fixture` or explicit `codex` |
| `HB_CODEX_TIMEOUT` | `10` | Execution wait limit in seconds, 0.1–600 |
| `HB_MAX_CONCURRENCY` | `1` | Active runs per server worker, 1–4 |
| `HB_OUTPUT_LIMIT` | `16384` | Captured bytes per stream, 256–1048576 |
| `HB_WORKSPACE_ROOT` | `.runs` | Parent for temporary, per-run empty directories |
| `HB_CODEX_BINARY` | `codex` | Operator-controlled CLI executable |
| `HB_AUTH_FILE` | `~/.codex/auth.json` | Local presence check only; does not configure CLI authentication |

`GET /health` reports process health, backend and active capacity. `GET /health?deep=1` in real mode additionally checks executable availability and the configured auth-file path. That local presence check does not prove a valid account and may be unsuitable for a CLI configured with another authentication method. Fixture health requires no credentials.

For real mode, use an already authenticated CLI. Example in PowerShell:

```powershell
$env:HB_BACKEND = "codex"
$env:HB_CODEX_TIMEOUT = "60"
python main.py
```

The bridge uses `codex exec --json --ephemeral --ignore-user-config --skip-git-repo-check --sandbox read-only -`, passing the prompt through stdin. It does not copy credentials or select a different model. User configuration is ignored for this invocation; existing CLI authentication remains managed by Codex. It creates an empty run workspace, not a checkout of `repo_url`.

A Windows smoke check with **Codex CLI 0.167.0-alpha.3.2** completed a fixed-text reply through this runner. It produced the exact expected assistant reply and no tool events. See the [sanitized compatibility receipt](real-cli-smoke.windows.json). This confirms that invocation on the recorded host, not compatibility with every release or automatic repair capability.

## Evidence you can reproduce

The [Windows demo record](demo-results.windows.json) was generated by `python -m examples.demo`: actual loopback HTTP calls and actual deterministic child processes, no model calls. It records completed, nonzero, timeout, truncated-output, busy and concurrent-health behavior. Timings are observations from that run, not throughput claims.

The [test suite](../tests/test_service.py) additionally checks missing executables, descendant cleanup, cancellation accounting, and rejection of request-selected commands. CI runs the same suite and demo on Windows and Linux; the Actions run is the authority for each platform's result.

## Container example

The current Dockerfile is fixture-only and runs as an unprivileged user. It does not install Codex or mount account credentials. Bind its published port to localhost:

```sh
docker build -t headless-bridge-fixture .
docker run --rm -p 127.0.0.1:8000:8000 headless-bridge-fixture
```

The repository documents this build path; Docker image execution has not been part of the recorded Windows acceptance. Earlier privileged Kubernetes examples are preserved as historical material, not current deployment guidance.

## References

- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [FastAPI synchronous and asynchronous functions](https://fastapi.tiangolo.com/async/#path-operation-functions)
- [Python subprocess](https://docs.python.org/3/library/subprocess.html)
