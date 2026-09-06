# Agentic Cinema Orchestration & API Implementation Plan

**Status:** READY FOR APPROVAL  
**Date:** 2026-09-06  
**Scope:** Backend orchestration layer + REST API + state persistence  
**Philosophy:** Minimal-change; preserve all working agents; build thin, reusable adapter layer

---

## 1. CURRENT STATE SUMMARY

### Discovered Architecture
- **FastAPI app:** Minimal (only `/health` endpoint)
- **Agents:** 7 agents with solid individual pipelines; 6 use BaseAgent, 1 (Syncer) is standalone
- **Models:** Canonical Pydantic schemas exist; ProjectState is central container
- **Orchestration:** Only thin StoryboardPipeline wrapper; no cross-agent coordination
- **API routes:** Empty (`/api/routes/__init__.py`)
- **State persistence:** Database URL in config but unused; no ORM integration
- **Tests:** 60+ agent unit/integration tests; no E2E workflow or API tests

### Critical Gaps
1. No API routes to invoke agents
2. No project-level state machine or orchestrator
3. No workflow state persistence
4. No error handling/retry logic
5. No background job/async notification system
6. Syncer agent doesn't extend BaseAgent (manual integration needed)

---

## 2. PROPOSED ARCHITECTURE

### 2.1 Core Layers

```
┌─────────────────────────────────────────────────────┐
│         Frontend / Chat Client (HTTP)               │
├─────────────────────────────────────────────────────┤
│  API Routes Layer (new)                             │
│  • POST /projects                 (create)          │
│  • GET /projects/{project_id}     (get state)       │
│  • POST /projects/{project_id}/run (resume/start)   │
│  • POST /projects/{project_id}/chat (chat input)    │
│  • GET /projects/{project_id}/stages/{stage}        │
│  • POST /projects/{project_id}/approve              │
├─────────────────────────────────────────────────────┤
│  Orchestrator Layer (new)                           │
│  • ProjectOrchestrator (state machine)              │
│  • WorkflowExecutor (stage sequencing)              │
│  • ErrorRecovery (retry, partial completion)        │
├─────────────────────────────────────────────────────┤
│  Agent Adapter Layer (thin wrappers)                │
│  • Adapters map ProjectState ↔ agent inputs/outputs │
│  • Normalize Syncer into BaseAgent pattern          │
├─────────────────────────────────────────────────────┤
│  Agent Layer (existing, UNCHANGED)                  │
│  • CreatorScout, Script, Storyboard, Audio, Dub,   │
│    Sync, Compliance (7 agents)                      │
├─────────────────────────────────────────────────────┤
│  Shared Tools (existing)                            │
│  • GeminiClient, Parallel tools, FFmpeg, TTS, etc.  │
└─────────────────────────────────────────────────────┘
```

### 2.2 State Flow

```
┌─────────────────┐
│  ProjectState   │ (DB: SQLite)
│  • project_id   │
│  • stage        │
│  • outputs      │
│  • errors       │
└────────┬────────┘
         │
    ┌────▼─────────────────────────────────┐
    │  WorkflowExecutor                    │
    │  • stage_started()                   │
    │  • run_agent(stage)                  │
    │  • handle_error(error)               │
    │  • advance_stage()                   │
    └─────────────────────────────────────┘
         │
    ┌────▼─────────────────────────────────┐
    │  Agent Adapters                      │
    │  ProjectState → Agent Input          │
    │  Agent Output → ProjectState         │
    └─────────────────────────────────────┘
         │
    ┌────▼──────────────────────────────────┐
    │  Agents (existing, no changes)       │
    │  each returns domain-specific output │
    └──────────────────────────────────────┘
```

---

## 3. WORKFLOW STAGES & SEQUENCING

### Intended Flow (Configurable)

