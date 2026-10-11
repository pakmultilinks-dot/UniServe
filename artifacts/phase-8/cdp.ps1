# Phase 8A — minimal raw-CDP driver (PowerShell + .NET ClientWebSocket).
# No new dependencies: talks directly to a Chrome started with
# --remote-debugging-port=9333 and a throwaway profile.
# Usage:
#   .\cdp.ps1 eval   "<js expression>"        # returns JSON-encoded result
#   .\cdp.ps1 nav    "<url>"                  # navigate + wait for load
#   .\cdp.ps1 shot   "<out.png>" [selector]   # screenshot (viewport, or element)
#   .\cdp.ps1 click  "<selector>"             # left click at element center
#   .\cdp.ps1 type   "<selector>" "<text>"    # focus + type text
#   .\cdp.ps1 key    "<keys>"                 # e.g. "Enter"
#   .\cdp.ps1 wait   "<ms>"                   # sleep inside the page session
param(
    [Parameter(Mandatory = $true)][string]$Action,
    [Parameter(Mandatory = $false)][string]$Arg1,
    [Parameter(Mandatory = $false)][string]$Arg2,
    [int]$TimeoutMs = 25000
)

$ErrorActionPreference = 'Stop'
$CDP = 'http://127.0.0.1:9333'

function Get-PageWsUrl {
    $targets = Invoke-RestMethod "$CDP/json" -TimeoutSec 5
    $page = $targets | Where-Object { $_.type -eq 'page' -and $_.url -match 'localhost:8090|localhost:3010|127.0.0.1:8090' } | Select-Object -First 1
    if (-not $page) { $page = $targets | Where-Object { $_.type -eq 'page' } | Select-Object -First 1 }
    if (-not $page) { throw 'No CDP page target found' }
    return $page.webSocketDebuggerUrl
}

function Invoke-CdpSession {
    param([scriptblock]$Body)
    $wsUrl = Get-PageWsUrl
    $ws = New-Object System.Net.WebSockets.ClientWebSocket
    $ws.Options.KeepAliveInterval = [TimeSpan]::FromSeconds(30)
    $ct = [Threading.CancellationToken]::None
    $ws.ConnectAsync([Uri]$wsUrl, $ct).GetAwaiter().GetResult()

    $id = 0
    $pending = @{}
    try {
        $send = {
            param($msg)
            $bytes = [Text.Encoding]::UTF8.GetBytes(($msg | ConvertTo-Json -Depth 8 -Compress))
            $seg = New-Object ArraySegment[byte] -ArgumentList @(,$bytes)
            $ws.SendAsync($seg, [Net.WebSockets.WebSocketMessageType]::Text, $true, $ct).GetAwaiter().GetResult()
        }
        $recv = {
            $buf = New-Object byte[] 1048576
            $ms = New-Object IO.MemoryStream
            do {
                $ms.SetLength(0)
                $done = $false
                do {
                    $seg = New-Object ArraySegment[byte] -ArgumentList @(,$buf)
                    $res = $ws.ReceiveAsync($seg, $ct).GetAwaiter().GetResult()
                    if ($res.MessageType -eq [Net.WebSockets.WebSocketMessageType]::Close) { return $null }
                    $ms.Write($buf, 0, $res.Count)
                    if ($res.EndOfMessage) { $done = $true }
                } while (-not $done)
                $txt = [Text.Encoding]::UTF8.GetString($ms.ToArray())
                $obj = $txt | ConvertFrom-Json
                if ($obj.id -and $pending.ContainsKey([int]$obj.id)) { return $obj }
            } while ($true)
        }
        $cmd = {
            param($method, $params)
            $script:id++
            $m = @{ id = $script:id; method = $method }
            if ($params) { $m.params = $params }
            $pending[[int]$script:id] = $true
            & $send $m
            $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMs)
            while ([DateTime]::UtcNow -lt $deadline) {
                $msg = & $recv
                if ($null -eq $msg) { throw 'CDP socket closed' }
                if ($msg.id -eq $script:id) { return $msg }
            }
            throw "CDP timeout waiting for $method"
        }
        & $Body $cmd
    }
    finally {
        try { $ws.CloseAsync([Net.WebSockets.WebSocketMessageType]::Close, [Net.WebSockets.WebSocketCloseStatus]::NormalClosure, $true, $ct).GetAwaiter().GetResult() } catch {}
        $ws.Dispose()
    }
}

