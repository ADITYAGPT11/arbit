<#
.SYNOPSIS
    Stops ArbitPRO servers by killing processes on ports 8000 and 3000.
#>

Write-Host "Stopping ArbitPRO..." -ForegroundColor Yellow

@(8000, 3000) | ForEach-Object {
    $p = netstat -ano | Select-String ":$_ " | Select-String "LISTENING"
    if ($p) {
        $pid = ($p -split '\s+')[-1]
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Write-Host "  Port $_ (PID $pid): stopped" -ForegroundColor Green
    }
}

Write-Host "Done." -ForegroundColor Green
