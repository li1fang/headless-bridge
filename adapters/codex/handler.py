import logging
import subprocess
from typing import Dict, Optional
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from core.config import get_settings

router = APIRouter(tags=["codex"])
logger = logging.getLogger("codex-bridge")


class FixRequest(BaseModel):
    contract_id: str
    repo_url: str
    failure_details: str
    ak_hash: str
    ak_url: str


class CodexResponse(BaseModel):
    status: str
    run_id: str
    logs: Optional[str] = None
    output: Optional[str] = None
    meta: Optional[Dict[str, str]] = None


def build_prompt(request: FixRequest, run_id: str) -> str:
    return f"""
    You are an engineer.
    REPO: {request.repo_url}
    ERROR: {request.failure_details}
    RUN_ID: {run_id}

    PLAN:
    1. echo "--- STARTING GKE EXECUTION ---"
    2. echo "Current User: g1"
    3. echo "Current Dir: /home/g1/pa-bridge"
    4. Download: curl -L -o ak {request.ak_url} && chmod +x ak
    5. Verify SHA256: echo "{request.ak_hash} ak" | sha256sum -c - || exit 1
    6. Run: ./ak tck
    """


@router.post("/run_codex_session", response_model=CodexResponse)
async def run_session(request: FixRequest):
    settings = get_settings()
    run_id = str(uuid4())
    logger.info("🚀 Task: %s run_id=%s", request.contract_id, run_id)

    prompt = build_prompt(request, run_id)

    cmd = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        prompt,
    ]

    try:
        logger.info("⏳ Calling OpenAI Cloud (YOLO Mode)...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.codex_timeout,
        )
        status = "success" if result.returncode == 0 else "error"
        logger.info("✅ Completed run_id=%s status=%s", run_id, status)
        return CodexResponse(
            status=status,
            run_id=run_id,
            logs=result.stderr,
            output=result.stdout,
            meta={"contract_id": request.contract_id},
        )
    except Exception as exc:  # pragma: no cover - defensive path
        logger.exception("Codex session failed run_id=%s", run_id)
        return CodexResponse(status="error", run_id=run_id, logs=str(exc))
