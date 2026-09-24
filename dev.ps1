# Avvio "modalità sviluppo" — backend + frontend con hot reload attivi.
#
# Uso:
#   .\dev.ps1
#
# Apre due finestre PowerShell separate:
#   1. Backend uvicorn (RELOAD=1) su http://127.0.0.1:8000
#   2. Frontend Vite (HMR)        su http://localhost:5173
#
# Poi apre il browser su :5173 (Vite proxya /api → :8000).
# Chiudi le due finestre (o Ctrl+C in ciascuna) per fermare tutto.

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$FrontendDir = Join-Path $ProjectRoot "frontend"

# --- Prerequisiti ---------------------------------------------------------

if (-not (Test-Path $Python)) {
    Write-Host "ERRORE: .venv non trovato. Setup una tantum:" -ForegroundColor Red
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "ERRORE: frontend/node_modules mancante. Setup una tantum:" -ForegroundColor Red
    Write-Host "  cd frontend; npm install" -ForegroundColor Yellow
    exit 1
}

# --- Avvio backend --------------------------------------------------------

Write-Host "==> Avvio backend (hot reload) in nuova finestra..." -ForegroundColor Cyan
$backendCmd = "`$Host.UI.RawUI.WindowTitle = 'JobMatcher · Backend :8000'; `$env:RELOAD = '1'; & '$Python' run.py"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd `
    -WorkingDirectory $ProjectRoot

# --- Avvio frontend -------------------------------------------------------

Write-Host "==> Avvio frontend (HMR Vite) in nuova finestra..." -ForegroundColor Cyan
$frontendCmd = "`$Host.UI.RawUI.WindowTitle = 'JobMatcher · Frontend :5173'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd `
    -WorkingDirectory $FrontendDir

# --- Attendi che siano pronti --------------------------------------------

Write-Host "==> Attendo che entrambi siano pronti..." -ForegroundColor Cyan

$backendReady = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" `
            -Headers @{ "X-API-Token" = "local-dev-token-2026" } `
            -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop | Out-Null
        $backendReady = $true; break
    } catch { Start-Sleep -Seconds 1 }
}
if ($backendReady) {
    Write-Host "    Backend pronto." -ForegroundColor Green
} else {
    Write-Host "    Backend non pronto dopo 30s (controlla la sua finestra)." -ForegroundColor Yellow
}

$frontendReady = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        Invoke-WebRequest -Uri "http://localhost:5173/" `
            -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop | Out-Null
        $frontendReady = $true; break
    } catch { Start-Sleep -Seconds 1 }
}
if ($frontendReady) {
    Write-Host "    Frontend pronto." -ForegroundColor Green
} else {
    Write-Host "    Frontend non pronto dopo 30s (controlla la sua finestra)." -ForegroundColor Yellow
}

# --- Apri il browser ------------------------------------------------------

if ($frontendReady) {
    Write-Host "==> Apro il browser su http://localhost:5173" -ForegroundColor Cyan
    Start-Process "http://localhost:5173"
}

Write-Host ""
Write-Host "Modalità sviluppo attiva." -ForegroundColor Green
Write-Host "  Backend:  http://127.0.0.1:8000   (finestra: JobMatcher · Backend :8000)"
Write-Host "  Frontend: http://localhost:5173   (finestra: JobMatcher · Frontend :5173)"
Write-Host ""
Write-Host "Modifica un .py in app/    -> uvicorn ricarica automaticamente."
Write-Host "Modifica un .tsx/.css      -> Vite HMR aggiorna il browser in <1s."
Write-Host ""
Write-Host "Per fermare: chiudi le due finestre (o Ctrl+C in ciascuna)."
