import logging
import subprocess
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


def build_prompt(request: FixRequest) -> str:
    return f"""
    You are an engineer.
    REPO: {request.repo_url}
    ERROR: {request.failure_details}

    PLAN:
    1. echo "--- STARTING GKE EXECUTION ---"
    2. echo "Current User: g1"
    3. echo "Current Dir: /home/g1/pa-bridge"
    4. Download: curl -L -o ak {request.ak_url} && chmod +x ak
    5. Run: ./ak tck
    """


@router.post("/run_codex_session")
async def run_session(request: FixRequest):
    settings = get_settings()
    logger.info("🚀 Task: %s", request.contract_id)

    prompt = build_prompt(request)

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
        return {"status": status, "logs": result.stderr, "output": result.stdout}
    except Exception as exc:  # pragma: no cover - defensive path
        logger.exception("Codex session failed")
        return {"status": "error", "message": str(exc)}
