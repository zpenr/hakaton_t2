Set-Location $PSScriptRoot
# Порт 8000 часто занят WSL (wslrelay) — используем 8765
$port = if ($env:APP_PORT) { $env:APP_PORT } else { "8765" }
Write-Host "График смен: http://127.0.0.1:$port/ (только http, не https)" -ForegroundColor Green
uvicorn app.main:app --host 127.0.0.1 --port $port --reload
