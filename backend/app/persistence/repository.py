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

    # Phase 5: persist compliance checkpoints so approvals survive restarts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compliance_checkpoints (
            checkpoint_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,          -- yellow | approved | red | green
            report JSON,                   -- serialised ClearanceReport
            decisions JSON,                -- approval decisions (list)
            created_at TEXT NOT NULL,
            approved_at TEXT,
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
        """Load project by ID, fully deserialising all Pydantic sub-models."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        def _parse(col_name, model_cls):
            raw = row[col_name]
            if not raw:
                return None
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                return model_cls.model_validate(data)
            except Exception:
                return None

        def _parse_list(col_name, model_cls):
            raw = row[col_name]
            if not raw:
                return []
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                return [model_cls.model_validate(item) for item in data]
            except Exception:
                return []

        from ..shared.models.creator import CreatorProfile
        from ..shared.models.deal import DealContext
        from ..shared.models.script import ScriptVersion
        from ..shared.models.storyboard import ShotPlan
        from ..shared.models.media import MediaManifest
        from ..shared.models.sync import SyncReport
        from ..shared.models.audio import AudioMaster
        from ..shared.models.dub import DubTrack
        from ..shared.models.compliance import ClearanceReport

        return ProjectState(
            project_id=row["project_id"],
            project_name=row["project_name"],
            creator_profile=_parse("creator_profile", CreatorProfile),
            deal_context=_parse("deal_context", DealContext),
            script=_parse("script", ScriptVersion),
            storyboard=_parse("storyboard", ShotPlan),
            media_manifest=_parse("media_manifest", MediaManifest),
            sync_report=_parse("sync_report", SyncReport),
            audio_master=_parse("audio_master", AudioMaster),
            dub_tracks=_parse_list("dub_tracks", DubTrack),
            clearance_report=_parse("clearance_report", ClearanceReport),
            current_stage=row["current_stage"] or "CREATED",
            completed_stages=json.loads(row["completed_stages"]) if row["completed_stages"] else [],
            blocked_stages=json.loads(row["blocked_stages"]) if row["blocked_stages"] else [],
            errors=json.loads(row["errors"]) if row["errors"] else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            version=row["version"] or 1,
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

    @staticmethod
    async def get_queued_jobs() -> list:
        """Get all jobs with status='queued' — used by the worker loop."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM jobs WHERE status = 'queued' ORDER BY started_at ASC"
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    async def reset_interrupted_jobs() -> int:
        """
        On server startup, any jobs still marked 'running' were interrupted
        by a crash or restart. Reset them to 'queued' so the worker retries them.
        Returns the number of jobs reset.
        """
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE jobs SET status = 'queued' WHERE status = 'running'"
        )
        count = cursor.rowcount
        conn.commit()
        conn.close()
        if count:
            print(f"⚠ Recovered {count} interrupted job(s) from previous run.")
        return count



class ComplianceCheckpointRepository:
    """
    Phase 5: CRUD operations for compliance checkpoints.
    Checkpoints are persisted so YELLOW blocks survive server restarts.
    """

    @staticmethod
    async def save(checkpoint: dict) -> None:
        """Insert or replace a compliance checkpoint."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO compliance_checkpoints
            (checkpoint_id, project_id, stage, status, report, decisions, created_at, approved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                checkpoint["checkpoint_id"],
                checkpoint["project_id"],
                checkpoint["stage"],
                checkpoint["status"],
                json.dumps(checkpoint.get("report")) if checkpoint.get("report") else None,
                json.dumps(checkpoint.get("decisions", [])),
                checkpoint.get("created_at", datetime.utcnow().isoformat()),
                checkpoint.get("approved_at"),
            ),
        )
        conn.commit()
        conn.close()

    @staticmethod
    async def get_pending(project_id: str) -> list:
        """
        Return all YELLOW checkpoints for a project that have NOT been approved.
        The worker uses this to block downstream stages.
        """
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM compliance_checkpoints
            WHERE project_id = ? AND status = 'yellow' AND approved_at IS NULL
            ORDER BY created_at ASC
            """,
            (project_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    async def approve(checkpoint_id: str, decisions: list) -> bool:
        """
        Flip a YELLOW checkpoint to 'approved' so the worker unblocks.
        Returns True if a row was updated, False if checkpoint not found.
        """
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE compliance_checkpoints
            SET status = 'approved', approved_at = ?, decisions = ?
            WHERE checkpoint_id = ? AND status = 'yellow'
            """,
            (datetime.utcnow().isoformat(), json.dumps(decisions), checkpoint_id),
        )
        updated = cursor.rowcount
        conn.commit()
        conn.close()
        return updated > 0

    @staticmethod
    async def get_all_for_project(project_id: str) -> list:
        """Return all checkpoints for a project (for audit/display)."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM compliance_checkpoints WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
