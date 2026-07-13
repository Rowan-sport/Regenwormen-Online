"""
game_logic.py — Pickomino (Regenwormen) Core Game Engine
=========================================================
Pure game logic, no UI dependencies. Fully adjustable.

Rules of Pickomino:
- 8 dice, faces 1–5 + worm (worth 5 points)
- Tiles numbered 21–36, each showing worm value (1–4 worms)
- On your turn: roll all dice, pick a value group, set aside, roll rest
- Must always take ALL dice of chosen value
- Cannot pick same value twice in one turn
- MUST include at least one worm face to end turn
- Score = sum of kept dice; take highest available tile <= score
- If you can't take a tile, lose your top tile (goes back to center face-down)
- Steal: if your score exactly matches another player's top tile, steal it
"""

import random
import json
from typing import List, Optional, Dict, Tuple


WORM_VALUE = 5  # Worm face is worth 5 points
WORM_SYMBOL = "🪱"
DICE_FACES = [1, 2, 3, 4, 5, WORM_VALUE]  # 5 = worm


def tile_worms(tile_number: int) -> int:
    """Return how many worms a tile is worth based on its number."""
    if tile_number <= 24:
        return 1
    elif tile_number <= 28:
        return 2
    elif tile_number <= 32:
        return 3
    else:
        return 4


def dice_face_label(value: int) -> str:
    """Return display label for a dice face value."""
    return WORM_SYMBOL if value == WORM_VALUE else str(value)


class Die:
    def __init__(self):
        self.value: int = 1
        self.held: bool = False

    def roll(self):
        self.value = random.choice(DICE_FACES)

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "held": self.held,
            "label": dice_face_label(self.value)
        }


class Player:
    def __init__(self, player_id: int, name: str):
        self.player_id = player_id
        self.name = name
        self.tile_stack: List[int] = []  # top of stack = last element

    @property
    def top_tile(self) -> Optional[int]:
        return self.tile_stack[-1] if self.tile_stack else None

    @property
    def worm_count(self) -> int:
        return sum(tile_worms(t) for t in self.tile_stack)

    def add_tile(self, tile: int):
        self.tile_stack.append(tile)

    def remove_top_tile(self) -> Optional[int]:
        return self.tile_stack.pop() if self.tile_stack else None

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "name": self.name,
            "tile_stack": self.tile_stack,
            "top_tile": self.top_tile,
            "worm_count": self.worm_count
        }


