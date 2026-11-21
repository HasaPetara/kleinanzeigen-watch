' Startet run.bat ohne sichtbares Fenster - fuer die geplante Aufgabe.
' Aufruf durch den Task Scheduler:  wscript.exe run-hidden.vbs
'
' Projektordner = drei Ebenen ueber dieser Datei
' (<projekt>\deploy\windows\run-hidden.vbs)
Dim shell, fso, here, bat
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName)))
bat = here & "\run.bat"

If Not fso.FileExists(bat) Then
    ' Fehler sichtbar machen statt stumm zu scheitern
    If Not fso.FolderExists(here & "\logs") Then fso.CreateFolder here & "\logs"
    Dim stream
    Set stream = fso.OpenTextFile(here & "\logs\watch.log", 8, True)
    stream.WriteLine "[" & Now & "] FEHLER: run.bat nicht gefunden: " & bat
    stream.Close
    WScript.Quit 1
End If

shell.CurrentDirectory = here
shell.Run """" & bat & """", 0, False
