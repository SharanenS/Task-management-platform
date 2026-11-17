from people.models import Account
from sqlalchemy import select
from test_api import SETTINGS
from test_api import boundary as boundary


def headers():
    return {"Authorization": "Bearer valid-provider-token"}


def test_non_admin_is_denied_by_both_business_boundaries(boundary):
    people, gateway, sessions, identity = boundary
    response = people.get(
        "/internal/admin/workspace",
        headers={**headers(), "X-Service-Key": SETTINGS.service_key, "X-Actor-Role": "ADMIN"},
    )
    assert response.status_code == 403
    result = gateway.post(
        "/graphql",
        headers={**headers(), "X-Actor-Role": "ADMIN"},
        json={"query": "{ adminWorkspace { viewer { accountId } } }"},
    )
    assert result.status_code == 200
    assert result.json()["data"] is None
    assert result.json()["errors"][0]["extensions"]["code"] == "FORBIDDEN"


def test_admin_authority_is_rechecked_after_role_revocation(boundary):
    people, gateway, sessions, identity = boundary
    with sessions() as session:
        account = session.scalar(select(Account).where(Account.subject == identity.subject))
        account.grants[0].role = "ADMIN"
        session.commit()
    result = gateway.post(
        "/graphql",
        headers=headers(),
        json={"query": "{ adminWorkspace { viewer { companyRoles permissions } } }"},
    )
    assert result.json()["data"]["adminWorkspace"]["viewer"]["permissions"] == [
        "account:self:read",
        "admin:workspace:read",
    ]
    with sessions() as session:
        account = session.scalar(select(Account).where(Account.subject == identity.subject))
        account.grants[0].role = "EMPLOYEE"
        session.commit()
    result = gateway.post(
        "/graphql", headers=headers(), json={"query": "{ adminWorkspace { viewer { accountId } } }"}
    )
    assert result.json()["errors"][0]["extensions"]["code"] == "FORBIDDEN"
