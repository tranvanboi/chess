# ── Piece codes ──────────────────────────────────────────────────────────────
EMPTY    = 0
OFFBOARD = 99   # sentinel value filling the 10x12 padding cells

# White pieces (positive), black pieces (negative mirror)
W_PAWN, W_KNIGHT, W_BISHOP, W_ROOK, W_QUEEN, W_KING =  1,  2,  3,  4,  5,  6
B_PAWN, B_KNIGHT, B_BISHOP, B_ROOK, B_QUEEN, B_KING = -1, -2, -3, -4, -5, -6

WHITE =  1
BLACK = -1

# ── Move-generation offsets in the 10×12 mailbox ─────────────────────────────
# One step in each direction from any square's index:
#   +10 = one rank up   -10 = one rank down
#   + 1 = one file right  -1 = one file left
KNIGHT_OFFSETS = [-21, -19, -12, -8, 8, 12, 19, 21]
ROOK_RAYS      = [-10, 10, -1, 1]
BISHOP_RAYS    = [-11, -9,  9, 11]
QUEEN_RAYS     = ROOK_RAYS + BISHOP_RAYS
KING_OFFSETS   = [-11, -10, -9, -1, 1, 9, 10, 11]

# ── Display ───────────────────────────────────────────────────────────────────
PIECE_SYMBOLS = {
    W_KING: '♔', W_QUEEN: '♕', W_ROOK: '♖',
    W_BISHOP: '♗', W_KNIGHT: '♘', W_PAWN: '♙',
    B_KING: '♚', B_QUEEN: '♛', B_ROOK: '♜',
    B_BISHOP: '♝', B_KNIGHT: '♞', B_PAWN: '♟',
}

# Fallback if the system font can't render chess Unicode
PIECE_LETTERS = {
    W_KING: 'K', W_QUEEN: 'Q', W_ROOK: 'R',
    W_BISHOP: 'B', W_KNIGHT: 'N', W_PAWN: 'P',
    B_KING: 'k', B_QUEEN: 'q', B_ROOK: 'r',
    B_BISHOP: 'b', B_KNIGHT: 'n', B_PAWN: 'p',
}

# ── UI layout & palette ───────────────────────────────────────────────────────
SQUARE_SIZE    = 80
BOARD_OFFSET_X = 40
BOARD_OFFSET_Y = 60
WINDOW_WIDTH   = 720
WINDOW_HEIGHT  = 760

LIGHT_SQ        = (240, 217, 181)
DARK_SQ         = (181, 136,  99)
SELECTED_COLOR  = ( 20,  85,  30)   # selected square fill
LEGAL_DOT_COLOR = ( 20,  85,  30)   # dot on empty legal-move square
CHECK_COLOR     = (220,  50,  50)   # king-in-check border
BG_COLOR        = ( 22,  21,  18)   # window background
STATUS_COLOR    = (200, 200, 200)   # status / coordinate text
