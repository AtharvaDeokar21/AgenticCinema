# 🎬 Agentic Cinema

An agentic AI platform for the entertainment and creator ecosystem.

## Architecture

The system consists of specialized AI agents coordinated through
shared project state and an orchestration layer.

### Agents

- CreatorScout
- Script Suggestor
- Storyboard
- Syncer
- Audio
- Cultural Dub
- Compliance

### Team Ownership

| Developer | Agents |
|---|---|
| Saur | Audio, Cultural Dub |
| Mayank | Syncer |
| Atharva | Script Suggestor, Storyboard |
| Asmiya | Compliance, CreatorScout |

## Repository

```text
backend/     Backend, agents and orchestration
frontend/    Web application
docs/        Architecture and development documentation
```

## Backend

```text
Python + FastAPI + Google ADK + Gemini.
```

### Partner Integration

Parallel Web Systems is used for runtime web research,
extraction and other approved workflows where external
web intelligence is required.

## Development

See docs/development-guide.md.