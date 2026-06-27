"""
Engine interface + built-in players.

Every player — human or AI — is an Engine subclass.
The game controller calls get_move() each turn; human players return None
(meaning "wait for UI input"), engines return a Move immediately.

To add a new engine later:
  1. Subclass Engine
  2. Implement get_move(board) -> Move
  3. Append to AVAILABLE_ENGINES
"""

from __future__ import annotations
import random
from board import Board, Move


class Engine:
    """Abstract base for all players."""
    name:  str = "Unknown"
    elo:   int = 0
    style: str = ""

    def get_move(self, board: Board) -> Move | None:
        """
        Return the chosen Move, or None if this player is human
        (the UI will handle input instead).
        """
        raise NotImplementedError

    def is_human(self) -> bool:
        return False

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name!r})"


# ── Human ─────────────────────────────────────────────────────────────────────

class HumanPlayer(Engine):
    name  = "Human"
    elo   = 0
    style = "—"

    def get_move(self, board: Board) -> None:
        return None         # UI drives input

    def is_human(self) -> bool:
        return True


# ── Random engine (placeholder) ───────────────────────────────────────────────

class RandomEngine(Engine):
    """
    Picks a uniformly random legal move.
    Useful as a baseline and for testing — no chess knowledge whatsoever.
    """
    name  = "Random Bot"
    elo   = 200
    style = "Chaotic"

    def get_move(self, board: Board) -> Move | None:
        moves = board.get_all_legal_moves(board.turn)
        return random.choice(moves) if moves else None


# ── Registry ──────────────────────────────────────────────────────────────────
# The menu reads this list to populate the engine selection.
# Add new Engine subclasses here when they're ready.

AVAILABLE_ENGINES: list[type[Engine]] = [
    RandomEngine,
    # AggressiveEngine,   ← coming soon
    # PositionalEngine,   ← coming soon
    # StockfishEngine,    ← coming soon
]
