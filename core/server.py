import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from adapters.codex.handler import router as codex_router
from core.config import get_settings

logger = logging.getLogger("headless-bridge")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.service_name)

    app.include_router(codex_router)

    @app.get("/health")
    async def health(deep: bool = False):
        """Basic health endpoint with optional auth volume verification."""
        payload = {"status": "ok"}

        if deep:
            auth_path = Path(settings.auth_file)
            payload["auth_file"] = str(auth_path)
            payload["auth_present"] = auth_path.is_file()

            if not payload["auth_present"]:
                raise HTTPException(
                    status_code=503,
                    detail={"reason": "auth file missing", **payload},
                )

        return JSONResponse(payload)

    return app
