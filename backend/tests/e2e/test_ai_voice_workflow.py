import pytest
import httpx
import asyncio

@pytest.mark.asyncio
async def test_ai_voice_happy_path(async_client: httpx.AsyncClient):
    # 1. Create project
    response = await async_client.post("/projects", json={
        "project_name": "E2E Happy Path",
        "audio_mode": "AI_VOICE"
    })
    assert response.status_code == 200
    project_id = response.json()["project_id"]

    # Helper to queue and poll a stage
    async def run_stage(stage_name: str):
        res = await async_client.post(f"/projects/{project_id}/stages/{stage_name}", json={})
        assert res.status_code == 200
        job_id = res.json()["job_id"]
        
        # Poll up to 5 seconds
        for _ in range(50):
            await asyncio.sleep(0.1)
            res = await async_client.get(f"/projects/{project_id}/jobs/{job_id}")
            if res.status_code == 404:
                continue
            status = res.json()["status"]
            if status == "completed":
                return True
            if status == "failed":
                return False
        return False

    # 2. Run stages
    assert await run_stage("SCRIPT")
    assert await run_stage("STORYBOARD")
    assert await run_stage("AUDIO_AI")
    assert await run_stage("SYNC")
    assert await run_stage("DUBBING")

    # 3. Verify final state
    res = await async_client.get(f"/projects/{project_id}")
    assert res.status_code == 200
    data = res.json()
    assert "SCRIPT" in data["completed_stages"]
    assert "STORYBOARD" in data["completed_stages"]
    assert "AUDIO_AI" in data["completed_stages"]
    assert "SYNC" in data["completed_stages"]
    assert "DUBBING" in data["completed_stages"]
    
    assert data["script"] is not None
    assert data["storyboard"] is not None
    assert data["audio"] is not None
    # Wait, the response might not return all these fields explicitly yet, but we can check if they exist or just rely on completed_stages.
    # The API might not serialize sync_report and dub_tracks by default, but let's assume it does, or at least they aren't None if returned.
