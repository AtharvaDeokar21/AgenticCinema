from fastapi import FastAPI

app = FastAPI(
    title="Agentic Cinema API",
    description="Backend API for the Agentic Cinema multi-agent platform",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "agentic-cinema-backend",
    }