"""
Minimal DAG-based workflow definition.
Stages and their dependencies.
"""
from enum import Enum
from typing import Set, Dict, Optional, List
from pydantic import BaseModel


class StageType(str, Enum):
    """Workflow stages as DAG nodes"""
    CREATED = "CREATED"
    SCRIPT = "SCRIPT"
    STORYBOARD = "STORYBOARD"
    AUDIO_AI = "AUDIO_AI"
    AUDIO_CREATOR = "AUDIO_CREATOR"
    DUBBING = "DUBBING"
    SYNC = "SYNC"
    MEDIA_UPLOAD = "MEDIA_UPLOAD"
    CREATOR_SCOUT = "CREATOR_SCOUT"
    COMPLETED = "COMPLETED"


class StageDependency(BaseModel):
    source: StageType
    target: StageType
    condition: Optional[str] = None


class WorkflowDAG:
    """Simple DAG for workflow execution"""

    def __init__(self):
        self.dependencies: List[StageDependency] = []
        self._build_dag()

    def _build_dag(self):
        """Define workflow dependencies"""
        # SCRIPT depends on CREATED
        self.dependencies.append(StageDependency(source=StageType.CREATED, target=StageType.SCRIPT))

        # STORYBOARD depends on SCRIPT
        self.dependencies.append(StageDependency(source=StageType.SCRIPT, target=StageType.STORYBOARD))

        # AUDIO_AI depends on SCRIPT (for AI voice mode)
        self.dependencies.append(StageDependency(source=StageType.SCRIPT, target=StageType.AUDIO_AI))

        # AUDIO_CREATOR depends on SYNC (creator voice mode)
        self.dependencies.append(StageDependency(source=StageType.SYNC, target=StageType.AUDIO_CREATOR))

        # SYNC depends on MEDIA_UPLOAD and SCRIPT
        self.dependencies.append(StageDependency(source=StageType.MEDIA_UPLOAD, target=StageType.SYNC))
        self.dependencies.append(StageDependency(source=StageType.SCRIPT, target=StageType.SYNC))

        # DUBBING depends on either AUDIO path
        self.dependencies.append(StageDependency(source=StageType.AUDIO_AI, target=StageType.DUBBING))
        self.dependencies.append(StageDependency(source=StageType.AUDIO_CREATOR, target=StageType.DUBBING))

    def get_dependencies(self, stage: StageType) -> Set[StageType]:
        """Get immediate dependencies for a stage"""
        deps = set()
        for dep in self.dependencies:
            if dep.target == stage and not dep.condition:
                deps.add(dep.source)
        return deps

    def get_ready_stages(self, completed_stages: Set[StageType]) -> Set[StageType]:
        """Get stages that can run now (dependencies satisfied)"""
        ready = set()

        # Check all stages
        for stage in StageType:
            if stage in completed_stages:
                continue

            deps = self.get_dependencies(stage)
            if deps.issubset(completed_stages):
                ready.add(stage)

        return ready
