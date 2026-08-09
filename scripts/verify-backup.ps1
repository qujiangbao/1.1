[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$BackupDirectory)

$ErrorActionPreference = "Stop"
$Directory = (Resolve-Path -LiteralPath $BackupDirectory).Path
$ManifestPath = Join-Path $Directory "manifest.json"
if (-not (Test-Path -LiteralPath $ManifestPath)) { throw "manifest.json is missing" }
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($Entry in $Manifest) {
    $Path = Join-Path $Directory $Entry.file
    if (-not (Test-Path -LiteralPath $Path)) { throw "Missing backup file: $($Entry.file)" }
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Hash -ne $Entry.sha256) { throw "Checksum mismatch: $($Entry.file)" }
}
Write-Host "Backup verified: $Directory"
