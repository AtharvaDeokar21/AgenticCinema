"""
main.py - FastAPI entry point with Phase 4 persistent worker.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional
import asyncio
import uuid
from datetime import datetime

from app.persistence.repository import init_db, ProjectRepository, JobRepository
from app.orchestration.dag import StageType, WorkflowDAG
from app.shared.models.project import ProjectState, WorkflowConfig
from app.worker import run_worker_loop
from app.api.routes.chat_approval import router as chat_approval_router


# Initialize DAG at module level
dag = WorkflowDAG()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    init_db()
    print("✓ Database initialized")

    # Recover any jobs that were 'running' when the server last crashed
    await JobRepository.reset_interrupted_jobs()

    # Start the persistent background worker
    worker_task = asyncio.create_task(run_worker_loop())
    print("✓ Background worker started")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        print("✓ Background worker stopped")


app = FastAPI(
    title="Agentic Cinema API",
    description="Backend API for Agentic Cinema multi-agent platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from app.api.routes.projects import router as projects_router

# Register routers
app.include_router(chat_approval_router)
app.include_router(projects_router)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "agentic-cinema-backend"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
