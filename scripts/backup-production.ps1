[CmdletBinding()]
param(
    [string]$EnvFile = ".env.production",
    [string]$BackupRoot = ".local-backups"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TargetRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $BackupRoot))
if (-not $TargetRoot.StartsWith($RepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "BackupRoot must stay inside the project directory"
}
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Target = Join-Path $TargetRoot $Stamp
New-Item -ItemType Directory -Path $Target -Force | Out-Null

$Compose = @("compose", "--env-file", $EnvFile)
$PostgresId = (& docker @Compose ps -q postgres).Trim()
$BackendId = (& docker @Compose ps -q backend).Trim()
if (-not $PostgresId -or -not $BackendId) {
    throw "PostgreSQL and backend containers must be running"
}

& docker @Compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/industrial-park.dump'
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL backup failed" }
& docker cp "${PostgresId}:/tmp/industrial-park.dump" (Join-Path $Target "postgres.dump")
& docker exec $PostgresId rm -f /tmp/industrial-park.dump

& docker @Compose exec -T backend sh -c 'tar -czf /tmp/park-data.tgz -C /app/data park_documents policy_snapshots checkpoints'
if ($LASTEXITCODE -ne 0) { throw "Park document backup failed" }
& docker cp "${BackendId}:/tmp/park-data.tgz" (Join-Path $Target "park-data.tgz")
& docker exec $BackendId rm -f /tmp/park-data.tgz

$Manifest = Get-ChildItem -LiteralPath $Target -File | ForEach-Object {
    $Hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
    [PSCustomObject]@{ file = $_.Name; bytes = $_.Length; sha256 = $Hash.Hash.ToLowerInvariant() }
}
$Manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Target "manifest.json") -Encoding UTF8
Write-Host "Backup completed: $Target"
