#!/usr/bin/env python3
"""
AGENTIC CINEMA - WORKING DEMO
Simple, direct execution of the workflow.
No over-engineering. Just works.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.shared.models.creator import CreatorProfile
from app.shared.models.deal import DealContext
from app.shared.models.project import ProjectState, WorkflowConfig


async def main():
    """Run complete workflow demo"""

    print("\n" + "█" * 80)
    print("█ AGENTIC CINEMA - WORKING DEMO")
    print("█" * 80)

    # Initialize project
    print("\n[SETUP] Initializing project...")
    project = ProjectState(
        project_id="demo_" + "1",
        project_name="Tech Product Launch Campaign",
        creator_profile=CreatorProfile(
            creator_id="creator_001",
            name="Sarah Chen",
            platform="YouTube",
            niche="Technology Reviews",
            follower_count=250000,
            engagement_rate=8.5,
        ),
        deal_context=DealContext(
            brand_name="InnovateTech",
            campaign_name="Q4 2026 Launch",
            campaign_objective="Launch new AI-powered smartwatch with 60-second compelling video",
            target_audience="Tech enthusiasts aged 20-40",
            target_geographies=["US", "CA", "UK"],
            budget_range="$25,000 - $50,000",
        ),
        workflow_config=WorkflowConfig(audio_mode="AI_VOICE"),
        completed_stages=["CREATED"],
    )
    print(f"✓ Project: {project.project_name}")
    print(f"  Creator: {project.creator_profile.name}")
    print(f"  Brand: {project.deal_context.brand_name}")

    # Step 1: Generate Script
    print("\n[1/4] SCRIPT GENERATION")
    print("-" * 80)
    try:
        from app.agents.script_suggestor.agent import ScriptSuggestorAgent
        from app.agents.script_suggestor.schemas import ScriptRequest

        agent = ScriptSuggestorAgent()
        script_req = ScriptRequest(
            creator_profile=project.creator_profile,
            brief=f"""Create a compelling 60-second script for {project.deal_context.brand_name}'s
            new smartwatch launch. Target audience: {project.deal_context.target_audience}.
            Focus on innovation, design, and lifestyle benefits. Make it engaging and conversational.""",
            research_enabled=False,
        )

        print("Running Script Suggestor agent...")
        script = await agent.run(script_req)
        project.script = script
        project.completed_stages.append("SCRIPT")

        print(f"✓ Script generated!")
        print(f"  Title: {script.title}")
        print(f"  Beats: {len(script.beats)}")
        print(f"  Duration: ~60 seconds")

    except Exception as e:
        print(f"✗ Script generation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 2: Generate Storyboard
    print("\n[2/4] STORYBOARD GENERATION")
    print("-" * 80)
    try:
        from app.agents.storyboard.agent import StoryboardAgent

        agent = StoryboardAgent()
        print("Running Storyboard agent (this may take a minute)...")

        loop = asyncio.get_event_loop()
        storyboard = await loop.run_in_executor(
            None,
            agent.generate,
            project.script,
        )

        project.storyboard = storyboard
        project.completed_stages.append("STORYBOARD")

        print(f"✓ Storyboard generated!")
        print(f"  Shots: {len(storyboard.shots)}")
        print(f"  Visual style: {storyboard.visual_style or 'Default'}")
        print(f"  Color palette: {storyboard.color_palette or 'Professional'}")

    except Exception as e:
        print(f"✗ Storyboard generation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: Generate Audio (AI Voice)
    print("\n[3/4] AUDIO GENERATION (AI VOICE)")
    print("-" * 80)
    try:
        from app.agents.audio.agent import AudioAgent
        from app.agents.audio.schemas import AudioRequest, AudioInputMode

        agent = AudioAgent()
        audio_req = AudioRequest(
            video_path=str(Path(__file__).resolve().parent / "tmp" / "dummy.mp4"),
            mode=AudioInputMode.AI_VOICE,
            project_state=project,
        )

        print("Running Audio agent (AI Voice mode)...")
        audio_result = await agent.run(audio_req)

        project.audio_master = audio_result.audio_master
        project.completed_stages.append("AUDIO_AI")

        if audio_result.audio_master:
            print(f"✓ Audio generated!")
            print(f"  Duration: {audio_result.audio_master.duration}s")
            print(f"  Segments: {len(audio_result.audio_master.segments)}")
            print(f"  Sample rate: {audio_result.audio_master.sample_rate}Hz")
        else:
            print("⚠ Audio generated but audio_master is None")

    except Exception as e:
        print(f"✗ Audio generation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: Generate Dubbing (Optional - if locales are set)
    print("\n[4/4] DUBBING (CULTURAL LOCALIZATION)")
    print("-" * 80)
    try:
        target_locales = project.deal_context.target_geographies or ["US"]
        locale_map = {
            "US": ["en_US"],
            "CA": ["en_CA", "fr_CA"],
            "UK": ["en_GB"],
            "ES": ["es_ES"],
            "FR": ["fr_FR"],
        }

        dub_locales = []
        for geo in target_locales:
            dub_locales.extend(locale_map.get(geo, []))

        if dub_locales and project.audio_master:
            from app.agents.cultural_dub.agent import CulturalDubAgent
            from app.agents.cultural_dub.schemas import DubRequest

            agent = CulturalDubAgent()
            dub_req = DubRequest(
                audio_master=project.audio_master,
                target_locales=dub_locales[:2],  # Limit to 2 for demo speed
            )

            print(f"Running Cultural Dub agent for locales: {dub_locales[:2]}...")
            dub_result = await agent.run(dub_req)

            project.dub_tracks = dub_result.dub_tracks if hasattr(dub_result, 'dub_tracks') else []
            project.completed_stages.append("DUBBING")

            print(f"✓ Dubbing generated!")
            print(f"  Locales: {len(project.dub_tracks)}")

        else:
            print("⊘ Skipping dubbing (no locales configured)")

    except Exception as e:
        print(f"⚠ Dubbing failed (non-critical): {e}")
        # Don't fail the whole demo for dubbing

    # Summary
    print("\n" + "█" * 80)
    print("█ DEMO COMPLETE!")
    print("█" * 80)
    print(f"\nProject: {project.project_name}")
    print(f"Workflow: {' → '.join(project.completed_stages)}\n")
    print("Outputs:")
    print(f"  ✓ Script with {len(project.script.beats)} beats")
    print(f"  ✓ Storyboard with {len(project.storyboard.shots)} shots")
    print(f"  ✓ Audio ({len(project.audio_master.segments)} segments)")
    if project.dub_tracks:
        print(f"  ✓ Dubbing ({len(project.dub_tracks)} languages)")

    print("\n" + "█" * 80)
    print("✓ Ready for production!\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted.")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
