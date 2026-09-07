# 🎬 CreatorCrew

> **An agentic AI production studio for creators, filmmakers, and screenwriters.**

CreatorCrew is a multi-agent AI system designed to assist creators across the content-production lifecycle, from discovering opportunities and developing scripts to storyboarding, audio production, cultural localization, synchronization, compliance, and creator discovery.

The system is built around **Gemini + Google Agent Development Kit (ADK) + Parallel Web Systems**, with deterministic media tooling handling operations that should not be delegated to an LLM.

---

# 1. Vision

The goal is not to build a chatbot that gives filmmaking advice.

The goal is to build an **agentic production workflow** where specialized agents can reason about a project, use external tools, research current information, generate creative assets, analyze media, and update a shared project state.

The core design principle is:

```text
                User / Creator
                      │
                      ▼
               Project State
                      │
                      ▼
                 Orchestrator
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
     Agents         Agents         Agents
       │              │              │
       └──────────────┼──────────────┘
                      ▼
                Updated State
```

Agents **do not directly call other agents**.

Instead:

```text
Agent
  ↓
Read ProjectState
  ↓
Perform reasoning + tool calls
  ↓
Write result back to ProjectState
  ↓
Orchestrator decides what runs next
```

This keeps every agent independently replaceable and allows the workflow to evolve without tightly coupling agents together.

---

# 2. Core Technology Stack

| Layer                      | Technology                       | Purpose                                                  |
| -------------------------- | -------------------------------- | -------------------------------------------------------- |
| LLM / Multimodal reasoning | Gemini                           | Reasoning, generation, video/audio understanding         |
| Agent framework            | Google ADK                       | Agent definitions, tools, orchestration                  |
| Agent runtime              | Agent Engine                     | Managed agent execution                                  |
| Web intelligence           | Parallel Web Systems             | Search, extraction, research and current web information |
| Backend                    | Python                           | Core application and agent logic                         |
| API layer                  | FastAPI                          | Backend API                                              |
| Data validation            | Pydantic                         | Shared state and agent contracts                         |
| Media processing           | FFmpeg / FFprobe                 | Deterministic media operations                           |
| Image generation           | Imagen / Gemini image generation | Storyboards, concept art, thumbnails                     |
| Audio                      | Gemini TTS / Lyria               | Voice, music and audio generation                        |
| Storage                    | Cloud Storage                    | Media staging                                            |
| Deployment                 | Cloud Run / Agent Engine         | Backend and agent deployment                             |

---

# 3. Important Architecture Principle

### Gemini decides. Deterministic tools execute.

We do **not** ask an LLM to perform operations that should be deterministic.

For example:

```text
Gemini:
"Remove dead air from 01:12 to 01:19."

        ↓

FFmpeg:
Actually performs the cut.
```

Similarly:

```text
Gemini:
"This dialogue needs to be approximately
1.4 seconds shorter."

        ↓

Audio / TTS pipeline:
Regenerates the required segment.
```

The project plan explicitly follows this separation between model reasoning and deterministic execution.

---

# 4. Agent Architecture

The system currently contains seven planned agents.

```text
agents/
│
├── script_suggestor/
├── storyboard/
├── syncer/
├── audio/
├── cultural_dub/
├── compliance/
└── creator_scout/
```

### Script Suggestor

Responsible for transforming a creator's brief into script/story recommendations.

Uses:

* Gemini
* Parallel Search
* Creator/project context
* Existing script history

The planned workflow includes research, trend understanding, script development and evidence-backed recommendations.

---

### Storyboard

Transforms the script into a visual production plan.

Expected responsibilities include:

* Shot planning
* Camera/framing recommendations
* Visual grammar
* Lighting
* Mood
* Background
* Movement
* Concept art
* Storyboard panels
* Thumbnail variants

Parallel provides web/reference research while Gemini handles multimodal analysis and generation.

---

### Syncer

Handles synchronization of independently recorded media.

Inputs can include:

* Main camera clips
* Phone/B-roll footage
* Separate recorder audio
* Creator notes

The Syncer does **not render the final video**.

Its primary responsibility is to analyze the media and produce a synchronization report/instructions.

The intended architecture uses:

```text
FFprobe
   ↓
Media metadata
   ↓
Gemini transcription
   ↓
Timestamped transcripts
   ↓
Cross-source matching
   ↓
Sync Report
```

The project plan specifically describes using the camera's onboard audio as a synchronization reference and producing timestamp-based alignment instructions rather than pretending the model performs waveform mathematics.

---

### Audio

Handles audio generation and analysis.

Planned capabilities include:

* Audio analysis
* Segment analysis
* Voice generation
* Music generation
* Sound effects
* Audio cleanup
* Audio master generation

Technologies include Gemini multimodal capabilities, Gemini TTS and Lyria.

