import pytest
import httpx
import asyncio
import sqlite3
import uuid
from datetime import datetime

@pytest.mark.asyncio
async def test_compliance_yellow_block_and_approve(async_client: httpx.AsyncClient):
    # 1. Create project
    response = await async_client.post("/projects", json={
        "project_name": "E2E Compliance Test",
    })
    project_id = response.json()["project_id"]

    # 2. Inject a YELLOW checkpoint directly into DB to simulate failure from previous stage
    cp_id = str(uuid.uuid4())
    conn = sqlite3.connect("cinema_test.db")
    conn.execute("INSERT INTO compliance_checkpoints VALUES (?,?,?,?,?,?,?,?)",
                 (cp_id, project_id, "SCRIPT", "yellow", None, "[]", datetime.utcnow().isoformat(), None))
    conn.commit()
    conn.close()

    # 3. Queue SCRIPT
    res = await async_client.post(f"/projects/{project_id}/stages/SCRIPT", json={})
    job_id = res.json()["job_id"]

    # 4. Assert it stays queued (skipped by worker due to YELLOW)
    await asyncio.sleep(0.5)
    res = await async_client.get(f"/projects/{project_id}/jobs/{job_id}")
    assert res.json()["status"] == "queued"

    # 5. Check pending
    res = await async_client.get(f"/projects/{project_id}/compliance/pending")
    assert len(res.json()["pending_approvals"]) == 1

    # 6. Approve
    res = await async_client.post(f"/projects/{project_id}/approve", json={"checkpoint_id": cp_id, "decisions": []})
    assert res.status_code == 200

    # 7. Wait and assert it completes
    for _ in range(50):
        await asyncio.sleep(0.1)
        res = await async_client.get(f"/projects/{project_id}/jobs/{job_id}")
        if res.json()["status"] == "completed":
            break
    assert res.json()["status"] == "completed"
