"""
Pygame UI — knows nothing about chess rules.
All logic is delegated to Game; this file only draws and translates mouse clicks.

Controls (in-game):
  Left-click  — select piece / move
  F           — flip board (view from Black's side)
  ESC         — back to menu
"""

from __future__ import annotations
import os
import sys
import pygame
from constants import *
from board import rf_to_sq, sq_to_rf, EMPTY
from game import Game, GameStatus
from menu import MenuScreen

# How long (ms) to wait before the engine plays its move.
# Gives a brief visual pause so the move is noticeable.
ENGINE_MOVE_DELAY_MS = 1


# ── Coordinate helpers ────────────────────────────────────────────────────────

def sq_to_pixel(sq: int, flipped: bool) -> tuple[int, int]:
    """Top-left pixel corner of a board square."""
    rank, file = sq_to_rf(sq)
    if flipped:
        rank = 7 - rank
        file = 7 - file
    x = BOARD_OFFSET_X + file * SQUARE_SIZE
    y = BOARD_OFFSET_Y + (7 - rank) * SQUARE_SIZE
    return x, y

def pixel_to_sq(x: int, y: int, flipped: bool) -> int | None:
    """Board square under pixel (x, y), or None if outside the board."""
    file  = (x - BOARD_OFFSET_X) // SQUARE_SIZE
    rank  = 7 - (y - BOARD_OFFSET_Y) // SQUARE_SIZE
    if flipped:
        file = 7 - file
        rank = 7 - rank
    if 0 <= rank < 8 and 0 <= file < 8:
        return rf_to_sq(rank, file)
    return None


# ── Main UI class ─────────────────────────────────────────────────────────────

