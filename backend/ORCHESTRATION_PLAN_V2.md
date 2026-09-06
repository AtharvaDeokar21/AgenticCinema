# Agentic Cinema Orchestration & API Implementation Plan V2

**Status:** READY FOR APPROVAL  
**Date:** 2026-09-06  
**Version:** 2.0 (DAG-based workflow architecture)  
**Scope:** Backend orchestration layer + REST API + state persistence  
**Philosophy:** Minimal-change; preserve all working agents; flexible DAG execution model

---

## CHANGELOG FROM V1

**Major architectural changes:**
1. ✅ Replaced strictly sequential workflow with **state graph/DAG**
2. ✅ Made Audio independently invokable from an existing Script
3. ✅ Support two Audio modes: AI voice and creator voice
4. ✅ Allow creator voice Audio to follow Syncer
5. ✅ Don't make CreatorScout a mandatory first stage
6. ✅ Treat Compliance as a **cross-cutting checkpoint**, not a normal stage
7. ✅ Add **Chat Intent Router / Action Router**
8. ✅ Define **intermediate execution responses** and **job/status states**
9. ✅ Ensure **async agent invocation** is handled correctly
10. ✅ Allow **direct stage invocation** from the API, not only run entire workflow

---

## 1. CURRENT STATE SUMMARY

*(Unchanged from V1 - repository inspection findings)*

### Discovered Architecture
- **FastAPI app:** Minimal (only `/health` endpoint)
- **Agents:** 7 agents with solid individual pipelines; 6 use BaseAgent, 1 (Syncer) is standalone
- **Models:** Canonical Pydantic schemas exist; ProjectState is central container
- **Orchestration:** Only thin StoryboardPipeline wrapper; no cross-agent coordination
- **API routes:** Empty (`/api/routes/__init__.py`)
- **State persistence:** Database URL in config but unused; no ORM integration
- **Tests:** 60+ agent unit/integration tests; no E2E workflow or API tests

### Agent Entry Points (from repository inspection)

| Agent | Entry Point | Input | Output | Dependencies |
|-------|------------|-------|--------|--------------|
| **CreatorScout** | `async run(CreatorScoutRequest)` | CreatorProfile, DealContext | OpportunityQueue | Gemini, Parallel |
| **ScriptSuggestor** | `async run(ScriptRequest)` | brief, creator_profile, research_enabled | ScriptVersion | Gemini, Parallel |
| **StoryboardAgent** | `generate_full_pipeline(ScriptVersion, ...)` | ScriptVersion, constraints, style | ShotPlan + assets | Gemini, HF, Parallel |
| **SyncerAgent** | `async run(SyncRequest)` | video_path, script_beats, audio_clips | SyncMap | Gemini File API, ffmpeg |
| **AudioAgent** | `async run(AudioRequest)` | video_path, mode (CREATOR_VOICE \| AI_VOICE) | AudioResult | ffmpeg, Gemini TTS |
| **CulturalDubAgent** | `async run(DubRequest)` | audio_master, target_locales | CulturalDubResult | Gemini, Parallel |
| **ComplianceAgent** | `async run(ComplianceRequest)` | payload, images, audio, stage, prior_assets | ClearanceReport | Gemini, Parallel |

---

## 2. DAG-BASED WORKFLOW ARCHITECTURE

### 2.1 Core Concept: Stage Dependency Graph

Instead of a linear pipeline, we model the workflow as a **Directed Acyclic Graph (DAG)** where:
- **Nodes** = workflow stages (agents or actions)
- **Edges** = dependencies (stage B depends on output of stage A)
- **Execution** = topological sort with parallel execution where possible

### 2.2 Workflow DAG Definition

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENTIC CINEMA WORKFLOW DAG                  │
└─────────────────────────────────────────────────────────────────┘

ENTRY POINT: PROJECT_CREATED
    │
    ├──→ CREATOR_SCOUT (optional, independent)
    │         └──→ [outputs: OpportunityQueue]
    │
    └──→ SCRIPT
             ├─→ [requires: creator_profile, optional deal_context]
             └─→ [outputs: ScriptVersion with beats]
                      │
                      ├──→ STORYBOARD
                      │      ├─→ [requires: ScriptVersion]
                      │      └─→ [outputs: ShotPlan, visual assets]
                      │
                      └──→ AUDIO (AI_VOICE mode)
                             ├─→ [requires: ScriptVersion]
                             ├─→ [mode: AI_VOICE — beat-by-beat TTS]
                             └─→ [outputs: AudioMaster]
                                      │
                                      └──→ DUBBING
                                             ├─→ [requires: AudioMaster]
                                             └─→ [outputs: DubTrack[]]

MEDIA_UPLOAD (user action, explicit)
    └──→ [outputs: video_path in ProjectState]
             │
             ├──→ SYNC
             │      ├─→ [requires: video_path, ScriptVersion.beats]
             │      └─→ [outputs: SyncMap]
             │             │
             │             └──→ AUDIO (CREATOR_VOICE mode)
             │                    ├─→ [requires: video_path, SyncMap]
             │                    ├─→ [mode: CREATOR_VOICE — extract/clean]
             │                    └─→ [outputs: AudioMaster]
             │                             │
             │                             └──→ DUBBING
             │                                    └─→ [outputs: DubTrack[]]
             │
             └──→ STORYBOARD (alternative: generate from recorded video)
                    ├─→ [requires: video_path, ScriptVersion]
                    └─→ [outputs: ShotPlan derived from actual footage]

COMPLIANCE (cross-cutting checkpoint)
    ├─→ Runs AFTER any stage that produces checkable artifacts
    ├─→ [triggers: SCRIPT complete, STORYBOARD complete, AUDIO complete, etc.]
    ├─→ [inputs: stage output + prior tracked assets]
    └─→ [outputs: ClearanceReport with GREEN/YELLOW/RED status]
         └─→ GREEN: allow dependent stages to proceed
         └─→ YELLOW: block dependent stages until approval
         └─→ RED: block permanently

FINAL: PUBLISH_READY
    └─→ [requires: Script, Storyboard, Audio (or Dubbing), all compliance GREEN]
