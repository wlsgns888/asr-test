from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.main_dependencies import get_settings
from app.routes import minutes, transcribe, upload


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
    app.include_router(upload.router)
    app.include_router(transcribe.router)
    app.include_router(minutes.router)
    return app


app = create_app()
