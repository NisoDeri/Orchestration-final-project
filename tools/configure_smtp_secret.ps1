$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$secretsDir = Join-Path $repo "secrets"
$smtpPath = Join-Path $secretsDir "smtp.json"

New-Item -ItemType Directory -Force -Path $secretsDir | Out-Null

Write-Host ""
Write-Host "Configure Gmail SMTP for yardentziar@gmail.com"
Write-Host "Paste the 16-character Google App Password when prompted."
Write-Host "Input is hidden and will be written only to secrets\smtp.json."
Write-Host ""

$secure = Read-Host "Gmail App Password" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

if ([string]::IsNullOrWhiteSpace($password)) {
    throw "empty password; smtp.json not written"
}

$data = [ordered]@{
    host = "smtp.gmail.com"
    port = 587
    user = "yardentziar@gmail.com"
    password = $password
}

$json = $data | ConvertTo-Json
Set-Content -LiteralPath $smtpPath -Value $json -Encoding UTF8

Write-Host ""
Write-Host "Wrote $smtpPath"
Write-Host "You can close this window."
Read-Host "Press Enter to close"
