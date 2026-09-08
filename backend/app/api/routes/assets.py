"""
API route to fetch generated media assets like thumbnails and audio files
directly from the SQLite database via MediaRepository, with filesystem fallback.
"""
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse
import os
from pathlib import Path
from typing import Optional

from app.persistence.repository import ProjectRepository, MediaRepository

router = APIRouter(prefix="/projects", tags=["assets"])


@router.get("/{project_id}/assets")
async def get_project_asset(
    project_id: str,
    type: str = Query(..., description="Type of asset: 'audio_master', 'storyboard', 'video_thumbnail', 'dub_track'"),
    shot_id: Optional[str] = Query(None, description="Required if type='storyboard' or 'video_thumbnail'"),
    language: Optional[str] = Query(None, description="Required if type='dub_track' (e.g. 'ja-Generic')")
):
    """
    Fetch a generated asset for the project.
    Retrieves the binary data directly from the SQLite database.
    Falls back to filesystem and caches into SQLite if not present yet.
    """
    # 1. First, check SQLite database
    media = await MediaRepository.get_by_project_and_type(
        project_id=project_id,
        asset_type=type,
        shot_id=shot_id,
        language=language,
    )

    if media:
        return Response(
            content=media["data"],
            media_type=media["content_type"],
            headers={"Content-Disposition": f'inline; filename="{media["filename"]}"'},
        )

    # 2. Fallback: check filesystem via ProjectState
    project = await ProjectRepository.load(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    file_path = None
    content_type = "application/octet-stream"
    filename = f"asset_{type}"

    if type == "audio_master":
        if not project.audio_master or not project.audio_master.file_path:
            raise HTTPException(status_code=404, detail="Audio master not generated yet")
        file_path = project.audio_master.file_path
        content_type = "audio/wav"
        filename = "master.wav"

    elif type in ["storyboard", "thumbnail"]:
        if not shot_id:
            raise HTTPException(status_code=400, detail="shot_id is required for storyboard thumbnails")
        if not project.storyboard or not project.storyboard.shots:
            raise HTTPException(status_code=404, detail="Storyboard not generated yet")
        
        shot = next((s for s in project.storyboard.shots if s.shot_id == shot_id), None)
        if not shot or not shot.generated_image:
            raise HTTPException(status_code=404, detail=f"Shot {shot_id} not found or image not generated")
        
        file_path = shot.generated_image
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        content_type = "image/png"
        filename = f"{shot_id}.png"

    elif type == "video_thumbnail":
        if not shot_id:
            raise HTTPException(status_code=400, detail="shot_id (e.g. '01') is required for video_thumbnail assets")
        file_path = os.path.abspath(f"storage/storyboard/generated/{project_id}/thumbnails/thumbnail_{shot_id}.png")
        content_type = "image/png"
        filename = f"thumbnail_{shot_id}.png"

    elif type == "dub_track":
        if not language:
            raise HTTPException(status_code=400, detail="language is required for dub_track assets")
        if not project.dub_tracks:
            raise HTTPException(status_code=404, detail="Dub tracks not generated yet")
        
        track = next((t for t in project.dub_tracks if f"{t.language}-{t.geography}" == language), None)
        if not track or not track.audio_path:
            raise HTTPException(status_code=404, detail=f"Dub track for {language} not found or audio not generated")
        
        file_path = track.audio_path
        content_type = "audio/wav"
        filename = f"dub_{language}.wav"

    else:
        raise HTTPException(status_code=400, detail=f"Unknown asset type: {type}")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Asset not found in database or disk at {file_path}")

    # Read binary and cache into database for subsequent requests
    try:
        data = Path(file_path).read_bytes()
        media_id = f"{project_id}_{type}_{shot_id or language or 'main'}"
        await MediaRepository.save_media(
            project_id=project_id,
            media_id=media_id,
            asset_type=type,
            filename=filename,
            content_type=content_type,
            data=data,
            metadata={"shot_id": shot_id, "language": language},
        )
        return Response(
            content=data,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    except Exception:
        return FileResponse(file_path)
