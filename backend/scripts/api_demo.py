"""
E2E API Demo — Tests the entire system over HTTP.
This simulates exactly what the frontend will do.

Run the server in one terminal: python -m uvicorn app.main:app
Run this in another: python scripts/api_demo.py
"""
import asyncio
import httpx
import json
import sqlite3
import uuid
from datetime import datetime
import sys

BASE_URL = "http://localhost:8000"

async def test_api_flow():
    print("\n🎬 Agentic Cinema API End-to-End Demo")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # 0. Health check
            r = await client.get(f"{BASE_URL}/health")
            if r.status_code != 200:
                print("❌ Server is not running! Start it with: python -m uvicorn app.main:app")
                sys.exit(1)
            print("✓ Server is healthy")

            # 1. Create a project
            payload = {
                "project_name": "API Demo E2E",
                "audio_mode": "AI_VOICE",
                "creator_profile": {
                    "creator_id": "test_1",
                    "name": "API Tester",
                    "platform": "YouTube",
                    "niche": "Tech",
                    "follower_count": 50000
                }
            }
            r = await client.post(f"{BASE_URL}/projects", json=payload)
            r.raise_for_status()
            data = r.json()
            project_id = data["project_id"]
            print(f"✓ Project created: {project_id}")

            # 2. Queue SCRIPT stage
            print("\n[Stage 1] Queueing SCRIPT generation...")
            r = await client.post(f"{BASE_URL}/projects/{project_id}/stages/SCRIPT", json={"input": {"brief": "A 30 second short about coding"}})
            r.raise_for_status()
            script_job_id = r.json()["job_id"]
            print(f"✓ Job queued: {script_job_id}")

            # 3. Poll until SCRIPT completes
            script_done = False
            for _ in range(15):
                await asyncio.sleep(2)
                r = await client.get(f"{BASE_URL}/projects/{project_id}/jobs/{script_job_id}")
                status = r.json()["status"]
                print(f"  ... polling SCRIPT: {status}")
                if status == "completed":
                    script_done = True
                    break
                elif status == "failed":
                    print("❌ Script generation failed")
                    sys.exit(1)

            if not script_done:
                print("❌ Timeout waiting for SCRIPT")
                sys.exit(1)

            # 4. Verify SCRIPT content via the main GET /projects/{id}
            r = await client.get(f"{BASE_URL}/projects/{project_id}")
            r.raise_for_status()
            proj_state = r.json()
            beats = proj_state["script"]["beats"]
            print(f"✓ SCRIPT completed! Generated {len(beats)} beats.")

            # 5. Simulate YELLOW compliance block
            print("\n[Compliance] Simulating a YELLOW risk flag...")
            db = sqlite3.connect("cinema.db")
            cp_id = str(uuid.uuid4())
            db.execute("INSERT INTO compliance_checkpoints VALUES (?,?,?,?,?,?,?,?)",
                       (cp_id, project_id, "SCRIPT", "yellow", None, "[]", datetime.utcnow().isoformat(), None))
            db.commit()
            db.close()

            # 6. Check pending approvals
            r = await client.get(f"{BASE_URL}/projects/{project_id}/compliance/pending")
            pending = r.json()["pending_approvals"]
            print(f"✓ Found {len(pending)} pending approval(s).")

            # 7. Approve the YELLOW checkpoint
            print("  ... Approving checkpoint via API...")
            r = await client.post(f"{BASE_URL}/projects/{project_id}/approve", json={"checkpoint_id": cp_id, "decisions": []})
            r.raise_for_status()
            print("✓ Checkpoint approved!")

            # 8. Chat interaction (mock chat intent routing)
            print("\n[Chat] Testing chat routing...")
            r = await client.post(f"{BASE_URL}/projects/{project_id}/chat", json={"message": "generate the storyboard"})
            r.raise_for_status()
            chat_res = r.json()
            print(f"✓ Chat intent mapped to: {chat_res['intent']}")
            if chat_res["job_id"]:
                print(f"✓ Chat automatically queued a job: {chat_res['job_id']}")
                # Since chat just queued storyboard, we wait for it
                sb_job_id = chat_res["job_id"]
                sb_done = False
                for _ in range(15):
                    await asyncio.sleep(2)
                    r = await client.get(f"{BASE_URL}/projects/{project_id}/jobs/{sb_job_id}")
                    if r.status_code == 404:
                        print("  ... waiting for job to register in DB")
                        continue
                    status = r.json()["status"]
                    print(f"  ... polling STORYBOARD: {status}")
                    if status == "completed":
                        sb_done = True
                        break
                    elif status == "failed":
                        print("❌ Storyboard failed")
                        sys.exit(1)
                
                if not sb_done:
                    print("❌ Timeout waiting for STORYBOARD")
                    sys.exit(1)
            else:
                print("⚠ Chat did not queue the job, invoking manually...")
                # Queue STORYBOARD manually
                r = await client.post(f"{BASE_URL}/projects/{project_id}/stages/STORYBOARD", json={})
                r.raise_for_status()
                sb_job_id = r.json()["job_id"]
                sb_done = False
                for _ in range(15):
                    await asyncio.sleep(2)
                    r = await client.get(f"{BASE_URL}/projects/{project_id}/jobs/{sb_job_id}")
                    if r.status_code == 404:
                        print("  ... waiting for job to register in DB")
                        continue
                    status = r.json()["status"]
                    print(f"  ... polling STORYBOARD: {status}")
                    if status == "completed":
                        sb_done = True
                        break
                    elif status == "failed":
                        print("❌ Storyboard failed")
                        sys.exit(1)
                
                if not sb_done:
                    print("❌ Timeout waiting for STORYBOARD")
                    sys.exit(1)

            # 9. Verify Storyboard content
            r = await client.get(f"{BASE_URL}/projects/{project_id}")
            r.raise_for_status()
            proj_state = r.json()
            shots = proj_state["storyboard"]["shots"]
            print(f"✓ STORYBOARD completed! Generated {len(shots)} shots.")

            # 10. Queue AUDIO_AI stage
            print("\n[Stage 3] Queueing AUDIO_AI generation...")
            r = await client.post(f"{BASE_URL}/projects/{project_id}/stages/AUDIO_AI", json={})
            r.raise_for_status()
            audio_job_id = r.json()["job_id"]
            
            audio_done = False
            for _ in range(15):
                await asyncio.sleep(2)
                r = await client.get(f"{BASE_URL}/projects/{project_id}/jobs/{audio_job_id}")
                status = r.json()["status"]
                print(f"  ... polling AUDIO_AI: {status}")
                if status == "completed":
                    audio_done = True
                    break
                elif status == "failed":
                    print("❌ Audio failed")
                    sys.exit(1)
            
            if not audio_done:
                print("❌ Timeout waiting for AUDIO")
                sys.exit(1)

            # 11. Final GET /projects check
            r = await client.get(f"{BASE_URL}/projects")
            r.raise_for_status()
            projects = r.json()["projects"]
            print(f"\n✓ API lists {len(projects)} total projects.")
            
            # 12. Delete project
            r = await client.delete(f"{BASE_URL}/projects/{project_id}")
            r.raise_for_status()
            print(f"✓ Cleaned up project {project_id}.")

            print("\n✅ API END-TO-END DEMO SUCCESSFUL!")
            
        except httpx.HTTPError as e:
            print(f"\n❌ HTTP Error: {e}")
            if hasattr(e, "response") and e.response:
                print(e.response.text)
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_api_flow())
