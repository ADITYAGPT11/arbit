<#
.SYNOPSIS
    Starts the ArbitPRO backend and frontend servers.
.DESCRIPTION
    Kills any lingering processes on ports 8000 and 3000, then starts:
    - Backend (FastAPI) on http://localhost:8000
    - Frontend (React)   on http://localhost:3000
    Each opens its own console window so you can see live logs.
.EXAMPLE
    .\scripts\start.ps1
#>

$RootDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$BackendPort = 8000
$FrontendPort = 3000

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  ArbitPRO - Starting Servers"                   -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# --- Step 1: Kill old processes ---
Write-Host "> Killing old processes..." -ForegroundColor Yellow

# Kill anything on backend port
$oldBackend = netstat -ano | Select-String "LISTENING" | Select-String ":$BackendPort "
if ($oldBackend) {
    $pidToKill = ($oldBackend -split '\s+')[-1]
    if ($pidToKill -and $pidToKill -ne "0") {
        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
        Write-Host "  Killed backend PID $pidToKill" -ForegroundColor Gray
    }
}

# Kill anything on frontend port
$oldFrontend = netstat -ano | Select-String "LISTENING" | Select-String ":$FrontendPort "
if ($oldFrontend) {
    $pidToKill = ($oldFrontend -split '\s+')[-1]
    if ($pidToKill -and $pidToKill -ne "0") {
        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
        Write-Host "  Killed frontend PID $pidToKill" -ForegroundColor Gray
    }
}

Start-Sleep -Seconds 1
Write-Host "  Done" -ForegroundColor Green
Write-Host ""

# --- Step 2: Check prerequisites ---
Write-Host "> Checking prerequisites..." -ForegroundColor Yellow

# Python
$pythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "  [ERROR] Virtual environment not found at $pythonExe" -ForegroundColor Red
    Write-Host "  Run: cd backend && py -3.12 -m venv .venv && .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}
Write-Host "  Python: OK ($pythonExe)" -ForegroundColor Green

# Backend deps
$uvicornCheck = & $pythonExe -c "import uvicorn; print('OK')" 2>$null
if ($uvicornCheck -ne "OK") {
    Write-Host "  [ERROR] Backend dependencies not installed." -ForegroundColor Red
    Write-Host "  Run: cd backend && .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}
Write-Host "  Backend deps: OK" -ForegroundColor Green

# Frontend
$nodeModules = Join-Path $FrontendDir "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "  [WARN] Frontend dependencies not installed. Installing now..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    npm install --legacy-peer-deps
    Pop-Location
    if (-not (Test-Path $nodeModules)) {
        Write-Host "  [ERROR] npm install failed" -ForegroundColor Red
        exit 1
    }
}
Write-Host "  Frontend deps: OK" -ForegroundColor Green

# .env files
$backendEnv = Join-Path $BackendDir ".env"
$frontendEnv = Join-Path $FrontendDir ".env"
if (-not (Test-Path $backendEnv)) {
    Write-Host "  [WARN] backend/.env missing - creating default..."
    @"
MONGO_URL=mongodb://localhost:27017
DB_NAME=arbitpro
ANGEL_API_KEY=
ANGEL_CLIENT_ID=
ANGEL_MPIN=
ANGEL_TOTP_SECRET=
TELEGRAM_BOT_TOKEN=
"@ | Out-File -FilePath $backendEnv -Encoding utf8
}
if (-not (Test-Path $frontendEnv)) {
    Write-Host "  [WARN] frontend/.env missing - creating default..."
    @"
REACT_APP_BACKEND_URL=http://localhost:8000
"@ | Out-File -FilePath $frontendEnv -Encoding utf8
}
Write-Host "  .env files: OK" -ForegroundColor Green

# MongoDB
Write-Host "  Checking MongoDB..." -ForegroundColor Yellow
try {
    $mongoCheck = New-Object System.Net.Sockets.TcpClient("localhost", 27017)
    $mongoCheck.Close()
    Write-Host "  MongoDB: OK (localhost:27017)" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] MongoDB not reachable on localhost:27017" -ForegroundColor Red
    Write-Host "  Start MongoDB first, or update MONGO_URL in backend/.env" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# --- Step 3: Start Backend ---
Write-Host "> Starting Backend (port $BackendPort)..." -ForegroundColor Yellow

$backendLog = Join-Path $RootDir "backend.log"
$backendCmd = "`"$pythonExe`" -m uvicorn server:app --reload --host 0.0.0.0 --port $BackendPort > `"$backendLog`" 2>&1"

# Start backend in a new window
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $backendCmd `
    -WorkingDirectory $BackendDir `
    -WindowStyle Normal

Write-Host "  PID: (see backend.log)" -ForegroundColor Gray

# Wait for backend to be healthy (up to 30s)
Write-Host "  Waiting for health check..." -ForegroundColor Gray
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$BackendPort/api/health" -UseBasicParsing -TimeoutSec 2 2>$null
        if ($response.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    } catch {}
}
if ($healthy) {
    Write-Host "  Backend: ++ Healthy" -ForegroundColor Green
} else {
    Write-Host "  Backend: !! Health check failed - check backend.log for errors" -ForegroundColor Red
    Write-Host "  (The server may still be starting, try curling http://localhost:$BackendPort/api/health)" -ForegroundColor Yellow
}
Write-Host ""

# --- Step 4: Start Frontend ---
Write-Host "> Starting Frontend (port $FrontendPort)..." -ForegroundColor Yellow

$frontendLog = Join-Path $RootDir "frontend.log"
$frontendCmd = "npm start > `"$frontendLog`" 2>&1"

# Start frontend in a new window
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $frontendCmd `
    -WorkingDirectory $FrontendDir `
    -WindowStyle Normal

Write-Host "  PID: (see frontend.log)" -ForegroundColor Gray
Write-Host "  The frontend takes 30-60s to compile the first time." -ForegroundColor Gray
Write-Host ""

# --- Step 5: Summary ---
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Servers starting!"                               -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend  -> http://localhost:$BackendPort" -ForegroundColor White
Write-Host "  API Docs -> http://localhost:$BackendPort/docs" -ForegroundColor White
Write-Host "  Frontend -> http://localhost:$FrontendPort" -ForegroundColor White
Write-Host ""
Write-Host "  Logs:" -ForegroundColor White
Write-Host "    backend.log  -> Get-Content backend.log -Wait" -ForegroundColor Gray
Write-Host "    frontend.log -> Get-Content frontend.log -Wait" -ForegroundColor Gray
Write-Host ""
Write-Host "  To stop: .\scripts\stop.ps1" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Cyan
