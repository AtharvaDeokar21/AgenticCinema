import os
import pytest
import sqlite3
import httpx
from datetime import datetime
from asgi_lifespan import LifespanManager
import asyncio

# Override DB path for tests
from pathlib import Path
import app.persistence.repository
app.persistence.repository.DB_PATH = Path("cinema_test_real.db")

# Mock the poll interval for tests so they run instantly
import app.worker
app.worker.POLL_INTERVAL = 0.1

from app.main import app as fastapi_app
from app.persistence.repository import init_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_db()
    yield
    if os.path.exists("cinema_test_real.db"):
        os.remove("cinema_test_real.db")

@pytest.fixture(autouse=True)
def clean_db():
    conn = sqlite3.connect("cinema_test_real.db")
    conn.execute("DELETE FROM jobs")
    conn.execute("DELETE FROM compliance_checkpoints")
    conn.execute("DELETE FROM projects")
    conn.commit()
    conn.close()

import pytest_asyncio

@pytest_asyncio.fixture
async def async_client():
    async with LifespanManager(fastapi_app):
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
