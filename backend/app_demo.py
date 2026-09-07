"""
Minimal working demo: create project → run workflow stages
Phase 1-2 combined: DAG + Project State + API Routes (simplified)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime
import json
import sqlite3
from pathlib import Path

# ============ DATABASE SETUP ============

DB_PATH = Path(__file__).parent / "cinema.db"

def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            project_name TEXT,
            audio_mode TEXT,
            completed_stages JSON,
            blocked_stages JSON,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            project_id TEXT,
            stage TEXT,
            status TEXT,
            started_at TEXT,
            completed_at TEXT
        )
    """)

    conn.commit()
    conn.close()

def get_db():
    """Get DB connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============ DAG DEFINITION ============

class StageType:
    CREATED = "CREATED"
    SCRIPT = "SCRIPT"
    STORYBOARD = "STORYBOARD"
    AUDIO_AI = "AUDIO_AI"
    AUDIO_CREATOR = "AUDIO_CREATOR"
    SYNC = "SYNC"
    MEDIA_UPLOAD = "MEDIA_UPLOAD"
    DUBBING = "DUBBING"

class DAG:
    """Minimal DAG: stage dependencies"""
    DEPS = {
        StageType.SCRIPT: [StageType.CREATED],
        StageType.STORYBOARD: [StageType.SCRIPT],
        StageType.AUDIO_AI: [StageType.SCRIPT],
        StageType.AUDIO_CREATOR: [StageType.SYNC],
        StageType.SYNC: [StageType.MEDIA_UPLOAD, StageType.SCRIPT],
        StageType.DUBBING: [StageType.AUDIO_AI, StageType.AUDIO_CREATOR],
    }

    @staticmethod
    def get_ready_stages(completed: List[str]) -> List[str]:
        """Get stages that can run now"""
        completed_set = set(completed)
        ready = []

        for stage, deps in DAG.DEPS.items():
            if stage not in completed_set and set(deps).issubset(completed_set):
                ready.append(stage)

        return ready

    @staticmethod
    def check_dependencies(stage: str, completed: List[str]) -> tuple[bool, List[str]]:
        """Check if stage dependencies are satisfied"""
        deps = DAG.DEPS.get(stage, [])
        completed_set = set(completed)
        missing = [d for d in deps if d not in completed_set]
        return len(missing) == 0, missing

# ============ REQUEST/RESPONSE MODELS ============

class CreateProjectRequest(BaseModel):
    project_name: str
    audio_mode: str = "AI_VOICE"

class InvokeStageRequest(BaseModel):
    input: Optional[dict] = None

# ============ FASTAPI APP ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("✓ Database initialized")
    yield

app = FastAPI(
    title="Agentic Cinema",
    description="Multi-agent workflow platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ ENDPOINTS ============

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/projects")
async def create_project(req: CreateProjectRequest):
    """Create project"""
    project_id = str(uuid.uuid4())[:8]

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO projects (project_id, project_name, audio_mode, completed_stages, blocked_stages, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        project_id,
        req.project_name,
        req.audio_mode,
        json.dumps(["CREATED"]),
        json.dumps([]),
        datetime.utcnow().isoformat(),
    ))
    conn.commit()
    conn.close()

    ready = DAG.get_ready_stages(["CREATED"])

    return {
        "project_id": project_id,
        "status": "created",
        "completed_stages": ["CREATED"],
        "ready_stages": ready,
    }

@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get project state"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    completed = json.loads(row["completed_stages"])
    ready = DAG.get_ready_stages(completed)

    return {
        "project_id": project_id,
        "project_name": row["project_name"],
        "audio_mode": row["audio_mode"],
        "completed_stages": completed,
        "ready_stages": ready,
        "created_at": row["created_at"],
    }

@app.post("/projects/{project_id}/stages/{stage_name}")
async def invoke_stage(project_id: str, stage_name: str, req: InvokeStageRequest):
    """Invoke stage"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    completed = json.loads(row["completed_stages"])

    # Check dependencies
    satisfied, missing = DAG.check_dependencies(stage_name, completed)
    if not satisfied:
        ready = DAG.get_ready_stages(completed)
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Cannot run {stage_name}. Missing: {missing}. Ready: {ready}"
        )

    # Create job
    job_id = str(uuid.uuid4())[:12]
    cursor.execute("""
        INSERT INTO jobs (job_id, project_id, stage, status, started_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (job_id, project_id, stage_name, "running", datetime.utcnow().isoformat(), None))

    # Mark stage as completed
    completed.append(stage_name)
    cursor.execute("""
        UPDATE projects SET completed_stages = ? WHERE project_id = ?
    """, (json.dumps(completed), project_id))

    conn.commit()
    conn.close()

    return {
        "project_id": project_id,
        "stage": stage_name,
        "job_id": job_id,
        "status": "started",
        "ready_stages": DAG.get_ready_stages(completed),
    }

@app.get("/projects/{project_id}/jobs/{job_id}")
async def get_job(project_id: str, job_id: str):
    """Get job status"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job_id,
        "stage": row["stage"],
        "status": row["status"],
        "started_at": row["started_at"],
    }

@app.get("/projects/{project_id}/dag")
async def get_dag(project_id: str):
    """Get workflow DAG"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT completed_stages FROM projects WHERE project_id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    completed = json.loads(row["completed_stages"])
    ready = set(DAG.get_ready_stages(completed))
    completed_set = set(completed)

    nodes = []
    for stage in [StageType.CREATED, StageType.SCRIPT, StageType.STORYBOARD, StageType.AUDIO_AI, StageType.AUDIO_CREATOR, StageType.SYNC, StageType.MEDIA_UPLOAD, StageType.DUBBING]:
        if stage in completed_set:
            status = "completed"
        elif stage in ready:
            status = "ready"
        else:
            status = "waiting"
        nodes.append({"stage": stage, "status": status})

    edges = []
    for target, sources in DAG.DEPS.items():
        for source in sources:
            edges.append({"source": source, "target": target})

    return {"nodes": nodes, "edges": edges}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