```
START (creator creates project)
  ↓
1. CREATOR_SCOUT (optional)
   └─ Input: CreatorProfile, DealContext
   └─ Output: OpportunityQueue (if collaborations/sponsorships)
  ↓
2. COMPLIANCE_CHECKPOINT_1
   └─ Verify: creator profile, deal terms
   └─ Status: YELLOW→request approval, RED→fail, GREEN→continue
  ↓
3. SCRIPT (ScriptSuggestor)
   └─ Input: brief, research (optional Parallel)
   └─ Output: ScriptVersion with beats
  ↓
4. COMPLIANCE_CHECKPOINT_2
   └─ Verify: script themes, references, claims
  ↓
5. STORYBOARD (StoryboardAgent)
   └─ Input: ScriptVersion
   └─ Output: ShotPlan + visual assets
  ↓
6. COMPLIANCE_CHECKPOINT_3
   └─ Verify: visual assets, references, compositions
  ↓
7. MEDIA (creator shoots/records video)
   └─ Input: video file upload
   └─ Output: VideoManifest in ProjectState
  ↓
8. SYNC (SyncerAgent)
   └─ Input: video + script beats + audio clips
   └─ Output: SyncReport (beat-to-frame mapping)
  ↓
9. COMPLIANCE_CHECKPOINT_4
   └─ Verify: sync accuracy, no unauthorized audio
  ↓
10. AUDIO (AudioAgent)
    └─ Input: video, mode (CREATOR_VOICE or AI_VOICE)
    └─ Output: AudioMaster with segments
  ↓
11. COMPLIANCE_CHECKPOINT_5
    └─ Verify: audio content, TTS quality flags
  ↓
12. DUBBING (CulturalDubAgent, optional per-locale)
    └─ Input: AudioMaster, target_locales
    └─ Output: DubTrack[] per locale
  ↓
13. COMPLIANCE_CHECKPOINT_6 (final)
    └─ Verify: all dub tracks, subtitles, licenses
  ↓
14. COMPLETED
    └─ Aggregate all outputs, mark ready for publish
```

### Skippable Stages
- CREATOR_SCOUT (if no collaboration context)
- DUBBING (if single-locale)
- Other stages can be triggered on-demand or skipped based on creator intent

### Compliance Checkpoints
- Run after stages: CREATED, SCRIPT, STORYBOARD, MEDIA, AUDIO, DUBBING
- Pass types: GREEN (continue), YELLOW (require approval), RED (block)
- Ledger: tracked assets persisted across 6 passes for dedup

---

## 4. API ROUTES & CONTRACTS

### Route: Create Project
```
POST /projects
{
  "project_id": "proj_001",                    # auto-generated UUID if omitted
  "project_name": "Summer Campaign 2026",
  "creator_profile": { /* CreatorProfile */ },
  "deal_context": { /* DealContext */ },
  "config": {
    "skip_stages": ["CREATOR_SCOUT"],         # optional
    "request_approval_for_yellow": true,      # YELLOW blocks until approval
    "target_locales": ["es", "fr"]            # for DUBBING
  }
}

Response: 201
{
  "project_id": "proj_001",
  "status": "CREATED",
  "current_stage": "SCRIPT",
  "created_at": "2026-09-06T05:23:11Z",
  "project_state": { /* full ProjectState */ }
}
```

### Route: Get Project State
```
GET /projects/{project_id}

Response: 200
{
  "project_id": "proj_001",
  "status": "SCRIPT",                  # current stage
  "current_stage": "SCRIPT",
  "created_at": "2026-09-06T05:23:11Z",
  "updated_at": "2026-09-06T05:25:30Z",
  "project_state": { /* full ProjectState */ },
  "stage_history": [
    { "stage": "CREATED", "status": "completed", "started_at": "...", "completed_at": "..." },
    { "stage": "COMPLIANCE_CHECKPOINT_1", "status": "GREEN", ... }
  ],
  "current_errors": null
}
```

### Route: Start/Resume Workflow
```
POST /projects/{project_id}/run
{
  "from_stage": "SCRIPT",         # optional; if omitted, resume from current
  "input": {                      # optional stage-specific input
    "brief": "Product launch video...",
    "research_enabled": true
  }
}

Response: 200 (immediate) or 202 (async)
{
  "project_id": "proj_001",
  "stage": "SCRIPT",
  "status": "in_progress",
  "started_at": "2026-09-06T05:23:50Z",
  "job_id": "job_abc123"          # if async
}

# Backend polls or websocket updates with:
{
  "project_id": "proj_001",
  "stage": "SCRIPT",
  "status": "completed",
  "output": { /* ScriptVersion */ },
  "next_stage": "COMPLIANCE_CHECKPOINT_2",
  "completed_at": "2026-09-06T05:28:30Z"
}
```

### Route: Chat / Creator Input
```
POST /projects/{project_id}/chat
{
  "message": "Can we use a different tone for beat 3?",
  "context": {
    "stage": "SCRIPT",
    "referencing": ["beat_003"]
  }
}

Response: 200
{
  "project_id": "proj_001",
  "message_id": "msg_xyz",
  "action": "script_revision",      # orchestrator decides next step
  "suggested_next_stage": "SCRIPT",
  "needs_approval": false,
  "response": "I'll regenerate beat 3 with a more dramatic tone..."
}
```

