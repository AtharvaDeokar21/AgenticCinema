import asyncio
import httpx
import json

async def main():
    # 1. Create a project
    async with httpx.AsyncClient() as client:
        res = await client.post("http://127.0.0.1:8000/projects", json={"project_name": "Test"})
        proj = res.json()
        pid = proj["project_id"]
        print("Project ID:", pid)
        
        # 2. Chat
        res = await client.post(f"http://127.0.0.1:8000/projects/{pid}/chat", json={"message": "Write a 3-beat script about a futuristic cyberpunk coffee brand."})
        chat_resp = res.json()
        print("Chat Response:", json.dumps(chat_resp, indent=2))
        job_id = chat_resp.get("job_id")
        print("Job ID:", job_id)
        
        if job_id:
            # 3. Check job
            res = await client.get(f"http://127.0.0.1:8000/projects/{pid}/jobs/{job_id}")
            job = res.json()
            print("Job Record in DB:", json.dumps(job, indent=2))

asyncio.run(main())
