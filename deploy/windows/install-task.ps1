# Legt die geplante Aufgabe "kleinanzeigen-watch" an (alle 5 Minuten, ohne
# Fenster). Aufruf:
#   powershell -ExecutionPolicy Bypass -File deploy\windows\install-task.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\windows\install-task.ps1 -Minutes 2
param(
    [int]$Minutes = 5,
    [string]$TaskName = "kleinanzeigen-watch"
)

$ErrorActionPreference = "Stop"

$windowsDir = $PSScriptRoot
$project = Split-Path -Parent (Split-Path -Parent $windowsDir)
$vbs = Join-Path $windowsDir "run-hidden.vbs"
$log = Join-Path $project "logs\watch.log"

if (-not (Test-Path $vbs)) {
    throw "run-hidden.vbs nicht gefunden: $vbs"
}
if (-not (Test-Path (Join-Path $project "config.toml"))) {
    throw "config.toml nicht gefunden in $project"
}

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument ('"' + $vbs + '"') -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $Minutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Kleinanzeigen-Suche alle $Minutes Minuten" -Force | Out-Null

Write-Host "Aufgabe '$TaskName' angelegt: alle $Minutes Minuten."
Write-Host "Testlauf wird gestartet ..."
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 12

Get-ScheduledTaskInfo -TaskName $TaskName | Format-List LastRunTime, LastTaskResult, NextRunTime

if (Test-Path $log) {
    Write-Host "Letzte Logzeilen:"
    Get-Content $log -Tail 8 -Encoding UTF8
}
