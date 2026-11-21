# kleinanzeigen-watch

Beobachtet eine oder mehrere Kleinanzeigen-Suchen und schickt neue Treffer per
Telegram. Alles wird über `config.toml` gesteuert – für eine andere Suche oder
ein anderes Preisfenster muss kein Code angefasst werden.

**Neu hier?** Schritt für Schritt:
[SETUP-WINDOWS.md](SETUP-WINDOWS.md) (Windows, dieser PC) ·
[SETUP-MAC.md](SETUP-MAC.md) (Mac + GitHub Actions).

Stand: lokal lauffähig und getestet, Deploy auf einen kostenlosen Host noch offen
(siehe „Dauerbetrieb").

```
7 Treffer, 0 passen, 7 aussortiert
--  3569386042   849 €  91090 Effeltrich (374 km)     Midea Portasplit 12500 BTU …   (374 km entfernt (max 200 km))
--  3547601306   820 €  99734 Nordhausen (315 km)     Midea PortaSplit 3,5 kW …      (315 km entfernt (max 200 km))
--  3535534017   770 €  32689 Kalletal (216 km)       Midea PortaSplit Cool …        (216 km entfernt (max 200 km))
--  3566766605   750 €  53115 Bonn (67 km)            Midea PortaSplit 8000 BTU …    (exclude trifft: \b8[.,]?000\b)
--  3502413647   688 €  66706 Perl (179 km)           … (ähnlich Midea PortaSplit)   (exclude trifft: ähnlich|…)
```

## Schnellstart

```bash
python -m watcher --dry-run -v     # zeigt nur an, sendet und speichert nichts
python -m watcher --seed           # Baseline: aktuelle Treffer merken, nichts senden
python -m watcher                  # normaler Lauf (für cron / systemd-Timer)
python -m watcher --test-telegram  # Bot-Konfiguration prüfen
python -m unittest discover -s tests -v
```

Nur Standardbibliothek, kein `pip install` nötig (Python ≥ 3.11 wegen `tomllib`).

## Konfiguration

`config.toml`, ein Block pro Suche:

| Feld | Bedeutung |
|---|---|
| `name` | Anzeigename, muss eindeutig sein |
| `keyword` | Suchbegriff, z. B. `portasplit`, `bosch waschmaschine` |
| `zip`, `radius_km` | Standort und Umkreis |
| `price_min`, `price_max` | Preisfenster, `= 0`/weglassen für „kein Filter" |
| `only_offers` | `true` = nur Verkaufsanzeigen, keine Gesuche |
| `require` | **alle** Muster müssen passen (Regex, case-insensitive) |
| `exclude` | **keines** darf passen (Regex, case-insensitive) |
| `max_per_run` | höchstens so viele Nachrichten pro Lauf |
| `max_age_hours` | `0` = Alter egal, sonst z. B. `48` |
| `notify_price_drop` | erneut melden, wenn der Preis sinkt |

Regex-Tipp: in TOML einfache Anführungszeichen nehmen (`'porta\s*-?\s*split'`),
sonst frisst TOML die Backslashes.

**Neue Suche anlegen:** Block kopieren, `name`/`keyword`/Preis anpassen – fertig.
Der Zustand wird pro `name` getrennt gespeichert.

### Warum die Filter so aussehen

- `porta\s*-?\s*split` trifft `PortaSplit`, `Porta Split` und `Porta-Split`.
- `exclude` matcht bewusst den **Modellnamen** `PortaSplit Cool` statt nur das
  Wort `cool`: „cooles Gerät" steht in vielen Anzeigentexten und würde sonst
  echte Treffer killen. Wer es hart will: `'\bcool\b'` zusätzlich eintragen.
- `ähnlich|aehnlich|vergleichbar` wirft Anzeigen raus, die nur „wie Midea
  PortaSplit" sind (z. B. „BE COOL BCPSK12KW") – das sind keine Midea-Geräte.
- `\b8[.,]?000\b` fängt `8000 BTU`, `8.000 BTU` und `8,000 BTU`.

### Der Umkreis wird selbst gerechnet

**Kleinanzeigen ignoriert `r200` in der serverseitigen Antwort komplett.** Nachweis:

```
/s-41812/.../portasplit/k0l1202r5      -> 7 Treffer (Bonn, Perl, Kalletal, Nordhausen, Effeltrich, …)
/s-41812/.../portasplit/k0l1202r200    -> dieselben 7 Treffer
/s-41812/.../portasplit/k0            -> dieselben 7 Treffer
```

Der Radius wird nur im Browser angewandt; im HTML stehen die Anzeigen aus ganz
Deutschland. Deshalb rechnet `watcher/geo.py` die Luftlinie aus den
PLZ-Mittelpunkten (`data/plz_de.csv.gz`, Quelle GeoNames, CC BY 4.0) und
`radius_km` filtert anschließend wirklich. Zusätzlich steht die Entfernung in
jeder Meldung.

## Telegram einrichten

1. Bei **@BotFather** `/newbot` → Token notieren.
2. Dem eigenen Bot einmal schreiben.
3. `https://api.telegram.org/bot<TOKEN>/getUpdates` aufrufen →
   `result[].message.chat.id` ist die `chat_id` (bei Gruppen negativ, z. B. `-100…`).
4. `chat_id` in `config.toml` eintragen, Token **nicht** in die Datei, sondern:

```bash
export TG_BOT_TOKEN="123456:ABC..."   # Linux/macOS
$env:TG_BOT_TOKEN = "123456:ABC..."   # Windows PowerShell
```