---

### Cultural Dub

Handles localization and culturally appropriate dubbing.

Expected responsibilities include:

* Dialogue adaptation
* Cultural localization
* Multi-language generation
* Voice generation
* Subtitle/localization support
* Segment-level processing

The agent should preserve the original narrative intent rather than performing literal word-for-word translation.

---

### Compliance

Evaluates generated or creator-provided content for relevant risks.

The compliance workflow should produce structured findings rather than simply returning:

```text
"Looks safe."
```

A useful output should identify:

```text
Risk
Severity
Reason
Evidence
Recommended action
```

Where external-world claims are involved, the system should retain supporting evidence.

---

### Creator Scout

Discovers potential creators, brands and collaboration opportunities.

Expected capabilities include:

* Creator discovery
* Brand discovery
* Opportunity ranking
* Public web research
* Deal-context matching
* Creator/project compatibility analysis

Parallel provides the web research layer for this agent.

The project plan specifically describes using Parallel capabilities such as FindAll, Entity Search, Search, Extract and Task depending on the research requirement.

---

# 5. Shared Project State

The central data structure is:

```text
backend/app/shared/models/project.py
```

It contains:

```python
ProjectState
```

The state currently contains:

```text
ProjectState
│
├── project_id
├── project_name
│
├── creator_profile
├── deal_context
│
├── script
├── storyboard
├── media_manifest
│
├── sync_report
├── audio_master
├── dub_tracks
│
├── clearance_report
├── creator_recommendations
│
├── current_stage
├── updated_at
└── errors
```

This is the central contract between agents.

For example:

```text
Script Suggestor
       │
       ▼
ProjectState.script
       │
       ▼
Storyboard
       │
       ▼
ProjectState.storyboard
```

The next agent does not need to know how the previous agent internally worked.

It only needs the relevant state.

---

# 6. Shared Models

All cross-agent contracts live under:

```text
backend/app/shared/models/
```

Current model categories:

```text
models/
├── project.py
├── creator.py
├── creator_scout.py
├── deal.py
├── script.py
├── storyboard.py
├── media.py
├── sync.py
├── audio.py
├── dub.py
└── compliance.py
```

### Rule

If information needs to move between agents, it should eventually have a **shared Pydantic model**.

Avoid passing undocumented dictionaries between agents.

---

# 7. Shared Tools

Common external capabilities live under:

```text
backend/app/shared/tools/
```

Current structure:

```text
tools/
│
├── gemini/
│   └── ...
│
├── parallel/
│   └── ...
│
├── media/
│   └── ...
│
├── audio/
│   └── ...
│
└── vision/
    └── ...
```

These are **tools**, not agents.

For example:

```text
Script Suggestor
     │
     ├── Gemini
     └── Parallel Search
```

rather than:

```text
Script Suggestor
     │
     └── Parallel Agent
```

---

# 8. Gemini Integration

Gemini is wrapped as a shared service so individual agents do not repeatedly implement authentication and API configuration.

Location:

```text
backend/app/shared/tools/gemini/
```

Current status:

```text
Gemini API
    ↓
GeminiClient
    ↓
Working ✅
```

Test:

```powershell
cd backend
python -m scripts.test_gemini
```

If the test produces a generated response, Gemini connectivity is working.

---

# 9. Parallel Integration

Parallel is a mandatory runtime integration for this hackathon.

It is **not enough to mention Parallel in the README**.

The application must actually invoke Parallel at runtime.

Current structure:

```text
backend/app/shared/tools/parallel/
├── client.py
├── search.py
└── __init__.py
```

Current flow:

```text
Agent
  ↓
ParallelSearch
  ↓
Parallel SDK
  ↓
Parallel Search API
  ↓
Fresh web results
```

Test:

```powershell
cd backend
python -m scripts.test_parallel
```

Parallel is intended to provide:

* Search
* Web extraction
* Research
* Current information
* Evidence / URLs

Different agents may use different Parallel capabilities depending on their workflow.

The project plan identifies Search, Extract, Task, FindAll, Entity Search and Monitor as relevant capabilities across the system.

---

# 10. Grounding / Evidence Rule

A core system rule:

> **Claims about the outside world should have evidence.**

For example:

```text
❌ "This creator has 2.5M followers."

✅ "This creator has 2.5M followers."
   └── Source URL
```

Parallel results provide web sources and excerpts, while research-oriented workflows can preserve supporting evidence.

The final system should avoid allowing unsupported external claims to silently pass through the pipeline.

---

# 11. Media Architecture

Media processing is intentionally separated from model reasoning.

```text
                 Media Asset
                      │
              ┌───────┴────────┐
              ▼                ▼
           FFprobe           Gemini
              │                │
       technical data      semantic data
              │                │
              └───────┬────────┘
                      ▼
                  Agent Logic
                      │
                      ▼
              Deterministic Tool
                      │
                      ▼
                Final Media
```