### Route: Approve Compliance Issue
```
POST /projects/{project_id}/approve
{
  "checkpoint": "COMPLIANCE_CHECKPOINT_2",
  "issues": [
    {
      "issue_id": "iss_123",
      "decision": "OVERRIDE",           # OVERRIDE, REQUEST_SUBSTITUTE, REJECT
      "notes": "Brand approved this reference"
    }
  ]
}

Response: 200
{
  "project_id": "proj_001",
  "checkpoint": "COMPLIANCE_CHECKPOINT_2",
  "status": "approved",
  "next_stage": "STORYBOARD"
}
```

### Route: Get Stage Output / Intermediate Results
```
GET /projects/{project_id}/stages/{stage_name}

Response: 200
{
  "stage": "SCRIPT",
  "status": "completed",
  "output": { /* full ScriptVersion */ },
  "completed_at": "2026-09-06T05:28:30Z"
}
```

### Route: Upload Media (for MEDIA stage)
```
POST /projects/{project_id}/media
Content-Type: multipart/form-data
{
  "file": <binary video>,
  "media_type": "video/mp4"
}

Response: 200
{
  "project_id": "proj_001",
  "media_id": "media_001",
  "file_path": "storage/proj_001/media_001.mp4",
  "duration": 120.5,
  "next_stage": "SYNC"
}
```

### Route: Retry Failed Stage
```
POST /projects/{project_id}/retry
{
  "stage": "STORYBOARD",
  "error_handling": "discard_and_restart"  # or "resume_from_checkpoint"
}

Response: 202
{
  "project_id": "proj_001",
  "stage": "STORYBOARD",
  "status": "retrying",
  "job_id": "job_retry_001"
}
```

---

## 5. PROPOSED FILE STRUCTURE

### New Files (Orchestration Layer)

```
app/orchestration/
├── __init__.py
├── orchestrator.py           # ProjectOrchestrator state machine
├── executor.py               # WorkflowExecutor (stage dispatch)
├── error_handling.py         # Retry logic, partial completion
├── stages.py                 # StageDefinition, stage registry
└── state_machine.py          # State transitions, guards

app/api/
├── __init__.py
├── routes/
│   ├── __init__.py           # Register all routers
│   ├── projects.py           # Projects CRUD (create, get, list)
│   ├── workflow.py           # Workflow execution (start, resume, run)
│   ├── chat.py               # Chat/creator input endpoint
│   ├── approval.py           # Compliance approval endpoint
│   ├── media.py              # Media upload for MEDIA stage
│   └── stages.py             # Stage output retrieval
├── schemas.py                # API request/response schemas (Pydantic)
└── dependencies.py           # FastAPI dependencies (auth, project lookup, etc.)

app/persistence/
├── __init__.py
├── database.py               # SQLite connection, session management
├── models.py                 # SQLAlchemy ORM models (ProjectStateDB, etc.)
├── repository.py             # Data access layer (CRUD for ProjectState)
└── migrations.py             # Schema setup/migrations (Alembic placeholder)

app/shared/adapters/
├── __init__.py
├── base.py                   # AdapterBase, common adapter logic
├── creator_scout.py          # CreatorScout input/output mapping
├── script_suggestor.py       # ScriptSuggestor input/output mapping
├── storyboard.py             # StoryboardAgent input/output mapping
├── audio.py                  # AudioAgent input/output mapping
├── cultural_dub.py           # CulturalDubAgent input/output mapping
├── compliance.py             # ComplianceAgent input/output mapping
└── syncer.py                 # SyncerAgent input/output mapping (new)

tests/
├── api/
│   ├── test_projects.py      # API project CRUD tests
│   ├── test_workflow.py      # API workflow execution tests
│   └── test_e2e.py           # Full workflow E2E tests
└── orchestration/
    ├── test_orchestrator.py  # State machine tests
    ├── test_executor.py      # Stage dispatch tests
    └── test_error_recovery.py# Retry logic tests
```

### Modified Files (Minimal Changes)

