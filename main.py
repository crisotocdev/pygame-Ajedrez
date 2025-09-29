import pygame
import os

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
timer    = pygame.time.Clock()
fps      = 60

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
    pawn_big = int(square * 0.65)  # 65 px cuando square=100
    small = int(square * 0.45)   # miniaturas panel

    def sc(img, w, h): 
        w=max(1,int(w)); h=max(1,int(h))
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

    white_pieces[:] = ['rook', 'knight', 'bishop', 'king', 'queen', 'bishop', 'knight', 'rook',
                       'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn']
    white_locations[:] = [(0,0), (1,0), (2,0), (3,0), (4,0), (5,0), (6,0), (7,0),
                          (0,1), (1,1), (2,1), (3,1), (4,1), (5,1), (6,1), (7,1)]
    black_pieces[:] = ['rook', 'knight', 'bishop', 'king', 'queen', 'bishop', 'knight', 'rook',
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

def path_clear_between(a, b, blockers):
    """True si entre a=(x1,y) y b=(x2,y) no hay piezas (excluye extremos)."""
    (x1,y1), (x2,y2) = a, b
    if y1 != y2: return False
    lo, hi = sorted([x1, x2])
    for x in range(lo+1, hi):
        if (x, y1) in blockers:
            return False
    return True

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

    # texto inferior
    if game_over is None:
        status_text = ['Blanco: Selecciona una pieza a Mover!', 'Blanco: Elige un Destino!',
                       'Negro: Selecciona una pieza a Mover!',  'Negro: Elige un Destino!'][turn_step]
    else:
        status_text = ("Tablas por ahogado" if game_over == 'draw'
                       else ("¡Jaque mate! Ganan Blancas" if game_over == 'white' else "¡Jaque mate! Ganan Negras"))
    surf = big_font.render(status_text, True, COL_TXT)
    text_x = (W // 2) - (surf.get_width() // 2)
    text_y = bar_y + (STATUS_H - surf.get_height()) // 2 - 10
    screen.blit(surf, (text_x, text_y))

    if game_over is not None:
        hint = font.render("Presiona R para reiniciar  |  Ctrl+Z para deshacer", True, COL_TXT)
        screen.blit(hint, ((W - hint.get_width()) // 2, bar_y + 60))

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
    off_pawn_x = int(square * 0.22)
    off_pawn_y = int(square * 0.30)

    # blancas
    for i in range(len(white_pieces)):
        index = piece_list.index(white_pieces[i])
        cell_x = board_rect.x + white_locations[i][0] * square
        cell_y = white_locations[i][1] * square
        if white_pieces[i] == 'pawn':
            screen.blit(white_images[0], (cell_x + off_pawn_x, cell_y + off_pawn_y))
        else:
            screen.blit(white_images[index], (cell_x + off_big, cell_y + off_big))
        if turn_step < 2 and selection == i:
            pygame.draw.rect(screen, COL_RED, [cell_x + 1, cell_y + 1, square - 2, square - 2], 2)

    # negras
    for i in range(len(black_pieces)):
        index = piece_list.index(black_pieces[i])
        cell_x = board_rect.x + black_locations[i][0] * square
        cell_y = black_locations[i][1] * square
        if black_pieces[i] == 'pawn':
            screen.blit(black_images[0], (cell_x + off_pawn_x, cell_y + off_pawn_y))
        else:
            screen.blit(black_images[index], (cell_x + off_big, cell_y + off_big))
        if turn_step >= 2 and selection == i:
            pygame.draw.rect(screen, COL_BLUE, [cell_x + 1, cell_y + 1, square - 2, square - 2], 2)

# ---- Resaltado de última jugada ----------------------------------------------
def draw_last_move(square):
    if not last_move:
        return
    W, H = screen.get_size()
    board_rect = board_rect_for(square, W, H)
    (fx, fy), (tx, ty) = last_move
    pygame.draw.rect(screen, COL_LAST, (board_rect.x + fx*square+2, fy*square+2, square-4, square-4), 3)
    pygame.draw.rect(screen, COL_LAST, (board_rect.x + tx*square+2, ty*square+2, square-4, square-4), 3)

# ---- Generación de movimientos (igual a tu lógica, con enroque en king) ------
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

    # ===== Enroque =====
    y0 = 0 if color == 'white' else 7
    king_start = (3, y0)  # tu disposición
    if position == king_start:
        global white_king_moved, white_rook_a_moved, white_rook_h_moved
        global black_king_moved, black_rook_a_moved, black_rook_h_moved

        enemies_attacks = squares_attacked_by('black' if color == 'white' else 'white')
        friends = white_locations if color == 'white' else black_locations
        enemies = black_locations if color == 'white' else white_locations
        blockers = friends + enemies

        # No estar en jaque ahora
        if (position not in enemies_attacks):
            # Corto (lado h): rey (3,y)->(5,y), torre (7,y)->(4,y)
            rook_h = (7, y0)
            can = False
            if color == 'white':
                can = (not white_king_moved) and (rook_h in white_locations) and (not white_rook_h_moved)
            else:
                can = (not black_king_moved) and (rook_h in black_locations) and (not black_rook_h_moved)
            if can and path_clear_between(position, rook_h, blockers):
                through = [(4, y0), (5, y0)]
                if all((sq not in enemies_attacks) for sq in through):
                    moves_list.append((5, y0))

            # Largo (lado a): rey (3,y)->(1,y), torre (0,y)->(2,y)
            rook_a = (0, y0)
            if color == 'white':
                can = (not white_king_moved) and (rook_a in white_locations) and (not white_rook_a_moved)
            else:
                can = (not black_king_moved) and (rook_a in black_locations) and (not black_rook_a_moved)
            if can and path_clear_between(position, rook_a, blockers):
                through = [(2, y0), (1, y0)]
                if all((sq not in enemies_attacks) for sq in through):
                    moves_list.append((1, y0))
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
    moves_list = []
    if color == 'white':
        if (position[0], position[1] + 1) not in white_locations and \
           (position[0], position[1] + 1) not in black_locations and position[1] < 7:
            moves_list.append((position[0], position[1] + 1))
        if (position[0], position[1] + 2) not in white_locations and \
           (position[0], position[1] + 2) not in black_locations and position[1] == 1:
            moves_list.append((position[0], position[1] + 2))
        if (position[0] + 1, position[1] + 1) in black_locations:
            moves_list.append((position[0] + 1, position[1] + 1))
        if (position[0] - 1, position[1] + 1) in black_locations:
            moves_list.append((position[0] - 1, position[1] + 1))
    else:
        if (position[0], position[1] - 1) not in white_locations and \
           (position[0], position[1] - 1) not in black_locations and position[1] > 0:
            moves_list.append((position[0], position[1] - 1))
        if (position[0], position[1] - 2) not in white_locations and \
           (position[0], position[1] - 2) not in black_locations and position[1] == 6:
            moves_list.append((position[0], position[1] - 2))
        if (position[0] + 1, position[1] - 1) in white_locations:
            moves_list.append((position[0] + 1, position[1] - 1))
        if (position[0] - 1, position[1] - 1) in white_locations:
            moves_list.append((position[0] - 1, position[1] - 1))
    return moves_list

# ---- Helpers de selección / jaque / simulación --------------------------------
def check_valid_moves():
    options_list = white_options if turn_step < 2 else black_options
    return options_list[selection]

def draw_valid(moves, square):
    color = COL_RED if turn_step < 2 else COL_BLUE
    W, H = screen.get_size()
    board_rect = board_rect_for(square, W, H)
    for mv in moves:
        pygame.draw.circle(screen, color, 
                           (board_rect.x + mv[0] * square + square//2, mv[1] * square + square//2), 5)

def _clone_state():
    # Guardar flags de enroque también
    return (white_pieces[:], white_locations[:], black_pieces[:], black_locations[:],
            captured_pieces_white[:], captured_pieces_black[:], last_move, turn_step,
            white_king_moved, white_rook_a_moved, white_rook_h_moved,
            black_king_moved, black_rook_a_moved, black_rook_h_moved)

def _restore_state(state):
    global white_pieces, white_locations, black_pieces, black_locations
    global captured_pieces_white, captured_pieces_black, last_move, turn_step
    global white_king_moved, white_rook_a_moved, white_rook_h_moved
    global black_king_moved, black_rook_a_moved, black_rook_h_moved
    (wp, wl, bp, bl, cpw, cpb, lm, ts,
     wkm, wra, wrh, bkm, bra, brh) = state
    white_pieces = wp; white_locations = wl
    black_pieces = bp; black_locations = bl
    captured_pieces_white = cpw; captured_pieces_black = cpb
    last_move = lm; turn_step = ts
    white_king_moved, white_rook_a_moved, white_rook_h_moved = wkm, wra, wrh
    black_king_moved, black_rook_a_moved, black_rook_h_moved = bkm, bra, brh

def _apply_move(color, sel_index, dest):
    global captured_pieces_white, captured_pieces_black
    global white_king_moved, white_rook_a_moved, white_rook_h_moved
    global black_king_moved, black_rook_a_moved, black_rook_h_moved

    did_capture = False

    if color == 'white':
        # captura si corresponde
        if dest in black_locations:
            idx = black_locations.index(dest)
            captured_pieces_white.append(black_pieces[idx])
            black_pieces.pop(idx); black_locations.pop(idx)
            did_capture = True

        moved_piece = white_pieces[sel_index]
        from_sq = white_locations[sel_index]
        white_locations[sel_index] = dest

        # flags de movimiento y enroque
        if moved_piece == 'king':
            white_king_moved = True
            # enroque corto (3,0)->(5,0) torre (7,0)->(4,0)
            if from_sq == (3,0) and dest == (5,0):
                if (7,0) in white_locations:
                    r = white_locations.index((7,0))
                    white_locations[r] = (4,0)
                    white_rook_h_moved = True
            # enroque largo (3,0)->(1,0) torre (0,0)->(2,0)
            if from_sq == (3,0) and dest == (1,0):
                if (0,0) in white_locations:
                    r = white_locations.index((0,0))
                    white_locations[r] = (2,0)
                    white_rook_a_moved = True
        elif moved_piece == 'rook':
            if from_sq == (0,0): white_rook_a_moved = True
            if from_sq == (7,0): white_rook_h_moved = True

    else:
        if dest in white_locations:
            idx = white_locations.index(dest)
            captured_pieces_black.append(white_pieces[idx])
            white_pieces.pop(idx); white_locations.pop(idx)
            did_capture = True

        moved_piece = black_pieces[sel_index]
        from_sq = black_locations[sel_index]
        black_locations[sel_index] = dest

        if moved_piece == 'king':
            black_king_moved = True
            # enroque corto (3,7)->(5,7) torre (7,7)->(4,7)
            if from_sq == (3,7) and dest == (5,7):
                if (7,7) in black_locations:
                    r = black_locations.index((7,7))
                    black_locations[r] = (4,7)
                    black_rook_h_moved = True
            # enroque largo (3,7)->(1,7) torre (0,7)->(2,7)
            if from_sq == (3,7) and dest == (1,7):
                if (0,7) in black_locations:
                    r = black_locations.index((0,7))
                    black_locations[r] = (2,7)
                    black_rook_a_moved = True
        elif moved_piece == 'rook':
            if from_sq == (0,7): black_rook_a_moved = True
            if from_sq == (7,7): black_rook_h_moved = True

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

def leaves_king_in_check(color, sel_index, dest):
    state = _clone_state()
    try:
        _apply_move(color, sel_index, dest)
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
    if turn_step < 2:
        if 'king' in white_pieces:
            king_index = white_pieces.index('king')
            king_location = white_locations[king_index]
            for opts in black_options:
                if king_location in opts and counter < 15:
                    x = board_rect.x + king_location[0] * square + 1
                    y = king_location[1] * square + 1
                    pygame.draw.rect(screen, COL_RED, [x, y, square-2, square-2], 4)
    else:
        if 'king' in black_pieces:
            king_index = black_pieces.index('king')
            king_location = black_locations[king_index]
            for opts in white_options:
                if king_location in opts and counter < 15:
                    x = board_rect.x + king_location[0] * square + 1
                    y = king_location[1] * square + 1
                    pygame.draw.rect(screen, COL_BLUE, [x, y, square-2, square-2], 4)

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
    draw_last_move(SQUARE)
    draw_pieces(SQUARE)
    draw_captured_panel(SQUARE)
    draw_check(SQUARE)

    if selection != 100 and game_over is None:
        valid_moves = legal_moves_for_selection()
        draw_valid(valid_moves, SQUARE)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run = False

        elif event.type == pygame.VIDEORESIZE:
            # aplica mínimos y reconfigura
            w = max(event.w, MIN_W); h = max(event.h, MIN_H)
            screen = pygame.display.set_mode((w, h), FLAGS)

        elif event.type == pygame.KEYDOWN:
            # Reiniciar (solo si terminó)
            if event.key == pygame.K_r and game_over is not None:
                reset_game_state()
            # Deshacer (Ctrl+Z)
            if (event.key == pygame.K_z) and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                if history:
                    state = history.pop()
                    _restore_state(state)
                    black_options = check_options(black_pieces, black_locations, "black")
                    white_options = check_options(white_pieces, white_locations, "white")
                    selection = 100; valid_moves = []; game_over = None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if game_over is not None:
                continue

            # traducir click a coordenadas de casilla según board_rect
            board_r = board_rect_for(SQUARE, W, H)
            mx, my = event.pos
            if not board_r.collidepoint(mx, my):
                continue
            x_coord = (mx - board_r.x) // SQUARE
            y_coord = my // SQUARE
            click_coords = (x_coord, y_coord)

            if turn_step <= 1:   # turno blancas
                if click_coords in white_locations:
                    selection = white_locations.index(click_coords)
                    if turn_step == 0:
                        turn_step = 1
                if selection != 100:
                    legal = legal_moves_for_selection()
                    if click_coords in legal:
                        history.append(_clone_state())
                        from_sq = white_locations[selection]
                        to_sq   = click_coords
                        last_move = (from_sq, to_sq)

                        did_capture = _apply_move('white', selection, to_sq)

                        if did_capture and CAPTURE_SOUND:
                            CAPTURE_SOUND.play()
                        elif MOVE_SOUND:
                            MOVE_SOUND.play()

                        black_options = check_options(black_pieces, black_locations, "black")
                        white_options = check_options(white_pieces, white_locations, "white")

                        if in_check('black') and not side_has_legal_move('black'):
                            game_over = 'white'
                        elif (not in_check('black')) and (not side_has_legal_move('black')):
                            game_over = 'draw'

                        turn_step = 2
                        selection = 100
                        valid_moves = []

            else:               # turno negras
                if click_coords in black_locations:
                    selection = black_locations.index(click_coords)
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

                        if did_capture and CAPTURE_SOUND:
                            CAPTURE_SOUND.play()
                        elif MOVE_SOUND:
                            MOVE_SOUND.play()

                        black_options = check_options(black_pieces, black_locations, "black")
                        white_options = check_options(white_pieces, white_locations, "white")

                        if in_check('white') and not side_has_legal_move('white'):
                            game_over = 'black'
                        elif (not in_check('white')) and (not side_has_legal_move('white')):
                            game_over = 'draw'

                        turn_step = 0
                        selection = 100
                        valid_moves = []

    pygame.display.flip()

pygame.quit()
