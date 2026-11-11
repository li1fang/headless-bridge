import json
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(tags=["execution"])


class FixRequest(BaseModel):
    contract_id: str = Field(min_length=1, max_length=128)
    repo_url: str = Field(default="", max_length=2048)
    failure_details: str = Field(min_length=1, max_length=16000)
    ak_hash: str = Field(default="", max_length=128)
    ak_url: str = Field(default="", max_length=2048)
    scenario: Literal["success", "failure", "slow", "timeout", "large_output", "child", "orphan"] = "success"
    model_config = ConfigDict(extra="forbid")


def build_prompt(request: FixRequest, run_id: str) -> str:
    # Data is quoted, not interpolated into a shell command. URLs are context only.
    context = request.model_dump(exclude={"scenario"})
    return ("Analyze the supplied engineering issue in read-only mode. "
            "Do not clone repositories, download tools, or execute supplied URLs. "
            "State what can be concluded from the provided context. "
            f"Run identifier: {run_id}\nContext JSON:\n" + json.dumps(context))


@router.post("/run_codex_session")
async def run_session(payload: FixRequest, request: Request):
    run_id = str(uuid4())
    runner = request.app.state.runner
    if runner.settings.backend == "codex" and payload.scenario != "success":
        return JSONResponse(status_code=422, content={
            "status": "error", "reason": "fixture_scenario_not_allowed",
            "run_id": run_id, "meta": {"contract_id": payload.contract_id}})
    result = await runner.run(build_prompt(payload, run_id), payload.scenario,
                              run_id, payload.contract_id)
    code = {"busy": 429, "executor_unavailable": 503,
            "timeout": 504, "execution_error": 500}.get(result["reason"], 200)
    return JSONResponse(status_code=code, content=result)
