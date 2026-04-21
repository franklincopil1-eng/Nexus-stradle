# Atlas-X Bridge Controller for Windows PowerShell
# This script bridges your local MT5 terminal with the Cloud Dashboard.

$apiUrl = "https://ais-dev-udk65hnd4gccc7nd7xsj6h-688925601810.europe-west2.run.app"

Write-Host "--- Atlas-X Enterprise Bridge ---" -ForegroundColor Cyan
Write-Host "Target Dashboard: $apiUrl"

# 1. Check Python
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python is not installed. Please install Python from python.org" -ForegroundColor Red
    exit
}

# 2. Install Dependencies
Write-Host "📦 Installing/Updating dependencies..." -ForegroundColor Yellow
python -m pip install MetaTrader5 pandas requests python-dotenv --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install dependencies." -ForegroundColor Red
    exit
}

# 3. Inject Environment Variables for local run
$env:API_URL = $apiUrl
# Exness Credentials (User should fill these if they aren't already in MT5)
$env:EXNESS_LOGIN = ""  # Set via PowerShell: $env:EXNESS_LOGIN = "12345"
$env:EXNESS_PASSWORD = ""
$env:EXNESS_SERVER = ""

Write-Host "🚀 Launching Atlas-X Trading Engine..." -ForegroundColor Green
Write-Host "Keep this window open while trading." -ForegroundColor Gray

python main.py
