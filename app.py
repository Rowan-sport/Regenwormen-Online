"""
app.py — Flask Web Server for Regenwormen (Regenwormen)
=====================================================
Features:
  - REST API for single/local game
  - Room-based online multiplayer via long-polling (no extra packages)
  - Tobii-first with mouse fallback
  - All settings adjustable via config.json

Run:  python app.py
Open: http://localhost:5000
"""

from flask import (Flask, render_template, session, jsonify,
                   request, redirect, url_for, Response)
from game_logic import PicominoGame
import json, os, uuid, time, threading

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "Regenwormen-rijndam-2025")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

# ── In-memory room store (for online multiplayer) ───────────────────────────
# Structure: { room_code: { "game": PicominoGame, "players": [...], "lock": Lock,
#              "version": int, "created": timestamp } }
ROOMS: dict = {}
ROOMS_LOCK = threading.Lock()

def cleanup_old_rooms():
    """Remove rooms older than 4 hours."""
    now = time.time()
    with ROOMS_LOCK:
        stale = [k for k, v in ROOMS.items() if now - v["created"] > 14400]
        for k in stale:
            del ROOMS[k]

# ── Helpers ─────────────────────────────────────────────────────────────────

def _reconstruct_game(state: dict) -> PicominoGame:
    from game_logic import Player, TurnState, Die
    game = PicominoGame.__new__(PicominoGame)
    m = state["meta"]
    game.center_tiles  = m["center_tiles"]
    game.removed_tiles = m["removed_tiles"]
    game.current_player_index = m["current_player_index"]
    game.num_dice      = m["num_dice"]
    game.tile_min      = m["tile_min"]
    game.tile_max      = m["tile_max"]
    game.game_over     = m["game_over"]
    game.winner        = m["winner"]
    game.round_number  = m["round_number"]
    game.log           = m["log"]

    game.players = []
    for p in state["players"]:
        pl = Player(p["player_id"], p["name"])
        pl.tile_stack = p["tile_stack"]
        game.players.append(pl)

    ts = state["turn"]
    turn = TurnState.__new__(TurnState)
    turn.player_id           = ts["player_id"]
    turn.kept_values         = ts["kept_values_raw"]
    turn.current_roll        = []
    turn.score               = ts["score"]
    turn.has_worm            = ts["has_worm"]
    turn.rolled_at_least_once = ts["rolled_at_least_once"]
    turn.phase               = ts["phase"]
    turn.message             = ts["message"]
    turn.bust                = ts["bust"]
    turn.dice = []
    for d in ts["dice"]:
        die = Die()
        die.value = d["value"]
        die.held  = d["held"]
        turn.dice.append(die)
    game.turn = turn
    return game

def _serialize_game(game: PicominoGame) -> dict:
    state = game.get_state()
    return {
        "players": state["players"],
        "turn":    state["turn"],
        "meta": {
            "center_tiles":         game.center_tiles,
            "removed_tiles":        game.removed_tiles,
            "current_player_index": game.current_player_index,
            "num_dice":  game.num_dice,
            "tile_min":  game.tile_min,
            "tile_max":  game.tile_max,
            "game_over": game.game_over,
            "winner":    game.winner,
            "round_number": game.round_number,
            "log":       game.log,
        }
    }

def get_game() -> PicominoGame | None:
    if "game_state" not in session:
        return None
    return _reconstruct_game(session["game_state"])

def save_game(game: PicominoGame):
    session["game_state"] = _serialize_game(game)
    session.modified = True

# ── Local game routes ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", config=CONFIG)

@app.route("/rules")
def rules_page():
    return render_template("rules.html", config=CONFIG)

@app.route("/start", methods=["POST"])
def start_game():
    data = request.get_json()
    names = [n.strip() for n in data.get("players", ["K.", "Speler 2"]) if n.strip()]
    if not names:
        names = ["K."]
    game = PicominoGame(names,
                        num_dice=CONFIG["game"]["num_dice"],
                        tile_min=CONFIG["game"]["tile_min"],
                        tile_max=CONFIG["game"]["tile_max"])
    save_game(game)
    return jsonify({"success": True, "state": game.get_state()})

@app.route("/game")
def game_page():
    if "game_state" not in session:
        return redirect(url_for("index"))
    return render_template("game.html", config=CONFIG)

@app.route("/api/state")
def api_state():
    game = get_game()
    if not game:
        return jsonify({"error": "No game"}), 404
    return jsonify(game.get_state())

