"""
Stage executor — Phase 4 (Persistent Jobs).
Jobs are written to SQLite immediately and picked up by the background worker.
No in-memory state is kept; all status reads go through JobRepository.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict

from ..orchestration.dag import StageType, WorkflowDAG
from ..shared.models.project import ProjectState
from ..persistence.repository import JobRepository


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StageExecutor:
    """Enqueues workflow stages as persistent SQLite jobs."""

    def __init__(self):
        self.dag = WorkflowDAG()

    async def execute_stage(
        self,
        project_id: str,
        stage: StageType,
        project: ProjectState,
        input_override: Optional[Dict] = None,
    ) -> dict:
        """
        Validate dependencies, write a 'queued' job to SQLite, and return
        the job_id immediately. The background worker (worker.py) picks it up.
        """
        # Validate dependencies
        deps = self.dag.get_dependencies(stage)
        completed = set(project.completed_stages)
        missing = deps - completed

        if missing and stage != StageType.CREATED:
            return {
                "error": "dependencies_not_satisfied",
                "stage": stage.value,
                "missing_dependencies": [s.value for s in missing],
                "ready_stages": [s.value for s in self.dag.get_ready_stages(completed)],
            }

        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "project_id": project_id,
            "stage": stage.value,
            "status": JobStatus.QUEUED,
            "progress": 0.0,
            "phase": None,
            # Store input_override so the worker can read it
            "result": str(input_override) if input_override else None,
            "error": None,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
        }

        # Persist to DB — the worker will pick this up on its next poll
        await JobRepository.save(job)

        return {
            "job_id": job_id,
            "stage": stage.value,
            "status": JobStatus.QUEUED,
        }

    async def get_job_status(self, job_id: str) -> Optional[dict]:
        """Read job status from the DB (survives server restarts)."""
        return await JobRepository.load(job_id)

    def get_ready_stages(self, project: ProjectState) -> list:
        """Get stages that can run now based on completed stages."""
        completed = set(project.completed_stages)
        ready = self.dag.get_ready_stages(completed)
        return [s.value for s in ready]
