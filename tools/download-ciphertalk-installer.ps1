$ErrorActionPreference = "Stop"

$packageRoot = Split-Path -Parent $PSScriptRoot
$vendorDir = Join-Path $packageRoot "vendor\ciphertalk"
$installer = Join-Path $vendorDir "CipherTalk-2026.729.0-Setup.exe"
$url = "https://github.com/ILoveBingLu/CipherTalk/releases/download/v2026.729.0/CipherTalk-2026.729.0-Setup.exe"
$expectedSha256 = "48354069b274591a2ca855fee8100addde3b0f75d05e8336ebb509f6a94bf88b"

New-Item -ItemType Directory -Path $vendorDir -Force | Out-Null

Write-Host "Downloading the official CipherTalk v2026.729.0 installer..."
Invoke-WebRequest -Uri $url -OutFile $installer

$actualSha256 = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSha256 -ne $expectedSha256) {
    Remove-Item -LiteralPath $installer -Force
    throw "CipherTalk installer SHA-256 mismatch: $actualSha256"
}

Write-Host "CipherTalk installer downloaded and verified:"
Write-Host $installer
