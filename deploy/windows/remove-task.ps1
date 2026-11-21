# Entfernt die geplante Aufgabe wieder.
#   powershell -ExecutionPolicy Bypass -File deploy\windows\remove-task.ps1
param([string]$TaskName = "kleinanzeigen-watch")

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $existing) {
    Write-Host "Aufgabe '$TaskName' existiert nicht."
    return
}
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Aufgabe '$TaskName' entfernt."
