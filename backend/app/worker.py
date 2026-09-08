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
    MediaRepository,
)
from app.orchestration.dag import StageType
from app.orchestration.compliance_decorator import ComplianceDecorator
from app.agents.compliance.agent import ComplianceAgent

logger = logging.getLogger(__name__)

POLL_INTERVAL = 3  # seconds between DB polls



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
            "report": checkpoint.report.model_dump(mode='json') if checkpoint.report else None,
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
            
            target_audience = None
            genre = None
            tone = None
            language = None
            if project.deal_context and project.deal_context.deal_terms:
                genre = project.deal_context.deal_terms.get("genre")
                target_audience = project.deal_context.deal_terms.get("target_audience")
                tone = project.deal_context.deal_terms.get("tone")
            if project.workflow_config and project.workflow_config.target_locales:
                language = project.workflow_config.target_locales[0]

            agent = ScriptSuggestorAgent()
            request = ScriptRequest(
                creator_profile=project.creator_profile,
                brief=brief,
                target_audience=target_audience,
                genre=genre,
                tone=tone,
                language=language,
                research_required=True
            )
            result = await agent.run(request)
            project.script = result
            compliance_data = {"script": result}

        elif stage == StageType.STORYBOARD:
            from app.agents.storyboard.agent import StoryboardAgent
            from app.agents.storyboard.schemas import ProductionConstraints

            if not project.script:
                raise ValueError("Script required for storyboard generation")

            agent = StoryboardAgent()
            
            cameras = []
            if project.creator_profile and project.creator_profile.equipment:
                cameras = project.creator_profile.equipment
                
            platform = "YouTube"
            if project.creator_profile and project.creator_profile.platform:
                platform = project.creator_profile.platform
                
            constraints = ProductionConstraints(
                cameras=cameras,
                platform=platform
            )
            
            # Use generate_full_pipeline instead of generate, but skip real image gen to save tokens
            pipeline_result = await agent.generate_full_pipeline(
                script=project.script,
                production_constraints=constraints,
                project_id=project_id,
                generate_thumbnails=True,
                generate_shots=True,
                generate_concept_art=False
            )
            
            shot_plan = pipeline_result["storyboard"]
            assets = pipeline_result.get("assets")
            if assets and hasattr(assets, "storyboard_assets"):
                asset_map = {a.shot_id: a.image_path for a in assets.storyboard_assets if a.shot_id}
                for shot in shot_plan.shots:
                    if shot.shot_id in asset_map:
                        shot.generated_image = asset_map[shot.shot_id]
                # Save storyboard shot keyframes to DB
                for asset in assets.storyboard_assets:
                    if asset.shot_id and asset.image_path and Path(asset.image_path).exists():
                        try:
                            img_data = Path(asset.image_path).read_bytes()
                            await MediaRepository.save_media(
                                project_id=project_id,
                                media_id=f"{project_id}_shot_{asset.shot_id}",
                                asset_type="storyboard",
                                filename=f"{asset.shot_id}.png",
                                content_type="image/png",
                                data=img_data,
                                metadata={"shot_id": asset.shot_id, "prompt": getattr(asset, "prompt", None)},
                            )
                        except Exception as exc:
                            logger.error("[Worker] Error saving storyboard asset %s to DB: %s", asset.shot_id, exc)

            # Save thumbnails to DB
            if assets and hasattr(assets, "thumbnails"):
                for thumb in assets.thumbnails:
                    if thumb.image_path and Path(thumb.image_path).exists():
                        try:
                            thumb_data = Path(thumb.image_path).read_bytes()
                            await MediaRepository.save_media(
                                project_id=project_id,
                                media_id=f"{project_id}_thumbnail_{thumb.variant}",
                                asset_type="video_thumbnail",
                                filename=f"thumbnail_{thumb.variant}.png",
                                content_type="image/png",
                                data=thumb_data,
                                metadata={"shot_id": thumb.variant, "variant": thumb.variant},
                            )
                        except Exception as exc:
                            logger.error("[Worker] Error saving thumbnail %s to DB: %s", thumb.variant, exc)

            # Also ensure any thumbnails written to disk directory are persisted to DB
            thumb_dir = Path(f"storage/storyboard/generated/{project_id}/thumbnails")
            if thumb_dir.exists():
                for p in thumb_dir.glob("*.png"):
                    try:
                        variant = p.stem.replace("thumbnail_", "")
                        await MediaRepository.save_media(
                            project_id=project_id,
                            media_id=f"{project_id}_{p.stem}",
                            asset_type="video_thumbnail",
                            filename=p.name,
                            content_type="image/png",
                            data=p.read_bytes(),
                            metadata={"shot_id": variant, "variant": variant},
                        )
                    except Exception as exc:
                        logger.error("[Worker] Error saving thumbnail file %s to DB: %s", p.name, exc)

            if assets and assets.errors:
                logger.error("[Storyboard] Asset generation errors: %s", assets.errors)           
            project.storyboard = shot_plan
            compliance_data = {"storyboard": shot_plan}

        elif stage in (StageType.AUDIO_AI, StageType.AUDIO_CREATOR):
            from app.agents.audio.agent import AudioAgent
            from app.agents.audio.schemas import AudioRequest, AudioInputMode

            if not project.script:
                raise ValueError("Script required for audio generation")

            audio_mode = AudioInputMode.AI_VOICE
            video_path_to_use = None
            output_dir = str(Path(__file__).resolve().parent.parent / "storage" / "audio" / project_id)

            if stage == StageType.AUDIO_CREATOR:
                audio_mode = AudioInputMode.CREATOR_VOICE
                if project.media_manifest and project.media_manifest.assets:
                    videos = [a for a in project.media_manifest.assets if a.asset_type.lower() == "video"]
                    if videos:
                        video_path_to_use = videos[0].file_path
                if not video_path_to_use:
                    raise ValueError("Creator voice mode requires an uploaded video. Upload media first.")

            agent = AudioAgent()
            request = AudioRequest(
                video_path=video_path_to_use,
                output_dir=output_dir,
                mode=audio_mode,
                project_state=project,
            )
            result = await agent.run(request)
            project.audio_master = result.audio_master
            compliance_data = {"audio": result.audio_master}

            # Save audio master to DB
            if project.audio_master and project.audio_master.file_path and Path(project.audio_master.file_path).exists():
                try:
                    audio_bytes = Path(project.audio_master.file_path).read_bytes()
                    await MediaRepository.save_media(
                        project_id=project_id,
                        media_id=f"{project_id}_audio_master",
                        asset_type="audio_master",
                        filename="master.wav",
                        content_type="audio/wav",
                        data=audio_bytes,
                        metadata={"duration": project.audio_master.duration, "mode": stage.value},
                    )
                except Exception as exc:
                    logger.error("[Worker] Error saving audio master to DB: %s", exc)

        elif stage == StageType.SYNC:
            from app.agents.syncer.agent import SyncerAgent
            from app.agents.syncer.schemas import SyncRequest, AudioClip

            if not project.script or not project.audio_master:
                raise ValueError("Script and Audio Master required for Syncer")

            video_path_to_use = str(Path(__file__).resolve().parent.parent / "tmp" / "dummy.mp4")
            if project.media_manifest and project.media_manifest.assets:
                # First try to find a video
                videos = [a for a in project.media_manifest.assets if a.asset_type.lower() == "video"]
                if videos:
                    video_path_to_use = videos[0].file_path
                else:
                    # If they uploaded an audio file (or something else), we still have no video
                    logger.warning("[Worker] No video found in media manifest, falling back to dummy video.")

            audio_clips = []
            for i, beat in enumerate(project.script.beats):
                if i < len(project.audio_master.segments):
                    segment = project.audio_master.segments[i]
                    # If AI voice was generated, it produces a single master audio track
                    # For creator voice, we might use the master track or individual clips
                    audio_clips.append(AudioClip(
                        beat_id=beat.beat_id,
                        file_path=project.audio_master.file_path,
                        duration=(segment.end_time - segment.start_time)
                    ))

            agent = SyncerAgent()
            request = SyncRequest(
                video_path=video_path_to_use,
                script_beats=project.script.beats,
                audio_clips=audio_clips
            )
            result = await agent.run(request)
            project.sync_report = result
            compliance_data = {"sync": result}

        elif stage == StageType.DUBBING:
            from app.agents.cultural_dub.agent import CulturalDubAgent
            from app.agents.cultural_dub.schemas import DubRequest, TargetLocale

            if not project.audio_master:
                raise ValueError("Audio Master required for Dubbing")

            target_locales = []
            
            # 1. Check if a dynamic language was passed in from the chat intent
            dynamic_lang = job.get("action", {}).get("params", {}).get("target_language")
            if dynamic_lang:
                target_locales.append(TargetLocale(language=dynamic_lang, geography="Generic"))
            
            # 2. Otherwise fallback to workflow config
            if not target_locales and project.workflow_config and project.workflow_config.target_locales:
                for loc in project.workflow_config.target_locales:
                    target_locales.append(TargetLocale(language=loc, geography=loc))
            
            # 3. Ultimate fallback
            if not target_locales:
                target_locales.append(TargetLocale(language="hi", geography="IN"))

            agent = CulturalDubAgent()
            request = DubRequest(
                project_id=project_id,
                audio_master=project.audio_master,
                target_locales=target_locales,
                generate_audio=True
            )
            result = await agent.run(request)
            if getattr(result, "degraded_reasons", None):
                logger.error("[Dubbing] degraded: %s", result.degraded_reasons)
            project.dub_tracks = result.tracks
            compliance_data = {"dubbing": result}

            # Save dub tracks to DB
            if project.dub_tracks:
                for track in project.dub_tracks:
                    if track.audio_path and Path(track.audio_path).exists():
                        try:
                            dub_bytes = Path(track.audio_path).read_bytes()
                            locale_key = f"{track.language}-{track.geography}"
                            await MediaRepository.save_media(
                                project_id=project_id,
                                media_id=f"{project_id}_dub_{track.language}_{track.geography}",
                                asset_type="dub_track",
                                filename=f"dub_{track.language}_{track.geography}.wav",
                                content_type="audio/wav",
                                data=dub_bytes,
                                metadata={
                                    "language": locale_key,
                                    "lang": track.language,
                                    "geo": track.geography,
                                },
                            )
                        except Exception as exc:
                            logger.error("[Worker] Error saving dub track %s to DB: %s", track.language, exc)

        elif stage == StageType.CREATOR_SCOUT:
            from app.agents.creator_scout.agent import CreatorScoutAgent
            from app.agents.creator_scout.schemas import CreatorScoutRequest

            context = job.get("action", {}).get("params", {}).get("creator_context")
            
            request = CreatorScoutRequest(
                creator_id="dynamic_creator_1",
                creator_name="Dynamic Creator",
                platforms=["YouTube", "TikTok"],
                niche=context or "Cinematic storytelling and filmmaking",
                categories_of_interest=["cameras", "camera lenses", "audio gear", "video editing software"],
                target_geography="India",
                audience_summary="Broad demographic" if not context else context,
                median_views=500000,
                engagement_rate=0.05
            )

            agent = CreatorScoutAgent()
            result = await agent.run(request)
            project.opportunity_queue = result
            compliance_data = {"creator_scout": result}

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
