"""
Start-screen menu rendered with pygame.

Layout (720 × 760 window):

  ┌──────────────────────────────────────────┐
  │                  CHESS                   │
  │                                          │
  │  ┌─────────────┐    ┌─────────────┐     │
  │  │    WHITE    │    │    BLACK    │     │
  │  │             │    │             │     │
  │  │ ● Human     │    │ ● Human     │     │
  │  │ ○ Random…   │    │ ○ Random…   │     │
  │  │ ○ [soon]    │    │ ○ [soon]    │     │
  │  └─────────────┘    └─────────────┘     │
  │                                          │
  │            [ Start Game ]                │
  └──────────────────────────────────────────┘

Call update(event) for every pygame event.
Call draw(screen) each frame.
When start_requested is True, read white_player / black_player.
"""

from __future__ import annotations
import pygame
from constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT,
    BG_COLOR, LIGHT_SQ, DARK_SQ, STATUS_COLOR,
)
from engine import Engine, HumanPlayer, RandomEngine
from firstengine import FirstEngine
from secondengine import SecondEngine


# ── Registry ──────────────────────────────────────────────────────────────────
# The menu reads this list to populate the engine selection.
# Add new Engine subclasses here when they're ready.

AVAILABLE_ENGINES: list[type[Engine]] = [
    RandomEngine,
    FirstEngine,
    SecondEngine,
    # AggressiveEngine,   ← coming soon
    # PositionalEngine,   ← coming soon
    # StockfishEngine,    ← coming soon
]

# ── Palette (local to menu) ───────────────────────────────────────────────────
_CARD_BG      = (35, 34, 30)
_CARD_BORDER  = (70, 65, 58)
_TITLE_COLOR  = (230, 210, 170)
_LABEL_COLOR  = (200, 195, 185)
_SELECTED_DOT = (100, 180, 100)
_IDLE_DOT     = (80,  75,  68)
_HOVER_COLOR  = (55,  52,  46)
_BTN_COLOR    = (60,  130,  60)
_BTN_HOVER    = (75,  160,  75)
_BTN_TEXT     = (230, 255, 230)
_DIM_COLOR    = (90,  87,  80)
_DIM_TEXT     = (100,  97,  90)


class _PlayerOption:
    """One selectable row inside a player card."""
    def __init__(self, player: Engine, label: str, sub: str, available: bool = True):
        self.player    = player
        self.label     = label
        self.sub       = sub        # secondary info (elo / style)
        self.available = available
        self.rect      = pygame.Rect(0, 0, 0, 0)  # filled in layout()


class _PlayerCard:
    """Card for one side (White or Black)."""
    def __init__(self, title: str, options: list[_PlayerOption]):
        self.title    = title
        self.options  = options
        self.selected = 0           # index into options
        self.rect     = pygame.Rect(0, 0, 0, 0)

    def selected_player(self) -> Engine:
        return self.options[self.selected].player

    def try_click(self, pos: tuple[int, int]) -> bool:
        for i, opt in enumerate(self.options):
            if opt.available and opt.rect.collidepoint(pos):
                self.selected = i
                return True
        return False


