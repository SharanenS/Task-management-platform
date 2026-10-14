import argparse

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ApplicationRole, Employee


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision one development employee profile")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", choices=[role.value for role in ApplicationRole], required=True)
    args = parser.parse_args()

    with SessionLocal() as session:
        employee = session.scalar(select(Employee).where(Employee.keycloak_subject == args.subject))
        if employee is None:
            employee = Employee(keycloak_subject=args.subject)
            session.add(employee)
        employee.email = args.email
        employee.display_name = args.display_name
        employee.role = ApplicationRole(args.role)
        employee.active = True
        session.commit()
        print(f"Provisioned development employee {employee.id}")


if __name__ == "__main__":
    main()
