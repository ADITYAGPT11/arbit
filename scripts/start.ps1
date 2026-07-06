<#
.SYNOPSIS
    Starts ArbitPRO backend (port 8000) and frontend (port 3000).
#>

$RootDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"

Write-Host "Starting ArbitPRO..." -ForegroundColor Cyan
Write-Host ""

# Kill old processes on ports 8000 and 3000
Write-Host "> Cleaning up old processes..." -ForegroundColor Yellow
@(8000, 3000) | ForEach-Object {
    $p = netstat -ano | Select-String ":$_ " | Select-String "LISTENING"
    if ($p) {
        $procId = ($p -split '\s+')[-1]
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 1

# Start backend (new window)
Write-Host "> Starting Backend (localhost:8000)..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList "/K", ".venv\Scripts\activate && uvicorn server:app --reload --host 0.0.0.0 --port 8000" `
    -WorkingDirectory $BackendDir -WindowStyle Normal

# Start frontend (new window)
Write-Host "> Starting Frontend (localhost:3000)..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList "/K", "npm start" `
    -WorkingDirectory $FrontendDir -WindowStyle Normal

Write-Host ""
Write-Host "Done. Close the windows to stop, or run scripts\stop.ps1" -ForegroundColor Cyan
