"""
Production persistence layer for projects.
Supports PostgreSQL (when DATABASE_URL is set) and SQLite (fallback for local dev).
"""
import json
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional, Any, List, Dict, Tuple
from pathlib import Path
from contextlib import contextmanager

try:
    import psycopg
    from psycopg.rows import dict_row
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False

from ..shared.models.project import ProjectState
from ..config.settings import get_settings


DB_PATH = Path(__file__).parent.parent.parent / "cinema.db"


def _get_database_url() -> str:
    settings = get_settings()
    url = getattr(settings, "database_url", "") or os.getenv("DATABASE_URL", "")
    if url.startswith("postgres://"):
        # Fix Render legacy postgres prefix for modern drivers
        url = url.replace("postgres://", "postgresql://", 1)
    return url.strip()


def is_postgres() -> bool:
    url = _get_database_url()
    return bool(url and (url.startswith("postgresql://") or url.startswith("postgres://")))


class DBConnection:
    """Wrapper that normalizes queries and result sets between SQLite and PostgreSQL."""
    def __init__(self, conn, is_pg: bool):
        self.conn = conn
        self.is_pg = is_pg

    def execute(self, query: str, params: Tuple[Any, ...] = ()) -> Any:
        cursor = self.conn.cursor()
        if self.is_pg:
            # Convert '?' placeholders to '%s' for psycopg
            pg_query = query.replace("?", "%s")
            cursor.execute(pg_query, params)
        else:
            cursor.execute(query, params)
        return cursor

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


@contextmanager
def get_db_context():
    """Context manager for DB connections ensuring commit/close across SQLite & Postgres."""
    pg_url = _get_database_url()
    if pg_url and HAS_PSYCOPG:
        try:
            conn = psycopg.connect(pg_url, row_factory=dict_row)
        except Exception as e:
            err_msg = str(e)
            print(f"❌ PostgreSQL Connection Error: {err_msg}")
            if "Network is unreachable" in err_msg or "2406:" in err_msg:
                print("💡 TIP: If using Supabase, make sure to use the 'Connection Pooler' URL (port 6543/5432) which supports IPv4 on Render.")
                print("💡 TIP: If using Render PostgreSQL, use the 'Internal Database URL' instead of the External Database URL.")
            raise
        wrapper = DBConnection(conn, is_pg=True)
        try:
            yield wrapper
            wrapper.commit()
        finally:
            wrapper.close()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        wrapper = DBConnection(conn, is_pg=False)
        try:
            yield wrapper
            wrapper.commit()
        finally:
            wrapper.close()