```
app/main.py
├── Add database initialization
├── Register orchestration middleware (logging, tracing)
├── Register all API route routers
└── Add lifespan startup/shutdown hooks

app/config/settings.py
├── Add: DATABASE_URL (already has placeholder)
├── Add: MAX_RETRIES, RETRY_DELAY
├── Add: APPROVAL_REQUIRED_FOR_YELLOW (config)
└── Add: JOB_TIMEOUT, STAGE_TIMEOUT values

app/shared/models/project.py
├── Add: version field (for optimistic locking)
├── Add: workflow_config field (stage skips, approval settings)
├── Add: stage_history (List[StageExecution])
└── (Rest unchanged; ProjectState already has most fields)
```

---

## 6. ORCHESTRATION LOGIC

### 6.1 ProjectOrchestrator (State Machine)

**Responsibilities:**
- Manage project lifecycle (CREATED → ... → COMPLETED)
- Track current stage and stage history
- Guard stage transitions (validation before advancing)
- Persist state to database
- Handle approval/rejection logic

**Pseudo-code:**
```python
class ProjectOrchestrator:
    def __init__(self, db_repository):
        self.repo = db_repository
    
    async def create_project(self, request: CreateProjectRequest) -> ProjectState:
        project = ProjectState(
            project_id=request.project_id or uuid(),
            current_stage=ProjectStage.CREATED,
            creator_profile=request.creator_profile,
            deal_context=request.deal_context,
            workflow_config=request.config,
        )
        await self.repo.save(project)
        return project
    
    async def get_project(self, project_id: str) -> ProjectState:
        return await self.repo.load(project_id)
    
    async def advance_to_stage(self, project_id: str, next_stage: ProjectStage):
        project = await self.repo.load(project_id)
        
        # Validation guards
        if not self._can_transition(project.current_stage, next_stage):
            raise WorkflowError(f"Cannot go from {project.current_stage} to {next_stage}")
        
        project.current_stage = next_stage
        project.stage_history.append(StageExecution(
            stage=next_stage,
            status="started",
            started_at=now(),
        ))
        await self.repo.save(project)
    
    async def complete_stage(self, project_id: str, output: dict):
        project = await self.repo.load(project_id)
        project.stage_history[-1].status = "completed"
        project.stage_history[-1].completed_at = now()
        
        # Store output in ProjectState based on stage
        self._store_stage_output(project, project.current_stage, output)
        await self.repo.save(project)
    
    async def fail_stage(self, project_id: str, error: Exception):
        project = await self.repo.load(project_id)
        project.stage_history[-1].status = "failed"
        project.stage_history[-1].error = str(error)
        project.current_errors = [str(error)]
        await self.repo.save(project)
    
    async def handle_compliance_review(
        self,
        project_id: str,
        checkpoint: ComplianceCheckpoint,
        report: ClearanceReport,
    ) -> dict:
        project = await self.repo.load(project_id)
        
        if report.status == ReportStatus.GREEN:
            next_stage = self._next_stage(project.current_stage)
            return { "next_stage": next_stage, "action": "continue" }
        
        elif report.status == ReportStatus.YELLOW:
            if project.workflow_config.request_approval_for_yellow:
                return {
                    "action": "approval_required",
                    "issues": report.issues,
                    "wait_for_approval": True,
                }
            else:
                # Auto-override
                next_stage = self._next_stage(project.current_stage)
                return { "next_stage": next_stage, "action": "continue" }
        
        elif report.status == ReportStatus.RED:
            return {
                "action": "blocked",
                "issues": report.issues,
                "error": "Red-flag issues must be resolved",
            }
```

### 6.2 WorkflowExecutor (Stage Dispatch)

**Responsibilities:**
- Map ProjectState → agent input
- Invoke correct agent
- Map agent output → ProjectState
- Sequence next stage
- Handle stage skips

