import argparse
from uuid import UUID

from app.config import settings
from app.db import SessionLocal
from app.models import Job


def remove(job_id: UUID) -> None:
    if settings.app_env not in {"development", "test"}:
        raise SystemExit("Cleanup is permitted only in development or test.")
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise SystemExit("The exact job was not found.")
        session.delete(job)
        session.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id", type=UUID)
    args = parser.parse_args()
    remove(args.job_id)


if __name__ == "__main__":
    main()
