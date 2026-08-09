[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BackupDirectory,
    [string]$EnvFile = ".env.production",
    [switch]$ConfirmRestore
)

$ErrorActionPreference = "Stop"
if (-not $ConfirmRestore) {
    throw "Restore overwrites the active database and document volume. Re-run with -ConfirmRestore."
}
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$AllowedRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot ".local-backups"))
$Source = (Resolve-Path -LiteralPath $BackupDirectory).Path
if (-not $Source.StartsWith($AllowedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "BackupDirectory must be inside $AllowedRoot"
}
& (Join-Path $PSScriptRoot "verify-backup.ps1") -BackupDirectory $Source

$Compose = @("compose", "--env-file", $EnvFile)
$PostgresId = (& docker @Compose ps -q postgres).Trim()
$BackendId = (& docker @Compose ps -q backend).Trim()
if (-not $PostgresId -or -not $BackendId) { throw "Required containers are not running" }

& docker cp (Join-Path $Source "postgres.dump") "${PostgresId}:/tmp/industrial-park.dump"
& docker @Compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges /tmp/industrial-park.dump'
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL restore failed" }
& docker exec $PostgresId rm -f /tmp/industrial-park.dump

& docker cp (Join-Path $Source "park-data.tgz") "${BackendId}:/tmp/park-data.tgz"
& docker @Compose exec -T backend sh -c 'tar -xzf /tmp/park-data.tgz -C /app/data && rm -f /tmp/park-data.tgz'
if ($LASTEXITCODE -ne 0) { throw "Park document restore failed" }
& docker @Compose restart backend
Write-Host "Restore completed. Run scripts/runtime_acceptance.ps1 to validate the service."