class TurnState:
    """Tracks everything about the current player's turn."""

    def __init__(self, player_id: int, num_dice: int = 8):
        self.player_id = player_id
        self.dice: List[Die] = [Die() for _ in range(num_dice)]
        self.kept_values: List[int] = []       # values already set aside this turn
        self.current_roll: List[int] = []      # the most recent roll result
        self.score: int = 0
        self.has_worm: bool = False
        self.rolled_at_least_once: bool = False
        self.phase: str = "roll"               # roll | select | end
        self.message: str = "Gooi de dobbelstenen!"
        self.bust: bool = False

    @property
    def free_dice(self) -> List[Die]:
        return [d for d in self.dice if not d.held]

    @property
    def held_dice(self) -> List[Die]:
        return [d for d in self.dice if d.held]

    def available_values_in_roll(self) -> List[int]:
        """Which values can still be chosen from the current roll?"""
        roll_values = set(d.value for d in self.free_dice)
        already_kept = set(self.kept_values)
        return sorted(v for v in roll_values if v not in already_kept)

    def is_bust(self) -> bool:
        """True if no valid selections possible from current roll."""
        return len(self.available_values_in_roll()) == 0

    def roll(self) -> List[int]:
        """Roll all free (non-held) dice."""
        for die in self.free_dice:
            die.roll()
        self.current_roll = [d.value for d in self.free_dice]
        self.rolled_at_least_once = True
        self.phase = "select"

        if self.is_bust():
            self.bust = True
            self.phase = "end"
            self.message = "💥 Geen geldige keuze! Je verliest je bovenste steen."
        else:
            self.message = "Kies een dobbelsteenwaarde om te houden."

        return self.current_roll

    def select_value(self, value: int) -> Tuple[bool, str]:
        """
        Player selects all dice of a given value to keep.
        Returns (success, message).
        """
        if value not in self.available_values_in_roll():
            return False, f"Je kunt {dice_face_label(value)} niet kiezen. Al gekozen of niet gegooid."

        count = sum(1 for d in self.free_dice if d.value == value)
        if count == 0:
            return False, "Die waarde zit niet in je huidige worp."

        # Hold all dice of this value
        for die in self.free_dice:
            if die.value == value:
                die.held = True

        self.kept_values.append(value)
        self.score += value * count
        if value == WORM_VALUE:
            self.has_worm = True

        self.phase = "roll"
        remaining = len(self.free_dice)
        if remaining == 0:
            self.phase = "end"
            self.message = f"Alle dobbelstenen gehouden! Score: {self.score}. Bevestig je beurt."
        else:
            self.message = f"✅ {count}× {dice_face_label(value)} gehouden. Gooi opnieuw of beëindig je beurt."

        return True, self.message

    def can_end_turn(self) -> bool:
        return self.has_worm and self.rolled_at_least_once and not self.bust

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "dice": [d.to_dict() for d in self.dice],
            "kept_values": [dice_face_label(v) for v in self.kept_values],
            "kept_values_raw": self.kept_values,
            "score": self.score,
            "has_worm": self.has_worm,
            "phase": self.phase,
            "message": self.message,
            "bust": self.bust,
            "rolled_at_least_once": self.rolled_at_least_once,
            "available_values": self.available_values_in_roll(),
            "can_end_turn": self.can_end_turn(),
            "free_dice_count": len(self.free_dice),
            "held_dice_count": len(self.held_dice)
        }


