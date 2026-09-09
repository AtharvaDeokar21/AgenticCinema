"""
Media upload endpoint, database-backed media storage, and creator voice workflow.
Eliminates reliance on hardcoded filesystem paths by storing media directly in SQLite.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Response
from typing import Optional
import os
import uuid
from pathlib import Path

from app.persistence.repository import ProjectRepository, MediaRepository
from app.shared.models.media import MediaManifest, MediaAsset
from app.shared.models.project import ProjectState

router = APIRouter(prefix="/projects", tags=["media"])

# Storage directory for intermediate/temporary processing (e.g. ffmpeg)
STORAGE_DIR = Path(__file__).parent.parent.parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)


@router.post("/{project_id}/media")
async def upload_media(project_id: str, file: UploadFile = File(...)):
    """Upload media file (video/audio) for creator voice workflow, storing binary in SQLite database."""
    project = await ProjectRepository.load(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        content = await file.read()
        file_ext = Path(file.filename).suffix.lower()
        media_id = f"media_{str(uuid.uuid4())[:8]}"
        is_video = file_ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]
        content_type = file.content_type or ("video/mp4" if is_video else "audio/wav")
        asset_type = "creator_upload"

        # 1. Save directly into SQLite database
        await MediaRepository.save_media(
            project_id=project_id,
            media_id=media_id,
            asset_type=asset_type,
            filename=file.filename,
            content_type=content_type,
            data=content,
            metadata={"size": len(content), "original_name": file.filename},
        )

        # 2. Also write to temporary storage for local tools (FFmpeg) that require filesystem paths
        file_path = STORAGE_DIR / project_id / f"{media_id}{file_ext}"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(content)

        asset = MediaAsset(
            asset_id=media_id,
            file_name=file.filename,
            file_path=str(file_path),
            asset_type="video" if is_video else "audio",
        )

        # Update project with media manifest
        if project.media_manifest is None:
            project.media_manifest = MediaManifest(assets=[asset])
        else:
            project.media_manifest.assets.append(asset)

        # Mark MEDIA_UPLOAD as completed and SYNC as ready
        if "MEDIA_UPLOAD" not in project.completed_stages:
            project.completed_stages.append("MEDIA_UPLOAD")

        await ProjectRepository.save(project)

        return {
            "project_id": project_id,
            "media_id": media_id,
            "filename": file.filename,
            "file_path": str(file_path),
            "file_size": len(content),
            "completed_stages": project.completed_stages,
            "ready_stages": ["SYNC"],
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Upload failed: {str(e)}")


@router.get("/{project_id}/media")
async def get_or_list_media(
    project_id: str,
    type: Optional[str] = Query(None, description="Asset type: 'audio_master', 'storyboard', 'video_thumbnail', 'dub_track', 'creator_upload'"),
    shot_id: Optional[str] = Query(None, description="Required if type='storyboard' or 'video_thumbnail'"),
    language: Optional[str] = Query(None, description="Required if type='dub_track' (e.g. 'ja-Generic')"),
):
    """
    Fetch media asset from the database.
    If 'type' is provided, streams the binary data directly from the DB.
    If 'type' is omitted, returns metadata list of all media assets stored for this project.
    """
    if not type:
        # Return listing of media assets metadata
        return await MediaRepository.list_by_project(project_id)

    # Fetch specific media by type from the database
    media = await MediaRepository.get_by_project_and_type(
        project_id=project_id,
        asset_type=type,
        shot_id=shot_id,
        language=language,
    )

    if not media:
        raise HTTPException(status_code=404, detail=f"Media asset of type '{type}' not found in database")

    return Response(
        content=media["data"],
        media_type=media["content_type"],
        headers={"Content-Disposition": f'inline; filename="{media["filename"]}"'},
    )


@router.get("/{project_id}/media/{media_id}")
async def get_media_by_id(
    project_id: str,
    media_id: str,
    download: bool = Query(False, description="Stream binary content instead of JSON metadata"),
):
    """
    Fetch media information or binary content by media_id.
    Returns JSON metadata by default (compatible with frontend getMedia).
    Pass ?download=true or use /{media_id}/download to stream the binary.
    """
    media = await MediaRepository.get_media(media_id)

    # Fallback to project state / disk if not yet migrated to DB
    if not media:
        project = await ProjectRepository.load(project_id)
        if project and project.media_manifest:
            asset = next((a for a in project.media_manifest.assets if a.asset_id == media_id), None)
            if asset and os.path.exists(asset.file_path):
                data = Path(asset.file_path).read_bytes()
                content_type = "video/mp4" if asset.asset_type == "video" else "audio/wav"
                await MediaRepository.save_media(
                    project_id=project_id,
                    media_id=media_id,
                    asset_type="creator_upload",
                    filename=asset.file_name,
                    content_type=content_type,
                    data=data,
                    metadata={"size": len(data)},
                )
                media = {
                    "media_id": media_id,
                    "project_id": project_id,
                    "asset_type": "creator_upload",
                    "filename": asset.file_name,
                    "content_type": content_type,
                    "data": data,
                    "metadata": {"size": len(data)},
                    "created_at": None,
                }

    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    if download:
        return Response(
            content=media["data"],
            media_type=media["content_type"],
            headers={"Content-Disposition": f'inline; filename="{media["filename"]}"'},
        )

    return {
        "project_id": project_id,
        "media_id": media["media_id"],
        "asset_type": media.get("asset_type"),
        "filename": media["filename"],
        "file_path": media.get("filename"),
        "file_type": media["content_type"],
        "file_size": len(media["data"]),
        "download_url": f"/projects/{project_id}/media/{media_id}/download",
        "metadata": media.get("metadata"),
        "created_at": media.get("created_at"),
    }


@router.get("/{project_id}/media/{media_id}/download")
async def download_media(project_id: str, media_id: str):
    """Stream binary content directly from the database."""
    media = await MediaRepository.get_media(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    return Response(
        content=media["data"],
        media_type=media["content_type"],
        headers={"Content-Disposition": f'inline; filename="{media["filename"]}"'},
    )


@router.delete("/{project_id}/media/{media_id}")
async def delete_media(project_id: str, media_id: str):
    """Delete uploaded media from database and disk"""
    project = await ProjectRepository.load(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Delete from database
        await MediaRepository.delete_media(media_id)

        # Clear from media manifest and disk if present
        if project.media_manifest and project.media_manifest.assets:
            for asset in project.media_manifest.assets:
                if asset.asset_id == media_id:
                    if os.path.exists(asset.file_path):
                        try:
                            os.remove(asset.file_path)
                        except OSError:
                            pass
            project.media_manifest.assets = [
                a for a in project.media_manifest.assets if a.asset_id != media_id
            ]
            if not project.media_manifest.assets:
                project.media_manifest = None
                if "MEDIA_UPLOAD" in project.completed_stages:
                    project.completed_stages.remove("MEDIA_UPLOAD")

        await ProjectRepository.save(project)

        return {
            "project_id": project_id,
            "media_id": media_id,
            "status": "deleted",
            "completed_stages": project.completed_stages,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Delete failed: {str(e)}")
