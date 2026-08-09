[CmdletBinding()]
param(
    [ValidateRange(1, 20)]
    [int]$Pages = 3,
    [ValidateRange(1, 3)]
    [int]$Workers = 3
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$WindowsOutput = Join-Path `
    $ProjectRoot `
    "backend\data\policy_snapshots\snapshot-$Timestamp"
$WslOutput = (
    "/mnt/d/industrial-park-v1.1/backend/data/" +
    "policy_snapshots/snapshot-$Timestamp"
)
$Crawl4AiToken = if ($env:CRAWL4AI_TOKEN) {
    $env:CRAWL4AI_TOKEN
} else {
    "demo-token-11235"
}

function Wait-Docker {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        return
    }
    $DockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path -LiteralPath $DockerDesktop -PathType Leaf)) {
        throw "Docker Desktop not found: $DockerDesktop"
    }
    Start-Process -FilePath $DockerDesktop -WindowStyle Hidden
    $Deadline = (Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 3
        docker info *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
    } while ((Get-Date) -lt $Deadline)
    throw "Docker engine did not become ready."
}

function Wait-Crawl4AI {
    docker inspect crawl4ai *> $null
    if ($LASTEXITCODE -eq 0) {
        docker start crawl4ai *> $null
    } else {
        docker run -d -p 11235:11235 --name crawl4ai --shm-size=1g `
            -e "CRAWL4AI_API_TOKEN=$Crawl4AiToken" `
            unclecode/crawl4ai:latest *> $null
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Crawl4AI container could not be started."
    }
    $Deadline = (Get-Date).AddMinutes(2)
    do {
        try {
            $Response = Invoke-WebRequest `
                -Uri "http://localhost:11235/health" `
                -UseBasicParsing `
                -TimeoutSec 3
            if ($Response.StatusCode -eq 200) {
                return
            }
        } catch {
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $Deadline)
    throw "Crawl4AI health check timed out."
}

function Invoke-Wsl {
    param([Parameter(Mandatory)][string]$Command)
    & wsl.exe -e bash -lc $Command
    if ($LASTEXITCODE -ne 0) {
        throw "WSL command failed with exit code $LASTEXITCODE."
    }
}

$Required = @(
    "D:\crawl4ai-tools\guangzhou_policy_snapshot.py",
    "D:\crawl4ai-tools\clean_guangzhou_policies.py",
    "D:\crawl4ai-tools\guangzhou_policy_snapshot_sources.json"
)
foreach ($Path in $Required) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file not found: $Path"
    }
}

$Mutex = [Threading.Mutex]::new(
    $false,
    "Local\IndustrialParkGuangzhouFullSnapshot"
)
$HasLock = $false
try {
    $HasLock = $Mutex.WaitOne(0)
    if (-not $HasLock) {
        throw "Another full snapshot is already running."
    }
    Wait-Docker
    Wait-Crawl4AI

    Write-Host "Creating full Guangzhou policy snapshot..." -ForegroundColor Cyan
    Write-Host "No database, no incremental state, no deduplication." -ForegroundColor DarkGray
    $SafeToken = $Crawl4AiToken.Replace("'", "'`"`"'`"`"'")
    $SnapshotCommand = (
        "cd /mnt/d/industrial-park-v1.1/backend && " +
        "PYTHONPATH=. .venv312/bin/python " +
        "/mnt/d/crawl4ai-tools/guangzhou_policy_snapshot.py " +
        "--config /mnt/d/crawl4ai-tools/guangzhou_policy_snapshot_sources.json " +
        "--output '$WslOutput' --pages $Pages --workers $Workers " +
        "--api http://localhost:11235 --token '$SafeToken'"
    )
    Invoke-Wsl -Command $SnapshotCommand

    Write-Host "Cleaning pure policy bodies and extracting deadlines..." -ForegroundColor Cyan
    $CleanCommand = (
        "cd /mnt/d/industrial-park-v1.1/backend && " +
        ".venv312/bin/python /mnt/d/crawl4ai-tools/clean_guangzhou_policies.py " +
        "--snapshot '$WslOutput' --fetch-attachments"
    )
    Invoke-Wsl -Command $CleanCommand

    Write-Host "Building validated runtime policy catalog..." -ForegroundColor Cyan
    $CatalogCommand = (
        "cd /mnt/d/industrial-park-v1.1/backend && " +
        ".venv312/bin/python scripts/build_policy_catalog.py " +
        "--snapshot '$WslOutput'"
    )
    Invoke-Wsl -Command $CatalogCommand

    Write-Host "Full snapshot is ready:" -ForegroundColor Green
    Write-Host $WindowsOutput -ForegroundColor Green
} finally {
    if ($HasLock) {
        $Mutex.ReleaseMutex()
    }
    $Mutex.Dispose()
}
