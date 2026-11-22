param([string]$PatchJson)

$ErrorActionPreference = "Stop"
$BASE = "G:\Mega\git\drmAIcu"
$PATCH_DIR = Join-Path $BASE "patch"

if (-not (Test-Path $PATCH_DIR)) {
    New-Item -ItemType Directory -Path $PATCH_DIR -Force | Out-Null
}

# 1. Парсим JSON (валидация синтаксиса)
try {
    $patch = $PatchJson | ConvertFrom-Json
}
catch {
    Write-Host "FAIL: JSON невалиден: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# 2. Проверяем структуру
if (-not $patch.operations -or $patch.operations.Count -eq 0) {
    Write-Host "FAIL: operations пустой или отсутствует" -ForegroundColor Red
    exit 1
}

$pid_ = $patch.patch_id
Write-Host "=== Патч $pid_ : $($patch.operations.Count) операций ===" -ForegroundColor Cyan

# 3. Сохраняем в patch/ (UTF-8 без BOM)
$outPath = Join-Path $PATCH_DIR "$pid_.json"
[System.IO.File]::WriteAllText($outPath, $PatchJson, (New-Object System.Text.UTF8Encoding $false))
Write-Host "OK: сохранён в $outPath" -ForegroundColor Green

# 4. Применяем через API (атомарно, с бэкапом)
$bytes = [System.Text.Encoding]::UTF8.GetBytes($PatchJson)
try {
    $resp = Invoke-RestMethod `
        -Uri "http://127.0.0.1:8080/api/patches/apply" `
        -Method Post `
        -Body $bytes `
        -ContentType "application/json; charset=utf-8"
}
catch {
    Write-Host "FAIL: запрос к API упал: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# 5. Показываем результат
$resp | ConvertTo-Json -Depth 10

if ($resp.success) {
    Write-Host "DONE: патч $pid_ применён атомарно" -ForegroundColor Green
} else {
    Write-Host "REJECTED: $($resp.error)" -ForegroundColor Yellow
    if ($resp.rolled_back) {
        Write-Host "Откат выполнен, файлы целы" -ForegroundColor Yellow
    }
    exit 1
}