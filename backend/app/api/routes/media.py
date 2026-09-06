"""
Media upload endpoint and creator voice workflow
Enables SCRIPT → MEDIA_UPLOAD → SYNC → AUDIO_CREATOR path
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Optional
import os
import uuid
from pathlib import Path

from ..persistence.repository import ProjectRepository
from ..shared.models.media import MediaManifest
from ..shared.models.project import ProjectState

router = APIRouter(prefix="/projects", tags=["media"])

# Storage directory for uploaded media
STORAGE_DIR = Path(__file__).parent.parent.parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)


@router.post("/{project_id}/media")
async def upload_media(project_id: str, file: UploadFile = File(...)):
    """Upload media file (video) for creator voice workflow"""

    project = await ProjectRepository.load(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Generate unique filename
        file_ext = Path(file.filename).suffix
        media_id = f"media_{str(uuid.uuid4())[:8]}"
        file_path = STORAGE_DIR / project_id / f"{media_id}{file_ext}"

        # Create directory if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Save file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # Update project with media manifest
        project.media_manifest = MediaManifest(
            media_id=media_id,
            file_path=str(file_path),
            file_size=len(content),
            file_type=file.content_type or "video/mp4",
            duration=None,  # Would need video analysis to get duration
        )

        # Mark MEDIA_UPLOAD as completed and SYNC as ready
        if "MEDIA_UPLOAD" not in project.completed_stages:
            project.completed_stages.append("MEDIA_UPLOAD")

        await ProjectRepository.save(project)

        return {
            "project_id": project_id,
            "media_id": media_id,
            "file_path": str(file_path),
            "file_size": len(content),
            "completed_stages": project.completed_stages,
            "ready_stages": ["SYNC"],  # SYNC now available if SCRIPT is done
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Upload failed: {str(e)}")


@router.get("/{project_id}/media/{media_id}")
async def get_media_info(project_id: str, media_id: str):
    """Get media file information"""

    project = await ProjectRepository.load(project_id)
    if not project or not project.media_manifest:
        raise HTTPException(status_code=404, detail="Media not found")

    return {
        "project_id": project_id,
        "media_id": project.media_manifest.media_id,
        "file_path": project.media_manifest.file_path,
        "file_type": project.media_manifest.file_type,
        "file_size": project.media_manifest.file_size,
        "duration": project.media_manifest.duration,
    }


@router.delete("/{project_id}/media/{media_id}")
async def delete_media(project_id: str, media_id: str):
    """Delete uploaded media"""

    project = await ProjectRepository.load(project_id)
    if not project or not project.media_manifest:
        raise HTTPException(status_code=404, detail="Media not found")

    try:
        # Delete file
        if os.path.exists(project.media_manifest.file_path):
            os.remove(project.media_manifest.file_path)

        # Clear media manifest
        project.media_manifest = None
        if "MEDIA_UPLOAD" in project.completed_stages:
            project.completed_stages.remove("MEDIA_UPLOAD")

        await ProjectRepository.save(project)

        return {
            "project_id": project_id,
            "status": "deleted",
            "completed_stages": project.completed_stages,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Delete failed: {str(e)}")
