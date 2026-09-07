import os
import pytest
import sqlite3
import httpx
from datetime import datetime
from asgi_lifespan import LifespanManager
import asyncio

# Override DB path for tests
from pathlib import Path
import app.persistence.repository
app.persistence.repository.DB_PATH = Path("cinema_test.db")

# Mock the poll interval for tests so they run instantly
import app.worker
app.worker.POLL_INTERVAL = 0.1

from app.main import app as fastapi_app
from app.persistence.repository import init_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_db()
    yield
    if os.path.exists("cinema_test.db"):
        os.remove("cinema_test.db")

@pytest.fixture(autouse=True)
def clean_db():
    conn = sqlite3.connect("cinema_test.db")
    conn.execute("DELETE FROM jobs")
    conn.execute("DELETE FROM compliance_checkpoints")
    conn.execute("DELETE FROM projects")
    conn.commit()
    conn.close()

import pytest_asyncio

@pytest_asyncio.fixture
async def async_client():
    async with LifespanManager(fastapi_app):
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client

from unittest.mock import AsyncMock

class MockGeminiClient:
    def __init__(self, *args, **kwargs):
        pass

    async def generate_content(self, prompt, **kwargs):
        return "mock text"

    def generate_structured(self, *args, **kwargs):
        # schema can be positional or keyword
        schema = kwargs.get("schema") or kwargs.get("response_schema")
        if not schema and len(args) >= 2:
            schema = args[1]
        
        from app.shared.models.script import ScriptVersion, ScriptBeat
        from app.shared.models.storyboard import ShotPlan, Shot
        from app.shared.models.compliance import ClearanceReport, ReportStatus
        from app.agents.storyboard.schemas import ProductionAwareStoryboard, ShotProductionPlan
        
        if schema == ScriptVersion:
            return ScriptVersion(version=1, created_at=datetime.utcnow(), full_text="Test Script", beats=[ScriptBeat(beat_id="b1", start_time=0.0, end_time=5.0, text="Hello world")])
        elif schema == ShotPlan:
            return ShotPlan(version=1, shots=[Shot(shot_id="s1", beat_id="b1", start_time=0.0, end_time=5.0, visual_description="A cool shot")])
        elif schema == ProductionAwareStoryboard:
            return ProductionAwareStoryboard(
                storyboard=ShotPlan(version=1, shots=[Shot(shot_id="s1", beat_id="b1", start_time=0.0, end_time=5.0, visual_description="A cool shot")]),
                production_plans=[ShotProductionPlan(shot_id="s1", feasibility="Easy")],
                overall_issues=[]
            )
        elif schema == ClearanceReport:
            prompt = str(args[0]) if args else str(kwargs.get("prompt", ""))
            if "mock_yellow" in prompt.lower():
                status = ReportStatus.PASSED_WITH_CONDITIONS
            else:
                status = ReportStatus.PASSED
            return ClearanceReport(status=status, stage="TEST")
        return schema() if schema else None

@pytest.fixture(autouse=True)
def mock_gemini(monkeypatch):
    monkeypatch.setattr("app.shared.tools.gemini.client.GeminiClient", MockGeminiClient)
    
    # Also patch the global instance created in app.worker at import time
    import app.worker
    if hasattr(app.worker, "_compliance_agent"):
        app.worker._compliance_agent.gemini = MockGeminiClient()

    from app.agents.storyboard.agent import StoryboardAgent
    from app.shared.models.storyboard import ShotPlan, Shot
    from app.agents.storyboard.schemas import StoryboardAssetGenerationResult
    
    async def mock_storyboard_pipeline(self, *args, **kwargs):
        shot_plan = ShotPlan(
            version=1, 
            shots=[Shot(shot_id="s1", beat_id="b1", start_time=0.0, end_time=5.0, visual_description="A cool shot")]
        )
        return {
            "storyboard": shot_plan,
            "assets": StoryboardAssetGenerationResult(storyboard_assets=[])
        }
        
    monkeypatch.setattr(StoryboardAgent, "generate_full_pipeline", mock_storyboard_pipeline)

    from app.agents.audio.agent import AudioAgent
    from app.agents.audio.schemas import AudioResult
    from app.shared.models.audio import AudioMaster, AudioSegment
    
    async def mock_audio_run(self, request, *args, **kwargs):
        # We need to return segments so Syncer can map them
        segment = AudioSegment(
            segment_id="seg1",
            transcript="Hello world",
            file_path="mock_segment.wav", 
            start_time=0.0, 
            end_time=5.0, 
            duration=5.0
        )
        return AudioResult(
            mode=request.mode,
            status="success",
            source_video_path=request.video_path,
            project_state=request.project_state,
            audio_master=AudioMaster(file_path="dummy.wav", duration=5.0, segments=[segment])
        )
        
    monkeypatch.setattr(AudioAgent, "run", mock_audio_run)
    
    from app.agents.syncer.agent import SyncerAgent
    from app.agents.syncer.schemas import SyncMap, AudioPlacement
    
    async def mock_syncer_run(self, request, *args, **kwargs):
        placements = []
        for clip in request.audio_clips:
            placements.append(AudioPlacement(
                beat_id=clip.beat_id,
                audio_clip_path=clip.file_path,
                video_start_time=0.0,
                video_end_time=5.0,
                mouth_motion_detected=True,
                confidence=1.0
            ))
        return SyncMap(
            video_path=request.video_path,
            video_duration=10.0,
            video_fps=30.0,
            placements=placements,
            target_fps=request.target_fps
        )
        
    monkeypatch.setattr(SyncerAgent, "run", mock_syncer_run)
    
    from app.agents.cultural_dub.agent import CulturalDubAgent
    from app.agents.cultural_dub.schemas import CulturalDubResult, CulturalDubTrackResult
    
    async def mock_dubbing_run(self, request, *args, **kwargs):
        tracks = []
        for loc in request.target_locales:
            tracks.append(CulturalDubTrackResult(
                language=loc.language,
                geography=loc.geography,
                segments=[],
                audio_path="mock_dub.wav"
            ))
        return CulturalDubResult(project_id=request.project_id, tracks=tracks)
        
    monkeypatch.setattr(CulturalDubAgent, "run", mock_dubbing_run)
