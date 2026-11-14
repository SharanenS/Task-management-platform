param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$ProjectName,
    [Parameter(Position=1)]
    [string]$ComposeFile = "compose.test.yaml",
    [Parameter(Position=2)]
    [string]$EnvFile = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not $ProjectName -or $ProjectName.Trim() -eq "") {
    throw "Compose project name is mandatory for test stack bootstrap."
}

$devProjects = @("enterprise-task-platform-phase2", "project2.0", "taskspace", "default")
if ($devProjects -contains $ProjectName.Trim().ToLower()) {
    throw "Protected development project name '$ProjectName' cannot be targeted for test bootstrap!"
}

if (-not $ComposeFile -or -not (Test-Path -LiteralPath $ComposeFile)) {
    throw "Compose file '$ComposeFile' does not exist."
}

if (-not $EnvFile -or $EnvFile.Trim() -eq "") {
    throw "Isolated environment file parameter is mandatory."
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Environment file '$EnvFile' does not exist."
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot

try {
    $settings = @{}
    Get-Content -LiteralPath $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $name, $value = $line.Split("=", 2)
            $k = $name.Trim()
            $v = $value.Trim()
            if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
                $v = $v.Substring(1, $v.Length - 2)
            }
            $settings[$k] = $v
        }
    }

    if ($settings.ContainsKey("COMPOSE_PROJECT_NAME") -and $settings["COMPOSE_PROJECT_NAME"] -ne $ProjectName) {
        throw "Project name mismatch: argument '$ProjectName' does not match COMPOSE_PROJECT_NAME '$($settings["COMPOSE_PROJECT_NAME"])' in environment file."
    }

    $requiredKeys = @(
        "FRONTEND_PORT",
        "KEYCLOAK_ADMIN_USERNAME",
        "KEYCLOAK_ADMIN_PASSWORD",
        "KEYCLOAK_ADMIN_CLIENT_SECRET",
        "DEV_USER_USERNAME",
        "DEV_USER_PASSWORD",
        "DEV_USER_EMAIL",
        "DEV_USER_DISPLAY_NAME",
        "DEV_USER_ROLE"
    )
    foreach ($key in $requiredKeys) {
        if (-not $settings.ContainsKey($key) -or -not $settings[$key]) {
            throw "Required isolated configuration '$key' is missing from '$EnvFile'."
        }
    }

    $frontendPort = $settings["FRONTEND_PORT"]
    $adminUser = $settings["KEYCLOAK_ADMIN_USERNAME"]
    $adminPass = $settings["KEYCLOAK_ADMIN_PASSWORD"]
    $adminSecret = $settings["KEYCLOAK_ADMIN_CLIENT_SECRET"]
    $devUser = $settings["DEV_USER_USERNAME"]
    $devPass = $settings["DEV_USER_PASSWORD"]
    $devEmail = $settings["DEV_USER_EMAIL"]
    $devName = $settings["DEV_USER_DISPLAY_NAME"]
    $devRole = $settings["DEV_USER_ROLE"]

    if ($DryRun) {
        Write-Host "Dry-run bootstrap validation successful for project '$ProjectName':" -ForegroundColor Green
        Write-Host "  COMPOSE_FILE=$ComposeFile"
        Write-Host "  ENV_FILE=$EnvFile"
        Write-Host "  FRONTEND_PORT=$frontendPort"
        return
    }

    Write-Host "Bootstrapping isolated Keycloak & Employee profile for project '$ProjectName'..." -ForegroundColor Cyan

    & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh config credentials `
        --server http://localhost:8080 --realm master `
        --user $adminUser --password $adminPass | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Keycloak admin credentials config failed." }

    $clientJson = & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh get clients -r taskspace -q clientId=taskspace-web
    $clients = @((($clientJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    if ($clients.Count -ne 1 -or -not $clients[0].id) {
        throw "Expected exactly one Taskspace OIDC client."
    }

    $clientDetailJson = & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh get "clients/$($clients[0].id)" -r taskspace
    $client = ($clientDetailJson -join "`n") | ConvertFrom-Json
    $client.rootUrl = "http://localhost:$frontendPort"
    $client.baseUrl = "http://localhost:$frontendPort/"
    $client.redirectUris = @("http://localhost:$frontendPort/auth/callback")
    $client.webOrigins = @("http://localhost:$frontendPort")
    if (-not $client.PSObject.Properties['attributes'] -or $null -eq $client.attributes) {
        $client | Add-Member -NotePropertyName 'attributes' -NotePropertyValue ([PSCustomObject]@{}) -Force
    }
    $client.attributes | Add-Member -NotePropertyName 'post.logout.redirect.uris' -NotePropertyValue "http://localhost:$frontendPort/signed-out" -Force
    $client.attributes | Add-Member -NotePropertyName 'pkce.code.challenge.method' -NotePropertyValue "S256" -Force

    $client | ConvertTo-Json -Depth 20 -Compress | & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh update "clients/$($clients[0].id)" -r taskspace -f - | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Updating Taskspace OIDC client failed." }

    $adminClientJson = & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh get clients -r taskspace -q clientId=taskspace-employee-admin
    $adminClients = @((($adminClientJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    if ($adminClients.Count -eq 0) {
        & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
            /opt/keycloak/bin/kcadm.sh create clients -r taskspace `
            -s "clientId=taskspace-employee-admin" -s "enabled=true" `
            -s "publicClient=false" -s "standardFlowEnabled=false" `
            -s "directAccessGrantsEnabled=false" -s "serviceAccountsEnabled=true" `
            -s "secret=$adminSecret" | Out-Null

        $adminClientJson = & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
            /opt/keycloak/bin/kcadm.sh get clients -r taskspace -q clientId=taskspace-employee-admin
        $adminClients = @((($adminClientJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    }

    & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh update "clients/$($adminClients[0].id)" -r taskspace `
        -s "enabled=true" -s "publicClient=false" `
        -s "standardFlowEnabled=false" -s "directAccessGrantsEnabled=false" `
        -s "serviceAccountsEnabled=true" `
        -s "secret=$adminSecret" | Out-Null

    $saJson = & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh get "clients/$($adminClients[0].id)/service-account-user" -r taskspace
    $sa = ($saJson -join "`n") | ConvertFrom-Json
    foreach ($r in @("manage-users", "view-users", "query-users")) {
        & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
            /opt/keycloak/bin/kcadm.sh add-roles -r taskspace --uid $sa.id `
            --cclientid realm-management --rolename $r | Out-Null
    }

    $userJson = & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh get users -r taskspace -q username=$devUser
    $users = @((($userJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    if ($users.Count -eq 0) {
        & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
            /opt/keycloak/bin/kcadm.sh create users -r taskspace `
            -s "username=$devUser" -s "email=$devEmail" `
            -s "firstName=Local" -s "lastName=User" `
            -s "enabled=true" -s "emailVerified=true" | Out-Null

        $userJson = & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
            /opt/keycloak/bin/kcadm.sh get users -r taskspace -q username=$devUser
        $users = @((($userJson -join "`n") | ConvertFrom-Json) | Where-Object { $null -ne $_ })
    }

    $subject = $users[0].id
    & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh update "users/$subject" -r taskspace `
        -s "enabled=true" -s "emailVerified=true" -s 'requiredActions=[]' | Out-Null

    & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T keycloak `
        /opt/keycloak/bin/kcadm.sh set-password -r taskspace --userid $subject `
        --new-password $devPass | Out-Null

    & docker compose -p $ProjectName -f $ComposeFile --env-file $EnvFile exec -T employee python -m app.bootstrap `
        --subject $subject --username $devUser `
        --email $devEmail --display-name $devName --role $devRole | Out-Null

    Write-Host "Isolated test stack bootstrap completed successfully." -ForegroundColor Green
}
finally {
    Pop-Location
}
