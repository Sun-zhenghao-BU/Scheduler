from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from scheduler_automation.api.routes import llm, tasks


def _static_dir() -> Path | None:
    candidates = [
        Path(os.environ["SCHEDULER_STATIC_DIR"]) if os.environ.get("SCHEDULER_STATIC_DIR") else None,
        Path.cwd() / "static",
        Path(__file__).parents[2] / "web" / "dist",
    ]
    for candidate in candidates:
        if candidate and (candidate / "index.html").exists():
            return candidate
    return None


def create_app() -> FastAPI:
    app = FastAPI(
        title="调度自动化 API",
        version="0.2.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    root = Path.cwd()

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(tasks.router)
    app.include_router(llm.router)

    app.state.root = root

    static_dir = _static_dir()
    if static_dir:
        assets_dir = static_dir / "assets"

        @app.get("/assets/{path:path}", include_in_schema=False)
        def assets(path: str) -> FileResponse:
            return FileResponse(assets_dir / path)

        @app.get("/", include_in_schema=False)
        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str = "") -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")
            file_path = static_dir / path
            if path and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