```

### 2.3 Key DAG Properties

1. **Multiple entry points:**
   - SCRIPT can start without CreatorScout
   - MEDIA_UPLOAD can happen independently
   - Compliance can be triggered on-demand

2. **Branch paths (audio modes):**
   - **AI_VOICE path:** SCRIPT → AUDIO(AI) → DUBBING
   - **CREATOR_VOICE path:** SCRIPT → MEDIA → SYNC → AUDIO(CREATOR) → DUBBING

3. **Independent stages:**
   - CREATOR_SCOUT can run in parallel with SCRIPT
   - STORYBOARD can be generated before or after MEDIA_UPLOAD

4. **Compliance as cross-cutting concern:**
   - Not a stage in the DAG; runs as a **checkpoint decorator**
   - Attached to stage completion events
   - Blocks downstream stages if YELLOW/RED

---

## 3. PROPOSED ARCHITECTURE (REVISED)

### 3.1 Core Layers

```
┌──────────────────────────────────────────────────────────────────┐
│              Frontend / Chat Client (HTTP/WebSocket)             │
├──────────────────────────────────────────────────────────────────┤
│  API Routes Layer (new)                                          │
│  • POST   /projects                    (create)                  │
│  • GET    /projects/{id}               (get state)               │
│  • POST   /projects/{id}/stages/{stage} (invoke single stage)    │
│  • POST   /projects/{id}/chat          (chat + intent routing)   │
│  • GET    /projects/{id}/jobs/{job_id} (poll job status)         │
│  • POST   /projects/{id}/approve       (compliance approval)     │
│  • POST   /projects/{id}/media         (upload media)            │
│  • GET    /projects/{id}/dag           (get execution graph)     │
├──────────────────────────────────────────────────────────────────┤
│  Orchestrator Layer (new, DAG-based)                             │
│  • WorkflowDAG           (stage dependencies, topological sort)  │
│  • StageExecutor         (async agent invocation)                │
│  • JobManager            (background task tracking)              │
│  • ComplianceDecorator   (cross-cutting checkpoint logic)        │
│  • ChatIntentRouter      (parse chat → workflow actions)         │
├──────────────────────────────────────────────────────────────────┤
│  Agent Adapter Layer (thin wrappers, UNCHANGED from V1)          │
│  • Adapters: ProjectState ↔ agent inputs/outputs                 │
├──────────────────────────────────────────────────────────────────┤
│  Agent Layer (existing, UNCHANGED)                               │
│  • CreatorScout, Script, Storyboard, Audio, Dub, Sync, Compliance│
├──────────────────────────────────────────────────────────────────┤
│  Persistence Layer (new, UNCHANGED from V1)                      │
│  • ProjectRepository, JobRepository, ComplianceLedgerRepository  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Workflow DAG Implementation

```python
from enum import Enum
from typing import List, Set, Dict, Optional
from pydantic import BaseModel

class StageType(str, Enum):
    """Workflow stages (nodes in DAG)"""
    PROJECT_CREATED = "PROJECT_CREATED"
    CREATOR_SCOUT = "CREATOR_SCOUT"
    SCRIPT = "SCRIPT"
    STORYBOARD = "STORYBOARD"
    MEDIA_UPLOAD = "MEDIA_UPLOAD"
    SYNC = "SYNC"
    AUDIO_AI_VOICE = "AUDIO_AI_VOICE"
    AUDIO_CREATOR_VOICE = "AUDIO_CREATOR_VOICE"
    DUBBING = "DUBBING"
    PUBLISH_READY = "PUBLISH_READY"

class StageDependency(BaseModel):
    """Edge in DAG: target_stage depends on source_stage"""
    source: StageType
    target: StageType
    condition: Optional[str] = None  # e.g., "audio_mode == AI_VOICE"

class WorkflowDAG:
    """
    Defines the workflow as a directed acyclic graph.
    Stages are nodes; dependencies are edges.
    """
    
    def __init__(self):
        self.stages: Set[StageType] = set()
        self.dependencies: List[StageDependency] = []
        self._build_default_dag()
    
    def _build_default_dag(self):
        """Define the default Agentic Cinema workflow DAG"""
        
        # Entry point
        self.add_stage(StageType.PROJECT_CREATED)
        
        # Independent: CreatorScout can run anytime after project creation
        self.add_stage(StageType.CREATOR_SCOUT)
        self.add_dependency(StageType.PROJECT_CREATED, StageType.CREATOR_SCOUT)
        
        # Core: Script depends only on project creation
        self.add_stage(StageType.SCRIPT)
        self.add_dependency(StageType.PROJECT_CREATED, StageType.SCRIPT)
        
        # Storyboard depends on Script
        self.add_stage(StageType.STORYBOARD)
        self.add_dependency(StageType.SCRIPT, StageType.STORYBOARD)
        
        # Audio (AI mode) depends on Script
        self.add_stage(StageType.AUDIO_AI_VOICE)
        self.add_dependency(StageType.SCRIPT, StageType.AUDIO_AI_VOICE,
                          condition="audio_mode == AI_VOICE")
        
        # Media upload is independent (user action)
        self.add_stage(StageType.MEDIA_UPLOAD)
        
        # Sync depends on Media + Script
        self.add_stage(StageType.SYNC)
        self.add_dependency(StageType.MEDIA_UPLOAD, StageType.SYNC)
        self.add_dependency(StageType.SCRIPT, StageType.SYNC)
        
        # Audio (creator mode) depends on Sync
        self.add_stage(StageType.AUDIO_CREATOR_VOICE)
        self.add_dependency(StageType.SYNC, StageType.AUDIO_CREATOR_VOICE,
                          condition="audio_mode == CREATOR_VOICE")
        
        # Dubbing depends on either Audio path
        self.add_stage(StageType.DUBBING)
        self.add_dependency(StageType.AUDIO_AI_VOICE, StageType.DUBBING,
                          condition="audio_mode == AI_VOICE")
        self.add_dependency(StageType.AUDIO_CREATOR_VOICE, StageType.DUBBING,
                          condition="audio_mode == CREATOR_VOICE")
        
        # Publish depends on core stages being complete
        self.add_stage(StageType.PUBLISH_READY)
        self.add_dependency(StageType.SCRIPT, StageType.PUBLISH_READY)
        self.add_dependency(StageType.STORYBOARD, StageType.PUBLISH_READY)
        # At least one audio path
        self.add_dependency(StageType.AUDIO_AI_VOICE, StageType.PUBLISH_READY,
                          condition="audio_mode == AI_VOICE")
        self.add_dependency(StageType.AUDIO_CREATOR_VOICE, StageType.PUBLISH_READY,
                          condition="audio_mode == CREATOR_VOICE")
    
    def add_stage(self, stage: StageType):
        self.stages.add(stage)
    
    def add_dependency(self, source: StageType, target: StageType, condition: Optional[str] = None):
        self.dependencies.append(StageDependency(source=source, target=target, condition=condition))
    
    def get_dependencies(self, stage: StageType, project_state: "ProjectState") -> Set[StageType]:
        """
        Return all stages that must complete before `stage` can run.
        Evaluates conditional dependencies based on project_state.
        """
        deps = set()
        for dep in self.dependencies:
            if dep.target == stage:
                # Evaluate condition if present
                if dep.condition:
                    if self._evaluate_condition(dep.condition, project_state):
                        deps.add(dep.source)
                else:
                    deps.add(dep.source)
        return deps
    
    def get_ready_stages(self, project_state: "ProjectState") -> Set[StageType]:
        """
        Return all stages that can run now (dependencies satisfied, not yet complete).
        """
        completed = set(project_state.completed_stages)
        ready = set()
        
        for stage in self.stages:
            if stage in completed:
                continue
            
            deps = self.get_dependencies(stage, project_state)
            if deps.issubset(completed):
                ready.add(stage)
        
        return ready
    
    def _evaluate_condition(self, condition: str, project_state: "ProjectState") -> bool:
        """
        Evaluate a conditional dependency.
        Simple eval for now; can be replaced with safer expression parser.
        """
        context = {
            "audio_mode": project_state.workflow_config.audio_mode,
            "has_media": project_state.media_manifest is not None,
            "has_script": project_state.script is not None,
        }
        try:
            return eval(condition, {"__builtins__": {}}, context)
        except Exception:
            return False
```

