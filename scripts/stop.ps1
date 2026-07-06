<#
.SYNOPSIS
    Stops ArbitPRO servers by killing processes on ports 8000 and 3000.
#>

Write-Host "Stopping ArbitPRO..." -ForegroundColor Yellow

@(8000, 3000) | ForEach-Object {
    $p = netstat -ano | Select-String ":$_ " | Select-String "LISTENING"
    if ($p) {
        $procId = ($p -split '\s+')[-1]
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Write-Host "  Port $_ (PID $procId): stopped" -ForegroundColor Green
    } else {
        Write-Host ("  Port " + $_ + ": nothing running") -ForegroundColor Gray
    }
}

Write-Host "Done." -ForegroundColor Green
