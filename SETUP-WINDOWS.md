# Setup auf diesem PC (Windows)

Alles ist vorbereitet. Du brauchst **drei Schritte**, danach läuft es alle
5 Minuten von allein — ohne Fenster, ohne GitHub, ohne Kosten.

Projektordner:
`C:\Users\beatle\Documents\deepseek-harness\default-workspace\kleinanzeigen-watch`

Python ist vorhanden (3.12.10), Task Scheduler läuft, nichts zu installieren.

---

## Schritt 1 — Telegram-Bot anlegen (in Telegram)

1. Telegram öffnen → Suche: **@BotFather** → den mit blauem Haken öffnen → **Start**
2. Senden: `/newbot`
3. **Name** eingeben, z. B. `PortaSplit Watch`
4. **Benutzername** eingeben, muss auf `bot` enden, z. B. `portasplit_watch_bot`
5. BotFather antwortet mit `7123456789:AAH...` → das ist der **Token** (kopieren)
6. Auf den Link `t.me/portasplit_watch_bot` tippen → **Start** → `hallo` senden
   *(ohne diese Nachricht darf der Bot dir nicht schreiben)*

### Chat-ID holen

Im Browser öffnen (`<TOKEN>` ersetzen):

```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

Im Text steht `"chat":{"id":123456789` → **diese Zahl** ist die Chat-ID.
Nichts da? Nochmal `hallo` senden, Seite neu laden.

**Kommt `{"ok":true,"result":[]}`**, ist der Token gültig, aber es ist noch
keine Nachricht beim Bot angekommen — dann wurde „hallo" meist an @BotFather
statt an den eigenen Bot geschickt. Statt Browser gibt es dafür ein Skript,
das die Token prüft, auf die Nachricht wartet und die ID ausgibt:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\find-chat-id.ps1
```

---

## Schritt 2 — Token und Chat-ID eintragen

PowerShell öffnen (Start → „PowerShell" tippen), dann:

```powershell
cd C:\Users\beatle\Documents\deepseek-harness\default-workspace\kleinanzeigen-watch
powershell -ExecutionPolicy Bypass -File deploy\windows\configure.ps1
```

Das Skript fragt nach **Chat-ID** (eintippen, Enter) und **Token**
(Eingabe bleibt unsichtbar, Enter). Es schreibt beides in `config.toml` und
schickt sofort eine Testnachricht.

- **„✅ kleinanzeigen-watch: Testnachricht" in Telegram** → weiter mit Schritt 3
- **Fehlermeldung** → meist: Bot nie angeschrieben, Chat-ID falsch oder Token
  vertippt. Skript nochmal starten.

---

## Schritt 3 — Zeitplan anlegen

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install-task.ps1
```

Das legt die Aufgabe **kleinanzeigen-watch** an: alle 5 Minuten, ohne Fenster
(über `wscript.exe` + `deploy\windows\run-hidden.vbs`), und startet einen
Testlauf. Du siehst danach:

```
TaskName      : kleinanzeigen-watch
LastRunTime   : ...
NextRunTime   : ...
Letzte Logzeilen:
[14:31:02] > Midea PortaSplit  ->  https://www.kleinanzeigen.de/...
[14:31:03]   8 Treffer, 0 passen, 8 aussortiert
[14:31:03]   nichts Neues
```

Fertig. Ab jetzt läuft es im Hintergrund.

**Alle 2 Minuten statt 5:**

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install-task.ps1 -Minutes 2
```

---

## Kontrolle

```powershell
Get-ScheduledTask -TaskName "kleinanzeigen-watch" | Select-Object State
Get-ScheduledTaskInfo -TaskName "kleinanzeigen-watch" | Format-List LastRunTime, LastTaskResult, NextRunTime
Get-Content logs\watch.log -Tail 20 -Encoding UTF8
```

`LastTaskResult: 0` = alles gut. Ein neuer Lauf erscheint alle 5 Minuten
im Log.

## Etwas ändern

`config.toml` mit Notepad öffnen:

```powershell
notepad config.toml
```

- `keyword` → anderer Suchbegriff
- `price_min` / `price_max` → anderes Preisfenster
- `radius_km` → Umkreis (wird selbst gerechnet, siehe README)
- `exclude` / `require` → Filter

Speichern, fertig — der nächste Lauf nutzt die neuen Werte. Wenn du die Suche
stark änderst: `state.json` löschen, damit der nächste Lauf wieder als
Baseline startet (sonst gelten alte Treffer als „schon gesehen").

## Ausschalten / löschen

```powershell
# pausieren
Disable-ScheduledTask -TaskName "kleinanzeigen-watch"

# wieder an
Enable-ScheduledTask -TaskName "kleinanzeigen-watch"

# ganz entfernen
powershell -ExecutionPolicy Bypass -File deploy\windows\remove-task.ps1
```

---

## Wichtig für diesen PC

- **Der PC muss laufen.** Im Ruhezustand/Herunterfahren passiert nichts.
  Die Aufgabe holt einen verpassten Lauf nach dem Aufwachen nach
  (`StartWhenAvailable`), aber sie kann nicht zaubern.
- **Läuft auch im Sperrbildschirm**, solange du angemeldet bist.
- **Akku:** Die Aufgabe startet auch im Akkubetrieb (kein Abbruch beim
  Wechsel auf Akku).
- **Log** wächst langsam (~2 Zeilen pro Lauf). Bei Bedarf:
  `Remove-Item logs\watch.log`
- **`config.toml` enthält den Bot-Token im Klartext.** Nicht in ein
  öffentliches Repo hochladen. Wenn der Token rausgeht: in Telegram
  `@BotFather` → `/revoke` → neuen Token eintragen.

## Wenn etwas nicht kommt

| Symptom | Ursache |
|---|---|
| Testnachricht fehlt | Bot nie angeschrieben oder Chat-ID falsch (Schritt 1) |
| `HTTP 403 – vermutlich Bot-Schutz` im Log | Seite blockt — dann melden, wir drosseln um |
| Läufe grün, aber keine Nachrichten | gerade 0 passende Anzeigen — normal (siehe README „Testen, wenn gerade nichts passt") |
| Aufgabe läuft nicht | PC im Ruhezustand? `Get-ScheduledTaskInfo` zeigt `NextRunTime` |
| `Zugriff verweigert` beim Anlegen | PowerShell als normaler Benutzer starten (nicht als Admin nötig) |
