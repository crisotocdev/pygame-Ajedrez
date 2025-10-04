# (CLEAN) ya no usamos copy; el dict de promoción se recrea sin rects
from ai import choose_by_level  # nuevo
ai_level = 0  # 0: random, 1: greedy

import pygame
import os
from dataclasses import dataclass

# ---- FIX de arranque/primer frame (Windows + centrado) ----
os.environ['SDL_WINDOWS_DPI_AWARENESS'] = 'permonitorv2'
os.environ['SDL_VIDEO_HIGHDPI_DISABLED'] = '1'
os.environ['SDL_VIDEO_CENTERED'] = '1'
# -----------------------------------------------------------

# === SONIDOS: baja latencia antes de pygame.init() ===
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()

# =================== CONFIGURACIÓN GENERAL ===================
WIDTH, HEIGHT = 1000, 900   # 800 tablero + 100 barra
SIDEBAR_W    = 200
STATUS_H     = 100
MIN_SQUARE   = 64
MIN_W        = 8 * MIN_SQUARE + SIDEBAR_W
MIN_H        = 8 * MIN_SQUARE + STATUS_H

FLAGS = pygame.RESIZABLE | pygame.SCALED
screen = pygame.display.set_mode((WIDTH, HEIGHT), FLAGS)
pygame.display.set_caption('Two-Player Pygame Chess!')

font     = pygame.font.Font('freesansbold.ttf', 20)
big_font = pygame.font.Font('freesansbold.ttf', 50)
coord_font = pygame.font.Font('freesansbold.ttf', 14)
timer    = pygame.time.Clock()
fps      = 60

# UX
flipped = False      # F: ver tablero desde negras
show_hints = True    # H: mostrar/ocultar puntos de destino
show_help = False  # F1: mostrar/ocultar ayuda de teclas


# -------- Colores --------
COL_BG = (50, 50, 50)
COL_BOARD_LIGHT = (211, 211, 211)
COL_BOARD_LINE  = (0, 0, 0)
COL_GOLD = (255, 204, 0)
COL_PANEL = (160, 160, 160)
COL_TXT = (0, 0, 0)
COL_RED = (220, 30, 30)
COL_BLUE = (30, 60, 220)
COL_LAST = (255, 215, 0)
COL_EP = (0, 200, 200)  # resaltado en passant

# === SONIDOS: cargar (MP3) ===
START_SOUND = MOVE_SOUND = CAPTURE_SOUND = None
try:
    START_SOUND = pygame.mixer.Sound('assets/sounds/start.mp3'); START_SOUND.set_volume(0.8)
except Exception as e:
    print("Aviso: no se pudo cargar start.mp3:", e)
try:
    MOVE_SOUND = pygame.mixer.Sound('assets/sounds/move.mp3'); MOVE_SOUND.set_volume(0.6)
except Exception as e:
    print("Aviso: no se pudo cargar move.mp3:", e)
try:
    CAPTURE_SOUND = pygame.mixer.Sound('assets/sounds/capture.mp3'); CAPTURE_SOUND.set_volume(0.8)
except Exception as e:
    print("Aviso: no se pudo cargar capture.mp3:", e)

# -------- Estado global --------
counter = 0
turn_step = 0         # 0-1 blancas, 2-3 negras
selection = 100
valid_moves = []
game_over = None      # None | 'white' | 'black' | 'draw'
last_move = None      # ((fx,fy),(tx,ty))
history = []          # pila de estados para deshacer

# ---- Enroque: flags de movimiento de rey y torres ----
white_king_moved = False
white_rook_a_moved = False   # torre en (0,0)
white_rook_h_moved = False   # torre en (7,0)
black_king_moved = False
black_rook_a_moved = False   # torre en (0,7)
black_rook_h_moved = False   # torre en (7,7)

# (Opcional futuro) En passant
ep_target = None  # casilla susceptible de captura al paso tras un doble paso; no se usa aún

# =================== CARGA DE IMÁGENES ORIGINALES (sin escalar) ===================
def _load_img(path):
    img = pygame.image.load(path).convert_alpha()
    return img

try:
    black_queen_o  = _load_img('assets/images/black queen.png')
    black_king_o   = _load_img('assets/images/black king.png')
    black_rook_o   = _load_img('assets/images/black rook.png')
    black_bishop_o = _load_img('assets/images/black bishop.png')
    black_knight_o = _load_img('assets/images/black knight.png')
    black_pawn_o   = _load_img('assets/images/black pawn.png')

    white_queen_o  = _load_img('assets/images/white queen.png')
    white_king_o   = _load_img('assets/images/white king.png')
    white_rook_o   = _load_img('assets/images/white rook.png')
    white_bishop_o = _load_img('assets/images/white bishop.png')
    white_knight_o = _load_img('assets/images/white knight.png')
    white_pawn_o   = _load_img('assets/images/white pawn.png')
except Exception as e:
    # Si faltan assets, usa rectángulos placeholder
    print("Aviso: Faltan imágenes, se usarán placeholders:", e)
    def ph(w,h,color=(200,60,60)):
        s=pygame.Surface((w,h),pygame.SRCALPHA); pygame.draw.rect(s,color,(0,0,w,h),border_radius=10)
        pygame.draw.rect(s,(255,230,230),(0,0,w,h),3,border_radius=10); return s
    # generar originales "neutros" 100x100 (se reescalan luego)
    black_queen_o=black_king_o=black_rook_o=black_bishop_o=black_knight_o=black_pawn_o=ph(100,100,(200,60,60))
    white_queen_o=white_king_o=white_rook_o=white_bishop_o=white_knight_o=white_pawn_o=ph(100,100,(60,60,200))

# Lista de nombres para mapping
piece_list = ['pawn', 'queen', 'king', 'knight', 'rook', 'bishop']

# === Caché de escalados por tamaño de casilla ===
_scaled_cache = {"square": None}

