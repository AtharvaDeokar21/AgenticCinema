"""
MINIMAL WORKING ORCHESTRATION
Simple, direct integration of existing agents.
No complex abstractions - just make it work.
"""
import json
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

# Simplified stage definitions
class Stage(str, Enum):
    SCRIPT = "SCRIPT"
    STORYBOARD = "STORYBOARD"
    AUDIO_AI = "AUDIO_AI"
    DUBBING = "DUBBING"
    SYNC = "SYNC"
    AUDIO_CREATOR = "AUDIO_CREATOR"

# Simple DAG: what must complete before what
STAGE_DEPENDENCIES = {
    Stage.SCRIPT: [],
    Stage.STORYBOARD: [Stage.SCRIPT],
    Stage.AUDIO_AI: [Stage.SCRIPT],
    Stage.DUBBING: [Stage.AUDIO_AI],
    Stage.SYNC: [Stage.SCRIPT],
    Stage.AUDIO_CREATOR: [Stage.SYNC],
}

class SimpleOrchestrator:
    """Minimal orchestrator: tracks state, checks dependencies, invokes agents"""

    def __init__(self):
        self.state = {
            "completed": [],
            "in_progress": None,
            "outputs": {},
            "errors": []
        }

    def can_run(self, stage: Stage) -> bool:
        """Check if stage dependencies are satisfied"""
        deps = STAGE_DEPENDENCIES.get(stage, [])
        return all(str(d) in [str(s) for s in self.state["completed"]] for d in deps)

    def get_ready_stages(self) -> list:
        """Get stages that can run now"""
        return [s for s in Stage if self.can_run(s) and str(s) not in [str(c) for c in self.state["completed"]]]

    async def run_stage(self, stage: Stage, project_data: Dict[str, Any]):
        """Run a stage, return output"""
        if not self.can_run(stage):
            deps = STAGE_DEPENDENCIES[stage]
            raise ValueError(f"{stage} requires: {deps}")

        self.state["in_progress"] = stage

        try:
            if stage == Stage.SCRIPT:
                return await self._run_script(project_data)
            elif stage == Stage.STORYBOARD:
                return await self._run_storyboard(project_data)
            elif stage == Stage.AUDIO_AI:
                return await self._run_audio_ai(project_data)
            elif stage == Stage.DUBBING:
                return await self._run_dubbing(project_data)
            else:
                raise ValueError(f"Unknown stage: {stage}")

        except Exception as e:
            self.state["errors"].append({"stage": stage, "error": str(e)})
            raise
        finally:
            self.state["in_progress"] = None
            self.state["completed"].append(stage)

    async def _run_script(self, project_data):
        """Invoke Script agent"""
        from app.agents.script_suggestor.agent import ScriptSuggestorAgent
        from app.agents.script_suggestor.schemas import ScriptRequest

        agent = ScriptSuggestorAgent()
        request = ScriptRequest(
            creator_profile=project_data.get("creator_profile"),
            brief=project_data.get("brief", "Create an engaging product launch script"),
            research_enabled=False,
        )
        result = await agent.run(request)
        self.state["outputs"]["script"] = result
        return result

    async def _run_storyboard(self, project_data):
        """Invoke Storyboard agent"""
        from app.agents.storyboard.agent import StoryboardAgent

        script = self.state["outputs"]["script"]
        if not script:
            raise ValueError("Script required for storyboard")

        agent = StoryboardAgent()
        # Run in executor since it's synchronous
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, agent.generate, script)
        self.state["outputs"]["storyboard"] = result
        return result

    async def _run_audio_ai(self, project_data):
        """Invoke Audio agent (AI Voice mode)"""
        from app.agents.audio.agent import AudioAgent
        from app.agents.audio.schemas import AudioRequest, AudioInputMode

        script = self.state["outputs"]["script"]
        if not script:
            raise ValueError("Script required for audio")

        agent = AudioAgent()
        request = AudioRequest(
            video_path="C:\Atharva\AgenticCinema\backend\tmp\dummy.mp4",  # Required but not used in AI mode
            mode=AudioInputMode.AI_VOICE,
            project_state=project_data,
        )
        result = await agent.run(request)
        self.state["outputs"]["audio"] = result
        return result

    async def _run_dubbing(self, project_data):
        """Invoke Dubbing agent"""
        from app.agents.cultural_dub.agent import CulturalDubAgent
        from app.agents.cultural_dub.schemas import DubRequest

        audio = self.state["outputs"]["audio"]
        if not audio or not audio.audio_master:
            raise ValueError("Audio required for dubbing")

        agent = CulturalDubAgent()
        target_locales = project_data.get("target_locales", ["es", "fr"])
        request = DubRequest(
            audio_master=audio.audio_master,
            target_locales=target_locales,
        )
        result = await agent.run(request)
        self.state["outputs"]["dubbing"] = result
        return result
