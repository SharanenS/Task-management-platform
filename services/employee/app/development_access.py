import argparse

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Employee, ProvisioningRequest

ALLOWED_ENVIRONMENTS = {"development", "test"}


def require_safe_context(subject: str, *, protected_subject: str) -> None:
    if settings.app_env.lower() not in ALLOWED_ENVIRONMENTS:
        raise SystemExit("Development employee access is disabled in this environment.")
    if not protected_subject:
        raise SystemExit("The protected primary subject is required.")
    if subject == protected_subject:
        raise SystemExit("Refusing to modify the protected primary employee profile.")


def set_active(subject: str, *, active: bool, protected_subject: str) -> None:
    require_safe_context(subject, protected_subject=protected_subject)
    with SessionLocal() as session:
        employee = session.scalar(select(Employee).where(Employee.keycloak_subject == subject))
        if employee is None:
            raise SystemExit("Development employee profile was not found.")
        employee.active = active
        session.commit()
        print("Development employee access state updated.")


def remove(subject: str, *, protected_subject: str) -> None:
    require_safe_context(subject, protected_subject=protected_subject)
    with SessionLocal() as session:
        employee = session.scalar(select(Employee).where(Employee.keycloak_subject == subject))
        if employee is None:
            print("Development employee profile is already absent.")
            return
        request = session.scalar(
            select(ProvisioningRequest).where(ProvisioningRequest.employee_id == employee.id)
        )
        if request is not None:
            session.delete(request)
            session.flush()
        session.delete(employee)
        session.commit()
        print("Development employee profile removed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintain disposable development employee access")
    subcommands = parser.add_subparsers(dest="command", required=True)

    state = subcommands.add_parser("set-active")
    state.add_argument("--subject", required=True)
    state.add_argument("--active", choices=["true", "false"], required=True)
    state.add_argument("--protected-subject", required=True)

    remove_profile = subcommands.add_parser("remove")
    remove_profile.add_argument("--subject", required=True)
    remove_profile.add_argument("--protected-subject", required=True)

    args = parser.parse_args()
    if args.command == "set-active":
        set_active(
            args.subject,
            active=args.active == "true",
            protected_subject=args.protected_subject,
        )
    else:
        remove(args.subject, protected_subject=args.protected_subject)


if __name__ == "__main__":
    main()
