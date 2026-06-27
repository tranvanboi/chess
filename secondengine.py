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
import random
from board import Board, Move
from engine import Engine
from constants import (
    WHITE, BLACK, EMPTY,
    W_PAWN, W_KNIGHT, W_BISHOP, W_ROOK, W_QUEEN, W_KING,
    B_PAWN, B_KNIGHT, B_BISHOP, B_ROOK, B_QUEEN, B_KING,
)


SEARCH_DEPTH = 3

# Score returned for checkmate. Must dwarf any realistic positional score
# (material tops out around 200 for the king bonus, so 100 000 is safe).
# The + depth term makes the engine prefer faster mates: a mate-in-1 scores
# MATE_SCORE+1, mate-in-3 scores MATE_SCORE+3, so the engine always chases
# the quickest finish rather than "any eventual mate."
MATE_SCORE = 100_000

# Small random noise added to every leaf evaluation.
# Large enough to break ties between equal-looking positions (preventing loops),
# small enough not to override real material differences (pawn = 1.0, so ±0.05
# means the engine will occasionally prefer an equal move but never sacrifice a
# pawn for noise).
JITTER = 0.05

class SecondEngine(Engine):
    name  = "Minimax"
    elo   = 900
    style = "Positional"

    # ── Entry point ───────────────────────────────────────────────────────────

    def get_move(self, board: Board) -> Move | None:
        piece_count = board.piece_count()
        turn_piece = min(board.piece_count_for(board.turn), board.piece_count_for(-board.turn))
        if turn_piece == 1:
            move, _ = self.minimax(SEARCH_DEPTH + 2, board,
                               float('-inf'), float('+inf'))
        elif piece_count < 5:
            move, _ = self.minimax(SEARCH_DEPTH + 2, board,
                               float('-inf'), float('+inf'))
        elif piece_count < 10:
            move, _ = self.minimax(SEARCH_DEPTH + 1, board,
                               float('-inf'), float('+inf'))
        else:
            move, _ = self.minimax(SEARCH_DEPTH, board,
                                float('-inf'), float('+inf'))
        return move

    # ── Minimax with alpha-beta pruning ───────────────────────────────────────

    def minimax(self, depth: int, board: Board,
                alpha: float, beta: float) -> tuple[Move | None, float]:
        """
        Negamax-style minimax with alpha-beta pruning.

        Returns (best_move, score) where score is always from WHITE's perspective.

        Fix summary vs original:
          1. board.turn is flipped manually around the recursive call because
             _apply() moves pieces but does NOT switch turn.
          2. Initial value is ±inf (not self.eval(board)) so the engine always
             finds the best available move even when every option is bad.
          3. Alpha-beta cuts branches that can't affect the result, making
             depth-3 fast enough to be playable.
        """
        moves = board.get_all_legal_moves(board.turn)

        if not moves:
            if board.in_check(board.turn):
                # Checkmate: the side to move lost.
                # +(MATE_SCORE + depth) if WHITE won (black is mated),
                # -(MATE_SCORE + depth) if BLACK won (white is mated).
                # The +depth term means the engine always prefers a shorter
                # forced mate over a longer one.
                if board.turn == WHITE:
                    return None, -(MATE_SCORE + depth * 100)   # white is mated
                else:
                    return None, +(MATE_SCORE + depth * 100)   # black is mated
            else:
                return None, 0.0   # stalemate — draw
 
        # ── Leaf node: return static evaluation ───────────────────────────────
        if depth == 0:
            return None, self.eval(board)

        # Shuffle so that moves with equal scores don't always resolve to the
        # same one (different shuffle each ply = different game each time).
        random.shuffle(moves)

        maximizing = (board.turn == WHITE)
        best_move  = moves[0]
        best_val   = float('-inf') if maximizing else float('+inf')

        for move in moves:
            board._apply(move)
            board.turn = -board.turn      # ← FIX 1: switch turn for next ply

            _, score = self.minimax(depth - 1, board, alpha, beta)

            board.turn = -board.turn      # restore turn before undo
            board._undo(move)

            if maximizing:
                if score > best_val:
                    best_val  = score
                    best_move = move
                alpha = max(alpha, best_val)
            else:
                if score < best_val:
                    best_val  = score
                    best_move = move
                beta = min(beta, best_val)

            if beta <= alpha:             # ← alpha-beta cutoff
                break

        return best_move, best_val

    # ── Evaluation (always from WHITE's perspective) ──────────────────────────

    def eval(self, board: Board) -> float:
        """
        Material + pawn structure + a small random jitter.

        The jitter (±JITTER) breaks evaluation ties so two engines playing
        each other don't lock into the same repeated sequence.  It is small
        enough that it never overrides a real material difference — a pawn
        is worth 1.0 and jitter is ±0.05.

        Mobility is excluded for performance: two get_all_legal_moves() calls
        per leaf node multiplies work by ~640× at depth 3.  The tree search
        captures mobility implicitly.
        """
        base = self._material(board) + self._pawn_penalties(board)
        return base + random.uniform(-JITTER, JITTER)

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
