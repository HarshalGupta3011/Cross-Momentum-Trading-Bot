# ============================================================
#  Zerodha Momentum Bot — Setup Script
#  Run this after extracting zerodha_momentum_bot.zip
#  Right-click this file → "Run with PowerShell"
# ============================================================

$ErrorActionPreference = "Stop"
$BotDir = "$PSScriptRoot\zerodha_momentum_bot"

function Write-Header {
    Clear-Host
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "   Zerodha Momentum Bot — Setup" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step($n, $msg) {
    Write-Host "[$n] $msg" -ForegroundColor Yellow
}

function Write-OK($msg) {
    Write-Host "  OK  $msg" -ForegroundColor Green
}

function Write-Fail($msg) {
    Write-Host "  FAIL  $msg" -ForegroundColor Red
}

function Pause-AndExit {
    Write-Host ""
    Write-Host "Press any key to exit..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit
}

# ── Check Python ──────────────────────────────────────────────
Write-Header
Write-Step 1 "Checking Python installation..."

try {
    $pyver = python --version 2>&1
    Write-OK "Found: $pyver"
} catch {
    Write-Fail "Python not found."
    Write-Host ""
    Write-Host "  Please install Python from https://www.python.org/downloads/" -ForegroundColor White
    Write-Host "  Make sure to check 'Add Python to PATH' during install." -ForegroundColor White
    Pause-AndExit
}

# ── Check pip ─────────────────────────────────────────────────
Write-Step 2 "Checking pip..."
try {
    $pipver = pip --version 2>&1
    Write-OK "Found: $pipver"
} catch {
    Write-Fail "pip not found. Reinstall Python and check 'Add to PATH'."
    Pause-AndExit
}

# ── Install dependencies ──────────────────────────────────────
Write-Step 3 "Installing dependencies..."
Write-Host "  (this may take a minute)" -ForegroundColor Gray

$packages = @("kiteconnect", "yfinance", "pandas", "numpy", "matplotlib", "schedule", "requests", "pyotp", "selenium", "webdriver-manager")

foreach ($pkg in $packages) {
    Write-Host "  Installing $pkg..." -ForegroundColor Gray -NoNewline
    try {
        pip install $pkg -q 2>&1 | Out-Null
        Write-Host " done" -ForegroundColor Green
    } catch {
        Write-Host " failed" -ForegroundColor Red
    }
}
Write-OK "All packages installed"

# ── Locate bot folder ─────────────────────────────────────────
Write-Step 4 "Locating bot files..."

if (-Not (Test-Path $BotDir)) {
    # Try current directory directly
    $BotDir = $PSScriptRoot
}

if (-Not (Test-Path "$BotDir\bot.py")) {
    Write-Fail "Could not find bot.py. Make sure this script is in the same folder as the zip or extracted folder."
    Pause-AndExit
}
Write-OK "Bot files found at: $BotDir"

# ── Edit config ───────────────────────────────────────────────
Write-Step 5 "Opening config.py for editing..."
Write-Host ""
Write-Host "  Fill in the following in config.py:" -ForegroundColor White
Write-Host "    KITE_API_KEY    = your API key" -ForegroundColor Gray
Write-Host "    KITE_API_SECRET = your API secret" -ForegroundColor Gray
Write-Host "    TOTAL_CAPITAL   = your capital in Rs" -ForegroundColor Gray
Write-Host "    TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID (optional)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Save and close Notepad when done." -ForegroundColor Yellow
Write-Host ""
Start-Process notepad "$BotDir\config.py" -Wait
Write-OK "config.py saved"

# ── Create logs folder ────────────────────────────────────────
Write-Step 6 "Creating logs folder..."
New-Item -ItemType Directory -Force -Path "$BotDir\logs" | Out-Null
Write-OK "logs\ folder ready"

# ── Ask what to do next ───────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Setup complete! What would you like to do?" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  [1] Run DRY RUN now (test without placing real orders)" -ForegroundColor White
Write-Host "  [2] Run LIVE bot (starts scheduler, rebalances monthly)" -ForegroundColor White
Write-Host "  [3] Exit" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Enter choice (1/2/3)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "Starting dry run..." -ForegroundColor Yellow
        Write-Host "(You will be asked to log in to Zerodha)" -ForegroundColor Gray
        Write-Host ""
        Set-Location $BotDir
        python bot.py --dry-run --now
        Write-Host ""
        Write-Host "Dry run complete. Check logs\bot.log for details." -ForegroundColor Green
    }
    "2" {
        Write-Host ""
        Write-Host "Starting live bot..." -ForegroundColor Yellow
        Write-Host "(You will be asked to log in to Zerodha)" -ForegroundColor Gray
        Write-Host "The bot will rebalance on the last trading day of each month at 9:30 AM." -ForegroundColor Gray
        Write-Host ""
        Write-Host "To stop the bot, close this window or press Ctrl+C" -ForegroundColor Red
        Write-Host ""
        Set-Location $BotDir
        python bot.py
    }
    "3" {
        Write-Host "Exiting." -ForegroundColor Gray
    }
    default {
        Write-Host "Invalid choice. Exiting." -ForegroundColor Red
    }
}

Pause-AndExit
