# Traegt Bot-Token und Chat-ID in config.toml ein und schickt eine Testnachricht.
#
# NUR FUER LOKALEN BETRIEB. Der Token landet dabei im Klartext in config.toml -
# im Cloud-Betrieb (GitHub Actions) gehoert er in die Repo-Secrets TG_BOT_TOKEN
# und TG_CHAT_ID, niemals in eine Datei, die hochgeladen wird.
#
#   powershell -ExecutionPolicy Bypass -File deploy\windows\configure.ps1
# Optional ohne Rueckfragen:
#   ... -ChatId 123456789 -Token "7123456789:AAH..."
param(
    [string]$ChatId,
    [string]$Token
)

$ErrorActionPreference = "Stop"

$project = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$configPath = Join-Path $project "config.toml"

if (-not (Test-Path $configPath)) { throw "config.toml nicht gefunden: $configPath" }

if (-not $ChatId) { $ChatId = (Read-Host "Chat-ID (Zahl aus getUpdates)").Trim() }
if (-not $Token) {
    Write-Host "Bot-Token eingeben (Eingabe bleibt unsichtbar):"
    $secure = Read-Host -AsSecureString
    $Token = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    ).Trim()
}
if (-not $ChatId -or -not $Token) { throw "Chat-ID und Token duerfen nicht leer sein." }

$text = [IO.File]::ReadAllText($configPath, [Text.Encoding]::UTF8)

# chat_id-Zeile ersetzen
$text = [regex]::Replace($text, '(?m)^chat_id\s*=.*$', 'chat_id = "' + $ChatId + '"')

# token-Zeile: ersetzen oder direkt nach alert_after_failures einfuegen
if ($text -match '(?m)^token\s*=.*$') {
    $text = [regex]::Replace($text, '(?m)^token\s*=.*$', 'token = "' + $Token + '"')
} else {
    $text = [regex]::Replace(
        $text,
        '(?m)^(alert_after_failures\s*=.*)$',
        '$1' + "`ntoken = `"$Token`""
    )
}

[IO.File]::WriteAllText($configPath, $text, (New-Object Text.UTF8Encoding($false)))

Write-Host "config.toml aktualisiert."
Write-Host "Sende Testnachricht ..."

Set-Location $project
& python -m watcher --test-telegram
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Test fehlgeschlagen. Haeufigste Ursachen:" -ForegroundColor Yellow
    Write-Host "  - Bot wurde noch nie angeschrieben (in Telegram 'Start' + 'hallo' senden)"
    Write-Host "  - Chat-ID falsch (nochmal getUpdates pruefen)"
    Write-Host "  - Token vertippt"
    exit 1
}

Write-Host ""
Write-Host "Sieht gut aus: Testnachricht ist raus. Naechster Schritt:"
Write-Host "  powershell -ExecutionPolicy Bypass -File deploy\windows\install-task.ps1"
