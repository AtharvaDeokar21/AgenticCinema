"""
DEMO RUNNER: End-to-end workflow test
Create project → Script → Storyboard → Audio AI
Shows working integration without overthinking it.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.shared.models.project import ProjectState, WorkflowConfig
from app.shared.models.creator import CreatorProfile
from app.shared.models.deal import DealContext


async def demo_workflow():
    """Run a complete workflow demo"""

    print("\n" + "="*70)
    print("AGENTIC CINEMA - WORKING DEMO")
    print("="*70)

    # Step 1: Create project
    print("\n[1/4] Creating project...")
    project = ProjectState(
        project_id="demo_001",
        project_name="Tech Product Launch",
        creator_profile=CreatorProfile(
            creator_id="creator_001",
            name="Alex Creator",
            platform="YouTube",
            niche="Tech Reviews",
            follower_count=100000,
        ),
        deal_context=DealContext(
            brand_name="TechCorp",
            campaign_name="Product Launch",
            campaign_objective="Introduce new smartphone to tech audience",
            target_audience="Tech enthusiasts aged 18-35",
            budget_range="$10k-$50k",
        ),
        completed_stages=["CREATED"],
        workflow_config=WorkflowConfig(
            audio_mode="AI_VOICE",
            target_locales=["en"],
        ),
    )
    print(f"✓ Project created: {project.project_id}")

    # Step 2: Run Script agent
    print("\n[2/4] Generating script...")
    try:
        from app.agents.script_suggestor.agent import ScriptSuggestorAgent
        from app.agents.script_suggestor.schemas import ScriptRequest

        agent = ScriptSuggestorAgent()
        request = ScriptRequest(
            creator_profile=project.creator_profile,
            brief="Create a 60-second tech product launch script that's engaging and persuasive",
            research_enabled=False,
        )
        script_result = await agent.run(request)
        project.script = script_result
        project.completed_stages.append("SCRIPT")
        print(f"✓ Script generated with {len(script_result.beats)} beats")
        print(f"  Title: {script_result.title}")
    except Exception as e:
        print(f"✗ Script generation failed: {e}")
        return

    # Step 3: Run Storyboard agent
    print("\n[3/4] Generating storyboard...")
    try:
        from app.agents.storyboard.agent import StoryboardAgent

        agent = StoryboardAgent()
        storyboard_result = agent.generate(project.script)
        project.storyboard = storyboard_result
        project.completed_stages.append("STORYBOARD")
        print(f"✓ Storyboard generated with {len(storyboard_result.shots)} shots")
        if storyboard_result.visual_style:
            print(f"  Visual style: {storyboard_result.visual_style}")
    except Exception as e:
        print(f"✗ Storyboard generation failed: {e}")
        return

    # Step 4: Run Audio agent (AI Voice)
    print("\n[4/4] Generating audio (AI Voice)...")
    try:
        from app.agents.audio.agent import AudioAgent
        from app.agents.audio.schemas import AudioRequest, AudioInputMode

        agent = AudioAgent()
        request = AudioRequest(
            video_path=str(Path(__file__).resolve().parent / "tmp" / "dummy.mp4"),  # Required but not used in AI mode
            mode=AudioInputMode.AI_VOICE,
            project_state=project,
        )
        audio_result = await agent.run(request)
        project.audio_master = audio_result.audio_master
        project.completed_stages.append("AUDIO_AI")
        print(f"✓ Audio generated")
        if audio_result.audio_master:
            print(f"  Duration: {audio_result.audio_master.duration}s")
            print(f"  Segments: {len(audio_result.audio_master.segments)}")
    except Exception as e:
        print(f"✗ Audio generation failed: {e}")
        return

    # Summary
    print("\n" + "="*70)
    print("DEMO COMPLETE!")
    print("="*70)
    print(f"\nProject: {project.project_name}")
    print(f"Completed stages: {' → '.join(project.completed_stages)}")
    print(f"\nOutputs:")
    print(f"  ✓ Script: {len(project.script.beats)} beats")
    print(f"  ✓ Storyboard: {len(project.storyboard.shots)} shots")
    print(f"  ✓ Audio: Generated")
    print(f"\nReady for next stages: DUBBING")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(demo_workflow())