---

## 4. API ROUTES & CONTRACTS (REVISED)

### 4.1 Create Project
```
POST /projects
{
  "project_id": "proj_001",                    # optional; auto-generated UUID if omitted
  "project_name": "Summer Campaign 2026",
  "creator_profile": { /* CreatorProfile */ },
  "deal_context": { /* DealContext, optional */ },
  "config": {
    "audio_mode": "AI_VOICE",                 # AI_VOICE | CREATOR_VOICE
    "enable_creator_scout": false,            # optional, default false
    "target_locales": ["es", "fr"],           # for DUBBING
    "request_approval_for_yellow": true       # compliance approval behavior
  }
}

Response: 201 Created
{
  "project_id": "proj_001",
  "status": "created",
  "completed_stages": ["PROJECT_CREATED"],
  "ready_stages": ["SCRIPT", "CREATOR_SCOUT"],  # stages that can run now
  "dag": { /* serialized WorkflowDAG */ },
  "created_at": "2026-09-06T05:23:11Z"
}
```

### 4.2 Get Project State
```
GET /projects/{project_id}

Response: 200 OK
{
  "project_id": "proj_001",
  "project_name": "Summer Campaign 2026",
  "status": "in_progress",                    # created, in_progress, blocked, completed
  "completed_stages": ["PROJECT_CREATED", "SCRIPT", "STORYBOARD"],
  "ready_stages": ["AUDIO_AI_VOICE"],         # can be invoked now
  "blocked_stages": {                         # stages blocked by compliance
    "DUBBING": "COMPLIANCE_AUDIO_YELLOW"
  },
  "running_jobs": [                           # currently executing stages
    {
      "job_id": "job_abc123",
      "stage": "AUDIO_AI_VOICE",
      "status": "running",
      "progress": 0.65,
      "started_at": "2026-09-06T06:10:00Z"
    }
  ],
  "project_state": { /* full ProjectState with outputs */ },
  "created_at": "2026-09-06T05:23:11Z",
  "updated_at": "2026-09-06T06:10:30Z"
}
```

### 4.3 Invoke Single Stage (NEW — direct invocation)
```
POST /projects/{project_id}/stages/{stage_name}
{
  "input": {                                  # optional stage-specific overrides
    "brief": "Product launch for Gen Z audience...",
    "research_enabled": true
  },
  "force": false                              # optional; bypass dependency checks
}

Response: 202 Accepted (async execution)
{
  "project_id": "proj_001",
  "stage": "SCRIPT",
  "job_id": "job_xyz789",
  "status": "queued",
  "estimated_duration": 15,                   # seconds
  "dependencies_satisfied": true,
  "job_url": "/projects/proj_001/jobs/job_xyz789"
}

OR Response: 400 Bad Request (dependencies not satisfied)
{
  "error": "dependencies_not_satisfied",
  "stage": "AUDIO_CREATOR_VOICE",
  "missing_dependencies": ["SYNC"],
  "ready_stages": ["STORYBOARD"],
  "message": "Cannot run AUDIO_CREATOR_VOICE; SYNC has not completed yet."
}
```

### 4.4 Chat with Intent Router (NEW)
```
POST /projects/{project_id}/chat
{
  "message": "Can we use a more dramatic tone for beat 3?",
  "context": {
    "referencing": ["beat_003"]             # optional; UI highlights
  }
}

Response: 200 OK
{
  "message_id": "msg_001",
  "intent": "revise_script_beat",           # detected intent
  "action": {
    "type": "invoke_stage",
    "stage": "SCRIPT",
    "params": {
      "revision_target": "beat_003",
      "instruction": "Use more dramatic tone"
    }
  },
  "response": "I'll regenerate beat 3 with a more dramatic tone. This will take about 10 seconds.",
  "job_id": "job_revision_001",              # if action is async
  "job_url": "/projects/proj_001/jobs/job_revision_001"
}

OR Response: 200 OK (clarification needed)
{
  "message_id": "msg_002",
  "intent": "clarify",
  "response": "Which beat would you like to revise? You have 12 beats in the current script.",
  "suggested_actions": [
    { "label": "Beat 3", "action": "revise_beat", "params": { "beat_id": "beat_003" } },
    { "label": "All beats", "action": "regenerate_script", "params": {} }
  ]
}
```

**Intent Router Classification:**
- `revise_script_beat` → invoke SCRIPT with revision params
- `regenerate_storyboard` → invoke STORYBOARD
- `change_audio_mode` → update project config, re-run AUDIO
- `upload_media` → return media upload URL
- `check_compliance` → manually trigger compliance checkpoint
- `clarify` → ask user for more context

