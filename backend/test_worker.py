import asyncio
import json
from app.worker import Worker
from app.persistence.repository import JobRepository
from app.api.routes.chat_approval import chat_router

async def main():
    job = {
        "job_id": "test_job_123",
        "project_id": "test_proj_123",
        "stage": "SCRIPT",
        "status": "queued",
        "progress": 0.0,
        "phase": None,
        "result": {"brief": "CYBERPUNK COFFEE BRAND SCRIPT PLEASE", "regenerate": False},
        "error": None
    }
    await JobRepository.save(job)
    
    # check what get_next_job returns
    saved_job = await JobRepository.get_next_job()
    print("SAVED JOB RESULT TYPE:", type(saved_job["result"]), "VALUE:", saved_job["result"])
    
    if saved_job and saved_job.get("result"):
        try:
            override = json.loads(saved_job["result"]) if isinstance(saved_job["result"], str) else saved_job["result"]
            brief = override.get("brief", "Generate an engaging creative script")
            print("EXTRACTED BRIEF:", brief)
        except Exception as e:
            print("ERROR EXTRACTING BRIEF:", e)

asyncio.run(main())
