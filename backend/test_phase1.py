"""
Simple test to verify Phase 1 works: DAG, project creation, stage invocation.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.shared.models.project import ProjectState, WorkflowConfig
from app.orchestration.dag import WorkflowDAG, StageType
from app.persistence.repository import ProjectRepository, init_db


async def test_phase1():
    """Test core Phase 1 functionality"""

    print("=" * 60)
    print("PHASE 1: DAG + PROJECT STATE + PERSISTENCE")
    print("=" * 60)

    # Initialize database
    print("\n1. Initializing database...")
    init_db()
    print("   ✓ Database initialized")

    # Test DAG
    print("\n2. Testing WorkflowDAG...")
    dag = WorkflowDAG()

    completed = {StageType.CREATED}
    ready = dag.get_ready_stages(completed)
    print(f"   Completed: {[s.value for s in completed]}")
    print(f"   Ready stages: {[s.value for s in ready]}")
    assert StageType.SCRIPT in ready, "SCRIPT should be ready after CREATED"
    print("   ✓ DAG dependency resolution works")

    # Test ProjectState creation
    print("\n3. Creating ProjectState...")
    project = ProjectState(
        project_id="demo_proj_001",
        project_name="Test Campaign",
        completed_stages=["CREATED"],
        workflow_config=WorkflowConfig(
            audio_mode="AI_VOICE",
            target_locales=["en", "es"],
        ),
    )
    print(f"   Project ID: {project.project_id}")
    print(f"   Audio mode: {project.workflow_config.audio_mode}")
    print("   ✓ ProjectState created")

    # Test persistence
    print("\n4. Testing persistence...")
    await ProjectRepository.save(project)
    print("   ✓ Project saved to database")

    loaded = await ProjectRepository.load("demo_proj_001")
    assert loaded is not None, "Project should be loaded"
    assert loaded.project_name == "Test Campaign", "Project name should match"
    print("   ✓ Project loaded from database")

    # Test DAG with loaded project
    print("\n5. Testing DAG with loaded project...")
    completed = set(loaded.completed_stages)
    ready = dag.get_ready_stages(completed)
    print(f"   Ready stages: {[s.value for s in ready]}")
    assert StageType.SCRIPT in ready, "SCRIPT should be ready"
    print("   ✓ DAG works with persistent state")

    # Simulate SCRIPT completion
    print("\n6. Simulating SCRIPT stage completion...")
    project.completed_stages.append(StageType.SCRIPT.value)
    await ProjectRepository.save(project)

    completed = set(project.completed_stages)
    ready = dag.get_ready_stages(completed)
    print(f"   Completed: {[s.value for s in completed]}")
    print(f"   Ready stages: {[s.value for s in ready]}")
    assert StageType.STORYBOARD in ready, "STORYBOARD should be ready after SCRIPT"
    assert StageType.AUDIO_AI in ready, "AUDIO_AI should be ready after SCRIPT"
    print("   ✓ Stage completion triggers DAG updates")

    print("\n" + "=" * 60)
    print("✓ PHASE 1 COMPLETE - All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_phase1())