def init_db():
    """Initialize database schema for SQLite or PostgreSQL."""
    with get_db_context() as db:
        if db.is_pg:
            # PostgreSQL Schema
            db.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    project_name TEXT NOT NULL,
                    creator_profile JSONB,
                    deal_context JSONB,
                    workflow_config JSONB,
                    script JSONB,
                    storyboard JSONB,
                    media_manifest JSONB,
                    sync_report JSONB,
                    audio_master JSONB,
                    dub_tracks JSONB,
                    clearance_report JSONB,
                    opportunity_queue JSONB,
                    current_stage TEXT,
                    completed_stages JSONB,
                    blocked_stages JSONB,
                    errors JSONB,
                    created_at TEXT,
                    updated_at TEXT,
                    version INTEGER DEFAULT 1
                )
            """)

            db.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL DEFAULT 0.0,
                    phase TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    result JSONB,
                    error JSONB
                )
            """)

            db.execute("""
                CREATE TABLE IF NOT EXISTS compliance_checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    report JSONB,
                    decisions JSONB,
                    created_at TEXT NOT NULL,
                    approved_at TEXT
                )
            """)

            db.execute("""
                CREATE TABLE IF NOT EXISTS media (
                    media_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
                    asset_type TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    data BYTEA NOT NULL,
                    metadata JSONB,
                    created_at TEXT NOT NULL
                )
            """)

            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_media_project_type ON media(project_id, asset_type)
            """)
        else:
            # SQLite Schema
            db.execute("""
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
                    opportunity_queue JSON,
                    current_stage TEXT,
                    completed_stages JSON,
                    blocked_stages JSON,
                    errors JSON,
                    created_at TEXT,
                    updated_at TEXT,
                    version INTEGER DEFAULT 1
                )
            """)

            db.execute("""
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

            db.execute("""
                CREATE TABLE IF NOT EXISTS compliance_checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    report JSON,
                    decisions JSON,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                )
            """)

            db.execute("""
                CREATE TABLE IF NOT EXISTS media (
                    media_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    data BLOB NOT NULL,
                    metadata JSON,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                )
            """)

            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_media_project_type ON media(project_id, asset_type)
            """)


class ProjectRepository:
    """CRUD operations for ProjectState (PostgreSQL + SQLite compatible)."""

    @staticmethod
    async def save(project: ProjectState) -> None:
        """Save or update project."""
        now = datetime.now(timezone.utc).isoformat()
        creator_json = project.creator_profile.model_dump_json() if project.creator_profile else None
        deal_json = project.deal_context.model_dump_json() if project.deal_context else None
        workflow_json = project.workflow_config.model_dump_json() if project.workflow_config else None
        script_json = project.script.model_dump_json() if project.script else None
        storyboard_json = project.storyboard.model_dump_json() if project.storyboard else None
        manifest_json = project.media_manifest.model_dump_json() if project.media_manifest else None
        sync_json = project.sync_report.model_dump_json() if project.sync_report else None
        audio_json = project.audio_master.model_dump_json() if project.audio_master else None
        dub_json = json.dumps([t.model_dump() for t in project.dub_tracks]) if project.dub_tracks else None
        clearance_json = project.clearance_report.model_dump_json() if project.clearance_report else None
        opp_json = project.opportunity_queue.model_dump_json() if project.opportunity_queue else None

        with get_db_context() as db:
            if db.is_pg:
                query = """
                    INSERT INTO projects
                    (project_id, project_name, creator_profile, deal_context, workflow_config,
                     script, storyboard, media_manifest, sync_report, audio_master, dub_tracks,
                     clearance_report, opportunity_queue, current_stage, completed_stages, blocked_stages, errors,
                     created_at, updated_at, version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (project_id) DO UPDATE SET
                        project_name = EXCLUDED.project_name,
                        creator_profile = EXCLUDED.creator_profile,
                        deal_context = EXCLUDED.deal_context,
                        workflow_config = EXCLUDED.workflow_config,
                        script = EXCLUDED.script,
                        storyboard = EXCLUDED.storyboard,
                        media_manifest = EXCLUDED.media_manifest,
                        sync_report = EXCLUDED.sync_report,
                        audio_master = EXCLUDED.audio_master,
                        dub_tracks = EXCLUDED.dub_tracks,
                        clearance_report = EXCLUDED.clearance_report,
                        opportunity_queue = EXCLUDED.opportunity_queue,
                        current_stage = EXCLUDED.current_stage,
                        completed_stages = EXCLUDED.completed_stages,
                        blocked_stages = EXCLUDED.blocked_stages,
                        errors = EXCLUDED.errors,
                        updated_at = EXCLUDED.updated_at,
                        version = EXCLUDED.version
                """
            else:
                query = """
                    INSERT OR REPLACE INTO projects
                    (project_id, project_name, creator_profile, deal_context, workflow_config,
                     script, storyboard, media_manifest, sync_report, audio_master, dub_tracks,
                     clearance_report, opportunity_queue, current_stage, completed_stages, blocked_stages, errors,
                     created_at, updated_at, version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

            db.execute(query, (
                project.project_id,
                project.project_name,
                creator_json,
                deal_json,
                workflow_json,
                script_json,
                storyboard_json,
                manifest_json,
                sync_json,
                audio_json,
                dub_json,
                clearance_json,
                opp_json,
                project.current_stage.value if project.current_stage else None,
                json.dumps(project.completed_stages),
                json.dumps(project.blocked_stages),
                json.dumps(project.errors),
                project.created_at.isoformat(),
                now,
                project.version,
            ))

    @staticmethod
    async def load(project_id: str) -> Optional[ProjectState]:
        """Load project by ID, fully deserialising all Pydantic sub-models."""
        with get_db_context() as db:
            cursor = db.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
            row = cursor.fetchone()

        if not row:
            return None

        data_dict = dict(row)

        def _parse(col_name, model_cls):
            raw = data_dict.get(col_name)
            if not raw:
                return None
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                return model_cls.model_validate(data)
            except Exception:
                return None

        def _parse_list(col_name, model_cls):
            raw = data_dict.get(col_name)
            if not raw:
                return []
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                return [model_cls.model_validate(item) for item in data]
            except Exception:
                return []

        def _parse_json_list(col_name):
            raw = data_dict.get(col_name)
            if not raw:
                return []
            try:
                return json.loads(raw) if isinstance(raw, str) else list(raw)
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
        from ..shared.models.creator_scout import OpportunityQueue
        from ..shared.models.project import WorkflowConfig

        return ProjectState(
            project_id=data_dict["project_id"],
            project_name=data_dict["project_name"],
            creator_profile=_parse("creator_profile", CreatorProfile),
            deal_context=_parse("deal_context", DealContext),
            workflow_config=_parse("workflow_config", WorkflowConfig) or WorkflowConfig(),
            script=_parse("script", ScriptVersion),
            storyboard=_parse("storyboard", ShotPlan),
            media_manifest=_parse("media_manifest", MediaManifest),
            sync_report=_parse("sync_report", SyncReport),
            audio_master=_parse("audio_master", AudioMaster),
            dub_tracks=_parse_list("dub_tracks", DubTrack),
            clearance_report=_parse("clearance_report", ClearanceReport),
            opportunity_queue=_parse("opportunity_queue", OpportunityQueue),
            current_stage=data_dict["current_stage"] or "CREATED",
            completed_stages=_parse_json_list("completed_stages"),
            blocked_stages=_parse_json_list("blocked_stages"),
            errors=_parse_json_list("errors"),
            created_at=datetime.fromisoformat(str(data_dict["created_at"])),
            updated_at=datetime.fromisoformat(str(data_dict["updated_at"])),
            version=data_dict.get("version") or 1,
        )

    @staticmethod
    async def list_all() -> list:
        """List all projects."""
        with get_db_context() as db:
            cursor = db.execute("SELECT project_id, project_name, created_at FROM projects ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    async def delete_project(project_id: str) -> bool:
        """Delete project and all associated records."""
        with get_db_context() as db:
            db.execute("DELETE FROM media WHERE project_id = ?", (project_id,))
            db.execute("DELETE FROM compliance_checkpoints WHERE project_id = ?", (project_id,))
            db.execute("DELETE FROM jobs WHERE project_id = ?", (project_id,))
            cursor = db.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            return cursor.rowcount > 0


class JobRepository:
    """CRUD operations for Jobs (PostgreSQL + SQLite compatible)."""

    @staticmethod
    async def save(job: dict) -> None:
        """Save or update job."""
        res_json = json.dumps(job.get("result")) if job.get("result") and isinstance(job.get("result"), dict) else job.get("result")
        err_json = json.dumps(job.get("error")) if job.get("error") and isinstance(job.get("error"), dict) else job.get("error")

        with get_db_context() as db:
            if db.is_pg:
                query = """
                    INSERT INTO jobs
                    (job_id, project_id, stage, status, progress, phase, started_at, completed_at, result, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (job_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        progress = EXCLUDED.progress,
                        phase = EXCLUDED.phase,
                        started_at = EXCLUDED.started_at,
                        completed_at = EXCLUDED.completed_at,
                        result = EXCLUDED.result,
                        error = EXCLUDED.error
                """
            else:
                query = """
                    INSERT OR REPLACE INTO jobs
                    (job_id, project_id, stage, status, progress, phase, started_at, completed_at, result, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

            db.execute(query, (
                job["job_id"],
                job["project_id"],
                job["stage"],
                job["status"],
                job.get("progress", 0.0),
                job.get("phase"),
                job.get("started_at"),
                job.get("completed_at"),
                res_json,
                err_json,
            ))

    @staticmethod
    async def load(job_id: str) -> Optional[dict]:
        """Load job by ID."""
        with get_db_context() as db:
            cursor = db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def get_by_project(project_id: str) -> list:
        """Get all jobs for a project."""
        with get_db_context() as db:
            cursor = db.execute("SELECT * FROM jobs WHERE project_id = ? ORDER BY started_at DESC", (project_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    async def get_queued_jobs() -> list:
        """Get all jobs with status='queued' — used by worker loop."""
        with get_db_context() as db:
            cursor = db.execute("SELECT * FROM jobs WHERE status = 'queued' ORDER BY started_at ASC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    async def reset_interrupted_jobs() -> int:
        """Reset 'running' jobs to 'queued' upon startup."""
        with get_db_context() as db:
            cursor = db.execute("UPDATE jobs SET status = 'queued' WHERE status = 'running'")
            count = cursor.rowcount or 0
            if count:
                print(f"⚠ Recovered {count} interrupted job(s) from previous run.")
            return count


class ComplianceCheckpointRepository:
    """CRUD operations for compliance checkpoints (PostgreSQL + SQLite compatible)."""

    @staticmethod
    async def save(checkpoint: dict) -> None:
        """Insert or replace a compliance checkpoint."""
        rep_json = json.dumps(checkpoint.get("report")) if checkpoint.get("report") and isinstance(checkpoint.get("report"), dict) else checkpoint.get("report")
        dec_json = json.dumps(checkpoint.get("decisions", [])) if checkpoint.get("decisions") is not None else None

        with get_db_context() as db:
            if db.is_pg:
                query = """
                    INSERT INTO compliance_checkpoints
                    (checkpoint_id, project_id, stage, status, report, decisions, created_at, approved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (checkpoint_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        report = EXCLUDED.report,
                        decisions = EXCLUDED.decisions,
                        approved_at = EXCLUDED.approved_at
                """
            else:
                query = """
                    INSERT OR REPLACE INTO compliance_checkpoints
                    (checkpoint_id, project_id, stage, status, report, decisions, created_at, approved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """

            db.execute(query, (
                checkpoint["checkpoint_id"],
                checkpoint["project_id"],
                checkpoint["stage"],
                checkpoint["status"],
                rep_json,
                dec_json,
                checkpoint.get("created_at", datetime.now(timezone.utc).isoformat()),
                checkpoint.get("approved_at"),
            ))

    @staticmethod
    async def get_pending(project_id: str) -> list:
        """Return all YELLOW checkpoints for a project that have NOT been approved."""
        with get_db_context() as db:
            cursor = db.execute(
                """
                SELECT * FROM compliance_checkpoints
                WHERE project_id = ? AND status = 'yellow' AND approved_at IS NULL
                ORDER BY created_at ASC
                """,
                (project_id,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    async def approve(checkpoint_id: str, decisions: list) -> bool:
        """Flip a YELLOW checkpoint to 'approved'."""
        with get_db_context() as db:
            cursor = db.execute(
                """
                UPDATE compliance_checkpoints
                SET status = 'approved', approved_at = ?, decisions = ?
                WHERE checkpoint_id = ? AND status = 'yellow'
                """,
                (datetime.now(timezone.utc).isoformat(), json.dumps(decisions), checkpoint_id),
            )
            return (cursor.rowcount or 0) > 0

    @staticmethod
    async def get_all_for_project(project_id: str) -> list:
        """Return all checkpoints for a project."""
        with get_db_context() as db:
            cursor = db.execute(
                "SELECT * FROM compliance_checkpoints WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


class MediaRepository:
    """CRUD operations for Media binary data stored in PostgreSQL (BYTEA) and SQLite (BLOB)."""

    @staticmethod
    async def save_media(
        project_id: str,
        media_id: str,
        asset_type: str,
        filename: str,
        content_type: str,
        data: bytes,
        metadata: Optional[dict] = None,
    ) -> None:
        """Save or replace a media asset with binary content."""
        now = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(metadata) if metadata else None

        with get_db_context() as db:
            if db.is_pg:
                query = """
                    INSERT INTO media
                    (media_id, project_id, asset_type, filename, content_type, data, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (media_id) DO UPDATE SET
                        asset_type = EXCLUDED.asset_type,
                        filename = EXCLUDED.filename,
                        content_type = EXCLUDED.content_type,
                        data = EXCLUDED.data,
                        metadata = EXCLUDED.metadata,
                        created_at = EXCLUDED.created_at
                """
                # Pass data as bytes or psycopg.Binary
                db.execute(query, (
                    media_id,
                    project_id,
                    asset_type,
                    filename,
                    content_type,
                    bytes(data),
                    meta_json,
                    now,
                ))
            else:
                query = """
                    INSERT OR REPLACE INTO media
                    (media_id, project_id, asset_type, filename, content_type, data, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                db.execute(query, (
                    media_id,
                    project_id,
                    asset_type,
                    filename,
                    content_type,
                    data,
                    meta_json,
                    now,
                ))

    @staticmethod
    async def get_media(media_id: str) -> Optional[dict]:
        """Fetch media by unique media_id."""
        with get_db_context() as db:
            cursor = db.execute("SELECT * FROM media WHERE media_id = ?", (media_id,))
            row = cursor.fetchone()

        if not row:
            return None
        res = dict(row)
        # Convert memoryview/bytearray to bytes if needed (Postgres BYTEA returns memoryview)
        if isinstance(res.get("data"), memoryview):
            res["data"] = res["data"].tobytes()
        if res.get("metadata") and isinstance(res["metadata"], str):
            try:
                res["metadata"] = json.loads(res["metadata"])
            except Exception:
                pass
        return res

    @staticmethod
    async def get_by_project_and_type(
        project_id: str,
        asset_type: str,
        shot_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Optional[dict]:
        """Fetch media asset for a project by asset_type, with optional shot_id or language filtering."""
        candidate_types = [asset_type]
        if asset_type == "thumbnail":
            candidate_types.append("video_thumbnail")
        elif asset_type == "video_thumbnail":
            candidate_types.append("thumbnail")

        placeholders = ",".join("?" for _ in candidate_types)

        with get_db_context() as db:
            cursor = db.execute(
                f"SELECT * FROM media WHERE project_id = ? AND asset_type IN ({placeholders}) ORDER BY created_at DESC",
                (project_id, *candidate_types),
            )
            rows = cursor.fetchall()

        if not rows:
            return None

        for r in rows:
            record = dict(r)
            if isinstance(record.get("data"), memoryview):
                record["data"] = record["data"].tobytes()

            meta = {}
            if record.get("metadata"):
                if isinstance(record["metadata"], str):
                    try:
                        meta = json.loads(record["metadata"])
                    except Exception:
                        pass
                elif isinstance(record["metadata"], dict):
                    meta = record["metadata"]
            record["metadata"] = meta

            if shot_id is not None:
                s_id = str(meta.get("shot_id") or meta.get("variant") or "")
                raw_shot = str(shot_id)
                if (
                    s_id == raw_shot
                    or s_id == raw_shot.zfill(2)
                    or record["media_id"].endswith(f"_{raw_shot}")
                    or record["media_id"].endswith(f"_{raw_shot.zfill(2)}")
                    or record["filename"].startswith(f"{raw_shot}.")
                    or record["filename"].startswith(f"{raw_shot.zfill(2)}.")
                    or record["filename"] == f"thumbnail_{raw_shot}.png"
                    or record["filename"] == f"thumbnail_{raw_shot.zfill(2)}.png"
                ):
                    return record
            elif language is not None:
                lang = str(meta.get("language") or meta.get("locale") or "")
                raw_lang = str(language).lower()
                if (
                    lang.lower() == raw_lang
                    or raw_lang in record["media_id"].lower()
                    or raw_lang in record["filename"].lower()
                ):
                    return record
            else:
                return record

        return None

    @staticmethod
    async def list_by_project(project_id: str) -> list[dict]:
        """List metadata for all media assets belonging to a project."""
        with get_db_context() as db:
            length_func = "OCTET_LENGTH(data)" if db.is_pg else "LENGTH(data)"
            cursor = db.execute(
                f"SELECT media_id, project_id, asset_type, filename, content_type, {length_func} as size, metadata, created_at FROM media WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            )
            rows = cursor.fetchall()

        items = []
        for row in rows:
            item = dict(row)
            if item.get("metadata") and isinstance(item["metadata"], str):
                try:
                    item["metadata"] = json.loads(item["metadata"])
                except Exception:
                    pass
            items.append(item)
        return items

    @staticmethod
    async def delete_media(media_id: str) -> bool:
        """Delete a media asset by media_id."""
        with get_db_context() as db:
            cursor = db.execute("DELETE FROM media WHERE media_id = ?", (media_id,))
            return (cursor.rowcount or 0) > 0

    @staticmethod
    async def delete_by_project(project_id: str) -> int:
        """Delete all media assets for a project."""
        with get_db_context() as db:
            cursor = db.execute("DELETE FROM media WHERE project_id = ?", (project_id,))
            return cursor.rowcount or 0
