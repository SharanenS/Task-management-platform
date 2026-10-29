import argparse
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import SourceEvent, WorkflowExecution, WorkflowRule


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove one proven disposable workflow rule")
    parser.add_argument("--rule-id", required=True)
    parser.add_argument("--expected-project-id", required=True)
    parser.add_argument("--expected-name", required=True)
    args = parser.parse_args()
    if settings.app_env not in {"development", "test"}:
        raise SystemExit("Development workflow cleanup is disabled in this environment.")
    rule_id, project_id = UUID(args.rule_id), UUID(args.expected_project_id)
    with SessionLocal() as session:
        rule = session.scalar(select(WorkflowRule).where(WorkflowRule.id == rule_id))
        if not rule or rule.project_id != project_id or rule.name != args.expected_name:
            raise SystemExit("Exact disposable workflow identity was not verified.")
        source_ids = list(
            session.scalars(
                select(WorkflowExecution.source_event_id).where(
                    WorkflowExecution.rule_id == rule.id
                )
            )
        )
        session.delete(rule)
        session.flush()
        for source_id in source_ids:
            if not session.scalar(
                select(WorkflowExecution.id).where(WorkflowExecution.source_event_id == source_id)
            ):
                source = session.get(SourceEvent, source_id)
                if source:
                    session.delete(source)
        session.commit()
    print("Disposable development workflow removed.")


if __name__ == "__main__":
    main()