### 4.5 Poll Job Status (NEW — standardized async pattern)
```
GET /projects/{project_id}/jobs/{job_id}

Response: 200 OK (job running)
{
  "job_id": "job_xyz789",
  "project_id": "proj_001",
  "stage": "STORYBOARD",
  "status": "running",                      # queued, running, completed, failed, cancelled
  "progress": 0.45,                         # 0.0 to 1.0
  "phase": "visual_asset_generation",       # current sub-phase (if agent reports)
  "started_at": "2026-09-06T06:15:00Z",
  "estimated_completion": "2026-09-06T06:17:30Z",
  "logs": [                                 # recent log entries
    { "timestamp": "2026-09-06T06:15:30Z", "message": "Reference research complete" },
    { "timestamp": "2026-09-06T06:16:00Z", "message": "Generating shot 5/12..." }
  ]
}

Response: 200 OK (job completed)
{
  "job_id": "job_xyz789",
  "project_id": "proj_001",
  "stage": "STORYBOARD",
  "status": "completed",
  "progress": 1.0,
  "started_at": "2026-09-06T06:15:00Z",
  "completed_at": "2026-09-06T06:17:45Z",
  "result": {
    "output": { /* ShotPlan */ },
    "compliance_status": "GREEN",           # if compliance ran automatically
    "next_ready_stages": ["AUDIO_AI_VOICE", "MEDIA_UPLOAD"]
  }
}

Response: 200 OK (job failed)
{
  "job_id": "job_xyz789",
  "project_id": "proj_001",
  "stage": "STORYBOARD",
  "status": "failed",
  "progress": 0.65,
  "started_at": "2026-09-06T06:15:00Z",
  "failed_at": "2026-09-06T06:16:30Z",
  "error": {
    "type": "ProviderFailure",
    "message": "Gemini API quota exceeded",
    "recoverable": true,
    "retry_after": 60                       # seconds
  },
  "retry_url": "/projects/proj_001/stages/STORYBOARD"
}
```

### 4.6 Get Execution DAG (NEW — visualization)
```
GET /projects/{project_id}/dag

Response: 200 OK
{
  "nodes": [
    { "stage": "PROJECT_CREATED", "status": "completed" },
    { "stage": "SCRIPT", "status": "completed" },
    { "stage": "STORYBOARD", "status": "running", "job_id": "job_abc" },
    { "stage": "AUDIO_AI_VOICE", "status": "ready" },
    { "stage": "AUDIO_CREATOR_VOICE", "status": "blocked", "reason": "audio_mode != CREATOR_VOICE" },
    { "stage": "SYNC", "status": "not_ready", "missing_deps": ["MEDIA_UPLOAD"] }
  ],
  "edges": [
    { "source": "PROJECT_CREATED", "target": "SCRIPT" },
    { "source": "SCRIPT", "target": "STORYBOARD" },
    { "source": "SCRIPT", "target": "AUDIO_AI_VOICE", "condition": "audio_mode == AI_VOICE" }
  ]
}
```

### 4.7 Compliance Approval (UNCHANGED from V1, but async)
```
POST /projects/{project_id}/approve
{
  "checkpoint_id": "compliance_storyboard_001",
  "decisions": [
    {
      "issue_id": "iss_123",
      "decision": "OVERRIDE",               # OVERRIDE, REQUEST_SUBSTITUTE, REJECT
      "notes": "Brand approved this reference"
    }
  ]
}

Response: 200 OK
{
  "checkpoint_id": "compliance_storyboard_001",
  "status": "approved",
  "unblocked_stages": ["AUDIO_AI_VOICE"],   # stages now ready
  "project_state": { /* updated */ }
}
```

### 4.8 Upload Media (UNCHANGED from V1)
```
POST /projects/{project_id}/media
Content-Type: multipart/form-data
{
  "file": <binary video>,
  "media_type": "video/mp4"
}

Response: 200 OK
{
  "media_id": "media_001",
  "file_path": "storage/proj_001/media_001.mp4",
  "duration": 120.5,
  "completed_stages": ["MEDIA_UPLOAD"],
  "ready_stages": ["SYNC"]                  # SYNC now unblocked
}
```

---

## 5. ORCHESTRATION LOGIC (REVISED)

### 5.1 StageExecutor (Async Agent Invocation)

