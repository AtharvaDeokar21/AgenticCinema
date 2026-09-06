"""
Minimal API routes for projects and workflow execution.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid

from ..shared.models.project import ProjectState, WorkflowConfig
from ..shared.models.creator import CreatorProfile
from ..persistence.repository import ProjectRepository, JobRepository
from ..orchestration.dag import StageType
from ..orchestration.executor import StageExecutor

router = APIRouter(prefix="/projects", tags=["projects"])
executor = StageExecutor()


class CreateProjectRequest(BaseModel):
    project_name: str
    creator_profile: Optional[dict] = None
    audio_mode: str = "AI_VOICE"
    target_locales: list = []


class InvokeStageRequest(BaseModel):
    input: Optional[dict] = None
    force: bool = False


@router.post("")
async def create_project(req: CreateProjectRequest):
    """Create a new project"""
    project_id = str(uuid.uuid4())

    project = ProjectState(
        project_id=project_id,
        project_name=req.project_name,
        creator_profile=None,
        deal_context=None,
        completed_stages=["CREATED"],
        workflow_config=WorkflowConfig(
            audio_mode=req.audio_mode,
            target_locales=req.target_locales,
        ),
    )

    await ProjectRepository.save(project)

    ready_stages = executor.get_ready_stages(project)

    return {
        "project_id": project_id,
        "status": "created",
        "completed_stages": project.completed_stages,
        "ready_stages": ready_stages,
        "created_at": project.created_at.isoformat(),
    }


@router.get("/{project_id}")
async def get_project(project_id: str):
    """Get project state"""
    project = await ProjectRepository.load(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ready_stages = executor.get_ready_stages(project)

    # Get running jobs
    jobs = await JobRepository.get_by_project(project_id)
    running_jobs = [j for j in jobs if j["status"] == "running"]

    return {
        "project_id": project.project_id,
        "project_name": project.project_name,
        "status": "in_progress",
        "completed_stages": project.completed_stages,
        "ready_stages": ready_stages,
        "blocked_stages": project.blocked_stages,
        "running_jobs": running_jobs,
        "audio_mode": project.workflow_config.audio_mode,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


@router.post("/{project_id}/stages/{stage_name}")
async def invoke_stage(project_id: str, stage_name: str, req: InvokeStageRequest):
    """Invoke a single stage"""
    project = await ProjectRepository.load(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        stage = StageType[stage_name.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {stage_name}")

    # Execute stage
    result = await executor.execute_stage(
        project_id=project_id,
        stage=stage,
        project=project,
        input_override=req.input,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result)

    # Save updated project
    await ProjectRepository.save(project)

    return {
        "project_id": project_id,
        "stage": stage_name,
        "job_id": result["job_id"],
        "status": result["status"],
    }


@router.get("/{project_id}/jobs/{job_id}")
async def get_job_status(project_id: str, job_id: str):
    """Poll job status"""
    job = executor.get_job_status(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job_id,
        "project_id": job["project_id"],
        "stage": job["stage"],
        "status": job["status"],
        "progress": job["progress"],
        "started_at": job["started_at"],
        "completed_at": job["completed_at"],
        "result": job["result"],
        "error": job["error"],
    }


@router.get("/{project_id}/dag")
async def get_dag(project_id: str):
    """Get workflow DAG visualization"""
    project = await ProjectRepository.load(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    completed = set(project.completed_stages)
    ready = set(executor.get_ready_stages(project))
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
    for dep in executor.dag.dependencies:
        edges.append({
            "source": dep.source.value,
            "target": dep.target.value,
        })

    return {
        "nodes": nodes,
        "edges": edges,
    }
