# ai.py
from dataclasses import dataclass
from typing import Callable, Optional, Tuple, List
import math, random, time

# ==================== Tipos / contratos que main.py nos pasa ====================
@dataclass
class Move:
    color: str                 # 'white' | 'black'
    sel_index: int             # índice en white/black_pieces
    to: Tuple[int, int]        # (x, y)

GenMovesFn = Callable[[str], List[Move]]
PieceAtFn = Callable[[Tuple[int,int]], Optional[Tuple[str,str]]]
PieceNameByIdxFn = Callable[[str,int], str]
IsAttackedByFn = Callable[[Tuple[int,int], str], bool]
SimPushFn = Callable[[Move], object]   # debe devolver un "state" para deshacer
SimPopFn = Callable[[object], None]
InCheckFn = Callable[[str], bool]
SideHasLegalMoveFn = Callable[[str], bool]

# ===================== Parámetros de evaluación (centipeones) ===================
PIECE_VALUE = {
    'pawn': 100, 'knight': 320, 'bishop': 330, 'rook': 500, 'queen': 900, 'king': 0
}

# Tablas de casillas (desde POV blanco; para negras espejamos verticalmente)
PST_PAWN = [
    [  0,  0,  0,  0,  0,  0,  0,  0],
    [ 40, 40, 40, 40, 40, 40, 40, 40],
    [ 10, 10, 20, 30, 30, 20, 10, 10],
    [  6,  6, 10, 25, 25, 10,  6,  6],
    [  2,  2,  6, 12, 12,  6,  2,  2],
    [  1,  1,  2,  4,  4,  2,  1,  1],
    [  0,  0,  0, -2, -2,  0,  0,  0],
    [  0,  0,  0,  0,  0,  0,  0,  0],
]
PST_KNIGHT = [
    [ -40,-30,-20,-20,-20,-20,-30,-40],
    [ -30,-15,  0,  5,  5,  0,-15,-30],
    [ -20,  5, 10, 15, 15, 10,  5,-20],
    [ -20,  0, 15, 22, 22, 15,  0,-20],
    [ -20,  0, 12, 20, 20, 12,  0,-20],
    [ -20,  5, 10, 15, 15, 10,  5,-20],
    [ -30,-10,  0,  0,  0,  0,-10,-30],
    [ -40,-25,-20,-20,-20,-20,-25,-40],
]
PST_BISHOP = [
    [ -20,-10,-10,-10,-10,-10,-10,-20],
    [ -10,  5,  0,  0,  0,  0,  5,-10],
    [ -10, 10, 10, 12, 12, 10, 10,-10],
    [ -10,  0, 12, 16, 16, 12,  0,-10],
    [ -10,  0, 12, 16, 16, 12,  0,-10],
    [ -10, 10, 10, 12, 12, 10, 10,-10],
    [ -10,  5,  0,  0,  0,  0,  5,-10],
    [ -20,-10,-10,-10,-10,-10,-10,-20],
]
PST_ROOK = [
    [ 0,  0,  5,  8,  8,  5,  0,  0],
    [ 5,  8, 12, 16, 16, 12,  8,  5],
    [ 2,  6,  8, 12, 12,  8,  6,  2],
    [ 0,  2,  4,  6,  6,  4,  2,  0],
    [ 0,  2,  4,  6,  6,  4,  2,  0],
    [ 0,  0,  2,  4,  4,  2,  0,  0],
    [-4, -4, -2,  0,  0, -2, -4, -4],
    [-6, -6, -4, -2, -2, -4, -6, -6],
]
PST_QUEEN = [
    [ -20,-10,-10, -5, -5,-10,-10,-20],
    [ -10,  0,  5,  0,  0,  0,  0,-10],
    [ -10,  5,  5,  5,  5,  5,  5,-10],
    [  -5,  0,  5,  8,  8,  5,  0, -5],
    [  -5,  0,  5,  8,  8,  5,  0, -5],
    [ -10,  5,  5,  5,  5,  5,  5,-10],
    [ -10,  0,  5,  0,  0,  0,  0,-10],
    [ -20,-10,-10, -5, -5,-10,-10,-20],
]
PST_KING_MID = [
    [ -30,-40,-40,-50,-50,-40,-40,-30],
    [ -30,-40,-40,-50,-50,-40,-40,-30],
    [ -30,-35,-35,-45,-45,-35,-35,-30],
    [ -20,-30,-30,-30,-30,-30,-30,-20],
    [ -10,-20,-20,-20,-20,-20,-20,-10],
    [  10,  5,  0,  0,  0,  0,  5, 10],
    [  20, 20, 10,  0,  0, 10, 20, 20],
    [  20, 30, 20,  0,  0, 20, 30, 20],
]
PSTS = {
    'pawn': PST_PAWN,
    'knight': PST_KNIGHT,
    'bishop': PST_BISHOP,
    'rook': PST_ROOK,
    'queen': PST_QUEEN,
    'king': PST_KING_MID,
}

MOBILITY_W = 4
MATE = 100_000

