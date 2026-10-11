# Phase 7 - isolated test API launcher.
# Runs a development API instance against the ISOLATED test database only.
# Never points at uniserve_prod. Reads credentials at runtime; prints none.
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\Lenovo\Documents\Code_PlayGround\UniServe'
Set-Location $repo

$kv = @{}
Get-Content (Join-Path $repo '.env.production') |
    Where-Object { $_ -match '^\s*[A-Za-z_][A-Za-z0-9_]*\s*=' } |
    ForEach-Object { $p = $_ -split '=', 2; $kv[$p[0].Trim()] = $p[1].Trim() }

$env:POSTGRES_USER     = $kv['POSTGRES_USER']
$env:POSTGRES_PASSWORD = $kv['POSTGRES_PASSWORD']
$env:POSTGRES_HOST     = '127.0.0.1'
$env:POSTGRES_PORT     = '5433'
$env:POSTGRES_DB       = 'uniserve_test_phase7'   # <- isolated; NOT uniserve_prod
$env:APP_ENV           = 'development'            # -> DevelopmentEmailProvider (OTP to log)
$env:APP_DEBUG         = 'false'
$env:APP_HOST          = '127.0.0.1'
$env:APP_PORT          = '8001'
$env:CORS_ORIGINS      = '["http://localhost:3000","http://localhost:8081","http://localhost:8082"]'

# Fresh, test-only signing key so no production token is ever accepted here.
$secret = ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'))
$env:APP_SECRET_KEY = $secret
$env:JWT_SECRET_KEY = $secret

Set-Location (Join-Path $repo 'apps\api')
$log = Join-Path $repo 'artifacts\phase-7\api_test.log'
& ..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 *> $log