@app.route("/api/roll", methods=["POST"])
def api_roll():
    game = get_game()
    if not game:
        return jsonify({"error": "No game"}), 404
    result = game.roll_dice()
    save_game(game)
    return jsonify(result)

@app.route("/api/select", methods=["POST"])
def api_select():
    game = get_game()
    if not game:
        return jsonify({"error": "No game"}), 404
    value = int(request.get_json().get("value", 0))
    result = game.select_value(value)
    save_game(game)
    return jsonify(result)

@app.route("/api/end_turn", methods=["POST"])
def api_end_turn():
    game = get_game()
    if not game:
        return jsonify({"error": "No game"}), 404
    result = game.end_turn()
    save_game(game)
    return jsonify(result)

@app.route("/api/config")
def api_config():
    return jsonify(CONFIG)

@app.route("/api/reset", methods=["POST"])
def api_reset():
    session.clear()
    return jsonify({"success": True})

# ── Online multiplayer routes ────────────────────────────────────────────────

@app.route("/online")
def online_lobby():
    return render_template("online.html", config=CONFIG)

@app.route("/api/room/create", methods=["POST"])
def create_room():
    cleanup_old_rooms()
    data = request.get_json()
    host_name = (data.get("name") or "Speler 1").strip()[:30]
    code = str(uuid.uuid4())[:6].upper()
    with ROOMS_LOCK:
        ROOMS[code] = {
            "players": [{"name": host_name, "ready": False, "session": session.get("sid", str(uuid.uuid4()))}],
            "game_serial": None,
            "game": None,
            "version": 0,
            "created": time.time(),
            "started": False,
            "lock": threading.Lock()
        }
    session["room"] = code
    session["player_name"] = host_name
    session["sid"] = session.get("sid", str(uuid.uuid4()))
    return jsonify({"success": True, "code": code})

@app.route("/api/room/join", methods=["POST"])
def join_room():
    data = request.get_json()
    code = (data.get("code") or "").upper().strip()
    name = (data.get("name") or "Speler").strip()[:30]
    with ROOMS_LOCK:
        if code not in ROOMS:
            return jsonify({"success": False, "message": "Kamer niet gevonden."}), 404
        room = ROOMS[code]
        if room["started"]:
            return jsonify({"success": False, "message": "Spel al begonnen."}), 400
        if len(room["players"]) >= CONFIG["game"]["max_players"]:
            return jsonify({"success": False, "message": "Kamer is vol."}), 400
        sid = str(uuid.uuid4())
        room["players"].append({"name": name, "ready": False, "session": sid})
        room["version"] += 1
    session["room"] = code
    session["player_name"] = name
    session["sid"] = sid
    return jsonify({"success": True, "code": code})

@app.route("/api/room/state")
def room_state():
    code = session.get("room")
    if not code or code not in ROOMS:
        return jsonify({"error": "Not in a room"}), 404
    room = ROOMS[code]
    gs = None
    if room["game"]:
        gs = room["game"].get_state()
    return jsonify({
        "code": code,
        "players": room["players"],
        "started": room["started"],
        "version": room["version"],
        "game_state": gs
    })

@app.route("/api/room/start", methods=["POST"])
def start_room_game():
    code = session.get("room")
    if not code or code not in ROOMS:
        return jsonify({"error": "Not in a room"}), 404
    room = ROOMS[code]
    with room["lock"]:
        names = [p["name"] for p in room["players"]]
        room["game"] = PicominoGame(names,
                                    num_dice=CONFIG["game"]["num_dice"],
                                    tile_min=CONFIG["game"]["tile_min"],
                                    tile_max=CONFIG["game"]["tile_max"])
        room["started"] = True
        room["version"] += 1
    return jsonify({"success": True})

@app.route("/room/game")
def room_game_page():
    if "room" not in session:
        return redirect(url_for("online_lobby"))
    return render_template("room_game.html", config=CONFIG)

@app.route("/api/room/roll", methods=["POST"])
def room_roll():
    code = session.get("room")
    if not code or code not in ROOMS:
        return jsonify({"error": "No room"}), 404
    room = ROOMS[code]
    with room["lock"]:
        result = room["game"].roll_dice()
        room["version"] += 1
    return jsonify(result)

