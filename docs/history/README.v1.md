> Historical README; see [current overview](../../README.md).

# headless-bridge

**An HTTP adapter for a Codex CLI workflow in a container environment.**

The repository contains a FastAPI service, a Codex adapter, and Kubernetes deployment examples. A request supplies a repository URL and failure description; the adapter builds a prompt, invokes the CLI, and returns its output with a run identifier.

## Read the implementation

- [Request handling and prompt construction](https://github.com/li1fang/headless-bridge/blob/ca8d25bd3e50fd9ce6fc9aafa45e5640178ef7ba/adapters/codex/handler.py)
- [Health endpoints](https://github.com/li1fang/headless-bridge/blob/ca8d25bd3e50fd9ce6fc9aafa45e5640178ef7ba/core/server.py)
- [Configuration](https://github.com/li1fang/headless-bridge/blob/ca8d25bd3e50fd9ce6fc9aafa45e5640178ef7ba/core/config.py)
- [Container image](https://github.com/li1fang/headless-bridge/blob/ca8d25bd3e50fd9ce6fc9aafa45e5640178ef7ba/Dockerfile)
- [Kubernetes example](https://github.com/li1fang/headless-bridge/blob/ca8d25bd3e50fd9ce6fc9aafa45e5640178ef7ba/k8s/deployment.yaml)

The current adapter is specific to Codex. Other CLI adapters are not implemented here. This document describes the checked-in code, not a newly verified deployment or compatibility guarantee for current upstream CLI releases.

## HTTP interface

`POST /run_codex_session` accepts these required string fields:

```json
{
  "contract_id": "example-task",
  "repo_url": "https://example.com/repository.git",
  "failure_details": "Describe the observed failure and expected behavior.",
  "ak_url": "https://example.com/tool",
  "ak_hash": "REPLACE_WITH_THE_DOWNLOADED_FILE_SHA256_HEX"
}
```

These are illustrative placeholders, not runnable resources. Use a real digest in hexadecimal form: the generated prompt places `ak_hash` directly into a `sha256sum -c` input line. Do not prefix it with `sha256:`.

The handler passes download, checksum and execution instructions to the CLI through a prompt. It does **not** independently download or enforce the checksum in the HTTP service. A response includes `status`, `run_id`, `logs`, `output`, and `meta.contract_id`. `success` means the CLI process exited with code zero; it is not independent acceptance of a repaired project.

`GET /health` returns basic process health. `GET /health?deep=1` also checks whether the configured auth file exists, returning 503 if it is absent. It does not validate credentials with the upstream service or prove they have not expired.

## Configuration and deployment scope

| Environment variable | Default |
| --- | --- |
| `HB_SERVICE_NAME` | `headless-bridge` |
| `HB_AUTH_FILE` | `/root/.codex/auth.json` |
| `HB_CODEX_TIMEOUT` | `600` seconds |

The Dockerfile launches Uvicorn on port 8000 and installs an unpinned Codex CLI. The Kubernetes example references a maintainer-specific image and an existing `codex-auth` Secret, mounting its `auth.json` key read-only. The previously documented `scripts/generate_auth_secret.sh` is not present; there is no one-command credential setup supplied by this repository.

Review the deployment example before adapting it. It uses a privileged container and a LoadBalancer Service. The adapter invokes Codex with `--dangerously-bypass-approvals-and-sandbox`; the HTTP routes contain no application-level authentication or authorization. These settings do not establish confinement to a namespace or make the endpoint suitable for untrusted callers. Actual access controls, workload isolation and credential lifecycle require separate operator configuration and verification.

No credentials should be committed or embedded in image layers. This documentation update does not change code, privileges, network exposure, or authentication behavior, and does not deploy the service.

## History and maintenance

Earlier README revisions are retained in Git history. This revision replaces aspirational claims with the behavior visible in the current source. Report documentation discrepancies through [repository issues](https://github.com/li1fang/headless-bridge/issues).
