# MVP Dev Startup Script
# Prerequisites: PostgreSQL running (pgAdmin4), Python venv activated, pip install done

Write-Host "=== ClickBook MVP Dev Startup ===" -ForegroundColor Cyan

# 1. Create the database if it doesn't exist
Write-Host "`n[1/3] Ensuring 'sitecraft' database exists..." -ForegroundColor Yellow
$env:PGPASSWORD = "postgres"
psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'sitecraft'" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Could not connect to PostgreSQL. Make sure it's running!" -ForegroundColor Red
    Write-Host "  Open pgAdmin4 and verify the server is started." -ForegroundColor Red
    exit 1
}
$exists = psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'sitecraft'"
if ($exists.Trim() -ne "1") {
    Write-Host "  Creating database 'sitecraft'..." -ForegroundColor Yellow
    psql -U postgres -c "CREATE DATABASE sitecraft"
} else {
    Write-Host "  Database 'sitecraft' already exists." -ForegroundColor Green
}

# 2. Run migrations
Write-Host "[2/3] Running database migrations..." -ForegroundColor Yellow
python -m flask db upgrade

# 3. Start Flask
Write-Host "[3/3] Starting Flask dev server on http://localhost:5000" -ForegroundColor Green
python run.py
