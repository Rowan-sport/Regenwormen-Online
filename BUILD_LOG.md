# 📋 BUILD LOG — Regenwormen
## Toegankelijk gezelschapsspel voor jongeren met beperkte handfunctie (MACS 4–5)
### Project: Dobbelstenen Challenge — Rijndam Revalidatie

---

## 🎯 PROJECTOVERZICHT

| Item | Details |
|---|---|
| **Spel** | Regenwormen (ook bekend als Pickomino) |
| **Doelgroep** | K., 18 jaar, MACS 4–5, elektrische rolstoel, Tobii Dynavox gebruiker |
| **Tech stack** | Python 3.x + Flask + HTML/CSS/JS |
| **Invoer** | Tobii Dynavox (primair) → WebGazer webcam → Muis (fallback) |
| **Multiplay** | Lokaal (zelfde scherm) + Online (kamercode, long-polling) |
| **Taal UI** | Nederlands |
| **Laatste update** | Juli 2026 |

---

## 📁 BESTANDSSTRUCTUUR

```
pickomino/
├── app.py                  — Flask server + alle API routes + ngrok + cloud support
├── game_logic.py           — Puur Python spellogica (geen UI)
├── config.json             — Alle instellingen (dwell, kleuren, schaal)
├── requirements.txt        — pip dependencies (flask + gunicorn)
├── render.yaml             — Render.com deployment configuratie
├── .gitignore              — Houdt __pycache__ etc. uit GitHub
├── BUILD_LOG.md            — Dit bestand
├── templates/
│   ├── base.html           — Gedeeld HTML-skelet (gaze cursor, toast)
│   ├── index.html          — Startpagina + spelerssetup (geen zwevende worm)
│   ├── game.html           — Hoofdspelpagina (Option B layout, zoom 1.75)
│   ├── rules.html          — Spelregels pagina (grote terugknop)
│   ├── online.html         — Online lobby (grote terugknop)
│   └── room_game.html      — Online spelpagina (gedeelde kamer)
└── static/
    ├── css/main.css        — Alle styling (joyful thema, grote knoppen)
    └── js/
        ├── tobii.js        — Eye/head tracking module (dwell: 10000ms)
        └── ui.js           — UI helpers (toast, animaties, confetti)
```

---

## 🔢 VOLLEDIGE BUILDLOG — STAP VOOR STAP

### STAP 1 — Projectstructuur & Configuratie
**Bestand:** `config.json`
**Wat:** Centrale configuratie die door therapeuten aangepast kan worden zonder code aan te raken.
**Instellingen:**
- `dwell_time_ms` — Hoe lang kijken om te klikken (huidig: 10000ms / 10 seconden)
- `dwell_radius_px` — Hoe groot de gaze-zone per knop is
- `button_min_size_px` — Minimale knopgrootte (voor oogbesturing: 140px)
- `font_scale` — Tekstvergroting (standaard: 1.4×)
- `tobii.enabled` — Tobii SDK aan/uit
- `tobii.fallback_to_mouse` — Muis als fallback als Tobii niet beschikbaar is
- `tobii.gaze_cursor_color` — Kleur van de gaze-cursor
- `multiplayer.poll_interval_ms` — Hoe vaak de online game gesynchroniseerd wordt

---

### STAP 2 — Spellogica
**Bestand:** `game_logic.py`
**Wat:** Volledige Regenwormen spellogica, puur Python, geen UI.
**Klassen:**
- `Die` — Eén dobbelsteen (waarden 1–5 + worm=5)
- `Player` — Speler met steenstapel en wormteller
- `TurnState` — Complete beurtregistratie (gooi, houd, score, fase)
- `PicominoGame` — Hoofd-spelcontroller

**Spelregels geïmplementeerd:**
- 8 dobbelstenen met zijden 1–2–3–4–5–worm (worm = 5 punten)
- Stenen 21–36, elke steen heeft 1–4 wormen
- Verplicht minstens één worm houden per beurt
- Bust-logica als geen geldige waarde meer beschikbaar
- Stelen als score exact overeenkomt met bovensteen tegenstander
- Spel eindigt als alle stenen uit midden weg zijn
- Volledig serialiseerbaar naar dict (voor Flask sessie/kamer opslag)

**Gecorrigeerde strafregels (officiële Regenwormen regels):**
- Bij bust of geen steen beschikbaar:
  1. Speler's bovenste steen gaat **terug naar het midden** (face-up)
  2. De **hoogste steen in het midden** wordt permanent verwijderd (face-down)

---

### STAP 3 — Flask Server
**Bestand:** `app.py`
**Wat:** Web server met REST API voor spel + online kamers + ngrok + cloud support.

**Lokaal spel routes:**
- `GET /` — Startpagina
- `POST /start` — Nieuw spel starten
- `GET /game` — Spelpagina
- `POST /api/roll` — Gooi dobbelstenen
- `POST /api/select` — Kies waarde om te houden
- `POST /api/end_turn` — Beëindig beurt + pak steen

