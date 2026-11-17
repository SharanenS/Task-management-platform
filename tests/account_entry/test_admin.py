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


def test_account_controls_require_independent_admin_authority(boundary):
    from uuid import uuid4

    people, gateway, sessions, identity = boundary
    request = {
        "request_id": str(uuid4()),
        "username": "test.user",
        "email": "test@example.test",
        "display_name": "Test",
        "role": "ADMIN",
    }
    assert (
        people.post(
            "/internal/admin/accounts/create",
            json=request,
            headers={**headers(), "X-Service-Key": SETTINGS.service_key, "X-Actor-Role": "ADMIN"},
        ).status_code
        == 403
    )
    result = gateway.post(
        "/graphql",
        headers={**headers(), "X-Actor-Role": "ADMIN"},
        json={"query": "{ accountAdministration { accounts { id email } } }"},
    )
    assert (
        result.json()["data"] is None
        and result.json()["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    )
    result = gateway.post(
        "/graphql",
        headers=headers(),
        json={
            "query": "mutation($input:CreateAccountInput!){createAccount(input:$input){state}}",
            "variables": {
                "input": {
                    "requestId": request["request_id"],
                    "username": "test.user",
                    "email": "test@example.test",
                    "displayName": "Test",
                    "role": "ADMIN",
                }
            },
        },
    )
    assert result.json()["errors"][0]["extensions"]["code"] == "FORBIDDEN"


def test_admin_can_read_accounts_but_private_service_key_is_still_required(boundary):
    people, gateway, sessions, identity = boundary
    with sessions() as s:
        account = s.scalar(select(Account).where(Account.subject == identity.subject))
        account.grants[0].role = "ADMIN"
        s.commit()
    assert people.get("/internal/admin/accounts", headers=headers()).status_code == 401
    result = gateway.post(
        "/graphql",
        headers=headers(),
        json={"query": "{accountAdministration {accounts {id role version} history {id} hasMore}}"},
    )
    assert result.json()["data"]["accountAdministration"]["accounts"][0]["role"] == "ADMIN"
    with sessions() as s:
        account = s.scalar(select(Account).where(Account.subject == identity.subject))
        account.active = False
        s.commit()
    assert (
        gateway.post(
            "/graphql", headers=headers(), json={"query": "{accountAdministration {accounts {id}}}"}
        ).status_code
        == 403
    )