FFmpeg/FFprobe will be used for:

* Media inspection
* Frame extraction
* Audio/video processing
* Rendering operations
* Deterministic transformations

FFmpeg installation is a local development dependency and is not required for the initial Gemini/Parallel integration tests.

---

# 12. Environment Setup

Create a virtual environment:

```powershell
python -m venv myenv
```

Activate:

```powershell
.\myenv\Scripts\Activate.ps1
```

Install backend dependencies:

```powershell
cd backend
pip install -r requirements.txt
```

Environment variables belong in:

```text
backend/.env
```

Never commit `.env`.

Use:

```text
backend/.env.example
```

for documenting required variables.

Expected configuration includes credentials for services such as:

```env
GEMINI_API_KEY=
PARALLEL_API_KEY=
```

Additional cloud credentials will be added when the corresponding infrastructure is introduced.

---

# 13. Current Development Status

### Foundation

| Component                     | Status |
| ----------------------------- | ------ |
| Repository structure          | ✅      |
| Backend / Frontend separation | ✅      |
| Python environment            | ✅      |
| Shared Pydantic models        | ✅      |
| ProjectState                  | ✅      |
| Gemini integration            | ✅      |
| Parallel Search integration   | ✅      |
| Agent folders                 | ✅      |
| Base agent contract           | ✅      |
| FFmpeg                        | ⏳      |
| ADK agent implementation      | ⏳      |
| Orchestrator                  | ⏳      |
| Frontend                      | ⏳      |
| Cloud deployment              | ⏳      |

---

# 14. Repository Structure

Current high-level structure:

```text
AgenticCinema/
│
├── README.md
├── .gitignore
│
├── backend/
│   │
│   ├── .env
│   ├── .env.example
│   ├── requirements.txt
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   │
│   │   ├── agents/
│   │   │   ├── script_suggestor/
│   │   │   ├── storyboard/
│   │   │   ├── syncer/
│   │   │   ├── audio/
│   │   │   ├── cultural_dub/
│   │   │   ├── compliance/
│   │   │   └── creator_scout/
│   │   │
│   │   ├── orchestrator/
│   │   │
│   │   ├── shared/
│   │   │   ├── models/
│   │   │   └── tools/
│   │   │
│   │   ├── api/
│   │   └── config/
│   │
│   ├── scripts/
│   │   ├── test_gemini.py
│   │   ├── test_parallel.py
│   │   └── test_project_state.py
│   │
│   └── tests/
│
└── frontend/
```

---

# 15. Where Should I Work?

Use the following ownership model:

| Area             | Primary owner      |
| ---------------- | ------------------ |
| Script Suggestor | Assigned developer |
| Storyboard       | Assigned developer |
| Syncer           | Assigned developer |
| Audio            | Assigned developer |
| Cultural Dub     | Assigned developer |
| Compliance       | Assigned developer |
| Creator Scout    | Assigned developer |
| Shared Models    | Team               |
| Shared Tools     | Team               |
| Orchestrator     | Team               |
| Frontend         | Team               |

Developer names are intentionally **not encoded into the repository structure**.

Ownership is managed through Git branches and team coordination.

---

# 16. Git Workflow

Do not directly develop features on `main`.

Create a feature branch:

```powershell
git checkout -b feature/<agent-name>
```

Examples:

```text
feature/script-suggestor
feature/storyboard
feature/syncer
feature/audio
feature/cultural-dub
feature/compliance
feature/creator-scout
```

Then:

```powershell
git add .
git commit -m "feat: implement <feature>"
git push origin feature/<agent-name>
```

Create a Pull Request into `main`.

---

# 17. Rules for Agent Development

### Rule 1: Don't call another agent directly

Avoid:

```python
storyboard_agent.run(...)
```

from inside Script Suggestor.

Instead:

```text
Agent
 ↓
ProjectState
 ↓
Orchestrator
 ↓
Next Agent
```

---

### Rule 2: Don't modify another agent's implementation

If your agent needs something from another agent:

1. Define the required data in a shared model.
2. Discuss the interface.
3. Let the orchestrator connect the workflow.

---

### Rule 3: Shared model changes require coordination

Changing:

```text
ScriptVersion
ShotPlan
SyncReport
```

can affect multiple agents.

Discuss shared-model changes before merging.

---

### Rule 4: Tools are shared infrastructure

Gemini, Parallel, FFmpeg and other integrations belong under:

```text
shared/tools/
```

Don't duplicate API clients inside individual agents.

---

### Rule 5: Agents should be independently testable

Every agent should eventually have:

```text
agent.py
prompts.py
schemas.py
tests/
```

The agent should be testable without running the entire cinematic pipeline.

---

