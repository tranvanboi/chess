"""
Game controller — owns the state machine that sits between UI and Board.

State machine per half-turn (human):
  IDLE → (click own piece) → PIECE_SELECTED → (click legal square) → move executes
       ↑_____________________________(click same or different own piece)____________|

Engine turns bypass the click state machine entirely:
  UI calls needs_engine_move() each frame → True → UI calls do_engine_move()
"""

from __future__ import annotations
from enum import Enum, auto
from board import Board, Move, rf_to_sq
from constants import WHITE, BLACK, W_QUEEN, B_QUEEN, EMPTY


class GameStatus(Enum):
    ONGOING    = auto()
    CHECK      = auto()
    CHECKMATE  = auto()
    STALEMATE  = auto()
    DRAW_50    = auto()


class SelectionState(Enum):
    IDLE     = auto()
    SELECTED = auto()   # a piece has been clicked, legal moves are highlighted


class Game:
    def __init__(self, white=None, black=None):
        # Import here to avoid circular imports at module level
        from engine import HumanPlayer
        self.board             = Board()
        self.white             = white or HumanPlayer()
        self.black             = black or HumanPlayer()
        self.status            = GameStatus.ONGOING
        self.sel_state         = SelectionState.IDLE
        self.selected_sq: int | None   = None
        self.legal_moves: list[Move]   = []
        self.history:     list[Move]   = []

    # ── Engine turn API ───────────────────────────────────────────────────────

    def current_player(self):
        return self.white if self.board.turn == WHITE else self.black

    def needs_engine_move(self) -> bool:
        """True when it's an engine's turn and the game is still going."""
        return (
            self.status in (GameStatus.ONGOING, GameStatus.CHECK)
            and not self.current_player().is_human()
        )

    def do_engine_move(self):
        """Ask the current engine for its move and execute it."""
        move = self.current_player().get_move(self.board)
        if move:
            self._execute(move)
            self._deselect()

    # ── Public API called by the UI ───────────────────────────────────────────

    def on_square_clicked(self, sq: int) -> bool:
        """
        Process a click on board square sq.
        Returns True if a move was executed this click.
        """
        if self.status in (GameStatus.CHECKMATE, GameStatus.STALEMATE, GameStatus.DRAW_50):
            return False

        b = self.board
        piece = b.squares[sq]

        if self.sel_state == SelectionState.IDLE:
            # Try to select a piece
            if piece != EMPTY and b.color_of(piece) == b.turn:
                self._select(sq)
            return False

        # SELECTED state: try to move, re-select, or deselect
        move = self._find_move(sq)
        if move:
            self._execute(move)
            self._deselect()
            return True

        # Clicked own piece → re-select it
        if piece != EMPTY and b.color_of(piece) == b.turn:
            self._select(sq)
            return False

        # Clicked empty / enemy square that isn't a legal target → deselect
        self._deselect()
        return False

    def legal_targets(self) -> list[int]:
        """Square indices the currently selected piece may move to."""
        return [m.to_sq for m in self.legal_moves]

    def status_text(self) -> str:
        turn   = "White" if self.board.turn == WHITE else "Black"
        player = self.current_player()
        label  = f"{turn} ({player.name})"
        if self.status == GameStatus.CHECKMATE:
            winner = "Black" if self.board.turn == WHITE else "White"
            w_player = self.black if self.board.turn == WHITE else self.white
            return f"Checkmate — {winner} ({w_player.name}) wins!"
        if self.status == GameStatus.STALEMATE:
            return "Stalemate — Draw"
        if self.status == GameStatus.DRAW_50:
            return "Draw by 50-move rule"
        if self.status == GameStatus.CHECK:
            return f"{label} is in Check!"
        return f"{label} to move"

    def matchup_text(self) -> str:
        """One-line summary shown in the header, e.g. 'Human vs Random Bot'."""
        return f"{self.white.name}  vs  {self.black.name}"

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _select(self, sq: int):
        self.selected_sq = sq
        self.legal_moves = self.board.get_legal_moves(sq)
        self.sel_state   = SelectionState.SELECTED

    def _deselect(self):
        self.selected_sq = None
        self.legal_moves = []
        self.sel_state   = SelectionState.IDLE

    def _find_move(self, to_sq: int) -> Move | None:
        """Return the legal move going to to_sq, auto-picking queen for promotions."""
        candidates = [m for m in self.legal_moves if m.to_sq == to_sq]
        if not candidates:
            return None
        promos = [m for m in candidates if m.promotion]
        if promos:
            queen = W_QUEEN if self.board.turn == WHITE else B_QUEEN
            for m in promos:
                if m.promotion == queen:
                    return m
            return promos[0]   # fallback (shouldn't happen)
        return candidates[0]

    def _execute(self, move: Move):
        self.board.make_move(move)
        self.history.append(move)
        self._update_status()

    def _update_status(self):
        b = self.board
        if b.halfmove_clock >= 100:
            self.status = GameStatus.DRAW_50
            return
        has_moves = bool(b.get_all_legal_moves(b.turn))
        in_check  = b.in_check(b.turn)
        if not has_moves:
            self.status = GameStatus.CHECKMATE if in_check else GameStatus.STALEMATE
        elif in_check:
            self.status = GameStatus.CHECK
        else:
            self.status = GameStatus.ONGOING
