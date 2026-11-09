param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectName,
    [string]$ComposeFile = "compose.test.yaml",
    [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectName -or $ProjectName.Trim() -eq "") {
    throw "Compose project name is mandatory for test stack bootstrap."
}

$devProjects = @("enterprise-task-platform-phase2", "project2.0", "taskspace", "default")
if ($devProjects -contains $ProjectName.Trim().ToLower()) {
    throw "Protected development project name '$ProjectName' cannot be targeted for test bootstrap!"
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot

try {
    $settings = @{}
    if ($EnvFile) {
        if (-not (Test-Path -LiteralPath $EnvFile)) {
            throw "Environment file '$EnvFile' does not exist."
        }
        Get-Content -LiteralPath $EnvFile | ForEach-Object {
            $line = $_.Trim()
            if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
                $name, $value = $line.Split("=", 2)
                $settings[$name.Trim()] = $value.Trim()
            }
        }
    }

    $frontendPort = if ($settings.ContainsKey("FRONTEND_PORT")) { $settings["FRONTEND_PORT"] } elseif ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "3110" }
    $adminUser = if ($settings.ContainsKey("KEYCLOAK_ADMIN_USERNAME")) { $settings["KEYCLOAK_ADMIN_USERNAME"] } elseif ($env:KEYCLOAK_ADMIN_USERNAME) { $env:KEYCLOAK_ADMIN_USERNAME } else { "local-admin" }
    $adminPass = if ($settings.ContainsKey("KEYCLOAK_ADMIN_PASSWORD")) { $settings["KEYCLOAK_ADMIN_PASSWORD"] } elseif ($env:KEYCLOAK_ADMIN_PASSWORD) { $env:KEYCLOAK_ADMIN_PASSWORD } else { throw "KEYCLOAK_ADMIN_PASSWORD missing" }
    $adminSecret = if ($settings.ContainsKey("KEYCLOAK_ADMIN_CLIENT_SECRET")) { $settings["KEYCLOAK_ADMIN_CLIENT_SECRET"] } elseif ($env:KEYCLOAK_ADMIN_CLIENT_SECRET) { $env:KEYCLOAK_ADMIN_CLIENT_SECRET } else { throw "KEYCLOAK_ADMIN_CLIENT_SECRET missing" }
    $devUser = if ($settings.ContainsKey("DEV_USER_USERNAME")) { $settings["DEV_USER_USERNAME"] } elseif ($env:DEV_USER_USERNAME) { $env:DEV_USER_USERNAME } else { "local.user" }
    $devPass = if ($settings.ContainsKey("DEV_USER_PASSWORD")) { $settings["DEV_USER_PASSWORD"] } elseif ($env:DEV_USER_PASSWORD) { $env:DEV_USER_PASSWORD } else { throw "DEV_USER_PASSWORD missing" }
    $devEmail = if ($settings.ContainsKey("DEV_USER_EMAIL")) { $settings["DEV_USER_EMAIL"] } elseif ($env:DEV_USER_EMAIL) { $env:DEV_USER_EMAIL } else { "local.user@example.test" }
    $devName = if ($settings.ContainsKey("DEV_USER_DISPLAY_NAME")) { $settings["DEV_USER_DISPLAY_NAME"] } elseif ($env:DEV_USER_DISPLAY_NAME) { $env:DEV_USER_DISPLAY_NAME } else { "Local User" }
    $devRole = if ($settings.ContainsKey("DEV_USER_ROLE")) { $settings["DEV_USER_ROLE"] } elseif ($env:DEV_USER_ROLE) { $env:DEV_USER_ROLE } else { "ADMIN" }

    Write-Host "Bootstrapping isolated Keycloak & Employee profile for project '$ProjectName'..." -ForegroundColor Cyan

    & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh config credentials `
        --server http://localhost:8080 --realm master `
        --user $adminUser --password $adminPass | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Keycloak admin credentials config failed." }

    $clientJson = & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh get clients -r taskspace -q clientId=taskspace-web
    $clients = @((($clientJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    if ($clients.Count -ne 1 -or -not $clients[0].id) {
        throw "Expected exactly one Taskspace OIDC client."
    }

    $clientDetailJson = & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh get "clients/$($clients[0].id)" -r taskspace
    $client = ($clientDetailJson -join "`n") | ConvertFrom-Json
    $client.rootUrl = "http://localhost:$frontendPort"
    $client.baseUrl = "http://localhost:$frontendPort/"
    $client.redirectUris = @("http://localhost:$frontendPort/auth/callback")
    $client.webOrigins = @("http://localhost:$frontendPort")
    $client.attributes.'post.logout.redirect.uris' = "http://localhost:$frontendPort/signed-out"
    $client.attributes.'pkce.code.challenge.method' = "S256"

    $client | ConvertTo-Json -Depth 20 -Compress | & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh update "clients/$($clients[0].id)" -r taskspace -f - | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Updating Taskspace OIDC client failed." }

    $adminClientJson = & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh get clients -r taskspace -q clientId=taskspace-employee-admin
    $adminClients = @((($adminClientJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    if ($adminClients.Count -eq 0) {
        & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
            /opt/keycloak/bin/kcadm.sh create clients -r taskspace `
            -s "clientId=taskspace-employee-admin" -s "enabled=true" `
            -s "publicClient=false" -s "standardFlowEnabled=false" `
            -s "directAccessGrantsEnabled=false" -s "serviceAccountsEnabled=true" `
            -s "secret=$adminSecret" | Out-Null

        $adminClientJson = & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
            /opt/keycloak/bin/kcadm.sh get clients -r taskspace -q clientId=taskspace-employee-admin
        $adminClients = @((($adminClientJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    }

    & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh update "clients/$($adminClients[0].id)" -r taskspace `
        -s "enabled=true" -s "publicClient=false" `
        -s "standardFlowEnabled=false" -s "directAccessGrantsEnabled=false" `
        -s "serviceAccountsEnabled=true" `
        -s "secret=$adminSecret" | Out-Null

    $saJson = & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh get "clients/$($adminClients[0].id)/service-account-user" -r taskspace
    $sa = ($saJson -join "`n") | ConvertFrom-Json
    foreach ($r in @("manage-users", "view-users", "query-users")) {
        & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
            /opt/keycloak/bin/kcadm.sh add-roles -r taskspace --uid $sa.id `
            --cclientid realm-management --rolename $r | Out-Null
    }

    $userJson = & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh get users -r taskspace -q username=$devUser
    $users = @((($userJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    if ($users.Count -eq 0) {
        & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
            /opt/keycloak/bin/kcadm.sh create users -r taskspace `
            -s "username=$devUser" -s "email=$devEmail" `
            -s "firstName=Local" -s "lastName=User" `
            -s "enabled=true" -s "emailVerified=true" | Out-Null

        $userJson = & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
            /opt/keycloak/bin/kcadm.sh get users -r taskspace -q username=$devUser
        $users = @((($userJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    }

    $subject = $users[0].id
    & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh update "users/$subject" -r taskspace `
        -s "enabled=true" -s "emailVerified=true" -s 'requiredActions=[]' | Out-Null

    & docker compose -p $ProjectName -f $ComposeFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh set-password -r taskspace --userid $subject `
        --new-password $devPass | Out-Null

    & docker compose -p $ProjectName -f $ComposeFile exec -T employee python -m app.bootstrap `
        --subject $subject --username $devUser `
        --email $devEmail --display-name $devName --role $devRole | Out-Null

    Write-Host "Isolated test stack bootstrap completed successfully." -ForegroundColor Green
}
finally {
    Pop-Location
}