def _scaled_for_square(square):
    """Devuelve (white_images, small_white_images, black_images, small_black_images) para 'square'."""
    if _scaled_cache["square"] == square:
        return (_scaled_cache["w"], _scaled_cache["ws"],
                _scaled_cache["b"], _scaled_cache["bs"])

    # tamaños relativos (idénticos a tu layout original)
    big = int(square * 0.80)    # 80 px cuando square=100
    pawn_big = int(square * 0.90)  # 90 px cuando square=100
    small = int(square * 0.45)   # miniaturas panel

    def sc(img, w, h):
        w=max(1,int(w)); h=max(1,int(h))
        # Para pixel art puro cambia a: pygame.transform.scale(img, (w, h))
        return pygame.transform.smoothscale(img, (w, h))

    # blancos grandes
    white_pawn   = sc(white_pawn_o,   pawn_big, pawn_big)
    white_queen  = sc(white_queen_o,  big, big)
    white_king   = sc(white_king_o,   big, big)
    white_knight = sc(white_knight_o, big, big)
    white_rook   = sc(white_rook_o,   big, big)
    white_bishop = sc(white_bishop_o, big, big)
    white_images = [white_pawn, white_queen, white_king, white_knight, white_rook, white_bishop]

    # blancos pequeños
    white_pawn_s   = sc(white_pawn_o,   small, small)
    white_queen_s  = sc(white_queen_o,  small, small)
    white_king_s   = sc(white_king_o,   small, small)
    white_knight_s = sc(white_knight_o, small, small)
    white_rook_s   = sc(white_rook_o,   small, small)
    white_bishop_s = sc(white_bishop_o, small, small)
    small_white_images = [white_pawn_s, white_queen_s, white_king_s, white_knight_s, white_rook_s, white_bishop_s]

    # negros grandes
    black_pawn   = sc(black_pawn_o,   pawn_big, pawn_big)
    black_queen  = sc(black_queen_o,  big, big)
    black_king   = sc(black_king_o,   big, big)
    black_knight = sc(black_knight_o, big, big)
    black_rook   = sc(black_rook_o,   big, big)
    black_bishop = sc(black_bishop_o, big, big)
    black_images = [black_pawn, black_queen, black_king, black_knight, black_rook, black_bishop]

    # negros pequeños
    black_pawn_s   = sc(black_pawn_o,   small, small)
    black_queen_s  = sc(black_queen_o,  small, small)
    black_king_s   = sc(black_king_o,   small, small)
    black_knight_s = sc(black_knight_o, small, small)
    black_rook_s   = sc(black_rook_o,   small, small)
    black_bishop_s = sc(black_bishop_o, small, small)
    small_black_images = [black_pawn_s, black_queen_s, black_king_s, black_knight_s, black_rook_s, black_bishop_s]

    _scaled_cache.update({
        "square": square,
        "w": white_images, "ws": small_white_images,
        "b": black_images, "bs": small_black_images
    })
    return white_images, small_white_images, black_images, small_black_images

# =================== ESTADO DE PIEZAS Y RESETEO ===================
def reset_game_state():
    global white_pieces, white_locations, black_pieces, black_locations
    global captured_pieces_white, captured_pieces_black
    global turn_step, selection, valid_moves, game_over, last_move, history
    global white_options, black_options, counter
    global white_king_moved, white_rook_a_moved, white_rook_h_moved
    global black_king_moved, black_rook_a_moved, black_rook_h_moved
    global ep_target
    # [FIX] también reseteamos flags de promoción y arrastre
    global promotion_pending, awaiting_promotion
    global dragging, drag_index, drag_color, mouse_pos

    # Orden estándar: rook, knight, bishop, queen, king, bishop, knight, rook
    white_pieces[:] = ['rook', 'knight', 'bishop', 'queen', 'king', 'bishop', 'knight', 'rook',
                       'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn']
    white_locations[:] = [(0,0), (1,0), (2,0), (3,0), (4,0), (5,0), (6,0), (7,0),
                          (0,1), (1,1), (2,1), (3,1), (4,1), (5,1), (6,1), (7,1)]
    black_pieces[:] = ['rook', 'knight', 'bishop', 'queen', 'king', 'bishop', 'knight', 'rook',
                       'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn']
    black_locations[:] = [(0,7), (1,7), (2,7), (3,7), (4,7), (5,7), (6,7), (7,7),
                          (0,6), (1,6), (2,6), (3,6), (4,6), (5,6), (6,6), (7,6)]

    captured_pieces_white.clear()
    captured_pieces_black.clear()
    turn_step = 0
    selection = 100
    valid_moves = []
    game_over = None
    last_move = None
    history = []
    counter = 0

    # flags enroque
    white_king_moved = False
    white_rook_a_moved = False
    white_rook_h_moved = False
    black_king_moved = False
    black_rook_a_moved = False
    black_rook_h_moved = False

    # en passant
    ep_target = None

    # [FIX] limpiar promoción y arrastre
    promotion_pending = None
    awaiting_promotion = False
    dragging = False
    drag_index = None
    drag_color = None
    mouse_pos = (0, 0)

    white_options = check_options(white_pieces, white_locations, "white")
    black_options = check_options(black_pieces, black_locations, "black")

    if START_SOUND:
        START_SOUND.play()

white_pieces = []
white_locations = []
black_pieces = []
black_locations = []
captured_pieces_white = []
captured_pieces_black = []

