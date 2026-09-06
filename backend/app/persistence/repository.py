"""
Minimal persistence layer for projects.
SQLite-based repository for ProjectState.
"""
import json
import sqlite3
from datetime import datetime
from typing import Optional
from pathlib import Path

from ..shared.models.project import ProjectState


DB_PATH = Path(__file__).parent.parent.parent / "cinema.db"


def get_db():
    """Get SQLite connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database schema"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            creator_profile JSON,
            deal_context JSON,
            workflow_config JSON,
            script JSON,
            storyboard JSON,
            media_manifest JSON,
            sync_report JSON,
            audio_master JSON,
            dub_tracks JSON,
            clearance_report JSON,
            current_stage TEXT,
            completed_stages JSON,
            blocked_stages JSON,
            errors JSON,
            created_at TEXT,
            updated_at TEXT,
            version INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            progress REAL DEFAULT 0.0,
            phase TEXT,
            started_at TEXT,
            completed_at TEXT,
            result JSON,
            error JSON,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        )
    """)

    conn.commit()
    conn.close()


class ProjectRepository:
    """CRUD operations for ProjectState"""

    @staticmethod
    async def save(project: ProjectState) -> None:
        """Save or update project"""
        conn = get_db()
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT OR REPLACE INTO projects
            (project_id, project_name, creator_profile, deal_context, workflow_config,
             script, storyboard, media_manifest, sync_report, audio_master, dub_tracks,
             clearance_report, current_stage, completed_stages, blocked_stages, errors,
             created_at, updated_at, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project.project_id,
            project.project_name,
            project.creator_profile.json() if project.creator_profile else None,
            project.deal_context.json() if project.deal_context else None,
            project.workflow_config.json(),
            project.script.json() if project.script else None,
            project.storyboard.json() if project.storyboard else None,
            project.media_manifest.json() if project.media_manifest else None,
            project.sync_report.json() if project.sync_report else None,
            project.audio_master.json() if project.audio_master else None,
            json.dumps([t.dict() for t in project.dub_tracks]) if project.dub_tracks else None,
            project.clearance_report.json() if project.clearance_report else None,
            project.current_stage.value if project.current_stage else None,
            json.dumps(project.completed_stages),
            json.dumps(project.blocked_stages),
            json.dumps(project.errors),
            project.created_at.isoformat(),
            now,
            project.version,
        ))

        conn.commit()
        conn.close()

    @staticmethod
    async def load(project_id: str) -> Optional[ProjectState]:
        """Load project by ID"""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        # Reconstruct ProjectState from JSON
        return ProjectState(
            project_id=row["project_id"],
            project_name=row["project_name"],
            creator_profile=None,  # Simplified for demo
            deal_context=None,
            script=None,
            storyboard=None,
            media_manifest=None,
            sync_report=None,
            audio_master=None,
            dub_tracks=[],
            clearance_report=None,
            current_stage=row["current_stage"],
            completed_stages=json.loads(row["completed_stages"]) if row["completed_stages"] else [],
            blocked_stages=json.loads(row["blocked_stages"]) if row["blocked_stages"] else [],
            errors=json.loads(row["errors"]) if row["errors"] else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    async def list_all() -> list:
        """List all projects"""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT project_id, project_name, created_at FROM projects ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]


class JobRepository:
    """CRUD operations for Jobs"""

    @staticmethod
    async def save(job: dict) -> None:
        """Save or update job"""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO jobs
            (job_id, project_id, stage, status, progress, phase, started_at, completed_at, result, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job["job_id"],
            job["project_id"],
            job["stage"],
            job["status"],
            job.get("progress", 0.0),
            job.get("phase"),
            job.get("started_at"),
            job.get("completed_at"),
            json.dumps(job.get("result")) if job.get("result") else None,
            json.dumps(job.get("error")) if job.get("error") else None,
        ))

        conn.commit()
        conn.close()

    @staticmethod
    async def load(job_id: str) -> Optional[dict]:
        """Load job by ID"""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return dict(row)

    @staticmethod
    async def get_by_project(project_id: str) -> list:
        """Get all jobs for a project"""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM jobs WHERE project_id = ? ORDER BY started_at DESC", (project_id,))
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]
