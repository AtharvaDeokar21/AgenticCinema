import pytest

from app.shared.tools.parallel.monitor import ParallelMonitor
from app.shared.tools.parallel.task import ParallelTask


class FakeTaskRun:
    run_id = "trun_test"


class FakeOutput:
    content = {"locale": "ja-JP", "register": "conversational"}


class FakeResult:
    run = {"run_id": "trun_test", "status": "completed"}
    output = FakeOutput()


class FakeTaskRuns:
    def __init__(self):
        self.created = None
        self.result_run_id = None

    async def create(self, **kwargs):
        self.created = kwargs
        return FakeTaskRun()

    async def result(self, **kwargs):
        self.result_run_id = kwargs["run_id"]
        return FakeResult()


class FakeTaskSDK:
    def __init__(self):
        self.task_run = FakeTaskRuns()


class FakeMonitorSDK:
    def __init__(self):
        self.requests = []

    async def post(self, **kwargs):
        self.requests.append(("POST", kwargs))
        return {"monitor_id": "monitor_test", "status": "active"}

    async def get(self, **kwargs):
        self.requests.append(("GET", kwargs))
        return {"monitor_id": "monitor_test", "status": "active"}

    async def patch(self, **kwargs):
        self.requests.append(("PATCH", kwargs))
        return {"monitor_id": "monitor_test", "frequency": "2w"}

    async def delete(self, **kwargs):
        self.requests.append(("DELETE", kwargs))
        return {"monitor_id": "monitor_test", "status": "canceled"}


class FakeClient:
    def __init__(self, sdk):
        self.client = sdk
        self.closed = False

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_parallel_task_runs_structured_task_and_returns_output():
    sdk = FakeTaskSDK()
    tool = ParallelTask(client=FakeClient(sdk))

    response = await tool.run(
        task="Research Japanese short-form localization conventions.",
        processor="base",
        task_spec={
            "output_schema": {
                "type": "json",
                "json_schema": {"type": "object"},
            }
        },
        api_timeout=120,
    )

    assert sdk.task_run.created["input"].startswith("Research Japanese")
    assert sdk.task_run.created["processor"] == "base"
    assert "task_spec" in sdk.task_run.created
    assert sdk.task_run.result_run_id == "trun_test"
    assert response["run_id"] == "trun_test"
    assert response["output"]["locale"] == "ja-JP"


@pytest.mark.asyncio
async def test_parallel_monitor_lifecycle_uses_documented_endpoint():
    sdk = FakeMonitorSDK()
    tool = ParallelMonitor(client=FakeClient(sdk))

    created = await tool.create(
        query="Emerging Japanese slang relevant to creator localization.",
        frequency="1w",
        metadata={"locale": "ja-JP"},
    )
    fetched = await tool.get("monitor_test")
    updated = await tool.update("monitor_test", frequency="2w")
    canceled = await tool.cancel("monitor_test")

    assert created["monitor_id"] == "monitor_test"
    assert fetched["status"] == "active"
    assert updated["frequency"] == "2w"
    assert canceled["status"] == "canceled"

    assert sdk.requests[0][0] == "POST"
    assert sdk.requests[0][1]["path"] == "/v1alpha/monitors"
    assert sdk.requests[1][1]["path"] == "/v1alpha/monitors/monitor_test"
    assert sdk.requests[2][1]["path"] == "/v1alpha/monitors/monitor_test"
    assert sdk.requests[3][1]["path"] == "/v1alpha/monitors/monitor_test"
