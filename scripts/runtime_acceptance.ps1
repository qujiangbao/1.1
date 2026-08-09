param(
    [string]$EnvFile = ".env.production",
    [string]$BaseUrl = "http://localhost:8080/api/v1"
)

$ErrorActionPreference = "Stop"

function Assert-Condition {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw "Acceptance assertion failed: $Message"
    }
}

function Read-DotEnv {
    param([string]$Path)

    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        if ($parts.Count -ne 2) {
            continue
        }
        $value = $parts[1].Trim()
        if (
            $value.Length -ge 2 -and
            (($value.StartsWith('"') -and $value.EndsWith('"')) -or
             ($value.StartsWith("'") -and $value.EndsWith("'")))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $values[$parts[0].Trim()] = $value
    }
    return $values
}

function Invoke-Json {
    param(
        [string]$Method,
        [string]$Path,
        [object]$Body = $null,
        [hashtable]$Headers = @{}
    )

    $parameters = @{
        Uri = "$BaseUrl$Path"
        Method = $Method
        Headers = $Headers
        TimeoutSec = 180
    }
    if ($null -ne $Body) {
        $parameters.ContentType = "application/json; charset=utf-8"
        $parameters.Body = $Body | ConvertTo-Json -Depth 100 -Compress
    }
    try {
        return Invoke-RestMethod @parameters
    }
    catch {
        $status = $_.Exception.Response.StatusCode.value__
        throw "$Method $Path failed with HTTP $status"
    }
}

$environment = Read-DotEnv -Path $EnvFile
Assert-Condition ($environment.ContainsKey("ADMIN_USERNAME")) "ADMIN_USERNAME is missing"
Assert-Condition ($environment.ContainsKey("ADMIN_PASSWORD")) "ADMIN_PASSWORD is missing"

$login = Invoke-Json -Method POST -Path "/auth/login" -Body @{
    username = $environment["ADMIN_USERNAME"]
    password = $environment["ADMIN_PASSWORD"]
}
Assert-Condition ([bool]$login.access_token) "login did not return an access token"
Assert-Condition ([bool]$login.user.id) "login did not return a user id"
$headers = @{ Authorization = "Bearer $($login.access_token)" }

$robotics = [regex]::Unescape('\u673a\u5668\u4eba')
$coreComponents = [regex]::Unescape('\u6838\u5fc3\u96f6\u90e8\u4ef6')
$systemIntegration = [regex]::Unescape('\u7cfb\u7edf\u96c6\u6210')
$industrialSoftware = [regex]::Unescape('\u5de5\u4e1a\u8f6f\u4ef6')
$guangzhou = [regex]::Unescape('\u5e7f\u5dde')

$scenario = Invoke-Json -Method POST -Path "/investment/scenarios" -Headers $headers -Body @{
    name = "Container runtime acceptance-$([DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss'))"
    industry = $robotics
    target_chain_roles = @($coreComponents, $systemIntegration, $industrialSoftware)
    location_preference = $guangzhou
    limit = 2
    data_mode = "real"
}
Assert-Condition ($scenario.status -eq "READY") "scenario status is not READY"
Assert-Condition ([bool]$scenario.scenario_id) "scenario id is missing"