# 18. Development Philosophy

The project follows this pipeline:

```text
          INPUT
            │
            ▼
       Agent Reasoning
            │
       ┌────┴────┐
       ▼         ▼
    Gemini    External Tools
                 │
       ┌─────────┴─────────┐
       ▼                   ▼
    Parallel          Media Tools
       │                   │
       └─────────┬─────────┘
                 ▼
             Structured
               Output
                 │
                 ▼
           ProjectState
```

The system should prefer:

```text
Structured output
```

over:

```text
Free-form LLM response
```

whenever the result is consumed by another component.

---

# 19. Cost / Efficiency Considerations

Gemini video processing is one of the more expensive parts of this architecture.

Therefore:

### Sample when possible

For visual questions:

```text
Video
 ↓
Selected frames
 ↓
Gemini
```

instead of:

```text
Entire video
 ↓
Gemini
```

### Cache transcripts

The same transcript can be useful to:

* Syncer
* Audio Segment Analyser
* Cultural Dub

The project plan explicitly recommends generating the transcript once and reusing it rather than repeatedly processing the same audio.

### Use appropriate models

Use cheaper/faster models for straightforward processing and reserve stronger multimodal reasoning for decisions that actually require it.

---

# 20. Planned End-to-End Workflow

The intended high-level pipeline is:

```text
Creator / Project Brief
          │
          ▼
     Creator Scout
          │
          ▼
    Script Suggestor
          │
          ▼
       Storyboard
          │
          ▼
        Shoot
          │
          ▼
        Syncer
          │
          ▼
        Audio
          │
          ▼
     Cultural Dub
          │
          ▼
      Compliance
          │
          ▼
       Final Output
```

The actual orchestrator may execute agents conditionally rather than strictly linearly.

For example, compliance may run after individual stages rather than only once at the end.

The project plan emphasizes running validation after each agent so problems can be caught while they are still fixable without requiring a reshoot.

---

# 21. Final Product Output

The target product should ultimately provide creators with:

```text
🎨 Thumbnail variants
🎬 Concept art
📋 Storyboard panels
🎥 Shot plan
🎙️ Clean synchronized audio
🌍 Localized / dubbed audio
📝 Subtitles
🔍 Compliance findings
🔎 Creator / collaboration recommendations
📚 Evidence-backed research
```

The creator remains the final decision-maker.

The system provides recommendations, generated assets and structured production intelligence rather than attempting to replace creative taste or decisions carrying legal/reputational consequences.

---

# 22. Immediate Development Roadmap

### Phase 1: Foundation

* [x] Repository structure
* [x] Backend / frontend separation
* [x] Shared models
* [x] ProjectState
* [x] Gemini integration
* [x] Parallel Search integration
* [x] Agent folder structure

### Phase 2: Agent Framework

* [ ] Google ADK integration
* [ ] Agent definitions
* [ ] Agent tools
* [ ] Structured outputs
* [ ] Agent testing

### Phase 3: Core Agents

* [ ] Script Suggestor
* [ ] Storyboard
* [ ] Syncer
* [ ] Audio
* [ ] Cultural Dub
* [ ] Compliance
* [ ] Creator Scout

### Phase 4: Orchestration

* [ ] Workflow orchestration
* [ ] ProjectState updates
* [ ] Agent sequencing
* [ ] Error handling
* [ ] Retry logic
* [ ] Validation between stages

### Phase 5: Media Pipeline

* [ ] FFprobe
* [ ] FFmpeg
* [ ] Frame extraction
* [ ] Audio processing
* [ ] Media staging

### Phase 6: Frontend

* [ ] Project creation
* [ ] Agent workflow UI
* [ ] Script interface
* [ ] Storyboard interface
* [ ] Media upload
* [ ] Sync report
* [ ] Audio / dub controls
* [ ] Compliance report
* [ ] Creator recommendations

### Phase 7: Deployment

* [ ] Cloud deployment
* [ ] Agent Engine
* [ ] Cloud Run
* [ ] Cloud Storage
* [ ] Secrets
* [ ] Production testing

---

# 23. Current Priority

The immediate priority is **not frontend development**.

We first need to establish the agent framework:

```text
ADK
 ↓
Agent
 ↓
Tools
 ↓
Structured Output
 ↓
ProjectState
```

Then implement the agents individually.

The first complete vertical slice should demonstrate that one agent can:

```text
Receive project state
       ↓
Reason with Gemini
       ↓
Use Parallel when required
       ↓
Produce structured output
       ↓
Update ProjectState
```

Once this pattern is stable, the remaining agents can follow the same architecture.

---

# 🎬 Build Principle

> **One shared state. Specialized agents. Real tools. Evidence-backed reasoning. Deterministic execution.**

Build agents independently, keep their interfaces structured, and let the orchestrator connect the pieces.
