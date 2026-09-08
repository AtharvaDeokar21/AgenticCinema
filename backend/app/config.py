from pathlib import Path
import os

STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT", Path(__file__).resolve().parent.parent / "storage"))
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)