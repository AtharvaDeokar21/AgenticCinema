"""
Phase 4: Persistent Async Worker
Polls the SQLite `jobs` table and executes queued stage jobs.
This runs as a background asyncio task started in FastAPI's lifespan.

Design:
  - No Celery, no Redis — just SQLite + asyncio.
  - Every state transition is written to the DB immediately.
  - On startup, interrupted jobs (status='running') are reset to 'queued'.
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from app.persistence.repository import JobRepository, ProjectRepository
from app.orchestration.dag import StageType

logger = logging.getLogger(__name__)

# How often the worker checks for new queued jobs (seconds)
POLL_INTERVAL = 3

# Dummy video path used for AI Voice mode (no real video needed)
_DUMMY_VIDEO_PATH = str(Path(__file__).resolve().parent.parent / "tmp" / "dummy.mp4")


async def _execute_job(job: dict) -> None:
    """
    Run a single job end-to-end and persist its status at each step.
    """
    job_id = job["job_id"]
    project_id = job["project_id"]
    stage_str = job["stage"]

    # Mark as running immediately so the worker doesn't pick it up again
    job["status"] = "running"
    job["started_at"] = datetime.utcnow().isoformat()
    await JobRepository.save(job)
    logger.info(f"[Worker] Job {job_id} | Stage {stage_str} | RUNNING")

    try:
        stage = StageType(stage_str)
    except ValueError:
        job["status"] = "failed"
        job["error"] = json.dumps({"message": f"Unknown stage: {stage_str}"})
        job["completed_at"] = datetime.utcnow().isoformat()
        await JobRepository.save(job)
        return

    project = await ProjectRepository.load(project_id)
    if project is None:
        job["status"] = "failed"
        job["error"] = json.dumps({"message": f"Project {project_id} not found"})
        job["completed_at"] = datetime.utcnow().isoformat()
        await JobRepository.save(job)
        return

    try:
        if stage == StageType.SCRIPT:
            from app.agents.script_suggestor.agent import ScriptSuggestorAgent
            from app.agents.script_suggestor.schemas import ScriptRequest

            brief = "Generate an engaging creative script"
            # input_override may be stored as JSON in the result field at queue time
            if job.get("result"):
                try:
                    override = json.loads(job["result"]) if isinstance(job["result"], str) else job["result"]
                    brief = override.get("brief", brief)
                except Exception:
                    pass

            agent = ScriptSuggestorAgent()
            request = ScriptRequest(creator_profile=project.creator_profile, brief=brief)
            result = await agent.run(request)
            project.script = result

        elif stage == StageType.STORYBOARD:
            from app.agents.storyboard.agent import StoryboardAgent

            if not project.script:
                raise ValueError("Script required for storyboard generation")

            agent = StoryboardAgent()
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, agent.generate, project.script)
            project.storyboard = result

        elif stage == StageType.AUDIO_AI:
            from app.agents.audio.agent import AudioAgent
            from app.agents.audio.schemas import AudioRequest, AudioInputMode

            if not project.script:
                raise ValueError("Script required for audio generation")

            agent = AudioAgent()
            request = AudioRequest(
                video_path=_DUMMY_VIDEO_PATH,
                mode=AudioInputMode.AI_VOICE,
                project_state=project,
            )
            result = await agent.run(request)
            project.audio_master = result.audio_master

        else:
            logger.warning(f"[Worker] Stage {stage_str} not yet handled by worker, marking complete.")

        # Persist the updated project state
        if stage.value not in project.completed_stages:
            project.completed_stages.append(stage.value)
        await ProjectRepository.save(project)

        job["status"] = "completed"
        job["progress"] = 1.0
        job["result"] = json.dumps({"stage": stage_str, "status": "completed"})
        job["completed_at"] = datetime.utcnow().isoformat()
        await JobRepository.save(job)
        logger.info(f"[Worker] Job {job_id} | Stage {stage_str} | COMPLETED")

    except Exception as exc:
        job["status"] = "failed"
        job["progress"] = 0.0
        job["error"] = json.dumps({"type": type(exc).__name__, "message": str(exc)})
        job["completed_at"] = datetime.utcnow().isoformat()
        await JobRepository.save(job)
        logger.error(f"[Worker] Job {job_id} | Stage {stage_str} | FAILED: {exc}")


async def run_worker_loop() -> None:
    """
    Main worker loop. Started via asyncio.create_task() in FastAPI's lifespan.
    Polls for queued jobs every POLL_INTERVAL seconds.
    """
    logger.info("[Worker] Started — polling every %ds", POLL_INTERVAL)
    print(f"✓ Background worker started (polling every {POLL_INTERVAL}s)")

    while True:
        try:
            queued = await JobRepository.get_queued_jobs()
            for job in queued:
                # Each job runs concurrently; one slow agent won't block others
                asyncio.create_task(_execute_job(job))
        except Exception as exc:
            logger.error(f"[Worker] Poll error: {exc}")

        await asyncio.sleep(POLL_INTERVAL)