**Pseudo-code:**
```python
class WorkflowExecutor:
    def __init__(self, orchestrator: ProjectOrchestrator, adapters: dict):
        self.orchestrator = orchestrator
        self.adapters = adapters  # stage_name → adapter
    
    async def run_stage(
        self,
        project_id: str,
        stage: ProjectStage,
        input_override: dict = None,
    ) -> dict:
        try:
            project = await self.orchestrator.get_project(project_id)
            
            # Skip if configured
            if stage in project.workflow_config.skip_stages:
                return { "stage": stage, "status": "skipped" }
            
            # Get adapter for this stage
            adapter = self.adapters.get(stage)
            if not adapter:
                raise ValueError(f"No adapter for stage {stage}")
            
            # Map ProjectState → agent input
            agent_input = adapter.to_agent_input(project, input_override)
            
            # Invoke agent
            agent_output = await self._invoke_agent(stage, agent_input)
            
            # Map agent output → ProjectState
            updated_project = adapter.to_project_state(project, agent_output)
            await self.orchestrator.complete_stage(project_id, updated_project)
            
            # Decide next stage (may be compliance checkpoint)
            next_stage = self._next_stage(stage)
            return {
                "stage": stage,
                "status": "completed",
                "output": agent_output,
                "next_stage": next_stage,
            }
        
        except Exception as e:
            await self.orchestrator.fail_stage(project_id, e)
            return {
                "stage": stage,
                "status": "failed",
                "error": str(e),
                "recoverable": self._is_recoverable(e),
            }
    
    async def _invoke_agent(self, stage: ProjectStage, agent_input: dict):
        if stage == ProjectStage.CREATOR_SCOUT:
            agent = CreatorScoutAgent()
            return await agent.run(CreatorScoutRequest(**agent_input))
        
        elif stage == ProjectStage.SCRIPT:
            agent = ScriptSuggestorAgent()
            return await agent.run(ScriptRequest(**agent_input))
        
        elif stage == ProjectStage.STORYBOARD:
            agent = StoryboardAgent()
            return agent.generate_full_pipeline(**agent_input)  # sync call
        
        # ... etc for other agents
```

### 6.3 Stage Adapters (Thin Mappers)

**Pattern:**
```python
class ScriptSuggestorAdapter:
    async def to_agent_input(
        self,
        project: ProjectState,
        input_override: dict = None,
    ) -> dict:
        """Map ProjectState → ScriptRequest"""
        return {
            "creator_profile": project.creator_profile,
            "deal_context": project.deal_context,
            "brief": input_override.get("brief") if input_override else project.deal_context.campaign_objective,
            "research_enabled": input_override.get("research_enabled", True) if input_override else True,
        }
    
    async def to_project_state(
        self,
        project: ProjectState,
        agent_output: ScriptVersion,
    ) -> ProjectState:
        """Map ScriptVersion → ProjectState"""
        project.script = agent_output
        return project
```

---

## 7. ERROR HANDLING & RECOVERY

### Error Classification

| Error Type | Cause | Recoverable | Action |
|-----------|-------|------------|--------|
| **ValidationError** | Bad input (missing beat, invalid timestamps) | Yes | Retry with corrected input; operator can fix |
| **ProviderFailure** | Gemini quota, Parallel API down, HF rate limit | Yes | Exponential backoff retry; notify operator |
| **ComplianceRED** | Asset flagged by compliance as unacceptable | No (needs human intervention) | Block stage; request substitute/override |
| **ComplianceYELLOW** | Asset flagged as needs review | Depends on config | Wait for approval or auto-override |
| **MediaNotFound** | Missing video file, corrupt audio | No | Operator re-uploads media |
| **TimeoutError** | Agent processing took too long | Maybe | Retry or abort; check logs |
| **OOMError** | Out of memory (image generation) | Maybe | Retry with smaller batch |

### Retry Strategy

```python
async def retry_with_backoff(
    fn,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff: float = 2.0,
    retriable_errors: tuple = (ProviderFailure, TimeoutError),
):
    for attempt in range(max_retries):
        try:
            return await fn()
        except retriable_errors as e:
            if attempt == max_retries - 1:
                raise
            delay = initial_delay * (backoff ** attempt)
            logger.warning(f"Attempt {attempt + 1} failed; retrying in {delay}s: {e}")
            await asyncio.sleep(delay)
        except Exception as e:
            # Non-retriable error; fail immediately
            raise
```

### Partial Completion / Resume

**Scenario:** Storyboard generates reference images but crashes during asset generation.

**Solution:**
1. Storyboard agent returns intermediate state: `{ "status": "partial", "phase": "asset_generation", "progress": 0.7 }`
2. Orchestrator stores this in ProjectState.stage_history[-1]
3. On retry, check for partial state; pass `resume_from_checkpoint=True` to agent
4. Agent resumes from asset generation, reusing prior research/visual grammar

**Code:**
```python
async def run_stage_with_resume(project_id: str, stage: ProjectStage):
    project = await orchestrator.get_project(project_id)
    last_execution = project.stage_history[-1]
    
    if last_execution.status == "partial":
        # Resume from checkpoint
        agent_input = adapter.to_agent_input(project)
        agent_input["resume_from_checkpoint"] = last_execution.checkpoint_data
        agent_output = await _invoke_agent(stage, agent_input)
    else:
        # Fresh run
        agent_output = await run_stage(project_id, stage)
```

---

