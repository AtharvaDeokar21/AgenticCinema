"""
API route to fetch generated media assets like thumbnails and audio files
from the filesystem based on their paths stored in the project state.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
import os
from typing import Optional

from app.persistence.repository import ProjectRepository

router = APIRouter(prefix="/projects", tags=["assets"])


@router.get("/{project_id}/assets")
async def get_project_asset(
    project_id: str,
    type: str = Query(..., description="Type of asset: 'audio_master', 'storyboard', 'dub_track'"),
    shot_id: Optional[str] = Query(None, description="Required if type='storyboard'"),
    language: Optional[str] = Query(None, description="Required if type='dub_track' (e.g. 'ja-Generic')")
):
    """
    Fetch a generated asset file for the project.
    Reads the file path from the SQLite project state and serves the local file.
    """
    project = await ProjectRepository.load(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    file_path = None

    if type == "audio_master":
        if not project.audio_master or not project.audio_master.file_path:
            raise HTTPException(status_code=404, detail="Audio master not generated yet")
        file_path = project.audio_master.file_path

    elif type in ["storyboard", "thumbnail"]:
        if not shot_id:
            raise HTTPException(status_code=400, detail="shot_id is required for storyboard thumbnails")
        if not project.storyboard or not project.storyboard.shots:
            raise HTTPException(status_code=404, detail="Storyboard not generated yet")
        
        # Find the specific shot
        shot = next((s for s in project.storyboard.shots if s.shot_id == shot_id), None)
        if not shot or not shot.generated_image:
            raise HTTPException(status_code=404, detail=f"Shot {shot_id} not found or image not generated")
        
        # Paths might be relative to project root
        file_path = shot.generated_image
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

    elif type == "video_thumbnail":
        if not shot_id:
            raise HTTPException(status_code=400, detail="shot_id (e.g. '01') is required for video_thumbnail assets")
        # Video thumbnails are not tracked strictly in ProjectState, but their deterministic path is known
        file_path = os.path.abspath(f"storage/storyboard/generated/{project_id}/thumbnails/thumbnail_{shot_id}.png")

    elif type == "dub_track":
        if not language:
            raise HTTPException(status_code=400, detail="language is required for dub_track assets")
        if not project.dub_tracks:
            raise HTTPException(status_code=404, detail="Dub tracks not generated yet")
        
        # Find the specific language track (language in this context is the full locale string like 'hi-IN' or 'ja-Generic')
        track = next((t for t in project.dub_tracks if f"{t.language}-{t.geography}" == language), None)
        if not track or not track.audio_path:
            raise HTTPException(status_code=404, detail=f"Dub track for {language} not found or audio not generated")
        
        file_path = track.audio_path

    else:
        raise HTTPException(status_code=400, detail=f"Unknown asset type: {type}")

    # Verify file actually exists on disk
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Asset file not found on disk at {file_path}")

    return FileResponse(file_path)
