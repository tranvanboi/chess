# Chess

A Python chess game with a pygame GUI and built-in AI engines.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![pygame](https://img.shields.io/badge/pygame-required-green)

## Features

- Graphical board with legal-move highlighting, check indicators, and Unicode pieces
- Three game modes: Human vs Human, Human vs Engine, Engine vs Engine
- Three built-in engines of increasing strength:
  - **Random Bot** — picks a random legal move
  - **Shannon** (~600 ELO) — greedy 1-ply search using Shannon's 1949 evaluation (material, pawn structure, mobility)
  - **Minimax** (~900 ELO) — minimax with alpha-beta pruning and dynamic depth scaling
- Full rule support: castling, en passant, promotion, 50-move draw

## Requirements

- Python 3.10+
- [pygame](https://www.pygame.org/)

## Installation

```bash
git clone https://github.com/your-username/chess.git
cd chess
pip install pygame
```

## Running

```bash
python main.py
```

The start screen lets you pick a player type (Human or engine) for each side, then click **Start Game**.

## Project Structure

| File | Purpose |
|---|---|
| `main.py` | Entry point — launches the UI |
| `ui.py` | pygame rendering and event loop |
| `menu.py` | Start-screen layout and engine selection |
| `game.py` | Game controller and state machine |
| `board.py` | 10×12 mailbox board, move generation, and rules |
| `engine.py` | Base `Engine` class and `HumanPlayer` |
| `firstengine.py` | Shannon engine (greedy 1-ply) |
| `secondengine.py` | Minimax engine (alpha-beta pruning) |
| `constants.py` | Piece codes, board geometry, and UI palette |

## Adding a New Engine

1. Subclass `Engine` in a new file and implement `get_move(board) -> Move`.
2. Set `name`, `elo`, and `style` class attributes.
3. Import your class in `menu.py` and append it to `AVAILABLE_ENGINES`.

## License
