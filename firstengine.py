"""
FirstEngine — Shannon's evaluation function (1949), greedy 1-ply search.

                 f(p) = 200(K−K')
                      +   9(Q−Q')
                      +   5(R−R')
                      +   3(B−B' + N−N')
                      +   1(P−P')
                      − 0.5(D−D' + S−S' + I−I')
                      + 0.1(M−M')  + …

  K Q R B N P   = piece counts for the side being evaluated (WHITE)
  K'Q'R'B'N'P' = piece counts for the opponent (BLACK)
  D  = doubled pawns   (>1 friendly pawn on same file)
  S  = blocked pawns   (pawn that cannot advance — piece directly ahead)
  I  = isolated pawns  (no friendly pawn on either adjacent file)
  M  = mobility        (number of legal moves available)

eval() always returns the score from WHITE's perspective:
  positive → white is better
  negative → black is better

get_move() flips the sign for black so it always maximises its own advantage.
"""

from __future__ import annotations
from board import Board, Move
from engine import Engine
from constants import (
    WHITE, BLACK, EMPTY,
    W_PAWN, W_KNIGHT, W_BISHOP, W_ROOK, W_QUEEN, W_KING,
    B_PAWN, B_KNIGHT, B_BISHOP, B_ROOK, B_QUEEN, B_KING,
)


class FirstEngine(Engine):
    name  = "Shannon"
    elo   = 600
    style = "Greedy"

    # ── Entry point ───────────────────────────────────────────────────────────

    def get_move(self, board: Board) -> Move | None:
        """
        1-ply greedy search: try every legal move, keep the one with
        the best evaluation for the side to move.
        """
        moves = board.get_all_legal_moves(board.turn)
        if not moves:
            return None

        # +1 if we're white (maximise score), -1 if black (minimise = maximise negated)
        sign = 1 if board.turn == WHITE else -1

        best_move  = moves[0]
        best_score = float('-inf')

        for move in moves:
            board._apply(move)
            score = sign * self.eval(board)
            board._undo(move)
            if score > best_score:
                best_score = score
                best_move  = move

        return best_move

    # ── Evaluation (always from WHITE's perspective) ──────────────────────────

    def eval(self, board: Board) -> float:
        return (
            self._material(board)
            + self._pawn_penalties(board)
            + self._mobility(board)
        )

    # ── Material ──────────────────────────────────────────────────────────────

    def _material(self, board: Board) -> float:
        """
        200(K−K') + 9(Q−Q') + 5(R−R') + 3(B−B'+N−N') + 1(P−P')
        """
        pl = board.piece_list
        c  = lambda p: len(pl.get(p, []))   # noqa: E731  (concise inline)

        return (
            200 * (c(W_KING)   - c(B_KING))
          +   9 * (c(W_QUEEN)  - c(B_QUEEN))
          +   5 * (c(W_ROOK)   - c(B_ROOK))
          +   3 * ((c(W_BISHOP) - c(B_BISHOP)) + (c(W_KNIGHT) - c(B_KNIGHT)))
          +   1 * (c(W_PAWN)   - c(B_PAWN))
        )

    # ── Pawn penalties ────────────────────────────────────────────────────────

    def _pawn_penalties(self, board: Board) -> float:
        """
        −0.5 × ( (D−D') + (S−S') + (I−I') )

        D = doubled   S = blocked   I = isolated
        Primes = opponent.  Result is from WHITE's perspective.
        """
        pl = board.piece_list
        wp = pl.get(W_PAWN, [])
        bp = pl.get(B_PAWN, [])

        dw, db = self._doubled(wp),         self._doubled(bp)
        sw, sb = self._blocked(wp, board, WHITE), self._blocked(bp, board, BLACK)
        iw, ib = self._isolated(wp),        self._isolated(bp)

        return -0.5 * ((dw - db) + (sw - sb) + (iw - ib))

    # ── Mobility ──────────────────────────────────────────────────────────────

    def _mobility(self, board: Board) -> float:
        """
        0.1 × (M − M')
        M = number of legal moves for WHITE, M' for BLACK.
        """
        mw = len(board.get_all_legal_moves(WHITE))
        mb = len(board.get_all_legal_moves(BLACK))
        return 0.1 * (mw - mb)

    # ── Pawn-structure helpers ─────────────────────────────────────────────────

    @staticmethod
    def _file_of(sq: int) -> int:
        """0-indexed file (0 = a-file) from a mailbox square index."""
        return sq % 10 - 1

    def _doubled(self, pawn_squares) -> int:
        """
        Count pawns that share a file with at least one other friendly pawn.

        Two pawns on the same file → 1 doubled pawn (the extra one).
        Three on the same file → 2 doubled pawns, etc.
        """
        file_counts: dict[int, int] = {}
        for sq in pawn_squares:
            f = self._file_of(sq)
            file_counts[f] = file_counts.get(f, 0) + 1
        # Each file with n pawns contributes (n-1) doubled pawns
        return sum(n - 1 for n in file_counts.values() if n > 1)

    def _blocked(self, pawn_squares, board: Board, color: int) -> int:
        """
        Count pawns that cannot advance because the square directly ahead
        is occupied by any piece (friend or enemy).
        """
        forward = 10 if color == WHITE else -10
        return sum(
            1 for sq in pawn_squares
            if board.squares[sq + forward] != EMPTY
        )

    def _isolated(self, pawn_squares) -> int:
        """
        Count pawns with no friendly pawn on either adjacent file.
        A pawn on the a-file with no b-file pawn is isolated, etc.
        """
        files = {self._file_of(sq) for sq in pawn_squares}
        return sum(
            1 for sq in pawn_squares
            if (self._file_of(sq) - 1) not in files
            and (self._file_of(sq) + 1) not in files
        )