class MenuScreen:
    def __init__(self):
        self.start_requested = False
        self.white_player: Engine | None = None
        self.black_player: Engine | None = None

        self._title_font  = pygame.font.SysFont("Arial", 52, bold=True)
        self._head_font   = pygame.font.SysFont("Arial", 18, bold=True)
        self._body_font   = pygame.font.SysFont("Arial", 16)
        self._sub_font    = pygame.font.SysFont("Arial", 13)
        self._btn_font    = pygame.font.SysFont("Arial", 20, bold=True)

        self._btn_rect    = pygame.Rect(0, 0, 0, 0)
        self._btn_hovered = False

        self._cards = [
            _PlayerCard("WHITE", self._build_options()),
            _PlayerCard("BLACK", self._build_options()),
        ]
        # Black side defaults to Random so it's immediately playable
        self._cards[1].selected = 1

        self._layout()

    # ── Build option list ─────────────────────────────────────────────────────

    @staticmethod
    def _build_options() -> list[_PlayerOption]:
        opts = [
            _PlayerOption(HumanPlayer(), "Human", "You play", available=True),
        ]
        for cls in AVAILABLE_ENGINES:
            e = cls()
            opts.append(_PlayerOption(e, e.name, f"~{e.elo} Elo · {e.style}", available=True))
        # Placeholder for future engines
        opts.append(_PlayerOption(HumanPlayer(), "More engines", "coming soon…", available=False))
        return opts

    # ── Layout (pre-compute all rects) ────────────────────────────────────────

    def _layout(self):
        cw, ch = 280, 220          # card size
        gap    = 40                # gap between cards
        total_w = cw * 2 + gap
        cx     = (WINDOW_WIDTH - total_w) // 2
        cy     = 160

        for i, card in enumerate(self._cards):
            card.rect = pygame.Rect(cx + i * (cw + gap), cy, cw, ch)
            row_y = cy + 44
            for opt in card.options:
                opt.rect = pygame.Rect(cx + i * (cw + gap) + 12, row_y, cw - 24, 38)
                row_y += 42

        btn_w, btn_h = 200, 48
        self._btn_rect = pygame.Rect(
            (WINDOW_WIDTH - btn_w) // 2,
            cy + ch + 40,
            btn_w, btn_h,
        )

    # ── Event handling ────────────────────────────────────────────────────────

    def update(self, event: pygame.event.Event):
        mx, my = pygame.mouse.get_pos()
        self._btn_hovered = self._btn_rect.collidepoint(mx, my)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for card in self._cards:
                card.try_click(event.pos)
            if self._btn_hovered:
                self.white_player = self._cards[0].selected_player()
                self.black_player = self._cards[1].selected_player()
                self.start_requested = True

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface):
        screen.fill(BG_COLOR)
        self._draw_title(screen)
        for card in self._cards:
            self._draw_card(screen, card)
        self._draw_start_btn(screen)
        self._draw_hint(screen)

    def _draw_title(self, screen):
        surf = self._title_font.render("CHESS", True, _TITLE_COLOR)
        screen.blit(surf, surf.get_rect(centerx=WINDOW_WIDTH // 2, top=50))

        sub  = self._sub_font.render("Select players and start a new game", True, _DIM_COLOR)
        screen.blit(sub, sub.get_rect(centerx=WINDOW_WIDTH // 2, top=115))

    def _draw_card(self, screen, card: _PlayerCard):
        r = card.rect
        # Card background + border
        pygame.draw.rect(screen, _CARD_BG,    r, border_radius=8)
        pygame.draw.rect(screen, _CARD_BORDER, r, width=1, border_radius=8)

        # Card header (e.g. "WHITE")
        hdr = self._head_font.render(card.title, True, _TITLE_COLOR)
        screen.blit(hdr, hdr.get_rect(centerx=r.centerx, top=r.top + 12))

        # Divider line
        pygame.draw.line(screen, _CARD_BORDER,
                         (r.left + 12, r.top + 36), (r.right - 12, r.top + 36))

        # Option rows
        for i, opt in enumerate(card.options):
            self._draw_option(screen, card, opt, i)

    def _draw_option(self, screen, card: _PlayerCard,
                     opt: _PlayerOption, idx: int):
        r         = opt.rect
        selected  = (card.selected == idx)
        available = opt.available

        # Hover highlight for available options
        mx, my = pygame.mouse.get_pos()
        if available and r.collidepoint(mx, my) and not selected:
            pygame.draw.rect(screen, _HOVER_COLOR, r, border_radius=5)

        # Radio circle
        dot_x = r.left + 14
        dot_y = r.centery
        dot_color  = _SELECTED_DOT if selected  else (_IDLE_DOT if available else _DIM_TEXT)
        pygame.draw.circle(screen, dot_color, (dot_x, dot_y), 7)
        if selected:
            pygame.draw.circle(screen, _CARD_BG, (dot_x, dot_y), 3)
        else:
            pygame.draw.circle(screen, _CARD_BG,    (dot_x, dot_y), 7)
            pygame.draw.circle(screen, dot_color,   (dot_x, dot_y), 7, width=2)

        # Label
        txt_color = _LABEL_COLOR if available else _DIM_TEXT
        lbl = self._body_font.render(opt.label, True, txt_color)
        screen.blit(lbl, (r.left + 28, r.top + 4))

        # Sub-label (elo / style)
        if opt.sub:
            sub = self._sub_font.render(opt.sub, True, _DIM_COLOR if available else _DIM_TEXT)
            screen.blit(sub, (r.left + 28, r.top + 21))

    def _draw_start_btn(self, screen):
        color = _BTN_HOVER if self._btn_hovered else _BTN_COLOR
        r = self._btn_rect
        pygame.draw.rect(screen, color, r, border_radius=8)
        lbl = self._btn_font.render("Start Game", True, _BTN_TEXT)
        screen.blit(lbl, lbl.get_rect(center=r.center))

    def _draw_hint(self, screen):
        hint = self._sub_font.render(
            "ESC — back to menu during game", True, _DIM_COLOR)
        screen.blit(hint, hint.get_rect(
            centerx=WINDOW_WIDTH // 2,
            bottom=WINDOW_HEIGHT - 16))
