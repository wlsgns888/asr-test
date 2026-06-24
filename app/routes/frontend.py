from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "static"

router = APIRouter(include_in_schema=False)


@router.get("/")
async def get_frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
