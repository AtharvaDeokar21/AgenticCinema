"""
main.py - FastAPI entry point with Phase 4 persistent worker.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional
import asyncio
import uuid
from datetime import datetime

from app.persistence.repository import init_db, ProjectRepository, JobRepository
from app.orchestration.dag import StageType, WorkflowDAG
from app.orchestration.chat_router import ChatIntentRouter
from app.orchestration.compliance_decorator import ComplianceDecorator
from app.shared.models.project import ProjectState, WorkflowConfig
from app.agents.compliance.agent import ComplianceAgent
from app.worker import run_worker_loop


# Initialize DAG, routers, and decorator at module level
dag = WorkflowDAG()
chat_router = ChatIntentRouter()
compliance_agent = ComplianceAgent()
compliance_decorator = ComplianceDecorator(compliance_agent)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    init_db()
    print("✓ Database initialized")

    # Recover any jobs that were 'running' when the server last crashed
    await JobRepository.reset_interrupted_jobs()

    # Start the persistent background worker
    worker_task = asyncio.create_task(run_worker_loop())
    print("✓ Background worker started")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        print("✓ Background worker stopped")


app = FastAPI(
    title="Agentic Cinema API",
    description="Backend API for Agentic Cinema multi-agent platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ REQUEST/RESPONSE MODELS ============

class CreateProjectRequest(BaseModel):
    project_name: str
    audio_mode: str = "AI_VOICE"
    target_locales: list = []


class InvokeStageRequest(BaseModel):
    input: Optional[dict] = None


# ============ ENDPOINTS ============

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "agentic-cinema-backend"}


@app.post("/projects")
async def create_project(req: CreateProjectRequest):
    """Create a new project"""
    project_id = str(uuid.uuid4())[:8]

    project = ProjectState(
        project_id=project_id,
        project_name=req.project_name,
        completed_stages=["CREATED"],
        workflow_config=WorkflowConfig(
            audio_mode=req.audio_mode,
            target_locales=req.target_locales,
        ),
    )

    await ProjectRepository.save(project)

    # Get ready stages
    completed = set(project.completed_stages)
    ready = dag.get_ready_stages(completed)

    return {
        "project_id": project_id,
        "status": "created",
        "completed_stages": project.completed_stages,
        "ready_stages": [s.value for s in ready],
        "created_at": project.created_at.isoformat(),
    }


@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get project state"""
    project = await ProjectRepository.load(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get ready stages
    completed = set(project.completed_stages)
    ready = dag.get_ready_stages(completed)

    return {
        "project_id": project.project_id,
        "project_name": project.project_name,
        "status": "in_progress",
        "completed_stages": project.completed_stages,
        "ready_stages": [s.value for s in ready],
        "blocked_stages": project.blocked_stages,
        "audio_mode": project.workflow_config.audio_mode,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


@app.post("/projects/{project_id}/stages/{stage_name}")
async def invoke_stage(project_id: str, stage_name: str, req: InvokeStageRequest):
    """Invoke a single stage"""
    project = await ProjectRepository.load(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Parse stage
    try:
        stage = StageType[stage_name.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {stage_name}")

    # Check dependencies
    deps = dag.get_dependencies(stage)
    completed = set(project.completed_stages)
    missing = deps - completed

    if missing:
        ready = dag.get_ready_stages(completed)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "dependencies_not_satisfied",
                "stage": stage.value,
                "missing": [s.value for s in missing],
                "ready": [s.value for s in ready],
            },
        )

    # Write job to SQLite — the worker loop will pick it up automatically
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
    await JobRepository.save(job)

    return {
        "project_id": project_id,
        "stage": stage.value,
        "job_id": job_id,
        "status": "queued",
        "message": "Job queued. The worker will process it within a few seconds.",
    }


@app.get("/projects/{project_id}/jobs/{job_id}")
async def get_job_status(project_id: str, job_id: str):
    """Poll job status — reads from SQLite, survives server restarts."""
    job = await JobRepository.load(job_id)

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


@app.get("/projects/{project_id}/dag")
async def get_dag(project_id: str):
    """Get workflow DAG visualization"""
    project = await ProjectRepository.load(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    completed = set(project.completed_stages)
    ready = dag.get_ready_stages(completed)

    nodes = []
    for stage in StageType:
        if stage.value in completed:
            status_val = "completed"
        elif stage in ready:
            status_val = "ready"
        else:
            status_val = "waiting"

        nodes.append({"stage": stage.value, "status": status_val})

    edges = []
    for dep in dag.dependencies:
        edges.append({"source": dep.source.value, "target": dep.target.value})

    return {"nodes": nodes, "edges": edges}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