class PicominoGame:
    """
    Main game controller for Pickomino (Regenwormen).
    Fully serializable to/from dict for Flask session storage.
    """

    def __init__(self, player_names: List[str], num_dice: int = 8,
                 tile_min: int = 21, tile_max: int = 36):
        self.players: List[Player] = [
            Player(i, name) for i, name in enumerate(player_names)
        ]
        self.num_dice = num_dice
        self.tile_min = tile_min
        self.tile_max = tile_max

        # All available tiles in the center
        self.center_tiles: List[int] = list(range(tile_min, tile_max + 1))
        self.removed_tiles: List[int] = []  # face-down, out of game

        self.current_player_index: int = 0
        self.turn: TurnState = TurnState(0, num_dice)
        self.game_over: bool = False
        self.winner: Optional[str] = None
        self.round_number: int = 1
        self.log: List[str] = []

        self._log(f"🎮 Spel gestart met {len(self.players)} spelers!")

    def _log(self, msg: str):
        self.log.append(msg)
        if len(self.log) > 100:
            self.log = self.log[-100:]

    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_index]

    def roll_dice(self) -> dict:
        """Current player rolls free dice."""
        if self.turn.phase != "roll":
            return {"success": False, "message": "Je kunt nu niet gooien."}

        result = self.turn.roll()
        self._log(f"🎲 {self.current_player.name} gooit: {[dice_face_label(v) for v in result]}")

        if self.turn.bust:
            return {"success": True, "bust": True, "message": self.turn.message,
                    "state": self.get_state()}
        return {"success": True, "bust": False, "message": self.turn.message,
                "state": self.get_state()}

    def select_value(self, value: int) -> dict:
        """Current player selects a value from the roll."""
        if self.turn.phase != "select":
            return {"success": False, "message": "Je moet eerst gooien."}

        success, message = self.turn.select_value(value)
        if success:
            self._log(f"✋ {self.current_player.name} houdt alle {dice_face_label(value)}'s. Score nu: {self.turn.score}")
        return {"success": success, "message": message, "state": self.get_state()}

    def end_turn(self) -> dict:
        """Current player ends their turn and tries to claim a tile."""
        if not self.turn.can_end_turn():
            if self.turn.bust:
                return self._resolve_bust()
            return {"success": False, "message": "Je moet minstens één worm hebben en één keer gooien."}

        score = self.turn.score
        claimed_tile = None
        stole_from = None
        message = ""

        # Check steal: exact match with another player's top tile
        for player in self.players:
            if player.player_id != self.current_player.player_id:
                if player.top_tile == score:
                    stolen = player.remove_top_tile()
                    self.current_player.add_tile(stolen)
                    claimed_tile = stolen
                    stole_from = player.name
                    self._log(f"🥷 {self.current_player.name} steelt steen {stolen} van {player.name}!")
                    message = f"🥷 Gestolen! Steen {stolen} gepakt van {player.name}!"
                    break

        # If no steal, take highest available center tile <= score
        if claimed_tile is None:
            eligible = [t for t in self.center_tiles if t <= score]
            if eligible:
                tile = max(eligible)
                self.center_tiles.remove(tile)
                self.current_player.add_tile(tile)
                claimed_tile = tile
                self._log(f"🏆 {self.current_player.name} pakt steen {tile} (score: {score})")
                message = f"🏆 Steen {tile} gepakt! ({tile_worms(tile)} worm{'s' if tile_worms(tile)>1 else ''})"
            else:
                # Can't take a tile — lose top tile
                message = self._penalize_player()

        self._advance_turn()
        self._check_game_over()

        result = {"success": True, "claimed_tile": claimed_tile, "stole_from": stole_from,
                  "message": message, "state": self.get_state()}
        return result

    def _resolve_bust(self) -> dict:
        """Player busted — lose top tile."""
        message = self._penalize_player()
        self._advance_turn()
        self._check_game_over()
        return {"success": True, "bust": True, "message": message, "state": self.get_state()}

    def _penalize_player(self) -> str:
        """
        Official Regenwormen penalty rule:
        1. Player top tile goes back to center face-up.
        2. Highest tile in center is removed permanently (face-down, out of game).
        """
        returned_tile = self.current_player.remove_top_tile()
        msg_parts = []

        # Step 1: return player top tile to center face-up
        if returned_tile is not None:
            self.center_tiles.append(returned_tile)
            self.center_tiles.sort()
            self._log(f"\u21a9\ufe0f {self.current_player.name} legt steen {returned_tile} terug in het midden.")
            msg_parts.append(f"\u21a9\ufe0f Steen {returned_tile} terug in het midden.")
        else:
            self._log(f"\U0001f62c {self.current_player.name} heeft geen steen om terug te leggen.")
            msg_parts.append(f"\U0001f62c Geen steen om terug te leggen.")

        # Step 2: remove highest center tile permanently (face-down)
        if self.center_tiles:
            highest = max(self.center_tiles)
            self.center_tiles.remove(highest)
            self.removed_tiles.append(highest)
            self._log(f"\u274c Hoogste steen {highest} uit het midden verwijderd (omgedraaid).")
            msg_parts.append(f"\u274c Steen {highest} omgedraaid en uit het spel.")

        return " ".join(msg_parts)

    def _advance_turn(self):
        """Move to next player."""
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self.turn = TurnState(self.current_player_index, self.num_dice)
        if self.current_player_index == 0:
            self.round_number += 1
        self._log(f"➡️ Beurt van {self.current_player.name}")

    def _check_game_over(self):
        """Game ends when center tiles are all gone."""
        if not self.center_tiles:
            self.game_over = True
            # Winner = most worms
            ranked = sorted(self.players, key=lambda p: p.worm_count, reverse=True)
            self.winner = ranked[0].name
            self._log(f"🎉 Spel voorbij! Winnaar: {self.winner} met {ranked[0].worm_count} wormen!")

    def get_state(self) -> dict:
        """Full serializable game state for the frontend."""
        return {
            "players": [p.to_dict() for p in self.players],
            "center_tiles": self.center_tiles,
            "removed_tiles": self.removed_tiles,
            "current_player_index": self.current_player_index,
            "current_player_name": self.current_player.name,
            "turn": self.turn.to_dict(),
            "game_over": self.game_over,
            "winner": self.winner,
            "round_number": self.round_number,
            "log": self.log[-10:],
            "tile_worms": {str(t): tile_worms(t) for t in range(self.tile_min, self.tile_max + 1)}
        }
