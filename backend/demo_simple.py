#!/usr/bin/env python3
"""
AGENTIC CINEMA - MINIMAL WORKING DEMO
Simple direct execution. No complexity.
Just run the agents in sequence and show the output.
"""
import asyncio
import sys
from pathlib import Path
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent))


async def main():
    print("\n" + "="*70)
    print("AGENTIC CINEMA DEMO - Script → Storyboard → Audio AI")
    print("="*70)

    from app.shared.models.creator import CreatorProfile
    from app.shared.models.deal import DealContext
    from app.shared.models.project import ProjectState, WorkflowConfig

    # Initialize project state
    project = ProjectState(
        project_id="demo_001",
        project_name="Demo Project",
        creator_profile=CreatorProfile(
            creator_id="demo_001",
            name="Tech Creator",
            platform="YouTube",
            niche="Technology",
            follower_count=100000,
        ),
        deal_context=DealContext(
            brand_name="TechBrand",
            campaign_name="Demo Campaign",
            campaign_objective="Create demo content",
            target_audience="Tech enthusiasts",
            budget_range="$10k-$50k",
        ),
        workflow_config=WorkflowConfig(audio_mode="AI_VOICE"),
        completed_stages=["CREATED"],
    )

    # ========== STAGE 1: SCRIPT ==========
    print("\n[1/3] Running SCRIPT agent...")
    print("-"*70)
    try:
        from app.agents.script_suggestor.agent import ScriptSuggestorAgent
        from app.agents.script_suggestor.schemas import ScriptRequest

        agent = ScriptSuggestorAgent()
        req = ScriptRequest(
            creator_profile=project.creator_profile,
            brief="Create a 60-second tech product launch script",
            research_enabled=False,
        )

        script = await agent.run(req)
        project.script = script
        project.completed_stages.append("SCRIPT")
        print(f"✓ Script generated!")
        print(f"  - Title: {script.title}")
        print(f"  - Beats: {len(script.beats)}")
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # ========== STAGE 2: STORYBOARD ==========
    print("\n[2/3] Running STORYBOARD agent...")
    print("-"*70)
    try:
        from app.agents.storyboard.agent import StoryboardAgent

        agent = StoryboardAgent()
        loop = asyncio.get_event_loop()
        storyboard = await loop.run_in_executor(None, agent.generate, project.script)

        project.storyboard = storyboard
        project.completed_stages.append("STORYBOARD")
        print(f"✓ Storyboard generated!")
        print(f"  - Shots: {len(storyboard.shots)}")
        print(f"  - Visual style: {storyboard.visual_style or 'N/A'}")
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # ========== STAGE 3: AUDIO AI ==========
    print("\n[3/3] Running AUDIO agent (AI Voice)...")
    print("-"*70)
    try:
        from app.agents.audio.agent import AudioAgent
        from app.agents.audio.schemas import AudioRequest, AudioInputMode

        # Create a temporary dummy video file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(b"dummy video content")
            dummy_video_path = tmp.name

        try:
            agent = AudioAgent()
            req = AudioRequest(
                video_path=dummy_video_path,
                mode=AudioInputMode.AI_VOICE,
                project_state=project,
            )

            audio_result = await agent.run(req)
            project.audio_master = audio_result.audio_master
            project.completed_stages.append("AUDIO_AI")
            print(f"✓ Audio generated!")
            if audio_result.audio_master:
                print(f"  - Duration: {audio_result.audio_master.duration}s")
                print(f"  - Segments: {len(audio_result.audio_master.segments)}")
        finally:
            # Clean up temp file
            if os.path.exists(dummy_video_path):
                os.remove(dummy_video_path)

    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Summary
    print("\n" + "="*70)
    print("✓ DEMO COMPLETE!")
    print("="*70)
    print(f"\nProject: {project.project_name}")
    print(f"Workflow: {' → '.join(project.completed_stages)}")
    print(f"\nOutputs:")
    print(f"  ✓ Script: {len(project.script.beats)} beats")
    print(f"  ✓ Storyboard: {len(project.storyboard.shots)} shots")
    print(f"  ✓ Audio: Generated\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted.")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
