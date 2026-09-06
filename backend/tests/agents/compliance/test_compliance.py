
import asyncio
import json

from app.agents.compliance import ComplianceAgent, ComplianceRequest, render_report
from app.shared.models.stages import ProjectStage

SCRIPT_PAYLOAD = json.dumps(
    {
        "version": 1,
        "title": "Why your credit score doesn't care that it was UPI",
        "hook": "Everyone's explaining what a UPI credit line is. Nobody told you this.",
        "beats": [
            {
                "beat_id": "beat_001",
                "start_time": 0.0,
                "end_time": 3.0,
                "text": "Everyone's explaining what a UPI credit line is. Nobody told you this.",
                "audio_intent": "Open on 'Blinding Lights' by The Weeknd, first 8 seconds.",
            },
            {
                "beat_id": "beat_002",
                "start_time": 3.0,
                "end_time": 18.0,
                "text": (
                    "Unlike Paytm and PhonePe, this one reports to the bureau every "
                    "single month. Use it right and you'll see a 90-point jump in 60 days, "
                    "guaranteed."
                ),
            },
            {
                "beat_id": "beat_003",
                "start_time": 18.0,
                "end_time": 34.0,
                "text": "Shot on the concourse at Chhatrapati Shivaji Maharaj Terminus.",
            },
        ],
    },
    indent=2,
)


async def main():
    agent = ComplianceAgent()

    request = ComplianceRequest(
        project_id="demo-001",
        stage=ProjectStage.SCRIPT,
        pass_number=2,
        payload=SCRIPT_PAYLOAD,
        target_markets=["India"],
        is_sponsored=True,
        sponsor_brand="A fintech app",
    )

    report = await agent.run(request)

    print()
    print(render_report(report, project_name="fintech_explainer_v3"))
    print()
    print("-" * 72)
    print(report.model_dump_json(indent=2))

    await agent.search.close()


if __name__ == "__main__":
    asyncio.run(main())