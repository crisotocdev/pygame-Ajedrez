# ai.py
from dataclasses import dataclass
from typing import Callable, Optional
import random

# Valores de material (centipeones)
PIECE_VALUE = {
    'pawn': 100, 'knight': 320, 'bishop': 330, 'rook': 500, 'queen': 900, 'king': 0
}

@dataclass
class Move:
    color: str            # 'white' | 'black'
    sel_index: int        # índice dentro de white/black_pieces
    to: tuple[int, int]   # (x, y)

# --- Nivel 0: movimiento aleatorio --------------------------------------------
def choose_random(color: str, gen_moves: Callable[[str], list[Move]]) -> Optional[Move]:
    moves = gen_moves(color)
    if not moves: 
        return None
    return random.choice(moves)

# --- Nivel 1: “captura-mejor / evita perder material” -------------------------
# Scoring simple: (valor pieza capturada) - (valor de mi pieza si la casilla destino está atacada)
def choose_greedy(
    color: str,
    gen_moves: Callable[[str], list[Move]],
    piece_at: Callable[[tuple[int,int]], Optional[tuple[str, str]]],          # -> (name, color) | None
    piece_name_by_index: Callable[[str, int], str],                            # -> name
    is_attacked_by: Callable[[tuple[int,int], str], bool]                      # (square, by_color) -> bool
) -> Optional[Move]:
    moves = gen_moves(color)
    if not moves:
        return None

    opp = 'black' if color == 'white' else 'white'

    def score(m: Move) -> float:
        gain = 0
        target = piece_at(m.to)
        if target:
            gain += PIECE_VALUE.get(target[0], 0)

        # Penaliza si el destino está atacado por el rival
        my_piece = piece_name_by_index(color, m.sel_index)
        if is_attacked_by(m.to, opp):
            gain -= PIECE_VALUE.get(my_piece, 0)

        # Desempate leve
        return gain + random.random() * 0.01

    return max(moves, key=score, default=None)

# --- Nivel 2 (futuro): minimax d=2 (necesita simulación limpia) ---------------
# De momento dejamos un “stub” para cuando quieras avanzar:
def choose_minimax_stub(*args, **kwargs):
    # Retorna None para que el caller haga fallback
    return None

def choose_by_level(level: int, **kwargs) -> Optional[Move]:
    color = kwargs['color']
    gen_moves = kwargs['gen_moves']
    if level <= 0:
        return choose_random(color, gen_moves)
    elif level == 1:
        return choose_greedy(
            color,
            gen_moves,
            kwargs['piece_at'],
            kwargs['piece_name_by_index'],
            kwargs['is_attacked_by'],
        )
    else:
        # más adelante minimax d=2
        mv = choose_minimax_stub()
        return mv or choose_greedy(
            color,
            gen_moves,
            kwargs['piece_at'],
            kwargs['piece_name_by_index'],
            kwargs['is_attacked_by'],
        )
