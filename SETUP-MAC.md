# Setup am Mac – Schritt für Schritt

Zeitbedarf: ~15 Minuten. Danach läuft es alle 5 Minuten von allein.

Du brauchst: Mac, Browser, Telegram (App oder Web), GitHub-Konto
(kostenlos auf github.com anlegen, falls noch nicht da).

---

## Schritt 1 – Terminal öffnen

`⌘ + Leertaste` → „Terminal" tippen → `Enter`.

Prüfen, ob git da ist:

```bash
git --version
```

- **Ausgabe wie `git version 2.x`** → weiter mit Schritt 2.
- **Pop-up „Befehlszeilentools installieren"** → auf **Installieren** klicken,
  warten (5–10 Min), Terminal schließen und neu öffnen, nochmal prüfen.

---

## Schritt 2 – Projektordner auf den Mac holen

Die Datei `kleinanzeigen-watch.zip` herunterladen und **doppelklicken** →
es entsteht der Ordner `kleinanzeigen-watch` (liegt meist in „Downloads").

Dann im Terminal:

```bash
cd ~/Downloads/kleinanzeigen-watch
ls
```

Du solltest `config.toml`, `README.md`, `watcher`, `tests` sehen.

---

## Schritt 3 – Telegram-Bot anlegen

1. Telegram öffnen, oben in die Suche: **@BotFather** → den mit dem blauen
   Haken öffnen → unten **Start** drücken.
2. Nachricht senden: `/newbot`
3. BotFather fragt nach einem **Namen** (frei wählbar, z. B. `PortaSplit Watch`)
   → tippen, senden.
4. Danach nach einem **Benutzernamen**: muss auf `bot` enden, z. B.
   `portasplit_watch_bot` → senden. (Falls vergeben: anderen Namen probieren.)
5. BotFather antwortet mit einer Zeile wie
   `Use this token to access the HTTP API: 7123456789:AAH...`
   → **diesen Token kopieren**. Er ist wie ein Passwort: nicht weitergeben,
   nicht in Dateien schreiben, nicht in Chats posten.
6. Auf den Link `t.me/portasplit_watch_bot` in der Antwort tippen → **Start**
   drücken → irgendeine Nachricht senden (z. B. `hallo`).
   **Ohne diese Nachricht darf der Bot dir nicht schreiben.**

### Chat-ID herausfinden

Im Browser (Safari) diese Adresse öffnen – `<TOKEN>` durch deinen Token ersetzen:

```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

Im Ergebnis steht irgendwo:

```json
"chat": { "id": 123456789, "first_name": "..." }
```

Die Zahl (`123456789`, kann auch negativ sein) ist deine **Chat-ID**.
Nichts gefunden? Nochmal `hallo` an den Bot senden, Seite neu laden.

---

## Schritt 4 – GitHub-CLI installieren

Prüfen:

```bash
brew --version
```

- **Version wird angezeigt** → weiter mit `brew install gh`.
- **`command not found`** → Homebrew fehlt. Den Befehl von
  [brew.sh](https://brew.sh) in einem Stück kopieren und im Terminal ausführen
  (fragt nach dem Mac-Passwort), danach Terminal neu öffnen.

```bash
brew install gh
```

---

## Schritt 5 – Bei GitHub anmelden

```bash
gh auth login
```

Die Fragen so beantworten (Pfeiltasten + Enter):

1. `GitHub.com` → Enter
2. `HTTPS` → Enter
3. `Login with a web browser` → Enter
4. Es erscheint ein **Einmalcode** (z. B. `A1B2-C3D4`) → Code kopieren
5. `Enter` → Browser öffnet sich → Code einfügen → **Authorize** klicken
6. Zurück im Terminal: `Logged in as <dein-name>`

Git-Identität einmal setzen (sonst meckert der Commit):

```bash
git config --global user.name "Dein Name"
git config --global user.email "deine@mail-adresse.de"
```

---

## Schritt 6 – Repo anlegen und hochladen

Im Projektordner (`cd ~/Downloads/kleinanzeigen-watch`):

```bash
git init -b main
git add .
git commit -m "kleinanzeigen-watch"
gh repo create kleinanzeigen-watch --public --source=. --remote=origin --push
```

**Wichtig: `--public`.** Bei privaten Repos sind die Actions-Minuten nach
~2.000 pro Monat aufgebraucht (das wären hier ~8.600 Läufe), öffentlich ist
unbegrenzt. Der Bot-Token liegt nicht im Code, sondern in den Secrets.

---

## Schritt 7 – Token und Chat-ID als Secrets hinterlegen

```bash
gh secret set TG_BOT_TOKEN
```

→ `Paste your secret:` erscheint → **Token** einfügen (`⌘ + V`), `Enter`.
(Eingefügtes wird nicht angezeigt – das ist normal.)

```bash
gh secret set TG_CHAT_ID
```

→ **Chat-ID** einfügen, `Enter`.

Kontrolle:

```bash
gh secret list
```

Sollte beide Namen zeigen.

---

## Schritt 8 – Telegram testen (der Klick-Test)

```bash
gh workflow run watch.yml -f test_message=true
sleep 10
gh run list -w watch.yml -L 3
```

In Telegram sollte jetzt **„✅ kleinanzeigen-watch: Testnachricht"** ankommen.

- **Nichts angekommen?** `gh run view --log` zeigt den Fehler. Typisch:
  Chat-ID falsch (nochmal Schritt 3) oder der Bot hat nie eine Nachricht
  von dir bekommen.

---

## Schritt 9 – Ersten echten Lauf starten

```bash
gh workflow run watch.yml
sleep 10
gh run list -w watch.yml -L 3
```

Den neuesten Lauf ansehen:

```bash
gh run view <RUN-ID> --log
```

(RUN-ID steht in der Liste, z. B. `2345678901`.)

**Erwartete Zeile:**

```
Baseline gesetzt: 7 Anzeigen gespeichert, keine Nachricht.
```

Das ist richtig so: der erste Lauf merkt sich nur den Ist-Zustand, damit du
nicht 7 Nachrichten auf einmal bekommst. Ab jetzt meldet jeder neue Treffer.

**Falls stattdessen steht:**

```
Abruf fehlgeschlagen: HTTP 403 - vermutlich Bot-Schutz
```

→ GitHub-IPs werden geblockt. Dann Bescheid sagen, dann bauen wir um
(Raspberry Pi oder kleiner VPS).

---

## Schritt 10 – Kontrolle, dass der Zeitplan läuft

Auf github.com ins Repo → Reiter **Actions** → links „kleinanzeigen-watch".
Alle ~5–15 Minuten erscheint ein neuer Lauf. (GitHub ist da ungenau, das ist
normal.)

Steht dort „Workflows aren't being run on this repository", einmal auf
**I understand my workflows, go ahead and enable them** klicken.

---

## Später etwas ändern

Suchbegriff, Preis oder Ausschlüsse stehen in `config.toml`:

```bash
cd ~/Downloads/kleinanzeigen-watch
nano config.toml        # ändern, ⌃O Enter, ⌃X
git add config.toml
git commit -m "Filter angepasst"
git push
```

Der nächste Lauf nutzt die neuen Werte. Wichtig: Wenn du die Suche stark
änderst, ist ein Reset sinnvoll (`state.json` wird nicht im Repo gehalten,
sondern im Actions-Cache) — sonst gelten alte Treffer als „schon gesehen".

---

## Wenn etwas klemmt

| Meldung | Bedeutung / Lösung |
|---|---|
| `gh: command not found` | Schritt 4, `brew install gh` |
| `no commits yet` / Push leer | Schritt 6 von vorn: `git add .` + `git commit` |
| `HTTP 403 – vermutlich Bot-Schutz` | GitHub-IP geblockt → anderen Host nehmen |
| Testnachricht kommt nicht | Chat-ID falsch oder Bot nie angeschrieben (Schritt 3.6) |
| Lauf bricht bei „Tests" ab | Datei fehlt im Repo → `git status` prüfen, alles committen |
| Keine Nachrichten, aber Läufe grün | aktuell 0 passende Anzeigen – normal, siehe README „Testen" |
