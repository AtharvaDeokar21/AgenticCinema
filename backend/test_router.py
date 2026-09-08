import asyncio
from app.orchestration.chat_router import ChatIntentRouter

async def main():
    router = ChatIntentRouter()
    project_data = {"script": None}
    intent, action, resp = await router.route("Write a 3-beat script about a futuristic cyberpunk coffee brand.", project_data=project_data)
    print("INTENT:", intent)
    print("ACTION:", action)

asyncio.run(main())
