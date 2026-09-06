"""
Phase 4 + 5: Persistent Async Worker
- Polls the SQLite `jobs` table every POLL_INTERVAL seconds.
- Phase 5 addition: checks for pending YELLOW compliance blocks before running a job,
  and runs ComplianceDecorator after each stage, saving the result to the DB.
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from app.persistence.repository import (
    JobRepository,
    ProjectRepository,
    ComplianceCheckpointRepository,
)
from app.orchestration.dag import StageType
from app.orchestration.compliance_decorator import ComplianceDecorator
from app.agents.compliance.agent import ComplianceAgent

logger = logging.getLogger(__name__)

POLL_INTERVAL = 3  # seconds between DB polls

_DUMMY_VIDEO_PATH = str(Path(__file__).resolve().parent.parent / "tmp" / "dummy.mp4")

# Single shared compliance decorator (stateless between jobs — state is in the DB)
_compliance_agent = ComplianceAgent()
_compliance_decorator = ComplianceDecorator(_compliance_agent)


async def _run_compliance_check(project_id: str, stage: str, project_data: dict) -> None:
    """
    Run compliance after a stage completes and persist the checkpoint to SQLite.
    A YELLOW result will block downstream stages until the human approves it.
    """
    try:
        checkpoint = await _compliance_decorator.check(stage, project_data)
        if checkpoint is None:
            return  # stage doesn't require compliance (e.g. CREATED)

        await ComplianceCheckpointRepository.save({
            "checkpoint_id": checkpoint.checkpoint_id,
            "project_id": project_id,
            "stage": checkpoint.stage,
            "status": checkpoint.status.value.lower(),   # "green" | "yellow" | "red"
            "report": checkpoint.report.model_dump() if checkpoint.report else None,
            "decisions": [],
            "created_at": checkpoint.created_at,
            "approved_at": None,
        })

        logger.info(
            f"[Worker] Compliance [{stage}] → {checkpoint.status.value}"
        )
        if checkpoint.status.value.upper() == "YELLOW":
            logger.warning(
                f"[Worker] YELLOW compliance on {stage} for project {project_id}. "
                "Downstream stages blocked until approved."
            )
        elif checkpoint.status.value.upper() == "RED":
            logger.error(
                f"[Worker] RED compliance on {stage} for project {project_id}. Pipeline blocked."
            )
    except Exception as exc:
        logger.warning(f"[Worker] Compliance check error (non-blocking): {exc}")


async def _execute_job(job: dict) -> None:
    """
    Run a single job end-to-end and persist its status at each step.
    Phase 5: skips the job if a pending YELLOW block exists for this project.
    """
    job_id = job["job_id"]
    project_id = job["project_id"]
    stage_str = job["stage"]

    # ── Phase 5: Pre-run YELLOW block check ──────────────────────────────
    pending = await ComplianceCheckpointRepository.get_pending(project_id)
    if pending:
        logger.info(
            f"[Worker] Job {job_id} ({stage_str}) skipped — "
            f"waiting for approval on checkpoint(s): "
            f"{[p['checkpoint_id'] for p in pending]}"
        )
        return  # Leave as 'queued'; retry on next poll after human approves

    # ── Mark running ─────────────────────────────────────────────────────
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

    # Track what data was produced for the compliance check
    compliance_data: dict = {}

    try:
        if stage == StageType.SCRIPT:
            from app.agents.script_suggestor.agent import ScriptSuggestorAgent
            from app.agents.script_suggestor.schemas import ScriptRequest

            brief = "Generate an engaging creative script"
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
            compliance_data = {"script": result}

        elif stage == StageType.STORYBOARD:
            from app.agents.storyboard.agent import StoryboardAgent

            if not project.script:
                raise ValueError("Script required for storyboard generation")

            agent = StoryboardAgent()
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, agent.generate, project.script)
            project.storyboard = result
            compliance_data = {"storyboard": result}

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
            compliance_data = {"audio": result.audio_master}

        else:
            logger.warning(f"[Worker] Stage {stage_str} not yet handled by worker.")

        # Persist the updated project state
        if stage.value not in project.completed_stages:
            project.completed_stages.append(stage.value)
        await ProjectRepository.save(project)

        # ── Phase 5: Post-stage compliance check ─────────────────────────
        if compliance_data:
            await _run_compliance_check(project_id, stage_str, compliance_data)

        job["status"] = "completed"
        job["progress"] = 1.0
        job["result"] = json.dumps({"stage": stage_str, "status": "completed"})
        job["completed_at"] = datetime.utcnow().isoformat()
        await JobRepository.save(job)
        logger.info(f"[Worker] Job {job_id} | Stage {stage_str} | COMPLETED ✓")

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
                # Each job runs concurrently
                asyncio.create_task(_execute_job(job))
        except Exception as exc:
            logger.error(f"[Worker] Poll error: {exc}")

        await asyncio.sleep(POLL_INTERVAL)