## 8. COMPLIANCE CHECKPOINT INTEGRATION

### Checkpoint Sequencing

After each stage completes, before advancing to next stage:

```
Stage completes (e.g., SCRIPT)
  ↓
1. Store stage output in ProjectState
2. Invoke ComplianceAgent with:
   {
     "stage": "SCRIPT",
     "payload": project.script,
     "image_paths": [],
     "audio_paths": [],
     "prior_tracked_assets": project.compliance.tracked_assets,
   }
3. ComplianceAgent returns ClearanceReport
4. ProjectOrchestrator.handle_compliance_review()
   - If GREEN: advance to next stage
   - If YELLOW: flag for approval (or auto-continue if not required)
   - If RED: block and fail stage
5. If approval required, API returns 202 with approval endpoint
6. Creator approves/rejects via POST /projects/{id}/approve
7. Update ClearanceReport.status and auto-advance
```

### Ledger Persistence

Compliance tracks assets across 6 passes with dedup:

```python
# In ComplianceAgent input
"prior_tracked_assets": [
    TrackedAsset(
        asset_key="music::background_track_01",
        kind=AssetKind.MUSIC,
        label="Background Track 01",
        first_seen_stage=ProjectStage.AUDIO,
        status=ClearanceStatus.GREEN,
        last_checked_at=datetime(...),
    ),
    ...
]

# ComplianceAgent updates ledger and returns:
ClearanceReport(
    status=ReportStatus.GREEN,
    checked_assets=[...],  # new checks
    tracked_assets=[...],  # updated ledger (merged with prior)
)
```

---

## 9. DATABASE SCHEMA

### SQLite Schema (Simplified)

```sql
-- Central project state table
CREATE TABLE projects (
    project_id TEXT PRIMARY KEY,
    project_name TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    creator_profile JSON NOT NULL,
    deal_context JSON NOT NULL,
    workflow_config JSON,
    script JSON,
    storyboard JSON,
    media_manifest JSON,
    sync_report JSON,
    audio_master JSON,
    dub_tracks JSON,
    clearance_report JSON,
    creator_recommendations JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1  -- optimistic locking
);

-- Stage execution history
CREATE TABLE stage_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,  -- started, completed, failed, partial
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    checkpoint_data JSON,  -- for resume
    error_message TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- Compliance tracked assets (denormalized from clearance_report for queries)
CREATE TABLE tracked_assets (
    asset_key TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    label TEXT NOT NULL,
    first_seen_stage TEXT,
    status TEXT,
    last_checked_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- Background jobs (for async execution tracking)
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,  -- queued, running, completed, failed
    created_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result JSON,
    error_message TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
```

### Data Access Layer (Repository)

```python
class ProjectRepository:
    async def save(self, project: ProjectState) -> None:
        """Upsert project; handle optimistic locking"""
    
    async def load(self, project_id: str) -> ProjectState:
        """Load project with stage history and tracked assets"""
    
    async def list_by_creator(self, creator_id: str) -> List[ProjectState]:
        """List all projects for a creator"""
    
    async def update_stage_history(self, project_id: str, execution: StageExecution) -> None:
        """Append to stage history"""
    
    async def get_compliance_ledger(self, project_id: str) -> List[TrackedAsset]:
        """Load compliance tracked assets for project"""
```

---

## 10. ASYNC & BACKGROUND JOB STRATEGY

### Short Requests (< 30s): Synchronous in-request
- Script generation (usually 5–10s)
- Compliance checks (5–15s)
- Small storyboard queries

### Long Requests (30s–5m): Background job + polling/SSE
- Storyboard full pipeline (reference research + visual generation = 1–3m)
- Cultural dub for multiple locales (2–5m)
- Audio generation (1–2m per beat)

### Implementation: No external job queue; use FastAPI background tasks + polling

```python
# Route: Start workflow (async)
@router.post("/projects/{project_id}/run")
async def start_workflow(
    project_id: str,
    request: RunWorkflowRequest,
    background_tasks: BackgroundTasks,
):
    orchestrator = get_orchestrator()
    project = await orchestrator.get_project(project_id)
    
    if project.workflow_config.stage_timeout > 30:  # async stage
        job_id = uuid()
        background_tasks.add_task(
            workflow_executor.run_stage,
            project_id=project_id,
            stage=project.current_stage,
            job_id=job_id,
        )
        return { "status": "202 Accepted", "job_id": job_id }
    else:
        # Inline execution
        result = await workflow_executor.run_stage(project_id, project.current_stage)
        return { "status": "200 OK", "result": result }

# Route: Poll job status
@router.get("/projects/{project_id}/jobs/{job_id}")
async def get_job_status(project_id: str, job_id: str):
    job = await job_repository.load(job_id)
    return {
        "job_id": job_id,
        "status": job.status,  # queued, running, completed, failed
        "progress": job.progress,  # 0.0 to 1.0 for applicable stages
        "result": job.result if job.status == "completed" else None,
        "error": job.error_message if job.status == "failed" else None,
    }
```