$recommendationResponse = Invoke-Json `
    -Method GET `
    -Path "/investment/scenarios/$($scenario.scenario_id)/recommendations" `
    -Headers $headers
$snapshot = $recommendationResponse.data
$recommendations = @($snapshot.recommendations)
Assert-Condition ($recommendations.Count -ge 1) "real scenario returned no recommendations"
$first = $recommendations[0]
foreach ($agent in @(
    "Supervisor",
    "IndustryAgent",
    "InvestmentAgent",
    "EnterpriseData",
    "RiskAgent",
    "PolicyAgent"
)) {
    Assert-Condition ($null -ne $first.agent_outputs.$agent) "missing $agent output"
}

$candidateResponse = Invoke-Json -Method POST -Path "/investment/candidates" -Headers $headers -Body @{
    scenario_id = $scenario.scenario_id
    recommendation = $first
    data_mode = "real"
}
$candidate = $candidateResponse.data
Assert-Condition ([bool]$candidate.id) "candidate was not persisted"

$exposureItems = @()
for ($index = 0; $index -lt $recommendations.Count; $index++) {
    $exposureItems += @{
        enterprise_id = $recommendations[$index].enterprise_id
        position = $index + 1
        score = $recommendations[$index].overall_score
    }
}
$exposure = Invoke-Json `
    -Method POST `
    -Path "/investment/scenarios/$($scenario.scenario_id)/exposures" `
    -Headers $headers `
    -Body @{
        event_type = "IMPRESSION"
        data_mode = "real"
        items = $exposureItems
        context = @{ source = "runtime_acceptance" }
    }
Assert-Condition ($exposure.created -eq $recommendations.Count) "exposures were not persisted"

$occurredAt = [DateTime]::UtcNow.ToString("o")
$crmResponse = Invoke-Json -Method POST -Path "/investment/crm/events" -Headers $headers -Body @{
    candidate_id = $candidate.id
    event_type = "CONTACT"
    occurred_at = $occurredAt
    contact_name = "Runtime acceptance contact"
    contact_channel = "SYSTEM_TEST"
    summary = "Container end-to-end write acceptance"
    next_step = "Create and complete the follow-up task"
    evidence_refs = @("runtime-acceptance")
    data_mode = "real"
}
Assert-Condition ([bool]$crmResponse.data.id) "CRM event was not persisted"

$taskResponse = Invoke-Json -Method POST -Path "/investment/follow-up-tasks" -Headers $headers -Body @{
    candidate_id = $candidate.id
    title = "Complete container runtime acceptance"
    description = "Verify TODO, IN_PROGRESS and DONE transitions"
    owner_id = $login.user.id
    priority = "HIGH"
    data_mode = "real"
}
$task = $taskResponse.data
Assert-Condition ($task.status -eq "TODO") "new follow-up task is not TODO"

$inProgress = Invoke-Json `
    -Method PATCH `
    -Path "/investment/follow-up-tasks/$($task.id)" `
    -Headers $headers `
    -Body @{ status = "IN_PROGRESS" }
Assert-Condition ($inProgress.data.status -eq "IN_PROGRESS") "task did not enter IN_PROGRESS"

$done = Invoke-Json `
    -Method PATCH `
    -Path "/investment/follow-up-tasks/$($task.id)" `
    -Headers $headers `
    -Body @{
        status = "DONE"
        completion_note = "Container API, PostgreSQL and PDF acceptance passed"
    }
Assert-Condition ($done.data.status -eq "DONE") "task did not enter DONE"

$funnelResponse = Invoke-Json `
    -Method GET `
    -Path "/investment/crm/funnel?data_mode=real" `
    -Headers $headers
$contactStage = @($funnelResponse.data.stages) |
    Where-Object { $_.stage -eq "CONTACT" } |
    Select-Object -First 1
Assert-Condition ($null -ne $contactStage) "CONTACT funnel stage is missing"
Assert-Condition ($contactStage.count -ge 1) "CONTACT funnel count did not reflect the write"

$pdfResponse = Invoke-WebRequest `
    -Uri "$BaseUrl/investment/scenarios/$($scenario.scenario_id)/report.pdf" `
    -Method GET `
    -Headers $headers `
    -TimeoutSec 180
$contentType = [string]$pdfResponse.Headers["Content-Type"]
Assert-Condition ($contentType.StartsWith("application/pdf")) "report content type is not PDF"
Assert-Condition ($pdfResponse.RawContentLength -gt 1000) "report PDF is unexpectedly small"

$result = [ordered]@{
    status = "PASS"
    scenario_id = $scenario.scenario_id
    recommendation_count = $recommendations.Count
    enterprise_id = $first.enterprise_id
    candidate_id = $candidate.id
    exposure_count = $exposure.created
    crm_event_id = $crmResponse.data.id
    follow_up_task_id = $task.id
    follow_up_final_status = $done.data.status
    contact_funnel_count = $contactStage.count
    pdf_bytes = $pdfResponse.RawContentLength
}
$result | ConvertTo-Json -Depth 5
