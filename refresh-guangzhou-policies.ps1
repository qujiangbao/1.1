[CmdletBinding()]
param(
    [switch]$Watch,
    [ValidateRange(1, 20)]
    [int]$Pages = 3,
    [ValidateRange(1, 3)]
    [int]$Workers = 3,
    [ValidateRange(15, 1440)]
    [int]$IntervalMinutes = 30,
    [switch]$Force,
    [switch]$ImportPgvector
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$CrawlerRoot = "D:\crawl4ai-tools"
$CrawlerScript = Join-Path $CrawlerRoot "gz_gov_crawler.py"
$SourceConfig = Join-Path $CrawlerRoot "guangzhou_policy_sources.json"
$CacheDir = Join-Path $ProjectRoot "backend\data\policies_gz_gov"
$Crawl4AiApi = "http://localhost:11235"
$Crawl4AiToken = if ($env:CRAWL4AI_TOKEN) {
    $env:CRAWL4AI_TOKEN
} else {
    "demo-token-11235"
}

function Assert-RequiredFiles {
    foreach ($Path in @($CrawlerScript, $SourceConfig)) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            throw "Required file not found: $Path"
        }
    }
}

function Wait-DockerEngine {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        return
    }

    $DockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path -LiteralPath $DockerDesktop -PathType Leaf)) {
        throw "Docker Desktop is not installed at: $DockerDesktop"
    }
    Write-Host "Docker engine is unavailable; starting Docker Desktop..." -ForegroundColor Yellow
    Start-Process -FilePath $DockerDesktop -WindowStyle Hidden

    $Deadline = (Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 3
        docker info *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
    } while ((Get-Date) -lt $Deadline)
    throw "Docker engine did not become ready within 3 minutes."
}

function Wait-Crawl4AI {
    docker inspect crawl4ai *> $null
    if ($LASTEXITCODE -eq 0) {
        docker start crawl4ai *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "Existing Crawl4AI container could not be started."
        }
    } else {
        Write-Host "Creating Crawl4AI container..." -ForegroundColor Yellow
        docker run -d -p 11235:11235 --name crawl4ai --shm-size=1g `
            -e "CRAWL4AI_API_TOKEN=$Crawl4AiToken" `
            unclecode/crawl4ai:latest *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "Crawl4AI container creation failed."
        }
    }

    $Deadline = (Get-Date).AddMinutes(2)
    do {
        try {
            $Response = Invoke-WebRequest `
                -Uri "$Crawl4AiApi/health" `
                -UseBasicParsing `
                -TimeoutSec 3
            if ($Response.StatusCode -eq 200) {
                return
            }
        } catch {
            # The service commonly needs tens of seconds after the container starts.
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $Deadline)
    throw "Crawl4AI health endpoint did not become ready within 2 minutes."
}

function Invoke-WslCommand {
    param([Parameter(Mandatory)][string]$Command)
    & wsl.exe -e bash -lc $Command
    if ($LASTEXITCODE -ne 0) {
        throw "WSL command failed with exit code $LASTEXITCODE."
    }
}

function Invoke-PolicyRefresh {
    $ForceArgument = if ($Force) { " --force" } else { "" }
    $SafeToken = $Crawl4AiToken.Replace("'", "'`"`"'`"`"'")
    $CrawlerCommand = (
        "cd /mnt/d/industrial-park-v1.1/backend && " +
        "PYTHONPATH=. .venv312/bin/python /mnt/d/crawl4ai-tools/gz_gov_crawler.py " +
        "--config /mnt/d/crawl4ai-tools/guangzhou_policy_sources.json " +
        "--output /mnt/d/industrial-park-v1.1/backend/data/policies_gz_gov " +
        "--api http://localhost:11235 " +
        "--token '$SafeToken' " +
        "--pages $Pages --workers $Workers --refresh-days 7$ForceArgument"
    )
    Invoke-WslCommand -Command $CrawlerCommand

    $SyncCommand = (
        "cd /mnt/d/industrial-park-v1.1/backend && " +
        "PYTHONPATH=. .venv312/bin/python scripts/sync_crawl4ai_policies.py " +
        "--source data/policies_gz_gov --target data/policies_gz_gov"
    )
    Invoke-WslCommand -Command $SyncCommand

    if ($ImportPgvector) {
        Write-Host "Importing with real OpenAI embeddings..." -ForegroundColor Cyan
        $ImportCommand = (
            "cd /mnt/d/industrial-park-v1.1/backend && " +
            "PYTHONPATH=. .venv312/bin/python scripts/import_crawl4ai_policies.py " +
            "--cache data/policies_gz_gov --provider openai --continue-on-error"
        )
        Invoke-WslCommand -Command $ImportCommand
    }
}

Assert-RequiredFiles
$Mutex = [Threading.Mutex]::new(
    $false,
    "Local\IndustrialParkGuangzhouPolicySync"
)
$HasLock = $false
try {
    $HasLock = $Mutex.WaitOne(0)
    if (-not $HasLock) {
        throw "Another Guangzhou policy sync process is already running."
    }

    Wait-DockerEngine
    Wait-Crawl4AI

    do {
        $StartedAt = Get-Date
        Write-Host (
            "[{0}] Starting Guangzhou policy refresh..." -f
            $StartedAt.ToString("yyyy-MM-dd HH:mm:ss")
        ) -ForegroundColor Cyan
        try {
            Invoke-PolicyRefresh
            Write-Host (
                "[{0}] Policy cache and catalog are ready: {1}" -f
                (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"),
                $CacheDir
            ) -ForegroundColor Green
        } catch {
            Write-Warning $_
            if (-not $Watch) {
                throw
            }
        }

        if ($Watch) {
            Write-Host (
                "Next check in {0} minutes. Press Ctrl+C to stop." -f
                $IntervalMinutes
            ) -ForegroundColor DarkGray
            Start-Sleep -Seconds ($IntervalMinutes * 60)
        }
    } while ($Watch)
} finally {
    if ($HasLock) {
        $Mutex.ReleaseMutex()
    }
    $Mutex.Dispose()
}
