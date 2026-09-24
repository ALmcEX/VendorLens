[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$supabaseVersion = "2.117.0"

pnpm dlx "supabase@$supabaseVersion" start
pnpm dlx "supabase@$supabaseVersion" db reset

$statusJson = pnpm dlx "supabase@$supabaseVersion" status -o json | Out-String
$status = $statusJson | ConvertFrom-Json
$databaseUrl = [string]$status.DB_URL
$supabaseUrl = [string]$status.API_URL
$serviceRoleKey = [string]$status.SERVICE_ROLE_KEY

if (-not $databaseUrl -or -not $supabaseUrl -or -not $serviceRoleKey) {
    throw "Supabase status did not return DB_URL, API_URL, and SERVICE_ROLE_KEY."
}

$env:VENDORLENS_CONTAINER_DATABASE_URL = ($databaseUrl -replace '^postgresql://', 'postgresql+asyncpg://') -replace '127\.0\.0\.1', 'host.docker.internal'
$env:VENDORLENS_CONTAINER_SUPABASE_URL = $supabaseUrl -replace '127\.0\.0\.1', 'host.docker.internal'
$env:VENDORLENS_SUPABASE_SERVICE_ROLE_KEY = $serviceRoleKey
$env:NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000"

docker compose up -d --build api worker
pnpm --filter @vendorlens/web dev