```python
import asyncio
from typing import Optional, Dict, Any
from enum import Enum

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Job(BaseModel):
    job_id: str
    project_id: str
    stage: StageType
    status: JobStatus
    progress: float = 0.0
    phase: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[dict] = None
    result: Optional[dict] = None

class StageExecutor:
    """
    Executes individual workflow stages asynchronously.
    Wraps agent invocation with job tracking, progress reporting, and error handling.
    """
    
    def __init__(
        self,
        project_repo: ProjectRepository,
        job_repo: JobRepository,
        adapters: Dict[StageType, Any],
        dag: WorkflowDAG,
    ):
        self.project_repo = project_repo
        self.job_repo = job_repo
        self.adapters = adapters
        self.dag = dag
    
    async def execute_stage(
        self,
        project_id: str,
        stage: StageType,
        input_override: Optional[Dict] = None,
        force: bool = False,
    ) -> Job:
        """
        Execute a single workflow stage asynchronously.
        Returns a Job object immediately; actual execution happens in background.
        """
        
        # 1. Validate dependencies
        project = await self.project_repo.load(project_id)
        if not force:
            deps = self.dag.get_dependencies(stage, project)
            completed = set(project.completed_stages)
            missing = deps - completed
            if missing:
                raise DependencyNotSatisfiedError(
                    stage=stage,
                    missing=list(missing),
                    ready=list(self.dag.get_ready_stages(project)),
                )
        
        # 2. Create job
        job = Job(
            job_id=str(uuid.uuid4()),
            project_id=project_id,
            stage=stage,
            status=JobStatus.QUEUED,
            started_at=datetime.utcnow(),
        )
        await self.job_repo.save(job)
        
        # 3. Run in background
        asyncio.create_task(self._run_stage_job(job, input_override))
        
        return job
    
    async def _run_stage_job(self, job: Job, input_override: Optional[Dict] = None):
        """Background task: invoke agent and handle result"""
        try:
            job.status = JobStatus.RUNNING
            await self.job_repo.save(job)
            
            # Load project
            project = await self.project_repo.load(job.project_id)
            
            # Get adapter
            adapter = self.adapters.get(job.stage)
            if not adapter:
                raise ValueError(f"No adapter for stage {job.stage}")
            
            # Map input
            agent_input = await adapter.to_agent_input(project, input_override)
            
            # Invoke agent with progress callback
            agent_output = await self._invoke_agent(
                job.stage,
                agent_input,
                progress_callback=lambda progress, phase: self._update_job_progress(job.job_id, progress, phase),
            )
            
            # Map output back to ProjectState
            updated_project = await adapter.to_project_state(project, agent_output)
            updated_project.completed_stages.append(job.stage)
            await self.project_repo.save(updated_project)
            
            # Mark job complete
            job.status = JobStatus.COMPLETED
            job.progress = 1.0
            job.completed_at = datetime.utcnow()
            job.result = {"output": agent_output.dict() if hasattr(agent_output, "dict") else agent_output}
            await self.job_repo.save(job)
            
            # Trigger compliance checkpoint if needed
            if self._should_run_compliance(job.stage):
                await self._run_compliance_checkpoint(updated_project, job.stage)
        
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = {
                "type": type(e).__name__,
                "message": str(e),
                "recoverable": self._is_recoverable(e),
            }
            await self.job_repo.save(job)
            
            # Log error to project
            project = await self.project_repo.load(job.project_id)
            project.current_errors.append({
                "stage": job.stage,
                "error": str(e),
                "job_id": job.job_id,
            })
            await self.project_repo.save(project)
    
    async def _invoke_agent(
        self,
        stage: StageType,
        agent_input: Dict,
        progress_callback: Optional[callable] = None,
    ) -> Any:
        """Invoke the appropriate agent for this stage"""
        
        if stage == StageType.CREATOR_SCOUT:
            agent = CreatorScoutAgent()
            return await agent.run(CreatorScoutRequest(**agent_input))
        
        elif stage == StageType.SCRIPT:
            agent = ScriptSuggestorAgent()
            return await agent.run(ScriptRequest(**agent_input))
        
        elif stage == StageType.STORYBOARD:
            agent = StoryboardAgent()
            # Wrap sync call in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                agent.generate_full_pipeline,
                **agent_input,
            )
        
        elif stage == StageType.SYNC:
            agent = SyncerAgent()
            return await agent.run(SyncRequest(**agent_input))
        
        elif stage in (StageType.AUDIO_AI_VOICE, StageType.AUDIO_CREATOR_VOICE):
            agent = AudioAgent()
            # Determine mode from stage
            mode = AudioInputMode.AI_VOICE if stage == StageType.AUDIO_AI_VOICE else AudioInputMode.CREATOR_VOICE
            return await agent.run(AudioRequest(mode=mode, **agent_input))
        
        elif stage == StageType.DUBBING:
            agent = CulturalDubAgent()
            return await agent.run(DubRequest(**agent_input))
        
        else:
            raise ValueError(f"Unknown stage: {stage}")
    
    async def _update_job_progress(self, job_id: str, progress: float, phase: Optional[str] = None):
        """Update job progress (called by agent during execution)"""
        job = await self.job_repo.load(job_id)
        job.progress = progress
        job.phase = phase
        await self.job_repo.save(job)
    
    def _should_run_compliance(self, stage: StageType) -> bool:
        """Check if compliance should run after this stage"""
        compliance_stages = {
            StageType.SCRIPT,
            StageType.STORYBOARD,
            StageType.AUDIO_AI_VOICE,
            StageType.AUDIO_CREATOR_VOICE,
            StageType.DUBBING,
        }
        return stage in compliance_stages
    
    async def _run_compliance_checkpoint(self, project: ProjectState, stage: StageType):
        """Run compliance checkpoint as a cross-cutting concern"""
        compliance_agent = ComplianceAgent()
        
        # Build compliance request
        compliance_input = self._build_compliance_input(project, stage)
        
        report = await compliance_agent.run(ComplianceRequest(**compliance_input))
        
        # Store report
        project.clearance_report = report
        await self.project_repo.save(project)
        
        # Handle blocking if YELLOW/RED
        if report.status == ReportStatus.YELLOW and project.workflow_config.request_approval_for_yellow:
            # Block dependent stages
            checkpoint_id = f"compliance_{stage}_{uuid.uuid4()}"
            # Store pending approval in DB
            await self._store_pending_approval(project.project_id, checkpoint_id, report)
        
        elif report.status == ReportStatus.RED:
            # Hard block: fail project
            project.current_errors.append({
                "stage": stage,
                "error": "Compliance RED — unresolvable issues",
                "report": report.dict(),
            })
            await self.project_repo.save(project)
    
    def _build_compliance_input(self, project: ProjectState, stage: StageType) -> Dict:
        """Build ComplianceRequest from project state"""
        # Implementation depends on stage; extract relevant artifacts
        payload = {}
        image_paths = []
        audio_paths = []
        
        if stage == StageType.SCRIPT:
            payload = {"script": project.script.dict()}
        elif stage == StageType.STORYBOARD:
            payload = {"storyboard": project.storyboard.dict()}
            image_paths = [shot.generated_image for shot in project.storyboard.shots if shot.generated_image]
        elif stage in (StageType.AUDIO_AI_VOICE, StageType.AUDIO_CREATOR_VOICE):
            payload = {"audio": project.audio_master.dict()}
            audio_paths = [project.audio_master.file_path]
        # ... etc
        
        return {
            "stage": stage.value,
            "payload": payload,
            "image_paths": image_paths,
            "audio_paths": audio_paths,
            "prior_tracked_assets": project.clearance_report.tracked_assets if project.clearance_report else [],
        }
    
    def _is_recoverable(self, error: Exception) -> bool:
        """Classify errors as recoverable or not"""
        recoverable_types = (
            TimeoutError,
            ConnectionError,
            # Add provider-specific errors
        )
        return isinstance(error, recoverable_types)
```

### 5.2 ChatIntentRouter (NEW)

