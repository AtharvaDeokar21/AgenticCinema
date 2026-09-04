from app.shared.models.project import ProjectState


def main():
    project = ProjectState(
        project_id="test-001",
        project_name="Agentic Cinema Demo",
    )

    print("ProjectState created successfully")
    print()
    print(project.model_dump_json(indent=2))


if __name__ == "__main__":
    main()