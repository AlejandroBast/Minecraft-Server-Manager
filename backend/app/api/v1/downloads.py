"""Endpoints de catálogos de versiones y runtimes de Java."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AppSettings
from app.models.enums import ServerType
from app.schemas.downloads import JavaRuntimeRead, VersionListRead, VersionRead
from app.services.java_manager import JavaManager
from app.services.version_catalog import DOWNLOADABLE_TYPES, SUPPORT_NOTES, list_versions

router = APIRouter(prefix="/downloads", tags=["downloads"])


@router.get("/versions/{server_type}", response_model=VersionListRead)
def versions(server_type: ServerType) -> VersionListRead:
    supported = server_type in DOWNLOADABLE_TYPES
    return VersionListRead(
        type=server_type,
        supported=supported,
        reason=SUPPORT_NOTES.get(server_type),
        versions=(
            [VersionRead.model_validate(item) for item in list_versions(server_type)]
            if supported
            else []
        ),
    )


@router.get("/java", response_model=list[JavaRuntimeRead])
def java_runtimes(config: AppSettings) -> list[JavaRuntimeRead]:
    runtimes = JavaManager(config.java_dir).installed_runtimes()
    return [
        JavaRuntimeRead(major=major, path=str(path))
        for major, path in sorted(runtimes.items())
    ]