```python
from typing import Literal

class ChatIntent(str, Enum):
    REVISE_SCRIPT_BEAT = "revise_script_beat"
    REGENERATE_SCRIPT = "regenerate_script"
    REGENERATE_STORYBOARD = "regenerate_storyboard"
    CHANGE_AUDIO_MODE = "change_audio_mode"
    UPLOAD_MEDIA = "upload_media"
    CHECK_COMPLIANCE = "check_compliance"
    CLARIFY = "clarify"
    STATUS_QUERY = "status_query"

class ChatAction(BaseModel):
    type: Literal["invoke_stage", "update_config", "return_info", "clarify"]
    stage: Optional[StageType] = None
    params: Dict[str, Any] = {}

class ChatIntentRouter:
    """
    Parse creator chat messages and route to appropriate workflow actions.
    Uses LLM-based intent classification + structured output.
    """
    
    def __init__(self, gemini_client: GeminiClient):
        self.gemini = gemini_client
    
    async def route(
        self,
        message: str,
        project: ProjectState,
        context: Optional[Dict] = None,
    ) -> tuple[ChatIntent, ChatAction, str]:
        """
        Classify intent and determine action.
        Returns: (intent, action, response_message)
        """
        
        # Build prompt for intent classification
        prompt = self._build_intent_prompt(message, project, context)
        
        # Call Gemini with structured output
        classification = await self.gemini.generate_content(
            prompt=prompt,
            response_schema={
                "type": "object",
                "properties": {
                    "intent": {"type": "string", "enum": [e.value for e in ChatIntent]},
                    "confidence": {"type": "number"},
                    "extracted_params": {"type": "object"},
                    "response": {"type": "string"},
                },
            },
        )
        
        intent = ChatIntent(classification["intent"])
        params = classification["extracted_params"]
        response = classification["response"]
        
        # Map intent to action
        action = self._intent_to_action(intent, params, project)
        
        return intent, action, response
    
    def _build_intent_prompt(self, message: str, project: ProjectState, context: Optional[Dict]) -> str:
        """Build structured prompt for intent classification"""
        return f"""
You are an intent classifier for the Agentic Cinema workflow assistant.

Project context:
- Completed stages: {', '.join(project.completed_stages)}
- Ready stages: {', '.join(self._get_ready_stages(project))}
- Current script beats: {len(project.script.beats) if project.script else 0}
- Audio mode: {project.workflow_config.audio_mode}

User message: "{message}"

Classify the user's intent and extract relevant parameters.

Available intents:
- revise_script_beat: User wants to change a specific beat
- regenerate_script: User wants to regenerate the entire script
- regenerate_storyboard: User wants to regenerate storyboard
- change_audio_mode: User wants to switch between AI and creator voice
- upload_media: User wants to upload video
- check_compliance: User wants to manually check compliance
- status_query: User is asking about project status
- clarify: Intent is unclear; need more information

Return structured JSON with:
- intent: one of the above
- confidence: 0.0 to 1.0
- extracted_params: relevant parameters (beat_id, instruction, new_mode, etc.)
- response: friendly message to user explaining what you'll do next
"""
    
    def _intent_to_action(self, intent: ChatIntent, params: Dict, project: ProjectState) -> ChatAction:
        """Map classified intent to workflow action"""
        
        if intent == ChatIntent.REVISE_SCRIPT_BEAT:
            return ChatAction(
                type="invoke_stage",
                stage=StageType.SCRIPT,
                params={
                    "revision_target": params.get("beat_id"),
                    "instruction": params.get("instruction"),
                },
            )
        
        elif intent == ChatIntent.REGENERATE_SCRIPT:
            return ChatAction(
                type="invoke_stage",
                stage=StageType.SCRIPT,
                params={"regenerate": True},
            )
        
        elif intent == ChatIntent.REGENERATE_STORYBOARD:
            return ChatAction(
                type="invoke_stage",
                stage=StageType.STORYBOARD,
                params={},
            )
        
        elif intent == ChatIntent.CHANGE_AUDIO_MODE:
            new_mode = params.get("new_mode", "CREATOR_VOICE")
            return ChatAction(
                type="update_config",
                params={"audio_mode": new_mode},
            )
        
        elif intent == ChatIntent.CHECK_COMPLIANCE:
            return ChatAction(
                type="invoke_stage",
                stage="COMPLIANCE_MANUAL",
                params={},
            )
        
        elif intent == ChatIntent.STATUS_QUERY:
            return ChatAction(
                type="return_info",
                params={"info_type": "status"},
            )
        
        else:  # CLARIFY
            return ChatAction(
                type="clarify",
                params={"reason": "unclear_intent"},
            )
```

---

## 6. COMPLIANCE AS CROSS-CUTTING CHECKPOINT (REVISED)

### Compliance Decorator Pattern

Instead of treating Compliance as a stage in the DAG, it runs as a **decorator** around stage completion:

```python
class ComplianceDecorator:
    """
    Cross-cutting compliance checkpoint.
    Runs automatically after specified stages complete.
    """
    
    COMPLIANCE_STAGES = {
        StageType.SCRIPT,
        StageType.STORYBOARD,
        StageType.AUDIO_AI_VOICE,
        StageType.AUDIO_CREATOR_VOICE,
        StageType.DUBBING,
    }
    
    def __init__(self, compliance_agent: ComplianceAgent, project_repo: ProjectRepository):
        self.agent = compliance_agent
        self.repo = project_repo
    
    async def check(self, project_id: str, stage: StageType) -> ClearanceReport:
        """Run compliance check after stage completion"""
        
        if stage not in self.COMPLIANCE_STAGES:
            # No compliance needed for this stage
            return None
        
        project = await self.repo.load(project_id)
        
        # Build compliance request from stage output
        request = self._build_request(project, stage)
        
        # Run compliance
        report = await self.agent.run(request)
        
        # Store report
        project.clearance_report = report
        await self.repo.save(project)
        
        # Handle blocking
        if report.status == ReportStatus.YELLOW:
            await self._handle_yellow(project_id, stage, report)
        elif report.status == ReportStatus.RED:
            await self._handle_red(project_id, stage, report)
        
        return report
    
    async def _handle_yellow(self, project_id: str, stage: StageType, report: ClearanceReport):
        """Block dependent stages pending approval"""
        project = await self.repo.load(project_id)
        
        if project.workflow_config.request_approval_for_yellow:
            # Create pending approval record
            checkpoint = ComplianceCheckpoint(
                checkpoint_id=f"checkpoint_{stage}_{uuid.uuid4()}",
                project_id=project_id,
                stage=stage,
                report=report,
                status="pending_approval",
            )
            await self.repo.save_checkpoint(checkpoint)
            
            # Mark project as blocked
            project.blocked_stages = self._get_dependent_stages(project, stage)
            await self.repo.save(project)
        else:
            # Auto-approve YELLOW
            pass
    
    async def _handle_red(self, project_id: str, stage: StageType, report: ClearanceReport):
        """Hard block: prevent dependent stages from running"""
        project = await self.repo.load(project_id)
        
        # Block all downstream stages
        project.blocked_stages = self._get_dependent_stages(project, stage)
        project.current_errors.append({
            "type": "compliance_red",
            "stage": stage,
            "issues": [issue.dict() for issue in report.issues],
        })
        await self.repo.save(project)
    
    def _get_dependent_stages(self, project: ProjectState, stage: StageType) -> List[StageType]:
        """Get all stages that depend on `stage`"""
        dag = WorkflowDAG()
        dependent = []
        for dep in dag.dependencies:
            if dep.source == stage:
                dependent.append(dep.target)
        return dependent
```

