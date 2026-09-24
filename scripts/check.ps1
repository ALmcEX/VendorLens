[CmdletBinding()]
param(
    [switch]$Containers
)

$ErrorActionPreference = "Stop"
$uv = (Get-Command uv -ErrorAction Stop).Source

& $uv run pytest -q
& $uv run ruff check packages apps tests
& $uv run ruff format --check packages apps tests
& $uv run mypy packages/vendorlens-core/src apps/api/src apps/worker/src
pnpm lint
pnpm typecheck
pnpm test
pnpm build
docker compose config --quiet

if ($Containers) {
    docker build -f infra/docker/api.Dockerfile -t vendorlens-api:local .
    docker build -f infra/docker/worker.Dockerfile -t vendorlens-worker:local .
}
