"""
10×12 mailbox board + piece list + full move generation.

Two representations kept in sync at all times:

  squares: list[int]  (length 120)
      The mailbox array. Index = (rank+2)*10 + (file+1).
      Padding cells hold OFFBOARD (99); empty real squares hold EMPTY (0).
      Fast for move generation: probe neighbours with fixed offsets,
      bail out when you see OFFBOARD.

  piece_list: dict[int, list[int]]
      Maps piece_code → [sq, sq, …].
      Fast for iteration: engines and eval don't scan all 64 squares —
      they just loop over piece_list[W_PAWN], piece_list[B_ROOK], etc.
      Also gives O(1) king lookup: piece_list[W_KING][0].

Every _apply() and _undo() updates both structures together.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from constants import *


# ── Index helpers ─────────────────────────────────────────────────────────────

def rf_to_sq(rank: int, file: int) -> int:
    """0-indexed rank/file → mailbox index."""
    return (rank + 2) * 10 + (file + 1)

def sq_to_rf(sq: int) -> tuple[int, int]:
    """Mailbox index → (rank, file), both 0-indexed."""
    return sq // 10 - 2, sq % 10 - 1

def sq_name(sq: int) -> str:
    rank, file = sq_to_rf(sq)
    return "abcdefgh"[file] + str(rank + 1)


# ── Move object ───────────────────────────────────────────────────────────────

@dataclass
class Move:
    from_sq:   int
    to_sq:     int
    piece:     int              # piece that moved
    captured:  int = EMPTY      # piece on to_sq before the move (EMPTY if none)
    promotion: int = EMPTY      # piece code to promote to (EMPTY if not a promotion)

    is_castle:        bool = False
    castle_rook_from: int  = 0
    castle_rook_to:   int  = 0

    is_en_passant:  bool = False
    ep_captured_sq: int  = 0    # square of the pawn removed by en passant

    # ── Snapshot fields saved by _apply so _undo can restore them ────────────
    prev_ep_sq:      Optional[int] = field(default=None, repr=False)
    prev_castle_wk:  bool = field(default=True,  repr=False)
    prev_castle_wq:  bool = field(default=True,  repr=False)
    prev_castle_bk:  bool = field(default=True,  repr=False)
    prev_castle_bq:  bool = field(default=True,  repr=False)
    prev_halfmove:   int  = field(default=0,     repr=False)


# ── Board ─────────────────────────────────────────────────────────────────────

class Board:
    def __init__(self):
        # ── Mailbox array ─────────────────────────────────────────────────────
        # 120 cells; real squares are rows 2-9 / cols 1-8; padding = OFFBOARD.
        self.squares: list[int] = [OFFBOARD] * 120
        for rank in range(8):
            for file in range(8):
                self.squares[rf_to_sq(rank, file)] = EMPTY

        # ── Piece list ────────────────────────────────────────────────────────
        # piece_list[piece_code] = [sq, sq, …]
        # Kept perfectly in sync with squares by _pl_add / _pl_remove.
        self.piece_list: dict[int, list[int]] = {}

        # ── Game-state flags ──────────────────────────────────────────────────
        self.turn: int            = WHITE
        self.castle_wk: bool      = True
        self.castle_wq: bool      = True
        self.castle_bk: bool      = True
        self.castle_bq: bool      = True
        self.ep_sq: Optional[int] = None
        self.halfmove_clock: int  = 0
        self.fullmove: int        = 1

        self._setup()

    # ── Piece-list helpers ────────────────────────────────────────────────────

    def _pl_add(self, piece: int, sq: int):
        """Register that `piece` now occupies `sq`."""
        if piece not in self.piece_list:
            self.piece_list[piece] = []
        self.piece_list[piece].append(sq)

    def _pl_remove(self, piece: int, sq: int):
        """Remove `sq` from the list for `piece`."""
        lst = self.piece_list[piece]
        lst.remove(sq)
        if not lst:
            del self.piece_list[piece]

    # ── Initialisation ────────────────────────────────────────────────────────

    def _setup(self):
        """Place pieces on both representations simultaneously."""
        self.piece_list.clear()
        back = [W_ROOK, W_KNIGHT, W_BISHOP, W_QUEEN, W_KING,
                W_BISHOP, W_KNIGHT, W_ROOK]
        for file, piece in enumerate(back):
            sq_w = rf_to_sq(0, file)
            sq_b = rf_to_sq(7, file)
            self.squares[sq_w] =  piece
            self.squares[sq_b] = -piece
            self._pl_add( piece, sq_w)
            self._pl_add(-piece, sq_b)
        for file in range(8):
            sq_w = rf_to_sq(1, file)
            sq_b = rf_to_sq(6, file)
            self.squares[sq_w] = W_PAWN
            self.squares[sq_b] = B_PAWN
            self._pl_add(W_PAWN, sq_w)
            self._pl_add(B_PAWN, sq_b)

    # ── Public piece-list queries ─────────────────────────────────────────────

    def get_pieces(self, color: int) -> list[tuple[int, int]]:
        """Return [(piece_code, sq), …] for all pieces of the given colour."""
        signs = range(1, 7) if color == WHITE else range(-1, -7, -1)
        return [(code, sq)
                for code in signs
                for sq   in self.piece_list.get(code, [])]

    def piece_count(self) -> int:
        """Total number of pieces currently on the board (both colours)."""
        return sum(len(sqs) for sqs in self.piece_list.values())

    def piece_count_for(self, color: int) -> int:
        """Number of pieces belonging to one colour."""
        return sum(len(sqs) for code, sqs in self.piece_list.items()
                   if (code > 0) == (color > 0))

    # ── Utility ───────────────────────────────────────────────────────────────

    def color_of(self, piece: int) -> Optional[int]:
        if piece > 0: return WHITE
        if piece < 0: return BLACK
        return None

    def _is_enemy(self, piece: int, color: int) -> bool:
        return piece not in (EMPTY, OFFBOARD) and self.color_of(piece) != color

    def _is_own(self, piece: int, color: int) -> bool:
        return piece not in (EMPTY, OFFBOARD) and self.color_of(piece) == color

    def find_king(self, color: int) -> int:
        """O(1) king lookup via piece list."""
        king = W_KING if color == WHITE else B_KING
        sqs  = self.piece_list.get(king, [])
        return sqs[0] if sqs else -1

    # ── Attack detection ──────────────────────────────────────────────────────

    def is_attacked(self, sq: int, by: int) -> bool:
        """Return True if square sq is attacked by any piece of colour `by`."""
        b = self.squares

        # Knight
        knight = W_KNIGHT if by == WHITE else B_KNIGHT
        for off in KNIGHT_OFFSETS:
            if b[sq + off] == knight:
                return True

        # Sliding – rook / queen
        rook  = W_ROOK  if by == WHITE else B_ROOK
        queen = W_QUEEN if by == WHITE else B_QUEEN
        for ray in ROOK_RAYS:
            t = sq + ray
            while b[t] != OFFBOARD:
                if b[t] != EMPTY:
                    if b[t] in (rook, queen): return True
                    break
                t += ray

        # Sliding – bishop / queen
        bishop = W_BISHOP if by == WHITE else B_BISHOP
        for ray in BISHOP_RAYS:
            t = sq + ray
            while b[t] != OFFBOARD:
                if b[t] != EMPTY:
                    if b[t] in (bishop, queen): return True
                    break
                t += ray

        # King
        king = W_KING if by == WHITE else B_KING
        for off in KING_OFFSETS:
            if b[sq + off] == king:
                return True

        # Pawn  (a pawn of colour `by` would stand *behind* sq relative to its direction)
        if by == WHITE:
            # White pawns attack forward (+10±1), so they threaten sq from sq-9 / sq-11
            if b[sq - 9] == W_PAWN or b[sq - 11] == W_PAWN:
                return True
        else:
            # Black pawns attack forward (-10±1), threaten sq from sq+9 / sq+11
            if b[sq + 9] == B_PAWN or b[sq + 11] == B_PAWN:
                return True

        return False

    def in_check(self, color: int) -> bool:
        return self.is_attacked(self.find_king(color), -color)

    # ── Pseudo-legal move generation ──────────────────────────────────────────

    def _pseudo_moves(self, sq: int) -> list[Move]:
        piece = self.squares[sq]
        if piece in (EMPTY, OFFBOARD):
            return []
        color    = self.color_of(piece)
        abs_p    = abs(piece)
        moves: list[Move] = []

        if abs_p == 1:   self._pawn_moves(sq, color, moves)
        elif abs_p == 2: self._jump_moves(sq, piece, color, KNIGHT_OFFSETS, moves)
        elif abs_p == 3: self._slide_moves(sq, piece, color, BISHOP_RAYS, moves)
        elif abs_p == 4: self._slide_moves(sq, piece, color, ROOK_RAYS, moves)
        elif abs_p == 5: self._slide_moves(sq, piece, color, QUEEN_RAYS, moves)
        elif abs_p == 6:
            self._jump_moves(sq, piece, color, KING_OFFSETS, moves)
            self._castle_moves(sq, color, moves)

        return moves

    def _pawn_moves(self, sq: int, color: int, moves: list):
        b   = self.squares
        dir = 10 if color == WHITE else -10
        pawn = W_PAWN if color == WHITE else B_PAWN
        start_rank = 1 if color == WHITE else 6
        rank, _ = sq_to_rf(sq)

        # Single push
        t = sq + dir
        if b[t] == EMPTY:
            self._pawn_add(sq, t, pawn, EMPTY, color, moves)
            # Double push from starting rank
            if rank == start_rank:
                t2 = sq + 2 * dir
                if b[t2] == EMPTY:
                    moves.append(Move(sq, t2, pawn))

        # Diagonal captures (including en passant)
        for cap_off in (dir - 1, dir + 1):
            t = sq + cap_off
            if b[t] == OFFBOARD:
                continue
            if self._is_enemy(b[t], color):
                self._pawn_add(sq, t, pawn, b[t], color, moves)
            elif t == self.ep_sq:
                ep_cap = t - dir
                captured_pawn = b[ep_cap]
                # Guard: only generate EP if an enemy pawn is actually there.
                # Without this, calling get_all_legal_moves for the side that
                # just double-pushed (e.g. inside an eval loop that uses _apply
                # without switching turn) would produce a move with captured=EMPTY.
                if self._is_enemy(captured_pawn, color):
                    moves.append(Move(sq, t, pawn, captured_pawn,
                                      is_en_passant=True, ep_captured_sq=ep_cap))

    def _pawn_add(self, frm, to, pawn, captured, color, moves):
        """Add pawn move, expanding into four promotion moves if on final rank."""
        rank, _ = sq_to_rf(to)
        promo_rank = 7 if color == WHITE else 0
        if rank == promo_rank:
            q, r, b_, n = ((W_QUEEN, W_ROOK, W_BISHOP, W_KNIGHT) if color == WHITE
                           else (B_QUEEN, B_ROOK, B_BISHOP, B_KNIGHT))
            for promo in (q, r, b_, n):
                moves.append(Move(frm, to, pawn, captured, promotion=promo))
        else:
            moves.append(Move(frm, to, pawn, captured))

    def _jump_moves(self, sq, piece, color, offsets, moves):
        b = self.squares
        for off in offsets:
            t = sq + off
            if b[t] == OFFBOARD or self._is_own(b[t], color):
                continue
            moves.append(Move(sq, t, piece, b[t]))

    def _slide_moves(self, sq, piece, color, rays, moves):
        b = self.squares
        for ray in rays:
            t = sq + ray
            while b[t] != OFFBOARD:
                if b[t] == EMPTY:
                    moves.append(Move(sq, t, piece))
                elif self._is_enemy(b[t], color):
                    moves.append(Move(sq, t, piece, b[t]))
                    break
                else:
                    break
                t += ray

    def _castle_moves(self, sq, color, moves):
        b    = self.squares
        king = W_KING if color == WHITE else B_KING
        opp  = -color

        if color == WHITE:
            # Kingside: e1(25) → g1(27), rook h1(28) → f1(26)
            if (self.castle_wk and
                    b[26] == EMPTY and b[27] == EMPTY and
                    not self.is_attacked(25, opp) and
                    not self.is_attacked(26, opp) and
                    not self.is_attacked(27, opp)):
                moves.append(Move(25, 27, king,
                                  is_castle=True, castle_rook_from=28, castle_rook_to=26))
            # Queenside: e1(25) → c1(23), rook a1(21) → d1(24)
            if (self.castle_wq and
                    b[24] == EMPTY and b[23] == EMPTY and b[22] == EMPTY and
                    not self.is_attacked(25, opp) and
                    not self.is_attacked(24, opp) and
                    not self.is_attacked(23, opp)):
                moves.append(Move(25, 23, king,
                                  is_castle=True, castle_rook_from=21, castle_rook_to=24))
        else:
            # Kingside: e8(95) → g8(97), rook h8(98) → f8(96)
            if (self.castle_bk and
                    b[96] == EMPTY and b[97] == EMPTY and
                    not self.is_attacked(95, opp) and
                    not self.is_attacked(96, opp) and
                    not self.is_attacked(97, opp)):
                moves.append(Move(95, 97, king,
                                  is_castle=True, castle_rook_from=98, castle_rook_to=96))
            # Queenside: e8(95) → c8(93), rook a8(91) → d8(94)
            if (self.castle_bq and
                    b[94] == EMPTY and b[93] == EMPTY and b[92] == EMPTY and
                    not self.is_attacked(95, opp) and
                    not self.is_attacked(94, opp) and
                    not self.is_attacked(93, opp)):
                moves.append(Move(95, 93, king,
                                  is_castle=True, castle_rook_from=91, castle_rook_to=94))

    # ── Legal moves (filter pseudo-legal by check) ────────────────────────────

    def get_legal_moves(self, sq: int) -> list[Move]:
        piece = self.squares[sq]
        if piece in (EMPTY, OFFBOARD):
            return []
        color = self.color_of(piece)
        legal = []
        for move in self._pseudo_moves(sq):
            self._apply(move)
            if not self.in_check(color):
                legal.append(move)
            self._undo(move)
        return legal

    def get_all_legal_moves(self, color: int) -> list[Move]:
        """Uses piece list — iterates only occupied squares, not all 64."""
        moves = []
        for _piece, sq in self.get_pieces(color):
            moves.extend(self.get_legal_moves(sq))
        return moves

    # ── Apply / undo (internal, does NOT switch turn) ─────────────────────────
    #
    # Rule: every change to self.squares must be mirrored in self.piece_list
    # via _pl_add / _pl_remove.  The two structures must agree after every call.

    def _apply(self, move: Move):
        b    = self.squares
        dest = move.promotion if move.promotion else move.piece  # what lands on to_sq
        color = self.color_of(move.piece)

        # ── Save reversible state ─────────────────────────────────────────────
        move.prev_ep_sq     = self.ep_sq
        move.prev_castle_wk = self.castle_wk
        move.prev_castle_wq = self.castle_wq
        move.prev_castle_bk = self.castle_bk
        move.prev_castle_bq = self.castle_bq
        move.prev_halfmove  = self.halfmove_clock

        # ── Update piece list ────────────────── (mirrors every array write) ──
        self._pl_remove(move.piece, move.from_sq)       # piece leaves from_sq

        if move.captured and not move.is_en_passant:
            self._pl_remove(move.captured, move.to_sq)  # regular capture leaves to_sq

        self._pl_add(dest, move.to_sq)                  # dest piece arrives at to_sq

        if move.is_en_passant and move.captured:
            self._pl_remove(move.captured, move.ep_captured_sq)  # captured pawn gone

        if move.is_castle:
            rook = W_ROOK if color == WHITE else B_ROOK
            self._pl_remove(rook, move.castle_rook_from)
            self._pl_add(rook, move.castle_rook_to)

        # ── Update mailbox array (must match piece-list changes above) ────────
        b[move.to_sq]   = dest
        b[move.from_sq] = EMPTY

        if move.is_en_passant:
            b[move.ep_captured_sq] = EMPTY

        if move.is_castle:
            rook = W_ROOK if color == WHITE else B_ROOK
            b[move.castle_rook_to]   = rook
            b[move.castle_rook_from] = EMPTY

        # ── Game-state updates ────────────────────────────────────────────────
        if abs(move.piece) == 1 and abs(move.to_sq - move.from_sq) == 20:
            self.ep_sq = (move.from_sq + move.to_sq) // 2
        else:
            self.ep_sq = None

        if   move.piece ==  W_KING: self.castle_wk = self.castle_wq = False
        elif move.piece ==  B_KING: self.castle_bk = self.castle_bq = False
        if   move.from_sq == 21:   self.castle_wq = False
        elif move.from_sq == 28:   self.castle_wk = False
        elif move.from_sq == 91:   self.castle_bq = False
        elif move.from_sq == 98:   self.castle_bk = False
        if   move.to_sq == 21:    self.castle_wq = False
        elif move.to_sq == 28:    self.castle_wk = False
        elif move.to_sq == 91:    self.castle_bq = False
        elif move.to_sq == 98:    self.castle_bk = False

        if abs(move.piece) == 1 or move.captured != EMPTY:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

    def _undo(self, move: Move):
        b     = self.squares
        dest  = move.promotion if move.promotion else move.piece
        color = self.color_of(move.piece)

        # ── Update piece list (exact reverse of _apply) ───────────────────────
        self._pl_remove(dest, move.to_sq)               # dest piece leaves to_sq
        self._pl_add(move.piece, move.from_sq)           # original piece returns

        if move.captured and not move.is_en_passant:
            self._pl_add(move.captured, move.to_sq)     # regular capture restored

        if move.is_en_passant:
            self._pl_add(move.captured, move.ep_captured_sq)  # pawn restored

        if move.is_castle:
            rook = W_ROOK if color == WHITE else B_ROOK
            self._pl_remove(rook, move.castle_rook_to)
            self._pl_add(rook, move.castle_rook_from)

        # ── Update mailbox array ──────────────────────────────────────────────
        b[move.from_sq] = move.piece
        b[move.to_sq]   = EMPTY if move.is_en_passant else move.captured

        if move.is_en_passant:
            b[move.ep_captured_sq] = move.captured   # the captured pawn

        if move.is_castle:
            rook = W_ROOK if color == WHITE else B_ROOK
            b[move.castle_rook_from] = rook
            b[move.castle_rook_to]   = EMPTY

        # ── Restore game-state snapshots ──────────────────────────────────────
        self.ep_sq          = move.prev_ep_sq
        self.castle_wk      = move.prev_castle_wk
        self.castle_wq      = move.prev_castle_wq
        self.castle_bk      = move.prev_castle_bk
        self.castle_bq      = move.prev_castle_bq
        self.halfmove_clock = move.prev_halfmove

    # ── Public make_move (applies + switches turn) ────────────────────────────

    def make_move(self, move: Move):
        self._apply(move)
        self.turn = -self.turn
        if self.turn == WHITE:
            self.fullmove += 1
