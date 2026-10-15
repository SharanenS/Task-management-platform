import argparse
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Project


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove one proven disposable development project")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--expected-key", required=True)
    args = parser.parse_args()
    if settings.app_env not in {"development", "test"}:
        raise SystemExit("Development project cleanup is disabled in this environment.")
    project_id = UUID(args.project_id)
    with SessionLocal() as session:
        project = session.scalar(select(Project).where(Project.id == project_id))
        if not project or project.key != args.expected_key.strip().upper():
            raise SystemExit("Exact disposable project identity was not verified.")
        session.delete(project)
        session.commit()
    print("Disposable development project removed.")


if __name__ == "__main__":
    main()
