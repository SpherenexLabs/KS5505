<#
Publishes the dev server on a real HTTPS address through Cloudflare.

Why: a browser hands out GPS only on a secure origin, and a certificate made on
this machine is not trusted by the patient's phone, so the phone shows "Your
connection is not private" and never asks for location. A Cloudflare quick
tunnel hands out a genuine certificate for a trycloudflare.com name, which
every phone already trusts. No warning, and it works on mobile data too.

    powershell -ExecutionPolicy Bypass -File scripts\start-tunnel.ps1

Leave this window open. The address changes every run, so the script writes the
current one into backend\data\public_url.json and the dashboard picks it up:
the Tracking panel then shows the public link instead of the LAN one.

WARNING: while this runs, anyone who has the address can reach the app from the
internet, including the sign-in page. The tracking token is long and random, so
the link is hard to guess, but do not post these addresses anywhere. Close this
window to take it all offline again.

Press Ctrl+C to stop.
#>

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$publicUrlFile = Join-Path $projectRoot "backend\data\public_url.json"
$devPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5173" }

# ---------------------------------------------------------------- cloudflared
$cloudflared = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cloudflared) {
    $known = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    if (Test-Path -LiteralPath $known) {
        $cloudflared = $known
    }
    else {
        throw "cloudflared was not found. Install it with: winget install --id Cloudflare.cloudflared"
    }
}

# ---------------------------------------------------------------- dev server
$devServer = Get-NetTCPConnection -LocalPort $devPort -State Listen -ErrorAction SilentlyContinue
if (-not $devServer) {
    throw "Nothing is listening on port $devPort. Run 'npm run dev' first, then start this."
}

# The dev server uses the certificate from make-cert.ps1, which Cloudflare has
# no reason to trust. The hop is loopback only, so skip that check.
$certPath = Join-Path $projectRoot "certs\dev-cert.pem"
if (Test-Path -LiteralPath $certPath) {
    $target = "https://localhost:$devPort"
    $extraArgs = @("--no-tls-verify")
}
else {
    $target = "http://localhost:$devPort"
    $extraArgs = @()
}

Write-Host "Publishing $target through Cloudflare..."
Write-Host "Leave this window open. Press Ctrl+C to take it offline."
Write-Host ""

function Save-PublicUrl($url) {
    $record = [ordered]@{
        url       = $url
        target    = $target
        updatedAt = (Get-Date).ToString("s")
    }
    # WriteAllText with a BOM-less encoder, not Out-File -Encoding utf8:
    # Windows PowerShell writes a byte order mark that json.load rejects.
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($publicUrlFile, ($record | ConvertTo-Json), $encoding)
}

# Clear a stale address so the dashboard falls back to the LAN link if this
# run never reaches Cloudflare.
Save-PublicUrl ""

# cloudflared logs to stderr. Piping that through 2>&1 in Windows PowerShell
# wraps every line in an error record, which $ErrorActionPreference = "Stop"
# turns into a fatal error on the first log line. Redirecting to files and
# following them keeps the lines as plain text.
$outFile = Join-Path $env:TEMP "carebot-tunnel-out.log"
$errFile = Join-Path $env:TEMP "carebot-tunnel-err.log"
Remove-Item -LiteralPath $outFile, $errFile -Force -ErrorAction SilentlyContinue
New-Item -ItemType File -Path $outFile, $errFile -Force | Out-Null

$arguments = @("tunnel", "--url", $target) + $extraArgs
$process = Start-Process -FilePath $cloudflared -ArgumentList $arguments `
    -NoNewWindow -PassThru -RedirectStandardOutput $outFile -RedirectStandardError $errFile

$announced = $false
$seen = 0
try {
    while (-not $process.HasExited -or -not $announced) {
        Start-Sleep -Milliseconds 400

        $lines = @()
        foreach ($file in @($errFile, $outFile)) {
            if (Test-Path -LiteralPath $file) {
                $lines += Get-Content -LiteralPath $file -ErrorAction SilentlyContinue
            }
        }

        if ($lines.Count -gt $seen) {
            foreach ($line in $lines[$seen..($lines.Count - 1)]) {
                Write-Host $line

                if (-not $announced -and $line -match "https://[a-z0-9-]+\.trycloudflare\.com") {
                    $announced = $true
                    $publicUrl = $matches[0]
                    Save-PublicUrl $publicUrl

                    Write-Host ""
                    Write-Host ("=" * 66)
                    Write-Host "  Public address is live:"
                    Write-Host "  $publicUrl"
                    Write-Host ""
                    Write-Host "  Open the Tracking panel on the dashboard and share"
                    Write-Host "  the link it now shows. It opens on any phone, on any"
                    Write-Host "  network, with no certificate warning."
                    Write-Host ""
                    Write-Host "  Anyone with this address can reach the app. Keep it"
                    Write-Host "  private, and close this window to take it offline."
                    Write-Host ("=" * 66)
                    Write-Host ""
                }
            }
            $seen = $lines.Count
        }

        if ($process.HasExited -and -not $announced) {
            throw "cloudflared stopped before it produced an address. See $errFile"
        }
    }

    $process.WaitForExit()
}
finally {
    Save-PublicUrl ""
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host ""
    Write-Host "Tunnel closed. The dashboard is back to the local address."
}