# =================== GEOMETRÍA RESPONSIVA ===================
def compute_square(win_w, win_h):
    usable_w = max(win_w - SIDEBAR_W, 0)
    usable_h = max(win_h - STATUS_H, 0)
    square   = min(usable_w // 8, usable_h // 8)
    square   = max(square, MIN_SQUARE)
    return square

def board_rect_for(square, win_w, win_h):
    board_px = square * 8
    # centrado horizontal dentro del área útil
    margin_left = max((win_w - SIDEBAR_W - board_px) // 2, 0)
    return pygame.Rect(margin_left, 0, board_px, board_px)

def to_screen_xy(cell, square, board_rect):
    """(x,y) casilla -> esquina superior izquierda en pixeles (respeta flipped)."""
    x, y = cell
    if flipped:
        x = 7 - x
        y = 7 - y
    return board_rect.x + x * square, y * square

def mouse_to_cell(pos, square, board_rect):
    """(mx,my) mouse -> (x,y) casilla o None si fuera (respeta flipped)."""
    mx, my = pos
    if not board_rect.collidepoint(mx, my):
        return None
    dx = (mx - board_rect.x) // square
    dy = my // square
    if not (0 <= dx <= 7 and 0 <= dy <= 7):
        return None
    return (7 - dx, 7 - dy) if flipped else (dx, dy)

# =================== ATAQUES / AYUDAS PARA ENROQUE ===================
def pawn_attacks(position, color):
    x, y = position
    attacks = []
    if color == 'white':
        for dx in (-1, 1):
            nx, ny = x + dx, y + 1
            if 0 <= nx <= 7 and 0 <= ny <= 7:
                attacks.append((nx, ny))
    else:
        for dx in (-1, 1):
            nx, ny = x + dx, y - 1
            if 0 <= nx <= 7 and 0 <= ny <= 7:
                attacks.append((nx, ny))
    return attacks

def king_attacks(position):
    x, y = position
    res = []
    for dx, dy in [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]:
        nx, ny = x+dx, y+dy
        if 0 <= nx <= 7 and 0 <= ny <= 7:
            res.append((nx, ny))
    return res

def squares_attacked_by(color):
    """Conjunto de casillas atacadas por 'color' (sin contar enroques como ataque)."""
    pieces = white_pieces if color == 'white' else black_pieces
    locs   = white_locations if color == 'white' else black_locations
    attacked = set()
    for i, pc in enumerate(pieces):
        pos = locs[i]
        if pc == 'pawn':
            for s in pawn_attacks(pos, color):
                attacked.add(s)
        elif pc == 'knight':
            for s in check_knight(pos, color): attacked.add(s)
        elif pc == 'bishop':
            for s in check_bishop(pos, color): attacked.add(s)
        elif pc == 'rook':
            for s in check_rook(pos, color): attacked.add(s)
        elif pc == 'queen':
            for s in check_queen(pos, color): attacked.add(s)
        elif pc == 'king':
            for s in king_attacks(pos): attacked.add(s)
    return attacked

def piece_at(square):
    # square: (x, y)
    if square in white_locations:
        i = white_locations.index(square)
        return (white_pieces[i], 'white')
    if square in black_locations:
        i = black_locations.index(square)
        return (black_pieces[i], 'black')
    return None

def piece_name_by_index(color, idx):
    return white_pieces[idx] if color == 'white' else black_pieces[idx]

def is_attacked_by(square, by_color):
    return square in squares_attacked_by(by_color)

def path_clear_between(a, b, blockers):
    """True si entre a=(x1,y) y b=(x2,y) no hay piezas (excluye extremos)."""
    (x1,y1), (x2,y2) = a, b
    if y1 != y2: return False
    lo, hi = sorted([x1, x2])
    for x in range(lo+1, hi):
        if (x, y1) in blockers:
            return False
    return True

# [MOD] Ajuste de UI (ya tenías estas)
def _fit_font(text, font_path, max_w, max_h, base_px=50):
    size = min(base_px, int(max_h * 0.8))
    while size > 8:
        f = pygame.font.Font(font_path, size)
        if f.size(text)[0] <= max_w and f.get_height() <= max_h:
            return f
        size -= 1
    return pygame.font.Font(font_path, 8)

def _blit_centered(surface, surf, rect):
    x = rect.x + (rect.w - surf.get_width()) // 2
    y = rect.y + (rect.h - surf.get_height()) // 2
    surface.blit(surf, (x, y))

# =================== [NUEVO] PROMOCIÓN Y DRAG ===================
# Estados de promoción y arrastre
promotion_pending = None     # dict con {'color','index','buttons':{...}}
awaiting_promotion = False

dragging = False
drag_index = None
drag_color = None
mouse_pos = (0, 0)

def draw_promotion_menu(square):
    """Dibuja un popup centrado con 4 opciones: dama, torre, alfil, caballo."""
    global promotion_pending
    if not promotion_pending:
        return

    W, H = screen.get_size()
    shade = pygame.Surface((W, H), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 120))
    screen.blit(shade, (0, 0))

    box_w, box_h = int(W * 0.45), int(H * 0.22)
    box = pygame.Rect((W - box_w)//2, (H - box_h)//2, box_w, box_h)
    pygame.draw.rect(screen, (235, 235, 235), box, border_radius=14)
    pygame.draw.rect(screen, COL_GOLD, box, 6, border_radius=14)

    title = "Promoción: elige pieza"
    f = _fit_font(title, 'freesansbold.ttf', box.w - 40, int(box.h*0.25), base_px=48)
    surf = f.render(title, True, (20, 20, 20))
    _blit_centered(screen, surf, pygame.Rect(box.x, box.y+10, box.w, f.get_height()))

    opts = ['queen', 'rook', 'bishop', 'knight']
    btn_area = pygame.Rect(box.x+20, box.y + box.h//2 - 20, box.w-40, box.h//2 - 30)
    gap = 12
    btn_w = (btn_area.w - gap*3) // 4
    btn_h = btn_area.h
    btn_h = max(btn_h, 36)  # [FIX] altura mínima para evitar artefactos en ventanas pequeñas
    rects = {}
    for i, name in enumerate(opts):
        r = pygame.Rect(btn_area.x + i*(btn_w+gap), btn_area.y, btn_w, btn_h)
        pygame.draw.rect(screen, (245,245,245), r, border_radius=10)
        pygame.draw.rect(screen, (90,90,90), r, 2, border_radius=10)
        rects[name] = r

    # Íconos según color
    color = promotion_pending['color']
    white_imgs, _, black_imgs, _ = _scaled_for_square(square)
    imgs = white_imgs if color == 'white' else black_imgs
    name_to_idx = {'pawn':0, 'queen':1, 'king':2, 'knight':3, 'rook':4, 'bishop':5}
    for name, r in rects.items():
        idx = name_to_idx[name]
        icon = imgs[idx]
        scale = min(int(r.w*0.75), int(r.h*0.75))
        icon = pygame.transform.smoothscale(icon, (scale, scale))
        screen.blit(icon, (r.centerx - icon.get_width()//2, r.centery - icon.get_height()//2))

    promotion_pending['buttons'] = rects

def finalize_promotion(choice_piece):
    """Aplica la pieza elegida y pasa el turno; reevalúa fin de juego."""
    global promotion_pending, awaiting_promotion, turn_step, game_over
    if not promotion_pending:
        return
    color = promotion_pending['color']
    idx   = promotion_pending['index']

    if color == 'white':
        white_pieces[idx] = choice_piece
        _recalc_options()
        if in_check('black') and not side_has_legal_move('black'):
            set_game_over('white')
        elif (not in_check('black')) and (not side_has_legal_move('black')):
            set_game_over('draw')
        turn_step = 2
    else:
        black_pieces[idx] = choice_piece
        _recalc_options()
        if in_check('white') and not side_has_legal_move('white'):
            set_game_over('black')
        elif (not in_check('white')) and (not side_has_legal_move('white')):
            set_game_over('draw')
        turn_step = 0

    promotion_pending = None
    awaiting_promotion = False

# ---- Tablero y panel ----------------------------------------------------------
def draw_board(square):
    W, H = screen.get_size()
    board_rect = board_rect_for(square, W, H)

    # casillas (claro/oscuro)
    for y in range(8):
        for x in range(8):
            if (x + y) % 2 == 0:
                pygame.draw.rect(screen, COL_BOARD_LIGHT,
                                 (board_rect.x + x*square, y*square, square, square))

    # líneas del tablero
    for i in range(9):
        pygame.draw.line(screen, COL_BOARD_LINE,
                         (board_rect.x, i * square), (board_rect.x + board_rect.w, i * square), 2)
        pygame.draw.line(screen, COL_BOARD_LINE,
                         (board_rect.x + i * square, 0), (board_rect.x + i * square, board_rect.h), 2)

    # barra inferior
    bar_y = H - STATUS_H
    pygame.draw.rect(screen, COL_PANEL, [0, bar_y, W, STATUS_H])
    pygame.draw.rect(screen, COL_GOLD,  [0, bar_y, W, STATUS_H], 5)

    # panel derecho
    pygame.draw.rect(screen, COL_PANEL, [W - SIDEBAR_W, 0, SIDEBAR_W, H])
    pygame.draw.rect(screen, COL_GOLD,  [W - SIDEBAR_W, 0, SIDEBAR_W, H], 5)

    # texto inferior (centrado y con auto-shrink), incluye estado de promoción
    if awaiting_promotion and promotion_pending:
        status_text = "Elige pieza para la promoción (Q/R/B/N)"
    else:
        if game_over is None:
            status_text = ['Blanco: Selecciona una pieza a mover', 'Blanco: Elige un destino',
                           'Negro: Selecciona una pieza a mover',  'Negro: Elige un destino'][turn_step]
        else:
            status_text = ("Tablas por ahogado" if game_over == 'draw'
                           else ("¡Jaque mate! Ganan Blancas" if game_over == 'white' else "¡Jaque mate! Ganan Negras"))

    # Área de texto sin el panel derecho
    text_area = pygame.Rect(0, bar_y, max(50, W - SIDEBAR_W), STATUS_H)
    bar_inner = text_area.inflate(-20, -20)

    font_path = 'freesansbold.ttf'
    fit_font  = _fit_font(status_text, font_path, bar_inner.w, bar_inner.h, base_px=50)
    surf      = fit_font.render(status_text, True, COL_TXT)
    _blit_centered(screen, surf, bar_inner)

def draw_coords(square):
    """Dibuja letras (archivos) abajo y números (rangos) a la izquierda."""
    W, H = screen.get_size()
    board_rect = board_rect_for(square, W, H)

    files = "ABCDEFGH" if not flipped else "HGFEDCBA"
    for i, ch in enumerate(files):
        s = coord_font.render(ch, True, (0, 0, 0))
        x = board_rect.x + i * square + square - s.get_width() - 4
        y = 8 * square - s.get_height() - 2
        screen.blit(s, (x, y))

    ranks = ["8","7","6","5","4","3","2","1"] if not flipped else ["1","2","3","4","5","6","7","8"]
    for j, ch in enumerate(ranks):
        s = coord_font.render(ch, True, (0, 0, 0))
        x = board_rect.x + 2
        y = j * square + 2
        screen.blit(s, (x, y))

def draw_help_overlay():
    W, H = screen.get_size()
    shade = pygame.Surface((W, H), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 160))
    screen.blit(shade, (0, 0))

    box_w, box_h = min(520, int(W * 0.7)), min(360, int(H * 0.7))
    box = pygame.Rect((W - box_w)//2, (H - box_h)//2, box_w, box_h)
    pygame.draw.rect(screen, (245,245,245), box, border_radius=14)
    pygame.draw.rect(screen, COL_GOLD, box, 4, border_radius=14)

    lines = [
        "Atajos:",
        "F – Flip de tablero",
        "H – Mostrar/ocultar ayudas",
        "A – IA juega el turno actual",
        "0 / 1 – Nivel de IA (aleatorio / greedy)",
        "Ctrl+Z – Deshacer",
        "R – Reiniciar (solo si terminó)",
        "F1 – Mostrar/ocultar esta ayuda"
    ]

    y = box.y + 18
    title = pygame.font.Font('freesansbold.ttf', 26).render(lines[0], True, (25,25,25))
    screen.blit(title, (box.x + 18, y)); y += 36

    f = pygame.font.Font('freesansbold.ttf', 20)
    for s in lines[1:]:
        t = f.render(s, True, (35,35,35))
        screen.blit(t, (box.x + 22, y))
        y += 28


# ---- MINIATURAS DE CAPTURADAS -------------------------------------------------
def _small_img_for(piece_name, side, square):
    white_images, small_white_images, black_images, small_black_images = _scaled_for_square(square)
    idx = piece_list.index(piece_name)
    return small_white_images[idx] if side == 'white' else small_black_images[idx]

def draw_captured_panel(square):
    W, H = screen.get_size()
    panel_x = W - SIDEBAR_W
    panel_w = SIDEBAR_W
    top_y   = 10
    mid_y   = H // 2
    pad_x   = 12
    cell    = int(square * 0.48)  # proporcional al tamaño de casilla
    cols    = max(2, panel_w // max(1, cell))

    # Etiquetas
    title1 = font.render("Negras capturadas", True, COL_TXT)
    title2 = font.render("Blancas capturadas", True, COL_TXT)
    screen.blit(title1, (panel_x + (panel_w - title1.get_width()) // 2, top_y))
    screen.blit(title2, (panel_x + (panel_w - title2.get_width()) // 2, mid_y))

    # Sección 1 (negras capturadas por blancas)
    start_y = top_y + 26
    for i, name in enumerate(captured_pieces_white):
        col = i % cols
        row = i // cols
        x = panel_x + pad_x + col * cell
        y = start_y + row * cell
        img = _small_img_for(name, 'black', square)
        screen.blit(img, (x + (cell - img.get_width()) // 2,
                          y + (cell - img.get_height()) // 2))

    # Sección 2 (blancas capturadas por negras)
    start_y2 = mid_y + 26
    for i, name in enumerate(captured_pieces_black):
        col = i % cols
        row = i // cols
        x = panel_x + pad_x + col * cell
        y = start_y2 + row * cell
        img = _small_img_for(name, 'white', square)
        screen.blit(img, (x + (cell - img.get_width()) // 2,
                          y + (cell - img.get_height()) // 2))

# ---- Dibujo de piezas ---------------------------------------------------------
def draw_pieces(square):
    W, H = screen.get_size()
    board_rect = board_rect_for(square, W, H)
    white_images, _, black_images, _ = _scaled_for_square(square)

    # offsets como en tu layout original, pero relativos a la casilla
    off_big = int(square * 0.10)
    off_pawn_x = int(square * 0.10)
    off_pawn_y = int(square * 0.24)

    # mientras se arrastra, no pintamos esa pieza en su casilla
    # blancas
    for i in range(len(white_pieces)):
        if dragging and drag_color == 'white' and i == drag_index:
            continue
        index = piece_list.index(white_pieces[i])
        cell_x, cell_y = to_screen_xy(white_locations[i], square, board_rect)
        if white_pieces[i] == 'pawn':
            screen.blit(white_images[0], (cell_x + off_pawn_x, cell_y + off_pawn_y))
        else:
            screen.blit(white_images[index], (cell_x + off_big, cell_y + off_big))
        if turn_step < 2 and selection == i:
            pygame.draw.rect(screen, COL_RED, [cell_x + 1, cell_y + 1, square - 2, square - 2], 2)

    # negras
    for i in range(len(black_pieces)):
        if dragging and drag_color == 'black' and i == drag_index:
            continue
        index = piece_list.index(black_pieces[i])
        cell_x, cell_y = to_screen_xy(black_locations[i], square, board_rect)
        if black_pieces[i] == 'pawn':
            screen.blit(black_images[0], (cell_x + off_pawn_x, cell_y + off_pawn_y))
        else:
            screen.blit(black_images[index], (cell_x + off_big, cell_y + off_big))
        if turn_step >= 2 and selection == i:
            pygame.draw.rect(screen, COL_BLUE, [cell_x + 1, cell_y + 1, square - 2, square - 2], 2)

    # Pieza arrastrada “en el aire”
    if dragging and selection != 100:
        imgs = white_images if drag_color == 'white' else black_images
        name = (white_pieces if drag_color=='white' else black_pieces)[drag_index]
        idx  = piece_list.index(name)
        img  = imgs[idx]
        mx, my = mouse_pos
        screen.blit(img, (mx - img.get_width()//2, my - img.get_height()//2))

# ---- Resaltado de última jugada ----------------------------------------------
def draw_last_move(square):
    if not last_move:
        return
    W, H = screen.get_size()
    board_rect = board_rect_for(square, W, H)
    (fx, fy), (tx, ty) = last_move
    sx1, sy1 = to_screen_xy((fx, fy), square, board_rect)
    sx2, sy2 = to_screen_xy((tx, ty), square, board_rect)
    pygame.draw.rect(screen, COL_LAST, (sx1+2, sy1+2, square-4, square-4), 3)
    pygame.draw.rect(screen, COL_LAST, (sx2+2, sy2+2, square-4, square-4), 3)

def draw_ep_target(square):
    """Resalta la casilla ep_target (si existe) con un anillo + punto."""
    if ep_target is None or game_over is not None:
        return

    W, H = screen.get_size()
    board_rect = board_rect_for(square, W, H)

    sx, sy = to_screen_xy(ep_target, square, board_rect)
    cx = sx + square // 2
    cy = sy + square // 2

    r_outer = max(6, square // 3)   # anillo exterior
    r_inner = max(3, square // 10)  # punto central

    # anillo
    pygame.draw.circle(screen, COL_EP, (cx, cy), r_outer, 3)
    # punto
    pygame.draw.circle(screen, COL_EP, (cx, cy), r_inner)

# ---- Generación de movimientos (con enroque estándar en king) -----------------
def check_options(pieces, locations, turn):
    moves_list = []
    all_moves_list = []
    for i in range(len(pieces)):
        location = locations[i]
        piece = pieces[i]
        if piece == 'pawn':
            moves_list = check_pawn(location, turn)
        elif piece == 'rook':
            moves_list = check_rook(location, turn)
        elif piece == 'knight':
            moves_list = check_knight(location, turn)
        elif piece == 'bishop':
            moves_list = check_bishop(location, turn)
        elif piece == 'queen':
            moves_list = check_queen(location, turn)
        elif piece == 'king':
            moves_list = check_king(location, turn)  # incluye enroque
        all_moves_list.append(moves_list)
    return all_moves_list

def check_king(position, color):
    moves_list = []
    friends_list = white_locations if color == 'white' else black_locations
    directions = [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]
    for dx, dy in directions:
        nx, ny = position[0] + dx, position[1] + dy
        if 0 <= nx <= 7 and 0 <= ny <= 7 and (nx, ny) not in friends_list:
            moves_list.append((nx, ny))

    # ===== Enroque (estándar) =====
    y0 = 0 if color == 'white' else 7
    king_start = (4, y0)
    if position == king_start:
        global white_king_moved, white_rook_a_moved, white_rook_h_moved
        global black_king_moved, black_rook_a_moved, black_rook_h_moved

        enemies_attacks = squares_attacked_by('black' if color == 'white' else 'white')
        friends = white_locations if color == 'white' else black_locations
        enemies = black_locations if color == 'white' else white_locations
        blockers = friends + enemies

        # No estar en jaque ahora
        if (position not in enemies_attacks):
            # Corto (lado h): rey (4,y)->(6,y), torre (7,y)->(5,y)
            rook_h = (7, y0)
            can = False
            if color == 'white':
                can = (not white_king_moved) and (rook_h in white_locations) and (not white_rook_h_moved)
            else:
                can = (not black_king_moved) and (rook_h in black_locations) and (not black_rook_h_moved)
            if can and path_clear_between(position, rook_h, blockers):
                through = [(5, y0), (6, y0)]
                if all((sq not in enemies_attacks) for sq in through):
                    moves_list.append((6, y0))

            # Largo (lado a): rey (4,y)->(2,y), torre (0,y)->(3,y)
            rook_a = (0, y0)
            if color == 'white':
                can = (not white_king_moved) and (rook_a in white_locations) and (not white_rook_a_moved)
            else:
                can = (not black_king_moved) and (rook_a in black_locations) and (not black_rook_a_moved)
            if can and path_clear_between(position, rook_a, blockers):
                through = [(3, y0), (2, y0)]
                if all((sq not in enemies_attacks) for sq in through):
                    moves_list.append((2, y0))
    # ====================
    return moves_list

def check_queen(position, color):
    moves_list = []
    friends_list = white_locations if color == 'white' else black_locations
    enemies_list = black_locations if color == 'white' else white_locations
    directions = [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]
    for dx, dy in directions:
        chain = 1
        while True:
            nx = position[0] + chain * dx
            ny = position[1] + chain * dy
            if not (0 <= nx <= 7 and 0 <= ny <= 7): break
            if (nx, ny) in friends_list: break
            if (nx, ny) in enemies_list:
                moves_list.append((nx, ny))
                break
            moves_list.append((nx, ny))
            chain += 1
    return moves_list

def check_bishop(position, color):
    moves_list = []
    friends_list = white_locations if color == 'white' else black_locations
    enemies_list = black_locations if color == 'white' else white_locations
    for dx, dy in [(1,1),(1,-1),(-1,1),(-1,-1)]:
        chain = 1
        while True:
            nx = position[0] + chain * dx
            ny = position[1] + chain * dy
            if not (0 <= nx <= 7 and 0 <= ny <= 7): break
            if (nx, ny) in friends_list: break
            if (nx, ny) in enemies_list:
                moves_list.append((nx, ny))
                break
            moves_list.append((nx, ny))
            chain += 1
    return moves_list

def check_knight(position, color):
    moves_list = []
    friends_list = white_locations if color == 'white' else black_locations
    for dx, dy in [(2,1),(1,2),(-1,2),(-2,1),(-2,-1),(-1,-2),(1,-2),(2,-1)]:
        nx, ny = position[0] + dx, position[1] + dy
        if 0 <= nx <= 7 and 0 <= ny <= 7 and (nx, ny) not in friends_list:
            moves_list.append((nx, ny))
    return moves_list

def check_rook(position, color):
    moves_list = []
    friends_list = white_locations if color == 'white' else black_locations
    enemies_list = black_locations if color == 'white' else white_locations
    for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
        chain = 1
        while True:
            nx = position[0] + chain * dx
            ny = position[1] + chain * dy
            if not (0 <= nx <= 7 and 0 <= ny <= 7): break
            if (nx, ny) in friends_list: break
            if (nx, ny) in enemies_list:
                moves_list.append((nx, ny))
                break
            moves_list.append((nx, ny))
            chain += 1
    return moves_list

def check_pawn(position, color):
    # doble paso requiere que la casilla intermedia esté libre
    moves_list = []
    x, y = position
    occ_white = set(white_locations)
    occ_black = set(black_locations)
    occ = occ_white | occ_black

    if color == 'white':
        one = (x, y+1)
        two = (x, y+2)
        # avance 1
        if y < 7 and one not in occ:
            moves_list.append(one)
            # avance 2 (solo desde y==1 y si (x,y+1) estaba libre)
            if y == 1 and two not in occ:
                moves_list.append(two)
        # capturas normales
        if (x+1, y+1) in occ_black: moves_list.append((x+1, y+1))
        if (x-1, y+1) in occ_black: moves_list.append((x-1, y+1))

        # --- EN PASSANT: diagonal a ep_target ---
        if ep_target is not None:
            # derecha
            if ep_target == (x+1, y+1):
                cap_sq = (x+1, y)  # donde está el peón negro que dio doble paso
                if cap_sq in black_locations:
                    idx = black_locations.index(cap_sq)
                    if black_pieces[idx] == 'pawn':
                        moves_list.append(ep_target)
            # izquierda
            if ep_target == (x-1, y+1):
                cap_sq = (x-1, y)
                if cap_sq in black_locations:
                    idx = black_locations.index(cap_sq)
                    if black_pieces[idx] == 'pawn':
                        moves_list.append(ep_target)

    else:  # black
        one = (x, y-1)
        two = (x, y-2)
        # avance 1
        if y > 0 and one not in occ:
            moves_list.append(one)
            # avance 2 (solo desde y==6 y si (x,y-1) estaba libre)
            if y == 6 and two not in occ:
                moves_list.append(two)
        # capturas normales
        if (x+1, y-1) in occ_white: moves_list.append((x+1, y-1))
        if (x-1, y-1) in occ_white: moves_list.append((x-1, y-1))

        # --- EN PASSANT: diagonal a ep_target ---
        if ep_target is not None:
            # derecha
            if ep_target == (x+1, y-1):
                cap_sq = (x+1, y)  # donde está el peón blanco que dio doble paso
                if cap_sq in white_locations:
                    idx = white_locations.index(cap_sq)
                    if white_pieces[idx] == 'pawn':
                        moves_list.append(ep_target)
            # izquierda
            if ep_target == (x-1, y-1):
                cap_sq = (x-1, y)
                if cap_sq in white_locations:
                    idx = white_locations.index(cap_sq)
                    if white_pieces[idx] == 'pawn':
                        moves_list.append(ep_target)

    return moves_list

# ---- Helpers de selección / jaque / simulación --------------------------------
def check_valid_moves():
    options_list = white_options if turn_step < 2 else black_options
    return options_list[selection]

def draw_valid(moves, square):
    # no dibujar si el modal de promoción está activo o si ocultamos ayudas
    if (awaiting_promotion and promotion_pending) or (not show_hints) or selection == 100:
        return

    color = COL_RED if turn_step < 2 else COL_BLUE
    W, H = screen.get_size()
    board_rect = board_rect_for(square, W, H)

    # piezas del rival según a quién le toca
    opp_locs = set(black_locations if turn_step < 2 else white_locations)
    # pieza seleccionada (para detectar en-passant)
    sel_piece = (white_pieces if turn_step < 2 else black_pieces)[selection]

    for mv in moves:
        sx, sy = to_screen_xy(mv, square, board_rect)
        cx = sx + square // 2
        cy = sy + square // 2

        # ¿es captura? (incluye en-passant)
        is_capture = (mv in opp_locs)
        if not is_capture and sel_piece == 'pawn' and ep_target is not None and mv == ep_target:
            is_capture = True

        if is_capture:
            # anillo para captura
            pygame.draw.circle(screen, color, (cx, cy), max(6, square // 3), 3)
        else:
            # punto para movimiento silencioso
            pygame.draw.circle(screen, color, (cx, cy), max(4, square // 10))


# guarda también el estado de promoción (solo color/índice)
def _clone_state():
    pp = None if promotion_pending is None else {
        'color': promotion_pending.get('color'),
        'index': promotion_pending.get('index'),
    }
    return (white_pieces[:], white_locations[:], black_pieces[:], black_locations[:],
            captured_pieces_white[:], captured_pieces_black[:], last_move, turn_step,
            white_king_moved, white_rook_a_moved, white_rook_h_moved,
            black_king_moved, black_rook_a_moved, black_rook_h_moved, ep_target,
            awaiting_promotion, pp)

# restaura el estado de promoción
def _restore_state(state):
    global white_pieces, white_locations, black_pieces, black_locations
    global captured_pieces_white, captured_pieces_black, last_move, turn_step
    global white_king_moved, white_rook_a_moved, white_rook_h_moved
    global black_king_moved, black_rook_a_moved, black_rook_h_moved
    global ep_target, awaiting_promotion, promotion_pending

    (wp, wl, bp, bl, cpw, cpb, lm, ts,
     wkm, wra, wrh, bkm, bra, brh, ep,
     ap, pp) = state

    white_pieces = wp; white_locations = wl
    black_pieces = bp; black_locations = bl
    captured_pieces_white = cpw; captured_pieces_black = cpb
    last_move = lm; turn_step = ts
    white_king_moved, white_rook_a_moved, white_rook_h_moved = wkm, wra, wrh
    black_king_moved, black_rook_a_moved, black_rook_h_moved = bkm, bra, brh
    ep_target = ep
    awaiting_promotion = ap
    promotion_pending = pp  # los rects se regeneran al dibujar el menú

# agrega simulate=False
def _apply_move(color, sel_index, dest, simulate=False):
    global captured_pieces_white, captured_pieces_black
    global white_king_moved, white_rook_a_moved, white_rook_h_moved
    global black_king_moved, black_rook_a_moved, black_rook_h_moved
    global ep_target, promotion_pending, awaiting_promotion

    did_capture = False
    new_ep = None  # si esta jugada es doble paso, aquí guardamos la casilla intermedia

    if color == 'white':
        moved_piece = white_pieces[sel_index]
        from_sq = white_locations[sel_index]

        # captura normal si hay pieza en el destino
        if dest in black_locations:
            idx = black_locations.index(dest)
            captured_pieces_white.append(black_pieces[idx])
            black_pieces.pop(idx); black_locations.pop(idx)
            did_capture = True

        # mover pieza
        white_locations[sel_index] = dest

        # —— EN PASSANT (captura especial) ——:
        # si el destino coincide con ep_target y somos peón, quitamos el peón negro “atrás”
        if moved_piece == 'pawn' and ep_target is not None and dest == ep_target:
            # para blancas, el capturado está justo debajo del destino
            cap_sq = (dest[0], dest[1]-1)
            if cap_sq in black_locations:
                cidx = black_locations.index(cap_sq)
                if black_pieces[cidx] == 'pawn':
                    captured_pieces_white.append(black_pieces[cidx])
                    black_pieces.pop(cidx); black_locations.pop(cidx)
                    did_capture = True

        # flags enroque
        if moved_piece == 'king':
            white_king_moved = True
            if from_sq == (4,0) and dest == (6,0):
                if (7,0) in white_locations:
                    r = white_locations.index((7,0))
                    white_locations[r] = (5,0)
                    white_rook_h_moved = True
            if from_sq == (4,0) and dest == (2,0):
                if (0,0) in white_locations:
                    r = white_locations.index((0,0))
                    white_locations[r] = (3,0)
                    white_rook_a_moved = True
        elif moved_piece == 'rook':
            if from_sq == (0,0): white_rook_a_moved = True
            if from_sq == (7,0): white_rook_h_moved = True

        # promoción (no abrir menú en simulación)
        if moved_piece == 'pawn' and dest[1] == 7 and not simulate:
            promotion_pending = {'color': 'white', 'index': sel_index}
            awaiting_promotion = True

        # doble paso → preparar ep_target (casilla intermedia)
        if moved_piece == 'pawn' and abs(dest[1] - from_sq[1]) == 2:
            new_ep = (from_sq[0], (from_sq[1] + dest[1]) // 2)

    else:  # black
        moved_piece = black_pieces[sel_index]
        from_sq = black_locations[sel_index]

        if dest in white_locations:
            idx = white_locations.index(dest)
            captured_pieces_black.append(white_pieces[idx])
            white_pieces.pop(idx); white_locations.pop(idx)
            did_capture = True

        black_locations[sel_index] = dest

        # —— EN PASSANT (captura especial) ——:
        if moved_piece == 'pawn' and ep_target is not None and dest == ep_target:
            # para negras, el capturado está justo encima del destino
            cap_sq = (dest[0], dest[1]+1)
            if cap_sq in white_locations:
                cidx = white_locations.index(cap_sq)
                if white_pieces[cidx] == 'pawn':
                    captured_pieces_black.append(white_pieces[cidx])
                    white_pieces.pop(cidx); white_locations.pop(cidx)
                    did_capture = True

        if moved_piece == 'king':
            black_king_moved = True
            if from_sq == (4,7) and dest == (6,7):
                if (7,7) in black_locations:
                    r = black_locations.index((7,7))
                    black_locations[r] = (5,7)
                    black_rook_h_moved = True
            if from_sq == (4,7) and dest == (2,7):
                if (0,7) in black_locations:
                    r = black_locations.index((0,7))
                    black_locations[r] = (3,7)
                    black_rook_a_moved = True
        elif moved_piece == 'rook':
            if from_sq == (0,7): black_rook_a_moved = True
            if from_sq == (7,7): black_rook_h_moved = True

        if moved_piece == 'pawn' and dest[1] == 0 and not simulate:
            promotion_pending = {'color': 'black', 'index': sel_index}
            awaiting_promotion = True

        # doble paso → preparar ep_target (casilla intermedia)
        if moved_piece == 'pawn' and abs(dest[1] - from_sq[1]) == 2:
            new_ep = (from_sq[0], (from_sq[1] + dest[1]) // 2)

    # IMPORTANTÍSIMO:
    # El derecho de en passant dura sólo la respuesta del rival.
    # Si esta jugada NO fue un doble paso, se limpia (None).
    ep_target = new_ep

    return did_capture

def _king_pos(color):
    if color == 'white':
        k = white_pieces.index('king'); return white_locations[k]
    else:
        k = black_pieces.index('king'); return black_locations[k]

def in_check(color):
    king_sq = _king_pos(color)
    attacks = squares_attacked_by('black' if color == 'white' else 'white')
    return king_sq in attacks

# usa simulate=True para evitar menú de promoción en la simulación
def leaves_king_in_check(color, sel_index, dest):
    state = _clone_state()
    try:
        _apply_move(color, sel_index, dest, simulate=True)
        return in_check(color)
    finally:
        _restore_state(state)

def legal_moves_for_selection():
    base = check_valid_moves()
    color = 'white' if turn_step < 2 else 'black'
    sel = selection
    return [mv for mv in base if not leaves_king_in_check(color, sel, mv)]

def side_has_legal_move(color):
    if color == 'white':
        opts = check_options(white_pieces, white_locations, 'white')
        for i, moves in enumerate(opts):
            for mv in moves:
                if not leaves_king_in_check('white', i, mv): return True
        return False
    else:
        opts = check_options(black_pieces, black_locations, 'black')
        for i, moves in enumerate(opts):
            for mv in moves:
                if not leaves_king_in_check('black', i, mv): return True
        return False

def draw_check(square):
    global counter
    if game_over is not None:
        return

    W, H = screen.get_size()
    board_rect = board_rect_for(square, W, H)

    if 'king' in white_pieces and 'king' in black_pieces:
        w_king = white_locations[white_pieces.index('king')]
        b_king = black_locations[black_pieces.index('king')]

        if w_king in squares_attacked_by('black') and counter < 15:
            wx, wy = to_screen_xy(w_king, square, board_rect)
            pygame.draw.rect(screen, COL_RED,  (wx + 1, wy + 1, square - 2, square - 2), 4)

        if b_king in squares_attacked_by('white') and counter < 15:
            bx, by = to_screen_xy(b_king, square, board_rect)
            pygame.draw.rect(screen, COL_BLUE, (bx + 1, by + 1, square - 2, square - 2), 4)

# =================== API para IA (bots) ===================
@dataclass
class Move:
    color: str              # 'white' | 'black'
    sel_index: int          # índice dentro de white/black_pieces
    to: tuple[int,int]      # destino (x,y)

def generate_legal_moves(color: str) -> list[Move]:
    mv = []
    if color == 'white':
        opts = check_options(white_pieces, white_locations, 'white')
        for i, base in enumerate(opts):
            for dest in base:
                if not leaves_king_in_check('white', i, dest):
                    mv.append(Move('white', i, dest))
    else:
        opts = check_options(black_pieces, black_locations, 'black')
        for i, base in enumerate(opts):
            for dest in base:
                if not leaves_king_in_check('black', i, dest):
                    mv.append(Move('black', i, dest))
    return mv

def make_move(m: Move):
    # respetar promoción pendiente: no cerrar turno hasta elegir
    global last_move, turn_step
    history.append(_clone_state())
    if m.color == 'white':
        from_sq = white_locations[m.sel_index]; to_sq = m.to
        last_move = (from_sq, to_sq)
        did_capture = _apply_move('white', m.sel_index, to_sq)
        if did_capture and CAPTURE_SOUND: CAPTURE_SOUND.play()
        elif MOVE_SOUND: MOVE_SOUND.play()
        _recalc_options()
        if awaiting_promotion and promotion_pending:
            return last_move
        if in_check('black') and not side_has_legal_move('black'):
            set_game_over('white')
        elif (not in_check('black')) and (not side_has_legal_move('black')):
            set_game_over('draw')
        turn_step = 2
    else:
        from_sq = black_locations[m.sel_index]; to_sq = m.to
        last_move = (from_sq, to_sq)
        did_capture = _apply_move('black', m.sel_index, to_sq)
        if did_capture and CAPTURE_SOUND: CAPTURE_SOUND.play()
        elif MOVE_SOUND: MOVE_SOUND.play()
        _recalc_options()
        if awaiting_promotion and promotion_pending:
            return last_move
        if in_check('white') and not side_has_legal_move('white'):
            set_game_over('black')
        elif (not in_check('white')) and (not side_has_legal_move('white')):
            set_game_over('draw')
        turn_step = 0
    return last_move

def ai_play_current_turn():
    if game_over is not None:
        return

    color = 'white' if turn_step < 2 else 'black'

    mv = choose_by_level(
        ai_level,
        color=color,
        gen_moves=generate_legal_moves,
        piece_at=piece_at,
        piece_name_by_index=piece_name_by_index,
        is_attacked_by=is_attacked_by,
    )
    if not mv:
        return

    make_move(mv)

    # Si la IA promovió, promocionar a dama automáticamente
    if awaiting_promotion and promotion_pending and promotion_pending.get('color') == color:
        finalize_promotion('queen')  # la opción simple

def unmake_last():
    if history:
        _restore_state(history.pop())
        _recalc_options()

def _recalc_options():
    global white_options, black_options
    black_options = check_options(black_pieces, black_locations, "black")
    white_options = check_options(white_pieces, white_locations, "white")

def set_game_over(winner):
    global game_over
    game_over = winner

# ---- Primer frame sincronizado ----
def _first_frame(square):
    screen.fill(COL_BG)
    draw_board(square)
    draw_pieces(square)
    draw_captured_panel(square)
    pygame.display.flip()
    pygame.event.pump()
    pygame.time.wait(50)

# ---------- Arranque ----------
_first_frame(compute_square(*screen.get_size()))
# Inicializa listas y juego
white_pieces = []; white_locations = []; black_pieces = []; black_locations = []
captured_pieces_white = []; captured_pieces_black = []
reset_game_state()

# ---------- Bucle principal ----------
run = True
while run:
    timer.tick(fps)
    counter = counter + 1 if counter < 30 else 0

    W, H = screen.get_size()
    # cuadrado responsivo
    SQUARE = compute_square(W, H)

    screen.fill(COL_BG)
    draw_board(SQUARE)
    draw_coords(SQUARE)
    draw_last_move(SQUARE)
    draw_ep_target(SQUARE)
    draw_pieces(SQUARE)
    draw_captured_panel(SQUARE)
    draw_check(SQUARE)

    if selection != 100 and game_over is None:
        valid_moves = legal_moves_for_selection()
        draw_valid(valid_moves, SQUARE)

    # <<< AQUI: overlay de ayuda (encima de todo menos del popup de promoción)
    if show_help:
        draw_help_overlay()

    # dibujar menú de promoción por encima de todo
    if awaiting_promotion and promotion_pending:
        draw_promotion_menu(SQUARE)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False

        elif event.type == pygame.VIDEORESIZE:
            # aplica mínimos y reconfigura
            w = max(event.w, MIN_W); h = max(event.h, MIN_H)
            screen = pygame.display.set_mode((w, h), FLAGS)

        elif event.type == pygame.KEYDOWN:
            # Atajos para promoción (bloquea TODO lo demás mientras el modal está abierto)
            if awaiting_promotion and promotion_pending:
                keymap = {
                    pygame.K_q: 'queen',
                    pygame.K_r: 'rook',
                    pygame.K_b: 'bishop',
                    pygame.K_n: 'knight'
                }
                if event.key in keymap:
                    finalize_promotion(keymap[event.key])
                continue  # no procesar más teclas mientras el modal esté abierto

             # F1: mostrar/ocultar ayuda
            if event.key == pygame.K_F1:
                show_help = not show_help

            # Flip de tablero
            if event.key == pygame.K_f:
                flipped = not flipped

            # Toggle de ayudas
            elif event.key == pygame.K_h:
                show_hints = not show_hints

            # Reiniciar (solo si terminó)
            elif event.key == pygame.K_r and game_over is not None:
                reset_game_state()

            # Deshacer (Ctrl+Z)
            elif (event.key == pygame.K_z) and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                if history:
                    state = history.pop()
                    _restore_state(state)
                    _recalc_options()
                    selection = 100; valid_moves = []; game_over = None

            # === IA: teclas ===
            elif event.key in (pygame.K_0, pygame.K_KP0):
                ai_level = 0
                print("IA nivel 0 (aleatorio)")
            elif event.key in (pygame.K_1, pygame.K_KP1):
                ai_level = 1
                print("IA nivel 1 (greedy)")
            elif event.key == pygame.K_a:
                # IA juega el turno ACTUAL (respeta promoción y fin de partida)
                ai_play_current_turn()

        elif event.type == pygame.MOUSEMOTION:
            # actualizar posición del mouse para arrastre
            mouse_pos = event.pos

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # clic en menú de promoción
            if awaiting_promotion and promotion_pending:
                rects = promotion_pending.get('buttons', {})
                for name, r in rects.items():
                    if r.collidepoint(event.pos):
                        finalize_promotion(name)
                        break
                continue  # bloquear interacción con el tablero

            if game_over is not None:
                continue

            # traducir click a coordenadas de casilla según board_rect
            board_r = board_rect_for(SQUARE, W, H)
            click_coords = mouse_to_cell(event.pos, SQUARE, board_r)
            if click_coords is None:
                continue

            if turn_step <= 1:   # turno blancas
                if click_coords in white_locations:
                    selection = white_locations.index(click_coords)
                    # empezar drag
                    dragging = True; drag_index = selection; drag_color = 'white'; mouse_pos = event.pos
                    if turn_step == 0:
                        turn_step = 1
                if selection != 100:
                    legal = legal_moves_for_selection()
                    if click_coords in legal:  # clic-directo (sin drag) a destino
                        history.append(_clone_state())
                        from_sq = white_locations[selection]
                        to_sq   = click_coords
                        last_move = (from_sq, to_sq)
                        did_capture = _apply_move('white', selection, to_sq)
                        if did_capture and CAPTURE_SOUND: CAPTURE_SOUND.play()
                        elif MOVE_SOUND: MOVE_SOUND.play()
                        _recalc_options()
                        if awaiting_promotion and promotion_pending:
                            selection = 100; valid_moves = []
                        else:
                            if in_check('black') and not side_has_legal_move('black'):
                                game_over = 'white'
                            elif (not in_check('black')) and (not side_has_legal_move('black')):
                                game_over = 'draw'
                            turn_step = 2
                            selection = 100; valid_moves = []

            else:               # turno negras
                if click_coords in black_locations:
                    selection = black_locations.index(click_coords)
                    # empezar drag
                    dragging = True; drag_index = selection; drag_color = 'black'; mouse_pos = event.pos
                    if turn_step == 2:
                        turn_step = 3
                if selection != 100:
                    legal = legal_moves_for_selection()
                    if click_coords in legal:
                        history.append(_clone_state())
                        from_sq = black_locations[selection]
                        to_sq   = click_coords
                        last_move = (from_sq, to_sq)
                        did_capture = _apply_move('black', selection, to_sq)
                        if did_capture and CAPTURE_SOUND: CAPTURE_SOUND.play()
                        elif MOVE_SOUND: MOVE_SOUND.play()
                        _recalc_options()
                        if awaiting_promotion and promotion_pending:
                            selection = 100; valid_moves = []
                        else:
                            if in_check('white') and not side_has_legal_move('white'):
                                game_over = 'black'
                            elif (not in_check('white')) and (not side_has_legal_move('white')):
                                game_over = 'draw'
                            turn_step = 0
                            selection = 100; valid_moves = []

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            # soltar arrastre (drop)
            if dragging:
                dragging = False
                board_r = board_rect_for(SQUARE, W, H)
                mx, my = event.pos
                if board_r.collidepoint(mx, my):
                    drop = mouse_to_cell((mx, my), SQUARE, board_r)
                    if selection != 100:
                        legal = legal_moves_for_selection()
                        if drop in legal:
                            history.append(_clone_state())
                            if drag_color == 'white':
                                from_sq = white_locations[selection]; to_sq = drop
                                last_move = (from_sq, to_sq)
                                did_capture = _apply_move('white', selection, to_sq)
                                if did_capture and CAPTURE_SOUND: CAPTURE_SOUND.play()
                                elif MOVE_SOUND: MOVE_SOUND.play()
                                _recalc_options()
                                if awaiting_promotion and promotion_pending:
                                    selection = 100; valid_moves = []
                                else:
                                    if in_check('black') and not side_has_legal_move('black'):
                                        game_over = 'white'
                                    elif (not in_check('black')) and (not side_has_legal_move('black')):
                                        game_over = 'draw'
                                    turn_step = 2
                                    selection = 100; valid_moves = []
                            else:
                                from_sq = black_locations[selection]; to_sq = drop
                                last_move = (from_sq, to_sq)
                                did_capture = _apply_move('black', selection, to_sq)
                                if did_capture and CAPTURE_SOUND: CAPTURE_SOUND.play()
                                elif MOVE_SOUND: MOVE_SOUND.play()
                                _recalc_options()
                                if awaiting_promotion and promotion_pending:
                                    selection = 100; valid_moves = []
                                else:
                                    if in_check('white') and not side_has_legal_move('white'):
                                        game_over = 'black'
                                    elif (not in_check('white')) and (not side_has_legal_move('white')):
                                        game_over = 'draw'
                                    turn_step = 0
                                    selection = 100; valid_moves = []

    pygame.display.flip()

pygame.quit()
