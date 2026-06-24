import re
from typing import Final

ARTIFACT_ID_PATTERN: Final = re.compile(r"^[0-9a-f]{32}$")
ARTIFACT_ID_ERROR_CODE: Final = "artifact_id"
ARTIFACT_ID_ERROR_MESSAGE: Final = (
    "artifact id must be a 32-character lowercase hex string"
)


class InvalidArtifactIdError(RuntimeError):
    pass


def ensure_artifact_id(value: str) -> str:
    if ARTIFACT_ID_PATTERN.fullmatch(value) is None:
        raise InvalidArtifactIdError
    return value
