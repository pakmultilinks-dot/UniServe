# Phase 7 - isolated auth flow. Consumes the dev-provider OTP from the log
# without ever printing it. Operates ONLY against 127.0.0.1:8001 (test DB).
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\Lenovo\Documents\Code_PlayGround\UniServe'
$api  = 'http://127.0.0.1:8001/api/v1'
$uid  = 'bcc0f8c4-6b0c-4014-a742-8af77f754a41'
$email = 'phase7.qa.132874@lgu.edu.pk'
$pw = 'Qa7mid' + '1328' + '@Zx'

function Post-Json($url, $payload, $token) {
    $h = @{ 'Content-Type' = 'application/json' }
    if ($token) { $h['Authorization'] = 'Bearer ' + $token }
    try {
        $r = Invoke-WebRequest -Uri $url -Method Post -Headers $h `
            -Body ($payload | ConvertTo-Json) -TimeoutSec 30 -UseBasicParsing
        return @{ code = [int]$r.StatusCode; body = $r.Content }
    } catch {
        $resp = $_.Exception.Response
        if ($resp) {
            $txt = $resp.Content.ReadAsStringAsync().GetAwaiter().GetResult()
            return @{ code = [int]$resp.StatusCode; body = $txt }
        }
        return @{ code = 0; body = $_.Exception.Message }
    }
}

# 1. Fresh OTP
$r1 = Post-Json "$api/auth/otp/resend" @{ user_id = $uid; purpose = 'email_verification' } $null
Write-Output ("RESEND_HTTP=" + $r1.code)

Start-Sleep -Seconds 2

# 2. Extract OTP from dev-provider log (never printed)
$log = Join-Path $repo 'artifacts\phase-7\api_test.log'
$line = Get-Content $log | Where-Object { $_ -match 'otp=[0-9]{6}' } | Select-Object -Last 1
if (-not $line) { Write-Output 'OTP_NOT_FOUND_IN_LOG'; exit 1 }
$otp = ([regex]'otp=(\d{6})').Match($line).Groups[1].Value
Write-Output ('OTP_EXTRACTED=yes len=' + $otp.Length)

# 3. Verify email
$r2 = Post-Json "$api/auth/otp/verify" @{ user_id = $uid; otp = $otp; purpose = 'email_verification' } $null
Write-Output ("VERIFY_HTTP=" + $r2.code + " body=" + $r2.body)

# 4. Login
$r3 = Post-Json "$api/auth/login" @{ university_email = $email; password = $pw } $null
Write-Output ("LOGIN_HTTP=" + $r3.code)
if ($r3.code -ne 200) { Write-Output ("LOGIN_BODY=" + $r3.body); exit 1 }

$tok = ($r3.body | ConvertFrom-Json).access_token
Set-Content -Path (Join-Path $repo 'artifacts\phase-7\token.txt') -Value $tok -NoNewline
Write-Output 'TOKEN_SAVED=yes (not printed)'

# 5. Confirm identity via /me
$hm = @{ 'Authorization' = 'Bearer ' + $tok }
try {
    $me = Invoke-WebRequest -Uri "$api/auth/me" -Headers $hm -TimeoutSec 20 -UseBasicParsing
    $j = $me.Content | ConvertFrom-Json
    Write-Output ("ME_HTTP=" + $me.StatusCode + " role=" + $j.role + " status=" + $j.status + " category=" + $j.category)
} catch {
    $resp = $_.Exception.Response
    if ($resp) {
        $txt = $resp.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        Write-Output ("ME_HTTP=" + [int]$resp.StatusCode + " body=" + $txt)
    } else { Write-Output ("ME_ERR=" + $_.Exception.Message) }
}