@app.route("/api/room/select", methods=["POST"])
def room_select():
    code = session.get("room")
    if not code or code not in ROOMS:
        return jsonify({"error": "No room"}), 404
    room = ROOMS[code]
    value = int(request.get_json().get("value", 0))
    with room["lock"]:
        result = room["game"].select_value(value)
        room["version"] += 1
    return jsonify(result)

@app.route("/api/room/end_turn", methods=["POST"])
def room_end_turn():
    code = session.get("room")
    if not code or code not in ROOMS:
        return jsonify({"error": "No room"}), 404
    room = ROOMS[code]
    with room["lock"]:
        result = room["game"].end_turn()
        room["version"] += 1
    return jsonify(result)

# ── ngrok tunnel helper ─────────────────────────────────────────────────────

def start_ngrok(port: int, token: str = None, domain: str = None) -> str | None:
    """
    Try to start an ngrok tunnel and return the public URL.

    Option 1 — No account:
        start_ngrok(5000)

    Option 2 — Free account with fixed domain:
        start_ngrok(5000, token="your_token_here", domain="your-name.ngrok-free.app")

    Returns the public URL string, or None if ngrok is not available.
    """
    try:
        from pyngrok import ngrok as pyngrok, conf
        if token:
            conf.get_default().auth_token = token
        if domain:
            tunnel = pyngrok.connect(port, domain=domain)
        else:
            tunnel = pyngrok.connect(port)
        return tunnel.public_url.replace("http://", "https://")
    except ImportError:
        return None
    except Exception as e:
        print(f"[ngrok] Kon tunnel niet starten: {e}")
        return None


def print_share_banner(local_url: str, public_url: str = None):
    """Print a clear startup banner with sharing instructions."""
    print()
    print("=" * 58)
    print("  🪱  REGENWORMEN — GESTART!")
    print("=" * 58)
    print(f"  💻  Lokaal (jij):     {local_url}")
    if public_url:
        print(f"  🌐  Online (vrienden): {public_url}")
        print()
        print("  📱  Stuur deze link naar vrienden via WhatsApp:")
        print(f"      {public_url}/online")
        print()
        print("  ℹ️   Vrienden gaan naar de link, klikken 'Joinen',")
        print("      en voeren jouw kamerkode in.")
    else:
        print()
        print("  ℹ️   Tip: installeer pyngrok voor online delen:")
        print("      pip install pyngrok")
        print("      Zie de comments in app.py voor setup.")
    print("=" * 58)
    print()


if __name__ == "__main__":
    import webbrowser, threading

    PORT = int(os.environ.get("PORT", 5000))
    IS_CLOUD = os.environ.get("RENDER") or os.environ.get("CLOUD")
    local_url = f"http://localhost:{PORT}"

    # ── NGROK CONFIGURATIE ───────────────────────────────────────────────────
    # Kies één van de onderstaande opties:

    # OPTIE 1: Geen account, willekeurige link elke sessie
    # Zet USE_NGROK = True en laat TOKEN en DOMAIN leeg.

    # OPTIE 2: Gratis account, vaste link elke sessie
    # 1. Maak een gratis account op https://ngrok.com
    # 2. Kopieer je authtoken van https://dashboard.ngrok.com/get-started/your-authtoken
    # 3. Kies een domeinnaam op https://dashboard.ngrok.com/domains (bijv. regenwormen.ngrok-free.app)
    # 4. Vul TOKEN en DOMAIN hieronder in en zet USE_NGROK = True

    USE_NGROK = True          # Zet op False om ngrok uit te zetten
    TOKEN     = ""            # Optie 2: plak hier je ngrok authtoken
    DOMAIN    = ""            # Optie 2: plak hier je vaste domeinnaam

    # ────────────────────────────────────────────────────────────────────────

    public_url = None
    if USE_NGROK and not IS_CLOUD:
        print("🔌 ngrok tunnel starten...")
        public_url = start_ngrok(
            PORT,
            token=TOKEN if TOKEN else None,
            domain=DOMAIN if DOMAIN else None
        )
        if not public_url:
            print("⚠️  ngrok niet gevonden. Installeer met: pip install pyngrok")

    if not IS_CLOUD:
        print_share_banner(local_url, public_url)
        open_url = public_url if public_url else local_url
        threading.Timer(1.5, lambda: webbrowser.open(open_url)).start()
    else:
        print(f"🪱 Regenwormen draait in de cloud op poort {PORT}")

    app.run(debug=False, host="0.0.0.0", port=PORT, threaded=True, use_reloader=False)