**Online multiplayer routes:**
- `GET /online` — Online lobby
- `POST /api/room/create` — Nieuwe kamer (6-char code)
- `POST /api/room/join` — Joinen met kamercode
- `GET /api/room/state` — Kamerstatus ophalen (polling)
- `POST /api/room/start` — Host start het spel
- `POST /api/room/roll/select/end_turn` — Spelacties kamerbreed

**Extra functies:**
- Browser opent automatisch bij starten (`webbrowser` + `threading.Timer`)
- ngrok tunnel voor tijdelijk online delen (zie STAP 9)
- Cloud-ready voor Render.com (zie STAP 10)

---

### STAP 4 — Tobii / Eye Tracking Module
**Bestand:** `static/js/tobii.js`
**Wat:** Universele input-module met drie niveaus.

**Prioriteitsvolgorde:**
1. **Tobii SDK** (`window.EyeTracking`) — professioneel hardware
2. **WebGazer.js** — webcam-gebaseerd als Tobii ontbreekt
3. **Muis fallback** — altijd beschikbaar voor ontwikkeling/testen

**Dwell engine:**
- Dwell tijd: **10.000ms (10 seconden)** — aangepast voor K.
- Exponential smoothing op gaze coördinaten
- Visuele progressiebalk op elke knop tijdens dwell
- Visuele ring-indicator rondom het doel-element
- MutationObserver voor dynamisch toegevoegde knoppen
- Elk element met class `gaze-btn` of `data-gaze="true"` reageert automatisch

---

### STAP 5 — CSS Thema
**Bestand:** `static/css/main.css`
**Ontwerpdoelen:**
- Vrolijk, kleurrijk, niet-medisch uiterlijk
- Grote knoppen (min 140px) voor nauwkeurige oogbesturing
- Hoog contrast tekst
- Animaties: dobbelsteen gooi-animatie, confetti bij winst

**Kleuren:**
```
--primary    #FF6B35  — oranje (knoppen, actieve speler)
--secondary  #4ECDC4  — teal (waardeknoppen, online)
--accent     #FFE66D  — geel (gehouden dobbelstenen, scores)
--bg         #1A1A2E  — donkerblauw (achtergrond)
--success    #6BCF7F  — groen (steen gepakt)
--danger     #FF4757  — rood (bust, foutmeldingen)
--worm       #8BC34A  — groen (worm dobbelstenen)
```

**Lettertypes:**
- `Fredoka One` — koppen en knoppen (vrolijk, rond)
- `Nunito` — bodytekst (goed leesbaar)

---

### STAP 6 — Spelregels Pagina
**Bestand:** `templates/rules.html`
**Inhoud:**
- Visuele uitleg van dobbelsteenzijden en steenwaarden
- Stap-voor-stap beurt uitleg in het Nederlands
- Uitleg van speciale situaties (bust, stelen)
- Bediening uitleg (Tobii, hoofd, muis)
- Grote terugknop (160px breed, 64px hoog)

---

### STAP 7 — Online Kamer Systeem
**Bestanden:** `online.html`, `room_game.html`
**Flow:**
1. Host maakt kamer aan → krijgt 6-karakter code (bijv. `AB12CD`)
2. Anderen joinen via dezelfde code
3. Host drukt op "Spel Starten!"
4. Alle clients zien dezelfde spelstatus via polling (elke 800ms)
5. Alleen de actieve speler ziet actieknoppen
6. Niet-actieve spelers zien "Wacht op [naam]..."

---

### STAP 8 — Naam gewijzigd
**Pickomino → Regenwormen** overal zichtbaar:
- Browsertab, logo, knoppen, spelregels, terminal output
- Alle 6 HTML-bestanden + app.py bijgewerkt

---

### STAP 9 — ngrok Online Delen
**Bestand:** `app.py` (onderaan)
**Wat:** Tijdelijke publieke link zonder server.

**Optie 1 — Geen account (willekeurige link per sessie):**
```python
USE_NGROK = True
TOKEN     = ""
DOMAIN    = ""
```
```bash
pip install pyngrok
python app.py
# Terminal toont: https://a3f9-84-12.ngrok-free.app/online
```

**Optie 2 — Gratis account (vaste link elke sessie):**
1. Account maken op ngrok.com
2. Authtoken kopiëren van dashboard.ngrok.com
3. Domeinnaam kiezen op dashboard.ngrok.com/domains
4. Invullen in `app.py`:
```python
USE_NGROK = True
TOKEN     = "jouw_token_hier"
DOMAIN    = "regenwormen.ngrok-free.app"
```

**Nadeel:** Python moet actief blijven zolang vrienden meespelen.

---

### STAP 10 — Render.com Deployment (permanente link)
**Bestanden:** `render.yaml`, `requirements.txt`, `app.py`
**Wat:** Spel draait 24/7 in de cloud zonder Python open te houden.

