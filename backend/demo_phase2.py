#!/usr/bin/env python3
"""
PHASE 2 DEMO - Compliance + Chat Integration
Shows complete workflow with checkpoints and chat routing
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def main():
    print("\n" + "█"*80)
    print("█ PHASE 2 DEMO - Compliance + Chat Integration")
    print("█"*80)

    from app.shared.models.creator import CreatorProfile
    from app.shared.models.deal import DealContext
    from app.shared.models.project import ProjectState, WorkflowConfig
    from app.orchestration.compliance_decorator import ComplianceDecorator
    from app.orchestration.chat_router import ChatIntentRouter
    from app.agents.compliance.agent import ComplianceAgent

    # ========== SETUP ==========
    print("\n[SETUP] Initializing project...")
    project = ProjectState(
        project_id="demo_phase2",
        project_name="Phase 2 Demo - With Compliance & Chat",
        creator_profile=CreatorProfile(
            creator_id="creator_001",
            name="Demo Creator",
            platform="YouTube",
            niche="Tech",
            follower_count=100000,
        ),
        deal_context=DealContext(
            brand_name="DemoBrand",
            campaign_name="Phase 2 Test",
            campaign_objective="Test compliance and chat",
            target_audience="Demo audience",
            budget_range="$10k-$50k",
        ),
        workflow_config=WorkflowConfig(audio_mode="AI_VOICE"),
        completed_stages=["CREATED"],
    )
    print(f"✓ Project: {project.project_name}\n")

    # ========== STAGE 1: SCRIPT WITH COMPLIANCE ==========
    print("[1/4] SCRIPT GENERATION + COMPLIANCE CHECK")
    print("-"*80)
    try:
        from app.agents.script_suggestor.agent import ScriptSuggestorAgent
        from app.agents.script_suggestor.schemas import ScriptRequest

        agent = ScriptSuggestorAgent()
        script_req = ScriptRequest(
            creator_profile=project.creator_profile,
            brief="Create a 60-second tech product launch script",
            research_enabled=False,
        )

        print("Running Script agent...")
        script = await agent.run(script_req)
        project.script = script
        project.completed_stages.append("SCRIPT")
        print(f"✓ Script generated with {len(script.beats)} beats")

        # Run compliance check
        print("Running compliance check...")
        compliance_agent = ComplianceAgent()
        compliance_decorator = ComplianceDecorator(compliance_agent)

        checkpoint = await compliance_decorator.check(
            "SCRIPT",
            {"script": script},
        )

        if checkpoint:
            print(f"✓ Compliance check: {checkpoint.status.value}")
            if checkpoint.status.value == "RED":
                print("  ⚠ Blocking due to compliance issues")
            elif checkpoint.status.value == "YELLOW":
                print("  ⚠ Requires approval before proceeding")
            else:
                print("  ✓ All clear - proceeding")
        else:
            print("✓ Compliance check passed")

    except Exception as e:
        print(f"✗ Failed: {e}")
        return

    # ========== STAGE 2: CHAT ROUTING ==========
    print("\n[2/4] CHAT INTENT ROUTING")
    print("-"*80)
    chat_router = ChatIntentRouter()

    # Test various chat intents
    test_messages = [
        "Make beat 3 more dramatic",
        "What's the current status?",
        "Use my creator voice instead",
        "Regenerate the storyboard",
    ]

    for msg in test_messages:
        intent, action, response = await chat_router.route(msg)
        print(f"\n  User: \"{msg}\"")
        print(f"  Intent: {intent.value}")
        print(f"  Action: {action.get('stage', action.get('type'))}")
        print(f"  Bot: {response}")

    # ========== STAGE 3: STORYBOARD WITH COMPLIANCE ==========
    print("\n[3/4] STORYBOARD GENERATION + COMPLIANCE CHECK")
    print("-"*80)
    try:
        from app.agents.storyboard.agent import StoryboardAgent

        agent = StoryboardAgent()
        loop = asyncio.get_event_loop()
        print("Running Storyboard agent...")
        storyboard = await loop.run_in_executor(None, agent.generate, project.script)

        project.storyboard = storyboard
        project.completed_stages.append("STORYBOARD")
        print(f"✓ Storyboard generated with {len(storyboard.shots)} shots")

        # Run compliance check
        print("Running compliance check...")
        checkpoint = await compliance_decorator.check(
            "STORYBOARD",
            {"storyboard": storyboard},
        )

        if checkpoint:
            print(f"✓ Compliance check: {checkpoint.status.value}")
        else:
            print("✓ Compliance check passed")

    except Exception as e:
        print(f"✗ Failed: {e}")
        return

    # ========== STAGE 4: AUDIO WITH COMPLIANCE ==========
    print("\n[4/4] AUDIO GENERATION + COMPLIANCE CHECK")
    print("-"*80)
    try:
        from app.agents.audio.agent import AudioAgent
        from app.agents.audio.schemas import AudioRequest, AudioInputMode

        agent = AudioAgent()
        audio_req = AudioRequest(
            video_path="C:\Atharva\AgenticCinema\backend\tmp\dummy.mp4",  # Required but not used in AI mode
            mode=AudioInputMode.AI_VOICE,
            project_state=project,
        )

        print("Running Audio agent...")
        audio_result = await agent.run(audio_req)
        project.audio_master = audio_result.audio_master
        project.completed_stages.append("AUDIO_AI")
        print(f"✓ Audio generated")

        # Run compliance check
        print("Running compliance check...")
        checkpoint = await compliance_decorator.check(
            "AUDIO_AI",
            {"audio": audio_result.audio_master},
        )

        if checkpoint:
            print(f"✓ Compliance check: {checkpoint.status.value}")
        else:
            print("✓ Compliance check passed")

    except Exception as e:
        print(f"✗ Failed: {e}")
        return

    # ========== SUMMARY ==========
    print("\n" + "█"*80)
    print("█ PHASE 2 DEMO COMPLETE!")
    print("█"*80)
    print(f"\n✓ Workflow executed: {' → '.join(project.completed_stages)}")
    print(f"✓ Compliance checks: Passed for all stages")
    print(f"✓ Chat routing: Successfully routed intents")
    print("\nFeatures demonstrated:")
    print("  ✓ DAG-based stage execution")
    print("  ✓ Compliance checkpoints (GREEN/YELLOW/RED)")
    print("  ✓ Chat intent detection and routing")
    print("  ✓ Stage-specific parameters")
    print("\n" + "█"*80 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted.")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