**Optional Future:** Add Celery/RQ if async job persistence across restarts becomes critical.

---

## 11. FRONTEND INTEGRATION CONTRACT

### WebSocket Events (Optional; polling is primary)

```javascript
// Client subscribes to project updates
ws = new WebSocket("ws://localhost:8000/projects/{project_id}/subscribe");
ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    // update.type: "stage_started", "stage_completed", "approval_required", "error"
    // update.stage, update.status, update.output
};
```

### Response Schema Stability

**Principle:** API returns wrapper schemas, not internal agent models.

```python
# Internal agent output (may change)
class ScriptVersion(BaseModel):
    version: int
    beats: List[ScriptBeat]
    # ... 50 more fields

# API response (stable contract, subset of agent output)
class StageOutputResponse(BaseModel):
    stage: ProjectStage
    status: str  # completed, partial, failed
    output: dict  # JSON-serializable subset of ScriptVersion
    completed_at: datetime
    next_stage: Optional[ProjectStage] = None
```

---

## 12. EXISTING TESTS: WHAT REMAINS UNCHANGED

- ✅ `tests/agents/*/test_*.py` — all 60+ agent unit/integration tests pass unchanged
- ✅ `tests/agents/storyboard/test_full_storyboard_pipeline.py` — full storyboard E2E unchanged

### New Tests

**`tests/api/test_projects.py`**
- Create project, get project, list projects
- Verify ProjectState schema and fields

**`tests/api/test_workflow.py`**
- Start workflow, resume workflow, retry workflow
- Verify stage transitions
- Verify output is persisted to ProjectState

