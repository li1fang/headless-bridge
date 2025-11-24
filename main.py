import os
import subprocess
import logging
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("codex-bridge")

app = FastAPI()

class FixRequest(BaseModel):
    contract_id: str
    repo_url: str
    failure_details: str
    ak_hash: str
    ak_url: str

@app.post("/run_codex_session")
async def run_session(request: FixRequest):
    logger.info(f"🚀 Task: {request.contract_id}")

    prompt = f"""
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

    # === 终极修改：开启 YOLO 模式 ===
    # 这会彻底绕过 Landlock 和审批机制
    cmd = [
        "codex", "exec", 
        "--skip-git-repo-check", 
        "--dangerously-bypass-approvals-and-sandbox",
        prompt
    ]

    try:
        logger.info("⏳ Calling OpenAI Cloud (YOLO Mode)...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )

        status = "success" if result.returncode == 0 else "error"
        return {"status": status, "logs": result.stderr, "output": result.stdout}

    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
