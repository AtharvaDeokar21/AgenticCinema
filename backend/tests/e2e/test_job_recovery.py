import pytest
import sqlite3
import uuid
from datetime import datetime
from app.persistence.repository import JobRepository, ProjectRepository, init_db
from app.shared.models.project import ProjectState

@pytest.mark.asyncio
async def test_job_recovery():
    # 1. Setup raw DB state (without firing up FastAPI lifespan yet)
    init_db()
    
    project_id = str(uuid.uuid4())
    project = ProjectState(project_id=project_id, project_name="Recovery Test")
    await ProjectRepository.save(project)

    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "project_id": project_id,
        "stage": "SCRIPT",
        "status": "running",  # Stuck in running state
        "progress": 0.5,
        "phase": None,
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "result": None,
        "error": None,
    }
    await JobRepository.save(job)
    
    # 2. Call reset_interrupted_jobs (which runs on FastAPI lifespan startup)
    await JobRepository.reset_interrupted_jobs()

    # 3. Verify it moved to queued
    recovered_job = await JobRepository.load(job_id)
    assert recovered_job["status"] == "queued"
