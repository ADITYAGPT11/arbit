<#
.SYNOPSIS
    Stops the ArbitPRO backend and frontend servers gracefully.
.DESCRIPTION
    Finds and kills processes on ports 8000 (backend) and 3000 (frontend).
    Also kills any lingering python/uvicorn and node/react-scripts processes.
.EXAMPLE
    .\scripts\stop.ps1
#>

Write-Host "> Stopping ArbitPRO servers..." -ForegroundColor Yellow

$stopped = $false

# Kill processes on backend port 8000
$onPort8000 = netstat -ano | Select-String "LISTENING" | Select-String ":8000 "
if ($onPort8000) {
    $targetPid = ($onPort8000 -split '\s+')[-1]
    if ($targetPid -and $targetPid -ne "0") {
        Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
        Write-Host "  Backend (PID $targetPid): stopped" -ForegroundColor Green
        $stopped = $true
    }
}

# Kill processes on frontend port 3000
$onPort3000 = netstat -ano | Select-String "LISTENING" | Select-String ":3000 "
if ($onPort3000) {
    $targetPid = ($onPort3000 -split '\s+')[-1]
    if ($targetPid -and $targetPid -ne "0") {
        Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
        Write-Host "  Frontend (PID $targetPid): stopped" -ForegroundColor Green
        $stopped = $true
    }
}

if (-not $stopped) {
    Write-Host "  No running servers found." -ForegroundColor Gray
}

Write-Host "  Done." -ForegroundColor Green
