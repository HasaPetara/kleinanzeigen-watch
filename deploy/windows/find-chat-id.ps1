# Findet die Chat-ID eines Telegram-Bots und wartet dabei auf deine Nachricht.
#   powershell -ExecutionPolicy Bypass -File deploy\windows\find-chat-id.ps1
param([string]$Token)

$ErrorActionPreference = "Stop"
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }

if (-not $Token) {
    Write-Host "Bot-Token eingeben (bleibt unsichtbar):"
    $secure = Read-Host -AsSecureString
    $Token = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    ).Trim()
}
if (-not $Token) { throw "Kein Token eingegeben." }

$base = "https://api.telegram.org/bot$Token"

# 1) Token pruefen und Bot-Namen anzeigen
try {
    $me = Invoke-RestMethod -Uri "$base/getMe" -TimeoutSec 20
} catch {
    Write-Host "Der Token wird von Telegram abgelehnt (401 Unauthorized)." -ForegroundColor Red
    Write-Host "Token in BotFather nochmal kopieren: /mybots -> dein Bot -> API Token"
    exit 1
}
$botName = $me.result.username
Write-Host "Token gehoert zum Bot: @$botName" -ForegroundColor Green

# 2) Falls ein Webhook gesetzt ist, kommen Updates nicht per getUpdates an
try {
    $hook = Invoke-RestMethod -Uri "$base/getWebhookInfo" -TimeoutSec 20
    if ($hook.result.url) {
        Write-Host "Achtung: fuer diesen Bot ist ein Webhook gesetzt ($($hook.result.url))."
        Write-Host "Der wird jetzt entfernt, damit getUpdates funktioniert."
        Invoke-RestMethod -Uri "$base/deleteWebhook" -TimeoutSec 20 | Out-Null
    }
} catch { }

Write-Host ""
Write-Host "JETZT in Telegram:" -ForegroundColor Cyan
Write-Host "  1. https://t.me/$botName oeffnen"
Write-Host "  2. unten auf 'Start' druecken (oder /start senden)"
Write-Host "  3. 'hallo' senden"
Write-Host ""
Write-Host "Warte bis zu 120 Sekunden auf die Nachricht ..."

$deadline = (Get-Date).AddSeconds(120)
$offset = 0
$chat = $null
while ((Get-Date) -lt $deadline -and -not $chat) {
    try {
        $resp = Invoke-RestMethod -Uri "$base/getUpdates?timeout=10&offset=$offset" -TimeoutSec 25
        foreach ($update in $resp.result) {
            $offset = [int]$update.update_id + 1
            if ($update.message.chat.id) { $chat = $update.message.chat; break }
            if ($update.edited_message.chat.id) { $chat = $update.edited_message.chat; break }
            if ($update.channel_post.chat.id) { $chat = $update.channel_post.chat; break }
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $chat) {
    Write-Host ""
    Write-Host "Nichts angekommen." -ForegroundColor Red
    Write-Host "Pruefe: heisst der Chat in Telegram genau '@$botName'? Nicht @BotFather."
    Write-Host "Dann Skript nochmal starten."
    exit 1
}

$who = (@($chat.first_name, $chat.last_name) | Where-Object { $_ }) -join " "
Write-Host ""
Write-Host "Chat-ID gefunden: $($chat.id)" -ForegroundColor Green
if ($who) { Write-Host "Chat gehoert zu: $who" }
if ($chat.type -ne "private") { Write-Host "Typ: $($chat.type)" }

Write-Host ""
Write-Host "Naechster Schritt - beides in einem Aufruf:"
Write-Host "  powershell -ExecutionPolicy Bypass -File deploy\windows\configure.ps1 -ChatId $($chat.id)"