# ========================== Utilidades básicas ==========================
def other(c: str) -> str:
    return 'black' if c == 'white' else 'white'

def mirror_y(y: int) -> int:
    return 7 - y

# algebra simple "a8h1" con tu sistema de coordenadas (y=0 es la fila de arriba)
FILES = "abcdefgh"
def sq_to_alg(sq: Tuple[int,int]) -> str:
    x, y = sq
    file_ = FILES[x]
    rank = 8 - y
    return f"{file_}{rank}"

def move_to_alg(m: Move) -> str:
    return f"{sq_to_alg_from_index(m)}{sq_to_alg(m.to)}"

def sq_to_alg_from_index(m: Move) -> str:
    # No tenemos la casilla de origen explícita en Move,
    # así que devolvemos "??" para el from si quisiéramos SAN real.
    # Para PV imprimimos solo destino, o "fromto" si el caller conoce el origen.
    # Aquí devolvemos destino "e2e4" si el caller nos da el 'from'.
    return ""  # lo dejamos vacío y el caller arma from->to si lo conoce

# ========================== Niveles 0 y 1 ==========================
def choose_random(color: str, gen_moves: GenMovesFn) -> Optional[Move]:
    moves = gen_moves(color)
    if not moves:
        return None
    return random.choice(moves)

def choose_greedy(
    color: str,
    gen_moves: GenMovesFn,
    piece_at: PieceAtFn,
    piece_name_by_index: PieceNameByIdxFn,
    is_attacked_by: IsAttackedByFn,
) -> Optional[Move]:
    moves = gen_moves(color)
    if not moves:
        return None
    opp = 'black' if color == 'white' else 'white'

    def score(m: Move) -> float:
        gain = 0
        tgt = piece_at(m.to)
        if tgt:
            gain += PIECE_VALUE.get(tgt[0], 0)
        my_piece = piece_name_by_index(color, m.sel_index)
        if is_attacked_by(m.to, opp):
            gain -= PIECE_VALUE.get(my_piece, 0)
        return gain + random.random() * 0.01  # leve desempate

    return max(moves, key=score, default=None)

# ========================== Evaluación ==========================
def eval_static(
    to_move: str,
    gen_moves: GenMovesFn,
    piece_at: PieceAtFn,
) -> int:
    """
    Devuelve el score desde el punto de vista de quien mueve (negamax).
    Base: material + PST + movilidad.
    """
    total = 0

    # Material + PST
    for y in range(8):
        for x in range(8):
            p = piece_at((x, y))
            if not p:
                continue
            name, col = p
            val = PIECE_VALUE.get(name, 0)
            pst = PSTS[name]
            pst_bonus = pst[y][x] if col == 'white' else pst[mirror_y(y)][x]
            if col == 'white':
                total += val + pst_bonus
            else:
                total -= val + pst_bonus

    # Movilidad
    try:
        mob = len(gen_moves('white')) - len(gen_moves('black'))
        total += MOBILITY_W * mob
    except Exception:
        pass

    # Negamax: devolver score desde la perspectiva del que mueve
    return total if to_move == 'white' else -total

def order_moves(
    moves: List[Move],
    piece_at: PieceAtFn,
    piece_name_by_index: PieceNameByIdxFn,
) -> List[Move]:
    """Capturas primero (MVV-LVA). Silenciosas: preferir centro."""
    def key(m: Move):
        tgt = piece_at(m.to)
        if tgt:
            victim = PIECE_VALUE.get(tgt[0], 0)
            attacker = PIECE_VALUE.get(piece_name_by_index(m.color, m.sel_index), 0)
            return (1, victim - 0.01 * attacker)  # grupo capturas
        # silenciosa: prima centro
        cx, cy = 3.5, 3.5
        dx = m.to[0] - cx
        dy = m.to[1] - cy
        base = -(dx*dx + dy*dy)  # más cerca del centro = mayor
        return (0, base)

    return sorted(moves, key=key, reverse=True)

# ========================== Quiescence search ==========================
NODES = 0  # contador global por búsqueda

def qsearch(
    to_move: str,
    alpha: int, beta: int,
    gen_moves: GenMovesFn,
    piece_at: PieceAtFn,
    piece_name_by_index: PieceNameByIdxFn,
    sim_push: SimPushFn, sim_pop: SimPopFn,
) -> int:
    global NODES
    NODES += 1

    stand_pat = eval_static(to_move, gen_moves, piece_at)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    # Solo capturas (ignoramos EP por simplicidad)
    moves = [m for m in gen_moves(to_move) if piece_at(m.to) is not None]
    # Ordenar capturas también ayuda
    moves = order_moves(moves, piece_at, piece_name_by_index)

    for m in moves:
        st = sim_push(m)
        score = -qsearch(other(to_move), -beta, -alpha,
                         gen_moves, piece_at, piece_name_by_index,
                         sim_push, sim_pop)
        sim_pop(st)

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha

