<#
Sets up trusted HTTPS for the Vite dev server.

Why this exists: a browser hands out GPS only on a secure origin. localhost
counts as one, a plain http:// LAN address does not, so the patient's phone
never even sees the location prompt until the dev server speaks HTTPS.

A plain self-signed certificate makes Chrome show "Your connection is not
private" (NET::ERR_CERT_AUTHORITY_INVALID) because nothing vouches for it. So
this script does what mkcert does: it creates a small certificate authority
once, trusts that authority on this machine, and then signs a server
certificate with it. After that Chrome shows a normal padlock.

    powershell -ExecutionPolicy Bypass -File scripts\make-cert.ps1

The authority is trusted for the current user only, never machine wide, and it
is created here and never leaves this folder.

Re-run this whenever the Wi-Fi hands out a new IP address. The authority is
reused, so nothing has to be trusted again.

To undo the trust later:
    Get-ChildItem Cert:\CurrentUser\Root |
        Where-Object { $_.Subject -like "*CareBot*" } | Remove-Item
#>

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$certDir = Join-Path $projectRoot "certs"

$caKey = Join-Path $certDir "carebot-ca-key.pem"
$caCert = Join-Path $certDir "carebot-ca.pem"
$serverKey = Join-Path $certDir "dev-key.pem"
$serverCert = Join-Path $certDir "dev-cert.pem"
$phoneCopy = Join-Path $projectRoot "public\carebot-ca.crt"

# ---------------------------------------------------------------- openssl
$openssl = (Get-Command openssl -ErrorAction SilentlyContinue).Source
if (-not $openssl) {
    $gitOpenssl = "C:\Program Files\Git\mingw64\bin\openssl.exe"
    if (Test-Path -LiteralPath $gitOpenssl) {
        $openssl = $gitOpenssl
    }
    else {
        throw "openssl was not found. Install Git for Windows, or add openssl to PATH."
    }
}

if (-not (Test-Path -LiteralPath $certDir)) {
    New-Item -ItemType Directory -Path $certDir | Out-Null
}

# ---------------------------------------------------------------- authority
if ((Test-Path -LiteralPath $caCert) -and (Test-Path -LiteralPath $caKey)) {
    Write-Host "Reusing the existing CareBot certificate authority."
}
else {
    Write-Host "Creating the CareBot certificate authority..."
    & $openssl req -x509 -newkey rsa:2048 -nodes -days 3650 `
        -keyout $caKey -out $caCert `
        -subj "/CN=CareBot Local Development CA/O=CareBot" `
        -addext "basicConstraints=critical,CA:TRUE,pathlen:0" `
        -addext "keyUsage=critical,keyCertSign,cRLSign" `
        -addext "subjectKeyIdentifier=hash"
    if ($LASTEXITCODE -ne 0) { throw "openssl could not create the authority." }
}

# ---------------------------------------------------------------- server cert
# Cover localhost and every address this machine currently answers on, so the
# same certificate works for the dashboard and for the patient's phone.
$addresses = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -ne "127.0.0.1" } |
    Select-Object -ExpandProperty IPAddress -Unique

$names = @("DNS:localhost", "IP:127.0.0.1")
foreach ($address in $addresses) {
    $names += "IP:$address"
}
$subjectAltName = $names -join ", "
Write-Host "Certificate will cover: $subjectAltName"

$extPath = Join-Path $env:TEMP "carebot-leaf.cnf"
@"
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = $subjectAltName
"@ | Out-File -FilePath $extPath -Encoding ascii

$csrPath = Join-Path $env:TEMP "carebot-dev.csr"
$leafPath = Join-Path $env:TEMP "carebot-dev-leaf.pem"

& $openssl req -newkey rsa:2048 -nodes -keyout $serverKey -out $csrPath `
    -subj "/CN=CareBot Dev Server"
if ($LASTEXITCODE -ne 0) { throw "openssl could not create the server key." }

& $openssl x509 -req -in $csrPath -CA $caCert -CAkey $caKey -CAcreateserial `
    -out $leafPath -days 825 -sha256 -extfile $extPath
if ($LASTEXITCODE -ne 0) { throw "openssl could not sign the server certificate." }

# Vite serves the leaf followed by the authority, so a device that already
# trusts the authority never has to fetch anything.
Get-Content $leafPath, $caCert | Set-Content -Path $serverCert -Encoding ascii
Copy-Item -LiteralPath $caCert -Destination $phoneCopy -Force

Remove-Item -LiteralPath $csrPath, $leafPath, $extPath -Force -ErrorAction SilentlyContinue

# ---------------------------------------------------------------- trust it
# Import-Certificate opens a confirmation dialog and fails outright in a
# non-interactive shell. The store API below writes to the same place, for this
# user only, without a prompt.
$authority = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($caCert)
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
$store.Open("ReadWrite")

$alreadyTrusted = $store.Certificates | Where-Object { $_.Thumbprint -eq $authority.Thumbprint }
if ($alreadyTrusted) {
    Write-Host "The CareBot authority is already trusted for this user."
}
else {
    # Drop older CareBot authorities so re-running never piles them up.
    foreach ($stale in ($store.Certificates | Where-Object { $_.Subject -like "*CareBot*" })) {
        $store.Remove($stale)
    }
    $store.Add($authority)
    Write-Host "Trusted the CareBot authority for this user."
}
$store.Close()

Write-Host ""
Write-Host "Wrote $serverCert"
Write-Host "Wrote $phoneCopy  (install this one on the patient's phone)"
Write-Host ""
Write-Host "Restart the dev server:  npm run dev"
Write-Host "Then open:               https://localhost:5173"
Write-Host "Chrome shows a padlock. If it still warns, close every Chrome"
Write-Host "window and open it again so it re-reads the certificate store." 
Write-Host ""
Write-Host "On the patient's phone, to remove its warning too:"
Write-Host "  1. Open  https://<this machine's ip>:5173/carebot-ca.crt"
Write-Host "  2. Android: Settings, Security, Encryption, Install a certificate,"
Write-Host "     CA certificate, then pick the downloaded file."
Write-Host "  3. iPhone: install the profile, then turn it on under"
Write-Host "     Settings, General, About, Certificate Trust Settings."
Write-Host "Tapping Advanced then Proceed also works without installing anything."