**Eenmalige setup:**
1. **GitHub account** aanmaken op github.com
2. **Repository aanmaken** → `regenwormen` → alle bestanden uploaden
3. **Render account** aanmaken op render.com → Sign up with GitHub
4. **New Web Service** → selecteer repository → Deploy
5. Wacht ~2 minuten → permanente link verschijnt

**Resultaat:**
```
https://regenwormen.onrender.com        — spel
https://regenwormen.onrender.com/online — online lobby voor vrienden
```

**Let op:** gratis Render plan "slaapt" na 15 min inactiviteit. Eerste keer openen duurt ~30 seconden.

---

### STAP 11 — Game Layout (Option B)
**Bestand:** `templates/game.html`
**Wat:** Volledig scherm benut met twee-kolom layout.

**Layout:**
- **Links (25vw):** Vaste sidebar met spelverloop (log) en spelerscores
- **Rechts boven (75vw, scrollbaar):** Dobbelstenen, stenen, score
- **Rechts onder (vastgepind):** Grote actieknoppen altijd zichtbaar
- **Zoom: 1.75** — alles 75% groter voor betere leesbaarheid op Tobii scherm

---

### STAP 12 — Beurtaankondiging
**Bestand:** `templates/game.html`, `templates/room_game.html`
**Wat:** Volledig scherm overlay tussen beurten.
- Toont naam van volgende speler groot in beeld
- Grote "Ik ben er klaar voor!" knop (werkt met oogbesturing)
- Verdwijnt automatisch na 5 seconden als fallback

---

### STAP 13 — Volledig Scherm Knop
**Bestand:** `templates/game.html`
**Wat:** Kleine `⛶` knop rechtsonder in beeld.
- Klik/blik opent echte browser fullscreen (geen browserbalk)
- Klik opnieuw om te sluiten
- Verandert naar `✕` in fullscreen modus

---

### STAP 14 — Startpagina opgeschoond
**Bestand:** `templates/index.html`
**Wat:** Zwevende/springende worm emoji boven de titel verwijderd.
- Startpagina toont nu direct de titel "Regenwormen"
- Rustiger en overzichtelijker voor gebruiker

---

### STAP 15 — Knoppen vergroot
**Bestanden:** `templates/game.html`, `templates/rules.html`, `templates/online.html`
**Wat:** Navigatieknoppen groter gemaakt voor betere oogbesturing.
- Regels + Stop knoppen in navbar: `52px` hoog, `120px` breed
- Terugknop in spelregels en online pagina: `64px` hoog, `160px` breed
- Navbar hoogte verhoogd naar `72px`

---

## 🚀 HOE TE STARTEN (lokaal)

```bash
# 1. Installeer dependencies
pip install flask

# 2. Start de server (browser opent automatisch)
python app.py

# 3. Of met ngrok online delen
pip install pyngrok
python app.py
```

---

## ⚙️ AANPASSEN VOOR THERAPEUTEN

Open `config.json` en pas aan:

| Instelling | Wat het doet | Huidig |
|---|---|---|
| `accessibility.dwell_time_ms` | Hoe lang kijken om te klikken | 10000 (10 sec) |
| `accessibility.button_min_size_px` | Minimale knopgrootte | 140 |
| `accessibility.font_scale` | Tekstvergroting | 1.4 |
| `tobii.enabled` | Tobii SDK aan/uit | true |
| `tobii.fallback_to_mouse` | Muis fallback | true |
| `tobii.gaze_cursor_color` | Kleur gaze cursor | #FF6B35 |
| `players.default_names` | Standaard spelernamen | ["K.", ...] |

---

## 🔬 TOEKOMSTIGE VERBETERINGEN (buiten scope)

- [ ] Tobii WebSocket SDK directe hardware koppeling
- [ ] Spraaksynthese bij elke actie (Web Speech API)
- [ ] Statistieken per speler over meerdere sessies bewaren
- [ ] Meer spellen toevoegen (Yahtzee, Mexicaan Train) met zelfde engine
- [ ] Calibratiewizard voor Tobii oogpunten
- [ ] Adaptieve dwell tijd op basis van succespercentage

---

## 📚 BRONNEN

- Regenwormen spelregels: Zoch Verlag (originele editie)
- MACS classificatie: Manual Ability Classification System
- Tobii Web SDK: https://developer.tobii.com/
- WebGazer.js: https://webgazer.cs.brown.edu/
- Rijndam onderzoek: Dobbelstenen Challenge praktijkleerplan (Rowan Croon, 2026)
- Referentie implementatie: https://niels-mbh.github.io/Regenwormen/
- CIV Welzijn & Zorg Experimenteerhuis: https://civ-welzijnenzorg.nl/project/experimenteerhuis-zoetermeer/

---

*Log bijgehouden door: Claude Sonnet 4.6*
*Project: Dobbelstenen Challenge — De Haagse Hogeschool × Rijndam Revalidatie*
*Laatste update: Juli 2026*
