from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.main_dependencies import get_settings
from app.routes import capabilities, frontend, minutes, transcribe, upload

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_lifespan(
    settings: Settings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        settings.ensure_directories()
        yield

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    app = FastAPI(
        title="Meeting Minutes ASR",
        lifespan=create_lifespan(resolved_settings),
    )
    app.dependency_overrides[get_settings] = lambda: resolved_settings
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(frontend.router)
    app.include_router(capabilities.router)
    app.include_router(upload.router)
    app.include_router(transcribe.router)
    app.include_router(minutes.router)
    return app


app = create_app()
