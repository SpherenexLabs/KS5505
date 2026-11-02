<#
Clears a leftover dev server off the port before Vite tries to bind it.

npm runs this automatically through the "predev" script. The dev server is
started and stopped constantly, and a closed terminal does not always take the
node process with it. The leftover then owns port 5173, and because
vite.config.js sets strictPort, the next "npm run dev" stops with
"Port 5173 is already in use" rather than sliding onto 5174 and handing out a
tracking link that points at the wrong port.

Only a node process is ever stopped. Anything else on the port is reported and
left alone, because it is not ours to close.

    powershell -ExecutionPolicy Bypass -File scripts\free-port.ps1 [port]
#>

param(
    [int]$Port = 5173
)

# Never fail the npm script: this is a convenience, not a gate.
$ErrorActionPreference = "Continue"

$listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $listeners) {
    exit 0
}

foreach ($id in ($listeners | Select-Object -ExpandProperty OwningProcess -Unique)) {
    $process = Get-Process -Id $id -ErrorAction SilentlyContinue
    if (-not $process) { continue }

    if ($process.ProcessName -eq "node") {
        Write-Host "Port $Port was held by an old dev server (PID $id). Stopping it."
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    }
    else {
        Write-Host ""
        Write-Host "Port $Port is held by $($process.ProcessName) (PID $id), which is not a dev server."
        Write-Host "Close it, or free the port yourself with:"
        Write-Host "  Stop-Process -Id $id -Force"
        Write-Host ""
    }
}

# Give Windows a moment to release the socket before Vite asks for it.
Start-Sleep -Milliseconds 700
exit 0
