from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.main_dependencies import StorageDep
from app.schemas import UploadSummary
from app.services.storage_service import UnsupportedAudioError

router = APIRouter(tags=["uploads"])
AudioUpload = Annotated[UploadFile, File(...)]


@router.post("/uploads", status_code=status.HTTP_201_CREATED)
async def upload_audio(
    storage: StorageDep,
    file: AudioUpload,
) -> UploadSummary:
    try:
        summary = await storage.save_upload(file)
    except UnsupportedAudioError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio extension",
        ) from error
    return summary
