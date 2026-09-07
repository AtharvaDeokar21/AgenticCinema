"""
Phase 6: Consolidated API routes for projects and workflow execution.
All routes previously scattered in main.py are now here.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime

from app.shared.models.project import ProjectState, WorkflowConfig
from app.shared.models.creator import CreatorProfile
from app.persistence.repository import ProjectRepository, JobRepository, get_db
from app.orchestration.dag import StageType, WorkflowDAG

router = APIRouter(prefix="/projects", tags=["projects"])

# Single DAG instance for the router
dag = WorkflowDAG()

# --- Request Models ---

class CreateProjectRequest(BaseModel):
    project_name: str
    creator_profile: Optional[dict] = None
    audio_mode: str = "AI_VOICE"
    target_locales: list = []

class InvokeStageRequest(BaseModel):
    input: Optional[dict] = None
    force: bool = False

# --- Endpoints ---

@router.get("")
async def list_projects():
    """Phase 6: List all projects"""
    projects = await ProjectRepository.list_all()
    return {"projects": projects}


@router.post("")
async def create_project(req: CreateProjectRequest):
    """Create a new project"""
    project_id = str(uuid.uuid4())

    # Build properly populated ProjectState
    project = ProjectState(
        project_id=project_id,
        project_name=req.project_name,
        creator_profile=CreatorProfile(**req.creator_profile) if req.creator_profile else None,
        deal_context=None,
        completed_stages=["CREATED"],
        workflow_config=WorkflowConfig(
            audio_mode=req.audio_mode,
            target_locales=req.target_locales,
        ),
    )

    await ProjectRepository.save(project)

    ready_stages = dag.get_ready_stages(set(project.completed_stages))

    return {
        "project_id": project_id,
        "status": "created",
        "completed_stages": project.completed_stages,
        "ready_stages": [s.value for s in ready_stages],
        "created_at": project.created_at.isoformat(),
    }


@router.get("/{project_id}")
async def get_project(project_id: str):
    """Get full project state including all generated content."""
    project = await ProjectRepository.load(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    completed = set(project.completed_stages)
    ready = dag.get_ready_stages(completed)

    script_data = None
    if project.script:
        script_data = {
            "title": project.script.title,
            "beats": [
                {
                    "beat_id": b.beat_id,
                    "text": b.text,
                    "start_time": b.start_time,
                    "end_time": b.end_time,
                    "audio_intent": b.audio_intent,
                }
                for b in (project.script.beats or [])
            ],
        }

    storyboard_data = None
    if project.storyboard:
        storyboard_data = {
            "visual_style": project.storyboard.visual_style,
            "shots": [
                {
                    "shot_id": s.shot_id,
                    "description": s.visual_description,
                    "duration": s.end_time - s.start_time,
                }
                for s in (project.storyboard.shots or [])
            ],
        }

    audio_data = None
    if project.audio_master:
        audio_data = {
            "duration": project.audio_master.duration,
            "sample_rate": project.audio_master.sample_rate,
            "segments": len(project.audio_master.segments or []),
        }

    return {
        "project_id": project.project_id,
        "project_name": project.project_name,
        "completed_stages": project.completed_stages,
        "ready_stages": [s.value for s in ready],
        "blocked_stages": project.blocked_stages,
        "workflow_config": {
            "audio_mode": project.workflow_config.audio_mode,
            "target_locales": project.workflow_config.target_locales,
        },
        "script": script_data,
        "storyboard": storyboard_data,
        "audio": audio_data,
        "sync_report": project.sync_report.model_dump(mode="json") if project.sync_report else None,
        "dub_tracks": [dt.model_dump(mode="json") for dt in project.dub_tracks] if project.dub_tracks else [],
        "opportunity_queue": project.opportunity_queue.model_dump(mode="json") if project.opportunity_queue else None,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Phase 6: Delete a project and all its associated data"""
    success = await ProjectRepository.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {"status": "deleted", "project_id": project_id}


@router.post("/{project_id}/stages/{stage_name}")
async def invoke_stage(project_id: str, stage_name: str, req: InvokeStageRequest):
    """Invoke a single stage by queuing it for the worker"""
    project = await ProjectRepository.load(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        stage = StageType[stage_name.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {stage_name}")

    if stage.value in project.completed_stages and not req.force:
        raise HTTPException(status_code=400, detail=f"Stage {stage.value} already completed")

    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "project_id": project_id,
        "stage": stage.value,
        "status": "queued",
        "progress": 0.0,
        "phase": None,
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "result": None,
        "error": None,
    }

    if req.input:
        import json
        job["result"] = json.dumps(req.input)

    await JobRepository.save(job)

    return {
        "project_id": project_id,
        "stage": stage.value,
        "job_id": job_id,
        "status": "queued",
        "message": "Job queued successfully. Poll the jobs endpoint for status."
    }


@router.get("/{project_id}/jobs")
async def list_jobs(project_id: str):
    """List all jobs for a project"""
    project = await ProjectRepository.load(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    jobs = await JobRepository.get_by_project(project_id)
    return {"jobs": jobs}


@router.get("/{project_id}/jobs/{job_id}")
async def get_job_status(project_id: str, job_id: str):
    """Poll job status from the database"""
    # Quick sanity check for project
    project = await ProjectRepository.load(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch from SQLite via JobRepository (using direct fetch since get_by_project returns all)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return dict(row)


@router.get("/{project_id}/dag")
async def get_dag(project_id: str):
    """Get workflow DAG visualization"""
    project = await ProjectRepository.load(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    completed = set(project.completed_stages)
    ready = set(dag.get_ready_stages(completed))
    blocked = set(project.blocked_stages)

    nodes = []
    for stage in StageType:
        if stage.value in project.completed_stages:
            status = "completed"
        elif stage.value in ready:
            status = "ready"
        elif stage.value in blocked:
            status = "blocked"
        else:
            status = "waiting"

        nodes.append({
            "stage": stage.value,
            "status": status,
        })

    edges = []
    for dep in dag.dependencies:
        edges.append({
            "source": dep.source.value,
            "target": dep.target.value,
        })

    return {
        "nodes": nodes,
        "edges": edges,
    }
