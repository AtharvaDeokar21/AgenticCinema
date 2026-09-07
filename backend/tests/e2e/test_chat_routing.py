import pytest
import httpx
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_chat_routing(async_client: httpx.AsyncClient, monkeypatch):
    # 1. Create project
    res = await async_client.post("/projects", json={"project_name": "Chat Test"})
    project_id = res.json()["project_id"]

    # Mock the router explicitly for tests to ensure deterministic output
    from app.orchestration.chat_router import ChatIntentRouter
    
    async def mock_route(self, message, project_data=None):
        from app.orchestration.chat_router import ChatIntent
        if "storyboard" in message.lower():
            return (ChatIntent.REGENERATE_STORYBOARD, {"type": "invoke_stage", "stage": "STORYBOARD", "params": {}}, "Mocked")
        elif "clarify" in message.lower():
            return (ChatIntent.CLARIFY, {"type": "clarify", "params": {}}, "Mocked")
        return (ChatIntent.CLARIFY, {"type": "clarify", "params": {}}, "Mocked")
        
    monkeypatch.setattr(ChatIntentRouter, "route", mock_route)

    # 2. Test invoke stage
    res = await async_client.post(f"/projects/{project_id}/chat", json={"message": "generate storyboard"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "regenerate_storyboard"
    assert "job_id" in data

    # 3. Test clarify
    res = await async_client.post(f"/projects/{project_id}/chat", json={"message": "clarify something"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "clarify"
    assert data["job_id"] is None