---

## 7. FILE STRUCTURE (REVISED)

### New Files

```
app/orchestration/
├── __init__.py
├── dag.py                    # WorkflowDAG, StageDependency
├── executor.py               # StageExecutor (async agent invocation)
├── job_manager.py            # JobManager, Job status tracking
├── compliance_decorator.py   # ComplianceDecorator (cross-cutting)
├── intent_router.py          # ChatIntentRouter
└── error_handling.py         # Retry logic, error classification

app/api/routes/
├── __init__.py
├── projects.py               # POST /projects, GET /projects/{id}
├── stages.py                 # POST /projects/{id}/stages/{stage}
├── jobs.py                   # GET /projects/{id}/jobs/{job_id}
├── chat.py                   # POST /projects/{id}/chat
├── approval.py               # POST /projects/{id}/approve
├── media.py                  # POST /projects/{id}/media
└── dag.py                    # GET /projects/{id}/dag

app/api/
├── schemas.py                # Request/response Pydantic models
└── dependencies.py           # FastAPI dependencies

app/persistence/
├── __init__.py
├── database.py               # SQLite connection
├── models.py                 # SQLAlchemy ORM models
├── project_repository.py     # ProjectState CRUD
├── job_repository.py         # Job CRUD
└── compliance_repository.py  # Compliance checkpoint CRUD

app/shared/adapters/
├── __init__.py
├── base.py                   # AdapterBase
├── creator_scout.py
├── script_suggestor.py
├── storyboard.py
├── audio.py                  # Handles both AI_VOICE and CREATOR_VOICE
├── cultural_dub.py
├── syncer.py
└── (compliance is not here; runs as decorator)

tests/
├── orchestration/
│   ├── test_dag.py           # DAG construction, topological sort
│   ├── test_executor.py      # Stage execution, async handling
│   ├── test_intent_router.py # Chat intent classification
│   └── test_compliance.py    # Compliance decorator
├── api/
│   ├── test_projects.py
│   ├── test_stages.py        # Direct stage invocation
│   ├── test_jobs.py          # Job polling
│   ├── test_chat.py          # Chat endpoint
│   └── test_e2e_dag.py       # Full DAG workflow
```

### Modified Files (Minimal)

```
app/main.py
├── Register all route routers
├── Initialize WorkflowDAG
├── Initialize StageExecutor, JobManager, ComplianceDecorator
└── Lifespan: DB init, cleanup background jobs

app/config/settings.py
├── Add: AUDIO_MODE (default AI_VOICE)
├── Add: JOB_TIMEOUT, MAX_CONCURRENT_JOBS
├── Add: COMPLIANCE_AUTO_APPROVE_YELLOW (default False)

app/shared/models/project.py
├── Add: completed_stages: List[StageType]
├── Add: blocked_stages: List[StageType]
├── Add: workflow_config.audio_mode
├── Add: current_errors: List[Dict]
```

**Total:** 31 new files, 3 modified files.

---

## 8. DATABASE SCHEMA (REVISED)

```sql
-- Projects table (mostly unchanged)
CREATE TABLE projects (
    project_id TEXT PRIMARY KEY,
    project_name TEXT NOT NULL,
    creator_profile JSON NOT NULL,
    deal_context JSON,
    workflow_config JSON NOT NULL,
    completed_stages JSON NOT NULL,          -- List[StageType]
    blocked_stages JSON,                     -- List[StageType]
    script JSON,
    storyboard JSON,
    media_manifest JSON,
    sync_report JSON,
    audio_master JSON,
    dub_tracks JSON,
    clearance_report JSON,
    creator_recommendations JSON,
    current_errors JSON,                     -- List[Dict]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1
);

-- Jobs table (NEW)
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,                    -- queued, running, completed, failed, cancelled
    progress REAL DEFAULT 0.0,
    phase TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result JSON,
    error JSON,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- Compliance checkpoints table (NEW)
CREATE TABLE compliance_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    report JSON NOT NULL,
    status TEXT NOT NULL,                    -- pending_approval, approved, rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    decisions JSON,                          -- List of user decisions
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- Tracked assets (for compliance ledger, unchanged)
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
```

---

## 9. IMPLEMENTATION SEQUENCE (REVISED)

### Phase 1: DAG Core (2 days)
1. Create `app/orchestration/dag.py` — WorkflowDAG, stage dependencies
2. Write tests for DAG: topological sort, dependency resolution, conditional edges
3. Add `completed_stages`, `blocked_stages` to ProjectState model

### Phase 2: Job Management (1 day)
4. Create `app/persistence/job_repository.py` — Job CRUD
5. Create `app/orchestration/job_manager.py` — Background job tracking
6. Add jobs table to database schema

### Phase 3: Stage Executor (2 days)
7. Create `app/orchestration/executor.py` — StageExecutor with async agent invocation
8. Wire adapters to executor
9. Test async execution with progress callbacks

### Phase 4: Compliance Decorator (1 day)
10. Create `app/orchestration/compliance_decorator.py`
11. Wire into StageExecutor as post-completion hook
12. Test YELLOW/RED blocking behavior

### Phase 5: API Routes (2 days)
13. Create `app/api/routes/projects.py` — create, get
14. Create `app/api/routes/stages.py` — direct stage invocation
15. Create `app/api/routes/jobs.py` — job polling
16. Create `app/api/routes/dag.py` — DAG visualization
17. Register all routes in main.py

### Phase 6: Chat Intent Router (2 days)
18. Create `app/orchestration/intent_router.py`
19. Create `app/api/routes/chat.py`
20. Test intent classification with various inputs

### Phase 7: Testing & Integration (2 days)
21. Write E2E test: AI_VOICE path (Script → Audio AI → Dubbing)
22. Write E2E test: CREATOR_VOICE path (Script → Media → Sync → Audio Creator)
23. Write E2E test: Direct stage invocation
24. Write E2E test: Chat-driven workflow
25. Verify all 60+ existing agent tests pass