switch ($Action) {
    'eval' {
        $r = Invoke-CdpSession {
            param($cmd)
            & $cmd 'Runtime.evaluate' @{ expression = $Arg1; returnByValue = $true; awaitPromise = $true }
        }
        if ($r.result.exceptionDetails) { Write-Error ($r.result.exceptionDetails | ConvertTo-Json -Depth 6); exit 1 }
        $v = $r.result.result.value
        if ($v -is [string]) { $v } else { $v | ConvertTo-Json -Depth 8 -Compress }
    }
    'nav' {
        $null = Invoke-CdpSession { param($cmd) & $cmd 'Page.enable' @{} ; & $cmd 'Page.navigate' @{ url = $Arg1 } }
        Start-Sleep -Milliseconds 2500
        "navigated: $Arg1"
    }
    'shot' {
        $out = $Arg1
        $res = Invoke-CdpSession {
            param($cmd)
            & $cmd 'Runtime.evaluate' @{ expression = "document.querySelector('$Arg2') ? (()=>{document.querySelector('$Arg2').scrollIntoView({block:'center'}); return 'ok'})() : 'missing'"; returnByValue = $true }
        }
        $null = Start-Sleep -Milliseconds 600
        $shot = Invoke-CdpSession {
            param($cmd)
            & $cmd 'Page.enable' @{}
            if ($Arg2) { & $cmd 'Emulation.setDeviceMetricsOverride' @{ width = 1280; height = 900; deviceScaleFactor = 1; mobile = $false } }
            & $cmd 'Page.captureScreenshot' @{ format = 'png' }
        }
        $b64 = $shot.result.data
        [IO.File]::WriteAllBytes($out, [Convert]::FromBase64String($b64))
        "saved: $out ($([Math]::Round($b64.Length * 0.75 / 1024)) KB)"
    }
    'click' {
        $r = Invoke-CdpSession {
            param($cmd)
            & $cmd 'Runtime.evaluate' @{ expression = "(()=>{const e=document.querySelector('$Arg1'); if(!e) return null; const r=e.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2,w:r.width,h:r.height};})()"; returnByValue = $true }
        }
        $box = $r.result.result.value
        if (-not $box) { Write-Error "selector not found: $Arg1"; exit 1 }
        $null = Invoke-CdpSession {
            param($cmd)
            & $cmd 'Input.dispatchMouseEvent' @{ type = 'mousePressed'; x = $box.x; y = $box.y; button = 'left'; clickCount = 1 }
            & $cmd 'Input.dispatchMouseEvent' @{ type = 'mouseReleased'; x = $box.x; y = $box.y; button = 'left'; clickCount = 1 }
        }
        "clicked: $Arg1 @ $([Math]::Round($box.x)),$([Math]::Round($box.y))"
    }
    'type' {
        $null = Invoke-CdpSession {
            param($cmd)
            & $cmd 'Runtime.evaluate' @{ expression = "(()=>{const e=document.querySelector('$Arg1'); if(!e) return 'missing'; e.focus(); return 'focused';})()"; returnByValue = $true }
            & $cmd 'Input.insertText' @{ text = $Arg2 }
        }
        "typed into: $Arg1"
    }
    'key' {
        $null = Invoke-CdpSession { param($cmd) & $cmd 'Input.dispatchKeyEvent' @{ type = 'keyDown'; key = $Arg1; code = $Arg1; windowsVirtualKeyCode = 13 } ; & $cmd 'Input.dispatchKeyEvent' @{ type = 'keyUp'; key = $Arg1; code = $Arg1; windowsVirtualKeyCode = 13 } }
        "key: $Arg1"
    }
    'wait' {
        Start-Sleep -Milliseconds ([int]$Arg1)
        "waited: $Arg1 ms"
    }
    default { Write-Error "unknown action: $Action"; exit 1 }
}
