$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$environmentFile = Join-Path $repositoryRoot ".env"
if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw "Create .env from .env.example and replace every change-me value first."
}

$settings = @{}
Get-Content -LiteralPath $environmentFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $name, $value = $line.Split("=", 2)
        $settings[$name.Trim()] = $value.Trim()
    }
}

$required = @(
    "KEYCLOAK_ADMIN_USERNAME",
    "KEYCLOAK_ADMIN_PASSWORD",
    "KEYCLOAK_ADMIN_CLIENT_SECRET",
    "DEV_USER_USERNAME",
    "DEV_USER_PASSWORD",
    "DEV_USER_EMAIL",
    "DEV_USER_DISPLAY_NAME",
    "DEV_USER_ROLE"
)
foreach ($name in $required) {
    if (-not $settings[$name] -or $settings[$name] -like "change-me*") {
        throw "Set $name to a non-placeholder value in .env."
    }
}

function Invoke-Docker {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $output = & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed while provisioning the development identity."
    }
    return $output
}

Push-Location $repositoryRoot
try {
    $displayParts = $settings.DEV_USER_DISPLAY_NAME.Split(" ", 2)
    $firstName = $displayParts[0]
    $lastName = if ($displayParts.Count -gt 1) { $displayParts[1] } else { "User" }
    Invoke-Docker @(
        "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
        "config", "credentials", "--server", "http://localhost:8080", "--realm", "master",
        "--user", $settings.KEYCLOAK_ADMIN_USERNAME, "--password", $settings.KEYCLOAK_ADMIN_PASSWORD
    ) | Out-Null

    $clientJson = Invoke-Docker @(
        "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
        "get", "clients", "-r", "taskspace", "-q", "clientId=taskspace-web"
    )
    $clients = @((($clientJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    if ($clients.Count -ne 1 -or -not $clients[0].id) {
        throw "Expected exactly one Taskspace OIDC client."
    }
    $clientDetailJson = Invoke-Docker @(
        "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
        "get", "clients/$($clients[0].id)", "-r", "taskspace"
    )
    $client = ($clientDetailJson -join "`n") | ConvertFrom-Json
    $client.attributes.'post.logout.redirect.uris' = "http://localhost:3010/signed-out"
    $client.attributes.'pkce.code.challenge.method' = "S256"
    $client | ConvertTo-Json -Depth 20 -Compress | & docker compose exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh update "clients/$($clients[0].id)" -r taskspace -f -
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed while updating the Taskspace OIDC client."
    }

    $adminClientJson = Invoke-Docker @(
        "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
        "get", "clients", "-r", "taskspace", "-q", "clientId=taskspace-employee-admin"
    )
    $adminClients = @((($adminClientJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    if ($adminClients.Count -eq 0) {
        Invoke-Docker @(
            "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
            "create", "clients", "-r", "taskspace",
            "-s", "clientId=taskspace-employee-admin", "-s", "enabled=true",
            "-s", "publicClient=false", "-s", "standardFlowEnabled=false",
            "-s", "directAccessGrantsEnabled=false", "-s", "serviceAccountsEnabled=true",
            "-s", "secret=$($settings.KEYCLOAK_ADMIN_CLIENT_SECRET)"
        ) | Out-Null
        $adminClientJson = Invoke-Docker @(
            "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
            "get", "clients", "-r", "taskspace", "-q", "clientId=taskspace-employee-admin"
        )
        $adminClients = @((($adminClientJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    }
    if ($adminClients.Count -ne 1 -or -not $adminClients[0].id) {
        throw "Expected exactly one Employee Service administration client."
    }
    Invoke-Docker @(
        "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
        "update", "clients/$($adminClients[0].id)", "-r", "taskspace",
        "-s", "enabled=true", "-s", "publicClient=false",
        "-s", "standardFlowEnabled=false", "-s", "directAccessGrantsEnabled=false",
        "-s", "serviceAccountsEnabled=true",
        "-s", "secret=$($settings.KEYCLOAK_ADMIN_CLIENT_SECRET)"
    ) | Out-Null
    $serviceAccountJson = Invoke-Docker @(
        "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
        "get", "clients/$($adminClients[0].id)/service-account-user", "-r", "taskspace"
    )
    $serviceAccount = ($serviceAccountJson -join "`n") | ConvertFrom-Json
    foreach ($roleName in @("manage-users", "view-users", "query-users")) {
        Invoke-Docker @(
            "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
            "add-roles", "-r", "taskspace", "--uid", $serviceAccount.id,
            "--cclientid", "realm-management", "--rolename", $roleName
        ) | Out-Null
    }

    $userJson = Invoke-Docker @(
        "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
        "get", "users", "-r", "taskspace", "-q", "username=$($settings.DEV_USER_USERNAME)"
    )
    $users = @((($userJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    if ($users.Count -eq 0) {
        Invoke-Docker @(
            "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
            "create", "users", "-r", "taskspace",
            "-s", "username=$($settings.DEV_USER_USERNAME)",
            "-s", "email=$($settings.DEV_USER_EMAIL)",
            "-s", "firstName=$firstName", "-s", "lastName=$lastName",
            "-s", "enabled=true", "-s", "emailVerified=true"
        ) | Out-Null
        $userJson = Invoke-Docker @(
            "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
            "get", "users", "-r", "taskspace", "-q", "username=$($settings.DEV_USER_USERNAME)"
        )
        $users = @((($userJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    }
    if ($users.Count -ne 1 -or -not $users[0].id) {
        throw "Expected exactly one development identity after provisioning."
    }
    $subject = $users[0].id
    Invoke-Docker @(
        "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
        "update", "users/$subject", "-r", "taskspace",
        "-s", "email=$($settings.DEV_USER_EMAIL)",
        "-s", "firstName=$firstName", "-s", "lastName=$lastName",
        "-s", "enabled=true", "-s", "emailVerified=true",
        "-s", 'requiredActions=[]'
    ) | Out-Null
    Invoke-Docker @(
        "compose", "exec", "-T", "keycloak", "/opt/keycloak/bin/kcadm.sh",
        "set-password", "-r", "taskspace", "--userid", $subject,
        "--new-password", $settings.DEV_USER_PASSWORD
    ) | Out-Null

    Invoke-Docker @(
        "compose", "exec", "-T", "employee", "python", "-m", "app.bootstrap",
        "--subject", $subject, "--username", $settings.DEV_USER_USERNAME,
        "--email", $settings.DEV_USER_EMAIL,
        "--display-name", $settings.DEV_USER_DISPLAY_NAME, "--role", $settings.DEV_USER_ROLE
    )
    Write-Output "Development identity and employee profile are ready."
}
finally {
    Pop-Location
}
