from contextlib import asynccontextmanager
from pathlib import Path
import shutil

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from adapters.codex.handler import router
from core.config import Settings
from core.runner import Runner


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    runner = Runner(settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await runner.drain()

    app = FastAPI(title=settings.service_name, version="0.2.0", lifespan=lifespan)
    app.state.runner = runner
    app.include_router(router)

    @app.get("/health")
    async def health(deep: bool = False):
        payload = {"status": "ok", "backend": settings.backend,
                   "active_runs": runner.active, "capacity": settings.max_concurrency}
        code = 200
        if deep and settings.backend == "codex":
            executable = shutil.which(settings.codex_binary)
            payload.update(executor_available=bool(executable),
                           auth_present=Path(settings.auth_file).is_file(),
                           check_scope="local executable and auth-file presence only")
            if not executable or not payload["auth_present"]:
                payload["status"], code = "unavailable", 503
        return JSONResponse(payload, status_code=code)

    return app
