$ErrorActionPreference = "Stop"

$body = @'
{
  "patch_id": "114",
  "version": "1.0",
  "type": "multi",
  "description": "vaccine: protect add_middleware from hot-reload RuntimeError",
  "author": "review",
  "created_at": "2026-11-21T07:00:00",
  "operations": [
    {
      "type": "search_and_replace",
      "target_file": "main.py",
      "find": "app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])",
      "replace": "try:\n    app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])\nexcept RuntimeError:\n    pass"
    }
  ]
}
'@

$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)

try {
    $resp = Invoke-RestMethod `
        -Uri "http://127.0.0.1:8080/api/patches/apply" `
        -Method Post `
        -Body $bytes `
        -ContentType "application/json; charset=utf-8"
    $resp | ConvertTo-Json -Depth 10
}
catch {
    Write-Host "FAIL on /api/patches/apply, trying /api/patches/apply-atomic..." -ForegroundColor Yellow
    $resp = Invoke-RestMethod `
        -Uri "http://127.0.0.1:8080/api/patches/apply-atomic" `
        -Method Post `
        -Body $bytes `
        -ContentType "application/json; charset=utf-8"
    $resp | ConvertTo-Json -Depth 10
}