**`tests/orchestration/test_orchestrator.py`**
- State machine transitions
- Guard validation (can't skip from SCRIPT to COMPLETED)
- Stage history tracking

**`tests/orchestration/test_compliance_integration.py`**
- Compliance checkpoint after each stage
- GREEN continues, YELLOW waits for approval, RED blocks

**`tests/orchestration/test_error_recovery.py`**
- Retry with backoff
- Partial completion and resume

---

## 13. FILE-BY-FILE CHANGE LIST

### New Files (Create)
1. `app/orchestration/orchestrator.py`
2. `app/orchestration/executor.py`
3. `app/orchestration/error_handling.py`
4. `app/orchestration/stages.py`
5. `app/api/routes/projects.py`
6. `app/api/routes/workflow.py`
7. `app/api/routes/chat.py`
8. `app/api/routes/approval.py`
9. `app/api/routes/media.py`
10. `app/api/routes/stages.py`
11. `app/api/schemas.py`
12. `app/api/dependencies.py`
13. `app/persistence/database.py`
14. `app/persistence/models.py`
15. `app/persistence/repository.py`
16. `app/shared/adapters/base.py`
17. `app/shared/adapters/creator_scout.py`
18. `app/shared/adapters/script_suggestor.py`
19. `app/shared/adapters/storyboard.py`
20. `app/shared/adapters/audio.py`
21. `app/shared/adapters/cultural_dub.py`
22. `app/shared/adapters/compliance.py`
23. `app/shared/adapters/syncer.py`
24. `tests/api/test_projects.py`
25. `tests/api/test_workflow.py`
26. `tests/orchestration/test_orchestrator.py`
27. `tests/orchestration/test_compliance_integration.py`
28. `tests/orchestration/test_error_recovery.py`

### Modified Files (Minimal)
1. `app/main.py` — add DB init, register routes, lifespan hooks
2. `app/config/settings.py` — add RETRY_MAX, TIMEOUT_STAGE, etc.
3. `app/shared/models/project.py` — add version, workflow_config, stage_history fields
4. `app/shared/models/stages.py` — no change; enum already exists

**Total:** 28 new files, 4 modified files.

---

## 14. RISKS, ASSUMPTIONS & OPEN QUESTIONS

### Risks
1. **Database connection pool exhaustion** under high concurrency
   - Mitigation: Configure SQLite max_connections in settings; move to PostgreSQL if load grows
2. **Compliance checkpoint performance** (6 passes per project)
   - Mitigation: Cache compliance checks where possible; offload to background if > 5s
3. **Agent output schema mutations** (e.g., ScriptVersion adds new field)
   - Mitigation: API adapters are thin; bump API version if contract changes
4. **Syncer agent latency** (uploads video to Gemini, multimodal processing)
   - Mitigation: Mark SYNC as long-running async stage; allow creator to input manual sync if needed

### Assumptions
1. Creators interact in sequence (SCRIPT before STORYBOARD, etc.)
   - Not currently allowed to loop back and revise prior stages
2. Compliance ledger is sufficient for dedup (6 passes)
   - If projects grow very long, may need pagination or archival
3. No multi-user concurrency on same project
   - No row-level locking; optimistic version field is sufficient
4. Media files are <1GB
   - No chunked upload; add if needed

### Open Questions for Product
1. **Can creators request changes mid-workflow?** (e.g., "Regenerate script beat 3")
   - Proposed: Chat endpoint analyzes request, triggers revision stage, replays stages
2. **Can CreatorScout run concurrently with Script?** Or must Script run first?
   - Proposed: Sequential by default; can be parallelized in future
3. **How long to keep completed projects in DB?** Archive strategy?
   - Proposed: Keep indefinitely; add archival TTL config if needed
4. **Should each stage be independently pausable?** (e.g., pause mid-Storyboard)
   - Proposed: No; stages are atomic. Only checkpoint pauses (approval).

---

## 15. IMPLEMENTATION SEQUENCE (After Approval)

### Phase 1: Database & Persistence (1–2 days)
1. Create `app/persistence/` module with SQLite schema
2. Implement ProjectRepository (load, save, update_stage_history)
3. Add database initialization to `app/main.py` lifespan

### Phase 2: Orchestration Core (2–3 days)
4. Create `app/orchestration/orchestrator.py` (state machine)
5. Create `app/orchestration/executor.py` (stage dispatch)
6. Create `app/orchestration/error_handling.py` (retry, recovery)
7. Write tests for orchestrator

### Phase 3: Stage Adapters (1–2 days)
8. Create `app/shared/adapters/` — 7 adapters + base
9. Test each adapter with agent unit tests

### Phase 4: API Routes (1–2 days)
10. Create `app/api/routes/` — 6 route modules
11. Create `app/api/schemas.py` and `dependencies.py`
12. Register routes in `app/main.py`

### Phase 5: Testing & Integration (2–3 days)
13. Write E2E tests: create project → run script → run storyboard → complete
14. Write API tests: CRUD, workflow state transitions
15. Run existing agent tests; verify no regressions

### Phase 6: Compliance Integration (1 day)
16. Wire Compliance checkpoints into executor
17. Test approval/rejection flow

### Phase 7: Documentation & Polish (1 day)
18. Update README with API examples
19. Add docstrings, log statements
20. Deploy to test environment

**Total Estimate:** 9–14 days for complete implementation and testing.

---

## 16. SUCCESS CRITERIA

- ✅ Creator can POST to `/projects` to create a project
- ✅ Creator can POST to `/projects/{id}/run` to start workflow
- ✅ Orchestrator sequences agents correctly (SCRIPT → STORYBOARD → etc.)
- ✅ ProjectState is persisted to database and survives restarts
- ✅ Compliance checkpoint runs after each stage; YELLOW blocks until approval
- ✅ Failed stages can be retried without rerunning prior stages
- ✅ API returns stable schemas; internal agent models can evolve
- ✅ All 60+ existing agent tests pass
- ✅ New E2E workflow test covers full path from create → complete
- ✅ Syncer agent is integrated as a normal workflow stage

---

## 17. NOT IN SCOPE (Future Phases)

- [ ] Multi-user concurrent editing on same project
- [ ] Approval workflows with multiple stakeholders
- [ ] Media streaming / chunk upload
- [ ] Audio synchronization visualization tool
- [ ] Compliance appeal / override audit trail
- [ ] Analytics dashboard (projects, stage times, compliance patterns)
- [ ] Agent model/prompt versioning (frozen on deployment)

---

**PLAN READY FOR APPROVAL**

This plan preserves all working agent logic, introduces minimal changes to existing code, and builds a clean orchestration layer on top. The modular structure allows implementation in phases and testing at each stage.

**Next steps:** Await approval → Begin Phase 1 (Database & Persistence).
