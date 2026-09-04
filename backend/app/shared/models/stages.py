from enum import Enum


class ProjectStage(str, Enum):
    CREATED = "created"
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    MEDIA = "media"
    AUDIO = "audio"
    DUBBING = "dubbing"
    SYNC = "sync"
    COMPLIANCE = "compliance"
    CREATOR_SCOUT = "creator_scout"
    COMPLETED = "completed"