Auf dem Server: `.env` mit `TG_BOT_TOKEN=...`, `chmod 600 .env`, per
`EnvironmentFile` in systemd einbinden (siehe `deploy/systemd/`).

## Testen, wenn gerade nichts passt

Die Suche liefert mit dem echten 200-km-Radius aktuell 0 Treffer. Um die Kette
Abruf → Filter → Telegram einmal komplett zu sehen, die Grenzen testweise
weiten: `radius_km = 0` und `price_min = 0`, dann

```bash
python -m watcher --dry-run -v     # zeigt, was durchkommt
python -m watcher --seed           # Baseline neu setzen
```

Danach die Werte zurücksetzen. `--test-telegram` prüft nur den Bot.

## Dauerbetrieb mit GitHub Actions (kostenlos, alle 5 Minuten)

> **Auf diesem PC statt in der Cloud?** Dann nicht diesen Abschnitt nehmen,
> sondern [SETUP-WINDOWS.md](SETUP-WINDOWS.md): `deploy\windows\` enthält
> `configure.ps1` (Token + Chat-ID eintragen, Testnachricht), `install-task.ps1`
> (Aufgabe alle 5 Minuten, ohne Fenster) und `remove-task.ps1`.

Alles liegt bereit: `.github/workflows/watch.yml`.

1. **Öffentliches** Repo anlegen (bei öffentlichen Repos sind Actions-Minuten
   unbegrenzt; privat wären 8.600 Läufe/Monat über dem Free-Kontingent).
2. Code hochladen:

```bash
git init && git add . && git commit -m "kleinanzeigen-watch"
git remote add origin https://github.com/<dein-name>/kleinanzeigen-watch.git
git push -u origin main
```

3. **Secrets** setzen (Settings -> Secrets and variables -> Actions):
   `TG_BOT_TOKEN` = Bot-Token, `TG_CHAT_ID` = deine Chat-ID.
4. Actions -> "kleinanzeigen-watch" -> **Run workflow** (manuell, zum Testen).
   Der erste Lauf setzt nur die Baseline. Der zweite meldet Neues.

Was der Workflow macht: checkout -> Tests -> `state.json` aus dem Actions-Cache
holen -> ein Lauf -> Cache mit neuem Zustand speichern.

**Grenzen von GitHub Actions, die du kennen solltest:**

- Cron ist **nicht minutengenau**: `*/5` heißt oft 5-15 Minuten Verzögerung,
  bei Last auch mehr. Für "schnell sein" ist das der Preis für 0 €.
- Läuft nur, wenn das Repo aktiv bleibt - nach **60 Tagen ohne Commit** kann
  GitHub den Schedule deaktivieren. Ein Commit alle paar Wochen hilft.
- Ob die Azure-IPs von GitHub durchkommen, zeigt der erste Lauf im Log:
  `7 Treffer, ...` = gut, `HTTP 403 - vermutlich Bot-Schutz` = geblockt.

### Alternative: eigener Server (systemd)

Ein Lauf ist zustandslos außer `state.json`; 2 Minuten Takt sind unkritisch
(rund 720 Requests/Tag, ein Request pro Lauf).

```bash
sudo cp deploy/systemd/kleinanzeigen-watch.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kleinanzeigen-watch.timer
systemctl list-timers kleinanzeigen-watch.timer
```

**Vorher prüfen, ob der Host überhaupt darf:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36" \
  "https://www.kleinanzeigen.de/s-sortierung:neueste/41812/anzeige:angebote/preis:400:850/portasplit/k0r200"
```

`200` = gut. `403`/`429` = dieser Host wird geblockt, dann anderen nehmen.
Datacenter-IPs werden häufiger geblockt als Heim-IPs; ein Raspberry Pi zuhause
ist die robusteste kostenlose Variante.

## Wenn etwas klemmt

| Symptom | Ursache / Lösung |
|---|---|
| `Ergebnisliste fehlt im HTML` als Fehler | Layout-Änderung oder Blockseite → Fixture neu ziehen, Parser anpassen |
| dauerhaft `HTTP 403` | Bot-Schutz: Host wechseln, nicht schneller pollen |
| keine Nachricht beim ersten Lauf | normal – der erste Lauf setzt die Baseline (`--seed`) |
| Nachricht doppelt | `state.json` gelöscht? dann Baseline neu setzen |
| Umlaute kaputt | Seite liefert cp1252 trotz UTF-8-Header; `decode_page` behandelt das |

`state.json` löschen = Neustart (nächster Lauf ist wieder Baseline).

## Grenzen

- **5-Minuten-Cron heißt oft 5–15 Minuten Verzögerung** (GitHub ist da
  unzuverlässig). Bei gefragten Geräten kann die Anzeige in der Zeit weg sein.
- **Umkreis ist Luftlinie** und wird aus PLZ-Mittelpunkten geschätzt — bei
  Grenzfällen (Kalletal: 216 km) kann das ein paar Kilometer daneben liegen.
- **Textanfang ist abgeschnitten** (~200 Zeichen). Filter greifen auf Titel,
  Slug und diesem Anfang. Für Volltextsuche müsste man jede Detailseite laden.
- Die **robots.txt** von Kleinanzeigen verbietet genau diese gefilterten
  Such-URLs (`/*/anzeige:angebote`, `/*/preis:*`, `/*/k0*r200`). Das hier ist
  eine Grauzone: geringe Last, kein Login, aber es ist die erklärte
  Wunschrichtung des Betreibers. Risiko im schlimmsten Fall: IP-Sperre.
