from typing import List, Optional

from pydantic import BaseModel, Field


class MediaAsset(BaseModel):
    asset_id: str

    file_name: str

    file_path: str

    asset_type: str

    duration: Optional[float] = None

    fps: Optional[float] = None

    sample_rate: Optional[int] = None

    channels: Optional[int] = None

    checksum: Optional[str] = None


class MediaManifest(BaseModel):
    assets: List[MediaAsset] = Field(default_factory=list)

    normalized: bool = False

    source_format: Optional[str] = None