# ========================== Negamax + αβ ==========================
def negamax(
    depth: int,
    to_move: str,
    alpha: int, beta: int,
    gen_moves: GenMovesFn,
    piece_at: PieceAtFn,
    piece_name_by_index: PieceNameByIdxFn,
    sim_push: SimPushFn, sim_pop: SimPopFn,
    in_check: InCheckFn,
    use_quiescence: bool,
) -> Tuple[int, Optional[Move], List[Move]]:
    """
    Devuelve (score, best_move, PV)
    """
    global NODES
    moves = gen_moves(to_move)

    # terminal
    if not moves:
        if in_check(to_move):
            return -MATE, None, []
        else:
            return 0, None, []

    # hoja
    if depth == 0:
        if use_quiescence:
            return qsearch(to_move, alpha, beta,
                           gen_moves, piece_at, piece_name_by_index,
                           sim_push, sim_pop), None, []
        else:
            return eval_static(to_move, gen_moves, piece_at), None, []

    best_score = -math.inf
    best_move: Optional[Move] = None
    best_pv: List[Move] = []

    # ordenamiento
    moves = order_moves(moves, piece_at, piece_name_by_index)

    for m in moves:
        NODES += 1
        st = sim_push(m)
        val, _, pv_child = negamax(
            depth - 1, other(to_move), -beta, -alpha,
            gen_moves, piece_at, piece_name_by_index,
            sim_push, sim_pop, in_check,
            use_quiescence
        )
        sim_pop(st)

        score = -val
        if score > best_score:
            best_score = score
            best_move = m
            best_pv = [m] + pv_child

        if score > alpha:
            alpha = score
        if alpha >= beta:
            break

    return int(best_score), best_move, best_pv

class SearchAbort(Exception):
    pass

# ========================== Elección Minimax (niveles 2–4) ==========================
def choose_minimax(
    color: str,
    gen_moves: GenMovesFn,
    piece_at: PieceAtFn,
    piece_name_by_index: PieceNameByIdxFn,
    is_attacked_by: IsAttackedByFn,  # no lo usamos aún, queda para mejoras
    sim_push: SimPushFn,
    sim_pop: SimPopFn,
    in_check: InCheckFn,
    side_has_legal_move: SideHasLegalMoveFn,  # no lo usamos aún
    depth: int = 3,
    time_limit_ms: int = 250,
    use_quiescence: bool = False,
    last_move: Optional[Tuple[Tuple[int,int], Tuple[int,int]]] = None,  # opcional, no usado
) -> Optional[Move]:
    global NODES
    best_move = None
    best_pv: List[Move] = []
    start = time.perf_counter()

    # iterative deepening 1..depth
    for d in range(1, depth + 1):
        NODES = 0
        val, mv, pv = negamax(
            depth=d, to_move=color,
            alpha=-math.inf, beta=+math.inf,
            gen_moves=gen_moves,
            piece_at=piece_at,
            piece_name_by_index=piece_name_by_index,
            sim_push=sim_push, sim_pop=sim_pop,
            in_check=in_check,
            use_quiescence=use_quiescence,
        )
        elapsed = max(1e-9, time.perf_counter() - start)
        nps = int(NODES / elapsed)

        if mv:
            best_move = mv
            best_pv = pv

        # imprime stats de esta iteración
        pv_str = " ".join(f"{sq_to_alg(frm)}{sq_to_alg(m.to)}"
                          if frm is not None else f"{sq_to_alg(m.to)}"
                          for frm, m in _pv_with_from(best_pv, gen_moves))
        print(f"[AI] depth={d} score={val} nodes={NODES} nps={nps} pv={pv_str}")

        # control de tiempo “blando”
        if (elapsed * 1000.0) >= time_limit_ms:
            break

    return best_move

def _pv_with_from(pv: List[Move], gen_moves: GenMovesFn):
    """
    Intenta reconstruir 'from' de forma barata:
    para cada move de la PV, buscamos entre los legales de ese color
    cuál pieza tiene 'sel_index' y su ubicación actual.
    Nota: solo para imprimir; no se usa en la búsqueda.
    """
    # Clonamos la posición implícitamente a través de sim_push/sim_pop
    # pero aquí no las tenemos; así que devolvemos (None, move).
    # Si querés de verdad "from", más adelante podemos exponerlo desde main.py.
    return [(None, m) for m in pv]

# ========================== Selector por nivel ==========================
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
        # nivel 2 → depth=2 (sin quiescence)
        # nivel 3 → depth=3 (sin quiescence)
        # nivel 4 → depth=3 (con quiescence)
        depth = 2 if level == 2 else 3
        use_qs = (level >= 4)
        return choose_minimax(
            color=color,
            gen_moves=gen_moves,
            piece_at=kwargs['piece_at'],
            piece_name_by_index=kwargs['piece_name_by_index'],
            is_attacked_by=kwargs['is_attacked_by'],
            sim_push=kwargs['sim_push'],
            sim_pop=kwargs['sim_pop'],
            in_check=kwargs['in_check'],
            side_has_legal_move=kwargs['side_has_legal_move'],
            depth=depth,
            time_limit_ms=400,
            use_quiescence=use_qs,
            last_move=kwargs.get('last_move'),
        )
