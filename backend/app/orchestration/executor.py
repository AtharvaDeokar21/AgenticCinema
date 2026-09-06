"""
Minimal stage executor for running agents asynchronously.
"""
import asyncio
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from ..orchestration.dag import StageType, WorkflowDAG
from ..shared.models.project import ProjectState


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StageExecutor:
    """Execute individual workflow stages"""

    def __init__(self):
        self.dag = WorkflowDAG()
        self.running_jobs: Dict[str, dict] = {}  # In-memory job tracking for demo

    async def execute_stage(
        self,
        project_id: str,
        stage: StageType,
        project: ProjectState,
        input_override: Optional[Dict] = None,
    ) -> dict:
        """
        Execute a stage and return job info.
        Runs in background; returns job_id immediately.
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

        # Create job
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "project_id": project_id,
            "stage": stage.value,
            "status": JobStatus.QUEUED.value,
            "progress": 0.0,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
        }

        self.running_jobs[job_id] = job

        # Run in background
        asyncio.create_task(
            self._run_stage_job(job_id, project_id, stage, project, input_override)
        )

        return {
            "job_id": job_id,
            "stage": stage.value,
            "status": JobStatus.QUEUED.value,
        }

    async def _run_stage_job(
        self,
        job_id: str,
        project_id: str,
        stage: StageType,
        project: ProjectState,
        input_override: Optional[Dict] = None,
    ):
        """Background task: invoke agent"""
        job = self.running_jobs[job_id]

        try:
            job["status"] = JobStatus.RUNNING.value
            job["started_at"] = datetime.utcnow().isoformat()

            # Import agents here to avoid circular imports
            if stage == StageType.SCRIPT:
                from ..agents.script_suggestor.agent import ScriptSuggestorAgent
                from ..agents.script_suggestor.schemas import ScriptRequest

                agent = ScriptSuggestorAgent()
                request = ScriptRequest(
                    creator_profile=project.creator_profile,
                    brief=input_override.get("brief") if input_override else "Generate a creative script",
                )
                result = await agent.run(request)
                project.script = result

            elif stage == StageType.STORYBOARD:
                from ..agents.storyboard.agent import StoryboardAgent

                if not project.script:
                    raise ValueError("Script required for storyboard")

                agent = StoryboardAgent()
                # Run in thread pool since it's sync
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    agent.generate,
                    project.script,
                )
                project.storyboard = result

            elif stage == StageType.AUDIO_AI:
                from ..agents.audio.agent import AudioAgent
                from ..agents.audio.schemas import AudioRequest, AudioInputMode

                if not project.script:
                    raise ValueError("Script required for audio")

                agent = AudioAgent()
                request = AudioRequest(
                    video_path="tmp/dummy.mp4",  # No video for AI mode
                    mode=AudioInputMode.AI_VOICE,
                    project_state=project,
                )
                result = await agent.run(request)
                project.audio_master = result.audio_master

            job["result"] = {"stage": stage.value, "status": "completed"}
            job["status"] = JobStatus.COMPLETED.value
            project.completed_stages.append(stage.value)

        except Exception as e:
            job["error"] = {"type": type(e).__name__, "message": str(e)}
            job["status"] = JobStatus.FAILED.value

        job["completed_at"] = datetime.utcnow().isoformat()
        job["progress"] = 1.0 if job["status"] == JobStatus.COMPLETED.value else 0.0

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """Get job status"""
        return self.running_jobs.get(job_id)

    def get_ready_stages(self, project: ProjectState) -> list:
        """Get stages that can run now"""
        completed = set(project.completed_stages)
        ready = self.dag.get_ready_stages(completed)
        return [s.value for s in ready]