class ChessUI:
    def __init__(self):
        pygame.init()
        self.screen  = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Chess")
        self.clock   = pygame.time.Clock()

        self._init_fonts()

        # App state: start on the menu
        self._in_menu  = True
        self._menu     = MenuScreen()
        self.game: Game | None = None
        self.flipped   = False

        # Engine-move timer: timestamp when the engine turn started (ms), or None
        self._engine_move_at: int | None = None

    # ── Font loading ──────────────────────────────────────────────────────────

    def _init_fonts(self):
        self.ui_font    = pygame.font.SysFont("Arial", 20)
        self.coord_font = pygame.font.SysFont("Arial", 13)
        self.piece_font = None

        # --- Glyph verification -------------------------------------------
        # A tofu-box has pixels ONLY on its border; a real glyph has filled
        # interior pixels too. We render on a white bg and count dark interior
        # pixels to tell them apart.
        def _glyph_ok(font) -> bool:
            surf = font.render("♔", True, (0, 0, 0), (255, 255, 255))
            w, h = surf.get_size()
            if w < 12 or h < 12:
                return False
            margin = max(3, w // 6)
            dark = sum(
                1 for x in range(margin, w - margin)
                  for y in range(margin, h - margin)
                  if surf.get_at((x, y))[0] < 100   # dark pixel
            )
            return dark > 8

        # --- Direct font-file paths (most reliable) -----------------------
        font_paths = [
            # macOS — Apple Symbols carries the Misc Symbols block (chess pieces)
            "/System/Library/Fonts/Apple Symbols.ttf",
            "/System/Library/Fonts/AppleSymbols.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Lucida Grande.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            "/Library/Fonts/Arial Unicode MS.ttf",
            # Windows
            "C:/Windows/Fonts/seguisym.ttf",   # Segoe UI Symbol — has chess glyphs
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            # Linux
            "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/symbola/Symbola.ttf",
            "/usr/share/fonts/TTF/FreeSerif.ttf",
        ]
        for path in font_paths:
            if os.path.isfile(path):
                try:
                    f = pygame.font.Font(path, 52)
                    if _glyph_ok(f):
                        self.piece_font = f
                        print(f"[chess] piece font (file): {path}")
                        break
                    else:
                        print(f"[chess] font has no chess glyphs: {path}")
                except Exception as e:
                    print(f"[chess] could not load {path}: {e}")

        # --- SysFont fallback ---------------------------------------------
        if self.piece_font is None:
            available = pygame.font.get_fonts()
            candidates = [
                "applesymbols", "seguisymbol", "arialunicodems",
                "dejavusans", "freeserif", "freesans", "symbola",
                "lucidagrande", "notosanssymbols2",
            ]
            for name in candidates:
                if name in available:
                    try:
                        f = pygame.font.SysFont(name, 52)
                        if _glyph_ok(f):
                            self.piece_font = f
                            print(f"[chess] piece font (sysFont): {name}")
                            break
                        else:
                            print(f"[chess] sysFont '{name}' has no chess glyphs")
                    except Exception:
                        pass

        # --- Letter fallback (always works) ------------------------------
        if self.piece_font is None:
            print("[chess] no chess-glyph font found — using letter labels")
        # Cached bold font used by the letter fallback path
        self.letter_font = pygame.font.SysFont("Arial", 32, bold=True)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw_board(self):
        b        = self.game.board
        targets  = set(self.game.legal_targets())
        sel      = self.game.selected_sq
        in_check = self.game.status in (GameStatus.CHECK, GameStatus.CHECKMATE)

        for rank in range(8):
            for file in range(8):
                sq      = rf_to_sq(rank, file)
                is_light = (rank + file) % 2 == 0
                color   = LIGHT_SQ if is_light else DARK_SQ

                if sq == sel:
                    color = SELECTED_COLOR

                x, y = sq_to_pixel(sq, self.flipped)
                pygame.draw.rect(self.screen, color, (x, y, SQUARE_SIZE, SQUARE_SIZE))

                # Legal-move indicators
                if sq in targets:
                    cx = x + SQUARE_SIZE // 2
                    cy = y + SQUARE_SIZE // 2
                    if b.squares[sq] != EMPTY:
                        # Capture: draw a ring / border
                        pygame.draw.rect(self.screen, LEGAL_DOT_COLOR,
                                         (x, y, SQUARE_SIZE, SQUARE_SIZE), 5)
                    else:
                        # Empty square: draw a small dot
                        pygame.draw.circle(self.screen, LEGAL_DOT_COLOR, (cx, cy), 11)

        # King-in-check highlight (drawn as a border after the squares)
        if in_check:
            king_sq = b.find_king(b.turn)
            kx, ky  = sq_to_pixel(king_sq, self.flipped)
            pygame.draw.rect(self.screen, CHECK_COLOR,
                             (kx, ky, SQUARE_SIZE, SQUARE_SIZE), 5)

    def _draw_coordinates(self):
        files = list("abcdefgh")
        ranks = list("12345678")
        if self.flipped:
            files = files[::-1]
            ranks = ranks[::-1]

        for i in range(8):
            # File label below the board
            lbl = self.coord_font.render(files[i], True, STATUS_COLOR)
            self.screen.blit(lbl, (
                BOARD_OFFSET_X + i * SQUARE_SIZE + SQUARE_SIZE - 14,
                BOARD_OFFSET_Y + 8 * SQUARE_SIZE + 5,
            ))
            # Rank label to the left
            lbl = self.coord_font.render(ranks[7 - i], True, STATUS_COLOR)
            self.screen.blit(lbl, (
                BOARD_OFFSET_X - 18,
                BOARD_OFFSET_Y + i * SQUARE_SIZE + 5,
            ))

    def _draw_pieces(self):
        b = self.game.board
        for rank in range(8):
            for file in range(8):
                sq    = rf_to_sq(rank, file)
                piece = b.squares[sq]
                if piece == EMPTY:
                    continue

                x, y = sq_to_pixel(sq, self.flipped)
                cx   = x + SQUARE_SIZE // 2
                cy   = y + SQUARE_SIZE // 2

                if self.piece_font is not None:
                    # ── Unicode glyph path ────────────────────────────────
                    symbol   = PIECE_SYMBOLS[piece]
                    is_white = piece > 0
                    fg       = (255, 255, 255) if is_white else ( 15,  15,  15)
                    outline  = ( 15,  15,  15) if is_white else (230, 230, 230)
                    for dx, dy in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)):
                        s = self.piece_font.render(symbol, True, outline)
                        self.screen.blit(s, s.get_rect(center=(cx+dx, cy+dy)))
                    s = self.piece_font.render(symbol, True, fg)
                    self.screen.blit(s, s.get_rect(center=(cx, cy)))

                else:
                    # ── Letter fallback (circle + letter) ─────────────────
                    is_white = piece > 0
                    label    = PIECE_LETTERS[piece].upper()
                    fill     = (245, 240, 230) if is_white else ( 50,  45,  40)
                    border   = ( 60,  55,  50) if is_white else (200, 195, 185)
                    text_col = ( 40,  35,  30) if is_white else (230, 225, 215)
                    r        = SQUARE_SIZE // 2 - 6
                    pygame.draw.circle(self.screen, border, (cx, cy), r + 2)
                    pygame.draw.circle(self.screen, fill,   (cx, cy), r)
                    s = self.letter_font.render(label, True, text_col)
                    self.screen.blit(s, s.get_rect(center=(cx, cy)))

    def _draw_status(self):
        # Matchup (top centre, small)
        matchup = self.coord_font.render(self.game.matchup_text(), True, (120, 115, 105))
        self.screen.blit(matchup, matchup.get_rect(
            centerx=WINDOW_WIDTH // 2, top=8))

        # Status / turn text (top left)
        status_str = self.game.status_text()
        if self._engine_move_at is not None:
            status_str = "Engine thinking…"
        text = self.ui_font.render(status_str, True, STATUS_COLOR)
        self.screen.blit(text, (BOARD_OFFSET_X, 26))

        # Keyboard hints (top right)
        hint = self.coord_font.render("F flip   ESC menu", True, (100, 100, 100))
        self.screen.blit(hint, (WINDOW_WIDTH - hint.get_width() - 10, 26))

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if self._in_menu:
                    self._menu.update(event)
                    if self._menu.start_requested:
                        self._start_game(self._menu.white_player,
                                         self._menu.black_player)
                else:
                    self._handle_game_event(event)

            if self._in_menu:
                self._menu.draw(self.screen)
            else:
                self._tick_engine()   # fire engine move after delay
                self.screen.fill(BG_COLOR)
                self._draw_board()
                self._draw_pieces()
                self._draw_coordinates()
                self._draw_status()

            pygame.display.flip()
            self.clock.tick(60)

    def _start_game(self, white, black):
        self.game             = Game(white, black)
        self.flipped          = False
        self._engine_move_at  = None
        self._in_menu         = False
        # If white is an engine, schedule its first move immediately
        self._maybe_schedule_engine()

    def _handle_game_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._in_menu = True
                self._menu    = MenuScreen()   # fresh menu
            elif event.key == pygame.K_f:
                self.flipped = not self.flipped

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Block clicks while waiting for engine move
            if self._engine_move_at is not None:
                return
            if self.game.needs_engine_move():
                return
            sq = pixel_to_sq(*event.pos, self.flipped)
            if sq is not None:
                self.game.on_square_clicked(sq)
                self._maybe_schedule_engine()

    # ── Engine move timing ─────────────────────────────────────────────────────

    def _maybe_schedule_engine(self):
        """If it's now an engine's turn, set the delay timer."""
        if self.game and self.game.needs_engine_move():
            self._engine_move_at = pygame.time.get_ticks() + ENGINE_MOVE_DELAY_MS

    def _tick_engine(self):
        """Fire the engine move once the delay has elapsed."""
        if self._engine_move_at is None:
            return
        if pygame.time.get_ticks() < self._engine_move_at:
            return
        self._engine_move_at = None
        if self.game.needs_engine_move():
            self.game.do_engine_move()
            self._maybe_schedule_engine()   # chain: might be engine vs engine
