# ============================================================
# SkillProof — Git Setup Script
# Chạy script này SAU KHI cài Git: https://git-scm.com/download/win
#
# Cách dùng (PowerShell):
#   Set-Location D:\SkillProof_New
#   .\git_setup.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SkillProof — Git Initialization" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $ProjectDir

# ── Bước 1: Kiểm tra Git ─────────────────────────────────────────────────────
Write-Host "[1/6] Kiểm tra Git..." -ForegroundColor Yellow
try {
    $gitVersion = git --version
    Write-Host "  ✓ $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Git chưa được cài đặt." -ForegroundColor Red
    Write-Host "    Tải tại: https://git-scm.com/download/win" -ForegroundColor White
    exit 1
}

# ── Bước 2: Kiểm tra/khởi tạo repo ──────────────────────────────────────────
Write-Host ""
Write-Host "[2/6] Khởi tạo Git repository..." -ForegroundColor Yellow
if (Test-Path ".git") {
    Write-Host "  ℹ  Repository đã tồn tại, bỏ qua git init." -ForegroundColor DarkYellow
} else {
    git init
    Write-Host "  ✓ git init OK" -ForegroundColor Green
}

# ── Bước 3: Cấu hình user (nếu chưa có) ──────────────────────────────────────
Write-Host ""
Write-Host "[3/6] Cấu hình Git user..." -ForegroundColor Yellow
$userName  = git config user.name  2>$null
$userEmail = git config user.email 2>$null

if (-not $userName) {
    $userName = Read-Host "  Nhập tên của bạn (Git user.name)"
    git config user.name $userName
}
if (-not $userEmail) {
    $userEmail = Read-Host "  Nhập email của bạn (Git user.email)"
    git config user.email $userEmail
}
Write-Host "  ✓ user.name  = $userName" -ForegroundColor Green
Write-Host "  ✓ user.email = $userEmail" -ForegroundColor Green

# ── Bước 4: Đặt branch mặc định là main ──────────────────────────────────────
Write-Host ""
Write-Host "[4/6] Đặt branch mặc định: main..." -ForegroundColor Yellow
git checkout -b main 2>$null
if ($LASTEXITCODE -ne 0) {
    git branch -M main
}
Write-Host "  ✓ Branch: main" -ForegroundColor Green

# ── Bước 5: Stage tất cả file ────────────────────────────────────────────────
Write-Host ""
Write-Host "[5/6] Stage files..." -ForegroundColor Yellow
git add .
$staged = git diff --cached --name-only
Write-Host "  ✓ Staged $($staged.Count) file(s):" -ForegroundColor Green
$staged | ForEach-Object { Write-Host "    + $_" -ForegroundColor DarkGray }

# ── Kiểm tra không có file nhạy cảm ──────────────────────────────────────────
$sensitive = git diff --cached --name-only | Where-Object {
    $_ -match "\.db$|\.env|secrets|\.venv|password"
}
if ($sensitive) {
    Write-Host ""
    Write-Host "  ⚠  CẢNH BÁO: Phát hiện file nhạy cảm đã được stage!" -ForegroundColor Red
    $sensitive | ForEach-Object { Write-Host "    ! $_" -ForegroundColor Red }
    Write-Host "  Kiểm tra lại .gitignore trước khi commit." -ForegroundColor Red
    exit 2
}
Write-Host "  ✓ Không phát hiện file nhạy cảm." -ForegroundColor Green

# ── Bước 6: Tạo commit đầu tiên ──────────────────────────────────────────────
Write-Host ""
Write-Host "[6/6] Tạo commit đầu tiên..." -ForegroundColor Yellow
git commit -m "Initial SkillProof desktop application"
Write-Host "  ✓ Commit thành công!" -ForegroundColor Green

# ── Tóm tắt ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✅ Git đã khởi tạo thành công!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Trạng thái hiện tại:" -ForegroundColor White
git log --oneline -5
Write-Host ""
Write-Host "Khi có GitHub repository URL, chạy:" -ForegroundColor White
Write-Host '  git remote add origin <GITHUB_URL>' -ForegroundColor Cyan
Write-Host '  git push -u origin main' -ForegroundColor Cyan
Write-Host ""
