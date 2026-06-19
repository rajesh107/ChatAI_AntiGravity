# package.ps1 — Build a deployable tar.gz for ChatAI AntiGravity
# Usage: .\package.ps1
# Output: chatbot_<timestamp>.tar.gz in the project root

$PROJECT_NAME = "chatbot"
$VERSION      = (Get-Date -Format "yyyyMMdd_HHmmss")
$ARCHIVE_NAME = "${PROJECT_NAME}_${VERSION}.tar.gz"
$SCRIPT_DIR   = Split-Path -Parent $MyInvocation.MyCommand.Path

# Files and folders to include
$INCLUDE = @(
    "agent.py",
    "auth.py",
    "etl_cleaner.py",
    "flush_redis.py",
    "jwt_tester.py",
    "main.py",
    "onboard_client.py",
    "setup_admin.py",
    "system_msg.py",
    "upload_to_mysql.py",
    "requirements.txt",
    "API_DOCUMENTATION.md",
    "openapi.json",
    "TECHNICAL_REPORT.md",
    "CLAUDE_INTEGRATION.md",
    "CLAUDE_API_CONNECTION.md",
    "CONNECTORS_DOCUMENTATION.md",
    "PROMPT_DOCUMENTATION.md",
    "chatbot.service",
    "deploy.sh",
    "deploy_tarball.sh",
    "deploy_v2.sh",
    "schemas",
    "scripts"
)

# Temp staging folder
$STAGE_DIR = Join-Path $env:TEMP "${PROJECT_NAME}_stage"
$APP_DIR   = Join-Path $STAGE_DIR $PROJECT_NAME

Write-Host "========================================"
Write-Host " ChatAI AntiGravity -- Package Builder"
Write-Host " Output : $ARCHIVE_NAME"
Write-Host "========================================"

# Clean and create staging area
if (Test-Path $STAGE_DIR) { Remove-Item $STAGE_DIR -Recurse -Force }
New-Item -ItemType Directory -Path $APP_DIR | Out-Null

# Copy included files/folders
foreach ($item in $INCLUDE) {
    $src = Join-Path $SCRIPT_DIR $item
    $dst = Join-Path $APP_DIR $item
    if (Test-Path $src) {
        if ((Get-Item $src).PSIsContainer) {
            Copy-Item $src $dst -Recurse
        } else {
            Copy-Item $src $dst
        }
        Write-Host "  [+] $item"
    } else {
        Write-Host "  [!] MISSING: $item (skipped)"
    }
}

# Generate .env.example from current .env (strip values, keep keys)
$ENV_FILE = Join-Path $SCRIPT_DIR ".env"
if (Test-Path $ENV_FILE) {
    $example = Get-Content $ENV_FILE | ForEach-Object {
        $line = $_
        if ($line -match '^\s*#' -or $line -match '^\s*$') {
            $line
        } else {
            $eqPos = $line.IndexOf('=')
            if ($eqPos -ge 0) {
                $line.Substring(0, $eqPos + 1)
            } else {
                $line
            }
        }
    }
    $example | Set-Content (Join-Path $APP_DIR ".env.example") -Encoding UTF8
    Write-Host "  [+] .env.example (generated from .env)"
}

# Build tar.gz — tar from INSIDE the project folder so files extract directly
# (no top-level 'chatbot/' subfolder), compatible with:
#   tar -xzf ~/chatbot-v2.tar.gz -C /home/ubuntu/chatbot-v2
$OUTPUT = Join-Path $SCRIPT_DIR $ARCHIVE_NAME
Push-Location $APP_DIR
tar -czf $OUTPUT .
Pop-Location

# Cleanup staging
Remove-Item $STAGE_DIR -Recurse -Force

$SIZE_KB = [math]::Round((Get-Item $OUTPUT).Length / 1KB, 1)
Write-Host ""
Write-Host "========================================"
Write-Host " Done: $ARCHIVE_NAME ($SIZE_KB KB)"
Write-Host ""
Write-Host " Upload to EC2:"
Write-Host "   scp $ARCHIVE_NAME ubuntu@18.191.191.139:~/"
Write-Host ""
Write-Host " Deploy on EC2:"
Write-Host "   bash deploy_tarball.sh $ARCHIVE_NAME"
Write-Host "========================================"