### Phase 8: Documentation (1 day)
26. API documentation with OpenAPI/Swagger
27. Workflow DAG examples
28. Deployment guide

**Total Estimate:** 13 days

---

## 10. SUCCESS CRITERIA (REVISED)

- ✅ **DAG execution:** Stages execute based on dependency graph, not fixed sequence
- ✅ **Direct invocation:** Can POST to `/projects/{id}/stages/SCRIPT` without running full workflow
- ✅ **Audio modes:** AI_VOICE and CREATOR_VOICE paths work independently
- ✅ **CREATOR_VOICE after Syncer:** SYNC → AUDIO_CREATOR_VOICE dependency works
- ✅ **CreatorScout optional:** Can create project and run SCRIPT without CreatorScout
- ✅ **Compliance cross-cutting:** Compliance runs after stages, not as a stage itself
- ✅ **Chat routing:** Chat messages correctly trigger workflow actions
- ✅ **Async handling:** Long-running stages return job_id; polling returns progress
- ✅ **Job status:** Can poll job status with progress, phase, logs
- ✅ **Intermediate responses:** API returns ready_stages, blocked_stages, running_jobs
- ✅ **All existing tests pass:** 60+ agent tests unchanged

---

## 11. EXAMPLE WORKFLOWS

### 11.1 AI Voice Path (No Media Upload)
```
1. POST /projects
   → project_id: proj_001
   → ready_stages: [SCRIPT, CREATOR_SCOUT]

2. POST /projects/proj_001/stages/SCRIPT
   → job_id: job_001
   → status: running

3. GET /projects/proj_001/jobs/job_001
   → status: completed
   → ready_stages: [STORYBOARD, AUDIO_AI_VOICE]

4. POST /projects/proj_001/stages/AUDIO_AI_VOICE
   → job_id: job_002
   → Audio agent runs in AI_VOICE mode (beat-by-beat TTS)

5. GET /projects/proj_001/jobs/job_002
   → status: completed
   → compliance runs automatically → GREEN
   → ready_stages: [DUBBING]

6. POST /projects/proj_001/stages/DUBBING
   → Dub tracks generated for target locales

7. GET /projects/proj_001
   → status: completed
   → ready_stages: [PUBLISH_READY]
```

### 11.2 Creator Voice Path (With Media Upload)
```
1. POST /projects
   → audio_mode: CREATOR_VOICE

2. POST /projects/proj_001/stages/SCRIPT
   → Script completed
   → ready_stages: [STORYBOARD, MEDIA_UPLOAD]

3. POST /projects/proj_001/media (upload video)
   → MEDIA_UPLOAD completed
   → ready_stages: [SYNC] (needs both MEDIA + SCRIPT)

4. POST /projects/proj_001/stages/SYNC
   → Syncer analyzes video + script beats
   → ready_stages: [AUDIO_CREATOR_VOICE]

5. POST /projects/proj_001/stages/AUDIO_CREATOR_VOICE
   → Audio agent extracts/cleans creator voice from video
   → ready_stages: [DUBBING]
```

### 11.3 Chat-Driven Revision
```
1. POST /projects/proj_001/chat
   { "message": "Make beat 3 more dramatic" }
   → intent: revise_script_beat
   → action: invoke_stage SCRIPT with revision params
   → job_id: job_revision_001

2. GET /projects/proj_001/jobs/job_revision_001
   → status: completed
   → ready_stages: [STORYBOARD] (storyboard now needs regeneration)

3. POST /projects/proj_001/chat
   { "message": "Regenerate storyboard with new script" }
   → intent: regenerate_storyboard
   → job_id: job_storyboard_002
```

---

## 12. RISKS & MITIGATIONS (REVISED)

### Risk 1: DAG Cycles
**Issue:** Misconfigured dependencies could create cycles (impossible to resolve)  
**Mitigation:** DAG validation on initialization; reject cyclic graphs; comprehensive tests

### Risk 2: Compliance Blocking Too Aggressively
**Issue:** YELLOW/RED compliance blocks entire workflow; creator frustrated  
**Mitigation:** Allow per-issue override; provide clear substitution suggestions; async approval

### Risk 3: Job Tracking State Loss
**Issue:** Server restart loses in-memory background jobs  
**Mitigation:** Persist job state to DB; resume on restart; mark orphaned jobs as failed

### Risk 4: Async Agent Latency
**Issue:** Storyboard generation takes 2–3 minutes; frontend shows no progress  
**Mitigation:** Implement progress callbacks from agents; expose phase information in job status

### Risk 5: Intent Router Misclassification
**Issue:** Chat router misunderstands creator intent; triggers wrong action  
**Mitigation:** High confidence threshold (0.8+); clarify if low confidence; allow undo/cancel

---

## 13. OPEN QUESTIONS

1. **Should we support DAG customization per project?**  
   - E.g., creator disables STORYBOARD entirely for audio-only projects?
   - **Proposed:** Yes, via workflow_config.skip_stages

2. **Can agents be paused mid-execution?**  
   - E.g., pause STORYBOARD after reference research, before asset generation?
   - **Proposed:** Phase 2 feature; requires agent-level checkpoint support

3. **How to handle partial compliance approvals?**  
   - E.g., approve 3 of 5 YELLOW issues; what happens to unapproved 2?
   - **Proposed:** Require all YELLOW issues resolved before unblocking

4. **Should we support parallel stage execution?**  
   - E.g., run STORYBOARD and AUDIO_AI_VOICE concurrently after SCRIPT?
   - **Proposed:** Yes; DAG naturally supports this; limit max_concurrent_jobs in config

---

**PLAN V2 READY FOR APPROVAL**

This revised plan implements a flexible DAG-based workflow architecture that addresses all required changes:
- ✅ State graph/DAG replaces linear sequence
- ✅ Audio independently invokable from Script
- ✅ Two Audio modes (AI/creator) with separate paths
- ✅ Creator voice follows Syncer
- ✅ CreatorScout not mandatory
- ✅ Compliance as cross-cutting checkpoint
- ✅ Chat intent router
- ✅ Intermediate execution responses (ready_stages, blocked_stages, jobs)
- ✅ Async agent invocation with job tracking
- ✅ Direct stage invocation API

**Next steps:** Await approval → Begin Phase 1 (DAG Core).
