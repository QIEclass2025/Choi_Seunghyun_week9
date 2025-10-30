import pygame
import requests
import io

# --- 기본 상수 ---
BOARD_WIDTH, HEIGHT = 800, 800
LOG_WIDTH = 250
WIDTH = BOARD_WIDTH + LOG_WIDTH
ROWS, COLS = 8, 8
SQUARE_SIZE = BOARD_WIDTH // COLS

# --- 색상 ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
LIGHT_SQUARE = (238, 238, 210)
DARK_SQUARE = (118, 150, 86)
HIGHLIGHT_COLOR = (255, 255, 51, 150)
HIGHLIGHT_MOVE_COLOR = (105, 105, 105, 150) # 투명도 추가
HIGHLIGHT_CAPTURE_COLOR = (255, 0, 0, 150) # 캡처 색상

# --- 포켓몬 매핑 ---
POKEMON_MAPPING = {
    'wK': 'nidoking', 'wQ': 'arcanine', 'wB': 'alakazam', 'wN': 'rapidash', 'wR': 'onix', 'wP': 'pikachu',
    'bK': 'nidoqueen', 'bQ': 'houndoom', 'bB': 'gengar', 'bN': 'absol', 'bR': 'steelix', 'bP': 'meowth'
}

def load_pokemon_sprites(mapping):
    """PokeAPI에서 포켓몬 스프라이트를 다운로드하여 Pygame Surface 객체로 변환"""
    sprites = {}
    for piece, name in mapping.items():
        print(f"Downloading sprite for {name}...")
        try:
            # 1. 포켓몬 정보 요청
            res = requests.get(f"https://pokeapi.co/api/v2/pokemon/{name}")
            res.raise_for_status()
            data = res.json()
            
            # 2. 스프라이트 URL 가져오기
            sprite_url = data['sprites']['front_default']
            
            # 3. 이미지 데이터 다운로드
            img_res = requests.get(sprite_url)
            img_res.raise_for_status()
            img_data = img_res.content
            
            # 4. 이미지 데이터를 Pygame Surface로 변환
            img_file = io.BytesIO(img_data)
            surface = pygame.image.load(img_file).convert_alpha()
            
            # 5. 크기 조절
            scaled_surface = pygame.transform.scale(surface, (SQUARE_SIZE, SQUARE_SIZE))
            sprites[piece] = scaled_surface
            print(f"Success: {name}")

        except requests.exceptions.RequestException as e:
            print(f"Error downloading {name}: {e}")
            sprites[piece] = None # 실패 시 None 저장
            
    return sprites

class Game:
    def __init__(self, win):
        self.win = win
        self.board = self.setup_board()
        self.selected_piece = None
        self.turn = 'w'
        self.valid_moves = []
        self.move_log = []
        self.en_passant_possible = () # 앙파상 가능한 좌표, (row, col)
        self.promotion_pending = None # 폰 승급 대기 중인 위치, (row, col)
        self.castling_rights = {'w_king': True, 'w_queen': True, 'b_king': True, 'b_queen': True}
        self.game_over = False
        self.game_result = ""
        self.label_font = pygame.font.SysFont('arial', 18, bold=True)
        self.log_font = pygame.font.SysFont('malgungothic', 20)
        self.piece_sprites = self.show_loading_screen()

    def reset_game(self):
        """게임을 초기 상태로 리셋"""
        self.board = self.setup_board()
        self.selected_piece = None
        self.turn = 'w'
        self.valid_moves = []
        self.move_log = []
        self.en_passant_possible = ()
        self.promotion_pending = None
        self.castling_rights = {'w_king': True, 'w_queen': True, 'b_king': True, 'b_queen': True}
        self.game_over = False
        self.game_result = ""

    def show_loading_screen(self):
        """로딩 화면을 표시하고 포켓몬 스프라이트를 로드"""
        self.win.fill(BLACK)
        font = pygame.font.SysFont('malgungothic', 40)
        text = font.render("포켓몬을 불러오는 중...", True, WHITE)
        text_rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self.win.blit(text, text_rect)
        pygame.display.flip()
        
        # 실제 스프라이트 로딩
        return load_pokemon_sprites(POKEMON_MAPPING)

    def setup_board(self):
        # ... (기존과 동일)
        board = [
            ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
            ['bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP'],
            ['--', '--', '--', '--', '--', '--', '--', '--'],
            ['--', '--', '--', '--', '--', '--', '--', '--'],
            ['--', '--', '--', '--', '--', '--', '--', '--'],
            ['--', '--', '--', '--', '--', '--', '--', '--'],
            ['wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP'],
            ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR']
        ]
        return board

    def draw_board(self):
        # ... (기존과 동일)
        for row in range(ROWS):
            for col in range(COLS):
                color = LIGHT_SQUARE if (row + col) % 2 == 0 else DARK_SQUARE
                pygame.draw.rect(self.win, color, (col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))

    def draw_pieces(self):
        """다운로드한 포켓몬 이미지와 기물 텍스트를 보드에 그림"""
        for row in range(ROWS):
            for col in range(COLS):
                piece = self.board[row][col]
                if piece != '--':
                    # 포켓몬 스프라이트 그리기
                    sprite = self.piece_sprites.get(piece)
                    if sprite:
                        rect = sprite.get_rect(center=(col * SQUARE_SIZE + SQUARE_SIZE // 2, row * SQUARE_SIZE + SQUARE_SIZE // 2))
                        self.win.blit(sprite, rect)

                    # 기물 종류(Q, R 등)를 팀 색상에 맞게 그리기
                    piece_type = piece[1]
                    pos = (col * SQUARE_SIZE + 5, row * SQUARE_SIZE + 5)

                    if piece.startswith('w'):
                        # 흰색 글씨에 검은 테두리 추가
                        border_surface = self.label_font.render(piece_type, True, BLACK)
                        offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)] # 상하좌우
                        for dx, dy in offsets:
                            self.win.blit(border_surface, (pos[0] + dx, pos[1] + dy))

                        # 원래 흰색 글씨 그리기
                        text_surface = self.label_font.render(piece_type, True, WHITE)
                        self.win.blit(text_surface, pos)
                    else:
                        # 검은색 글씨는 그대로 그리기
                        text_surface = self.label_font.render(piece_type, True, BLACK)
                        self.win.blit(text_surface, pos)

    def draw_valid_moves(self):
        if self.selected_piece:
            # 선택된 칸 하이라이트
            highlight_surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
            highlight_surface.fill(HIGHLIGHT_COLOR)
            r, c = self.selected_piece[1]
            self.win.blit(highlight_surface, (c * SQUARE_SIZE, r * SQUARE_SIZE))
            
            # 유효한 움직임 표시
            for move in self.valid_moves:
                r, c = move
                is_capture = self.board[r][c] != '--' or move == self.en_passant_possible
                color = HIGHLIGHT_CAPTURE_COLOR if is_capture else HIGHLIGHT_MOVE_COLOR
                
                # 원을 그릴 Surface 생성
                circle_surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
                pygame.draw.circle(circle_surface, color, (SQUARE_SIZE // 2, SQUARE_SIZE // 2), 15)
                self.win.blit(circle_surface, (c * SQUARE_SIZE, r * SQUARE_SIZE))

    # --- 나머지 게임 로직 (select_piece, move_piece, get_valid_moves, handle_click)은 기존과 거의 동일 ---
    # (이 부분은 생략하고 기존 코드를 그대로 사용한다고 가정)
    def select_piece(self, row, col):
        piece = self.board[row][col]
        if self.promotion_pending is None and piece.startswith(self.turn):
            self.selected_piece = (piece, (row, col))
            self.valid_moves = self.get_valid_moves(piece, row, col)
            return True
        return False

    def update_castling_rights(self, piece, start_pos):
        if piece == 'wK':
            self.castling_rights['w_king'] = False
            self.castling_rights['w_queen'] = False
        elif piece == 'bK':
            self.castling_rights['b_king'] = False
            self.castling_rights['b_queen'] = False
        elif piece == 'wR':
            if start_pos == (7, 0):
                self.castling_rights['w_queen'] = False
            elif start_pos == (7, 7):
                self.castling_rights['w_king'] = False
        elif piece == 'bR':
            if start_pos == (0, 0):
                self.castling_rights['b_queen'] = False
            elif start_pos == (0, 7):
                self.castling_rights['b_king'] = False

    def move_piece(self, start_pos, end_pos):
        start_row, start_col = start_pos
        end_row, end_col = end_pos
        piece = self.board[start_row][start_col]

        # 기보 기록
        move_notation = self.get_chess_notation(start_pos, end_pos, piece)
        self.move_log.append(move_notation)

        # 1. 보드 위에서 말을 먼저 이동
        self.board[end_row][end_col] = piece
        self.board[start_row][start_col] = '--'

        # 2. 이번 이동이 앙파상 잡기였는지 확인 (상태를 업데이트하기 전)
        if piece[1] == 'P' and (end_row, end_col) == self.en_passant_possible:
            self.board[start_row][end_col] = '--' # 상대 폰 제거

        # 3. 다음 턴을 위한 앙파상 상태 설정
        if piece[1] == 'P' and abs(start_row - end_row) == 2:
            self.en_passant_possible = ((start_row + end_row) // 2, start_col)
        else:
            self.en_passant_possible = ()

        # 캐슬링 시 룩 이동
        if piece[1] == 'K' and abs(start_col - end_col) == 2:
            if end_col == 6: # 킹사이드
                self.board[end_row][5] = self.board[end_row][7]
                self.board[end_row][7] = '--'
            else: # 퀸사이드
                self.board[end_row][3] = self.board[end_row][0]
                self.board[end_row][0] = '--'

        # 캐슬링 권한 업데이트
        self.update_castling_rights(piece, start_pos)

        # 폰 프로모션 확인
        if piece[1] == 'P' and (end_row == 0 or end_row == 7):
            self.promotion_pending = (end_row, end_col)
            # 기보에 아직 =Q 등이 추가되지 않았으므로, 여기서 턴을 넘기지 않고 대기
        else:
            self.selected_piece = None
            self.valid_moves = []
            self.turn = 'b' if self.turn == 'w' else 'w'
            self.check_game_over() # 턴 전환 후 게임 종료(체크메이트, 스테일메이트) 확인

    def get_all_legal_moves(self, color):
        """주어진 색의 모든 기물에 대한 모든 유효한 움직임을 반환"""
        all_moves = []
        for r in range(ROWS):
            for c in range(COLS):
                piece = self.board[r][c]
                if piece.startswith(color):
                    moves = self.get_valid_moves(piece, r, c)
                    if moves:
                        all_moves.extend(moves)
        return all_moves

    def get_chess_notation(self, start_pos, end_pos, piece):
        def get_rank_file(r, c):
            return chr(ord('a') + c) + str(8 - r)

        # 캐슬링 표기
        if piece[1] == 'K' and abs(start_pos[1] - end_pos[1]) == 2:
            return "O-O" if end_pos[1] == 6 else "O-O-O"

        start_sq = get_rank_file(start_pos[0], start_pos[1])
        end_sq = get_rank_file(end_pos[0], end_pos[1])
        piece_char = piece[1] if piece[1] != 'P' else ''
        
        is_capture = self.board[end_pos[0]][end_pos[1]] != '--'
        if piece[1] == 'P' and start_pos[1] != end_pos[1] and not is_capture: # 앙파상
            is_capture = True

        capture_char = 'x' if is_capture else ''

        if piece_char == '': # 폰 움직임
            if capture_char == 'x':
                return get_rank_file(start_pos[0], start_pos[1])[0] + capture_char + end_sq
            return end_sq
        return piece_char + capture_char + end_sq

    def square_under_attack(self, r, c, color):
        """특정 칸이 주어진 색의 기물에게 공격받고 있는지 확인"""
        opponent_color = 'b' if color == 'w' else 'w'
        for row in range(ROWS):
            for col in range(COLS):
                p = self.board[row][col]
                if p.startswith(opponent_color):
                    # get_valid_moves를 재귀적으로 호출하지 않도록 간단한 버전 사용
                    moves = self.get_piece_moves(p, row, col)
                    for move in moves:
                        if move == (r, c):
                            return True
        return False

    def get_castle_moves(self, r, c, moves):
        if self.square_under_attack(r, c, self.turn):
            return # 현재 체크 상태면 캐슬링 불가
        if (self.turn == 'w' and self.castling_rights['w_king']) or (self.turn == 'b' and self.castling_rights['b_king']):
            # 킹사이드 캐슬링
            if self.board[r][c+1] == '--' and self.board[r][c+2] == '--':
                if not self.square_under_attack(r, c+1, self.turn) and not self.square_under_attack(r, c+2, self.turn):
                    moves.append((r, c+2))
        if (self.turn == 'w' and self.castling_rights['w_queen']) or (self.turn == 'b' and self.castling_rights['b_queen']):
            # 퀸사이드 캐슬링
            if self.board[r][c-1] == '--' and self.board[r][c-2] == '--' and self.board[r][c-3] == '--':
                if not self.square_under_attack(r, c-1, self.turn) and not self.square_under_attack(r, c-2, self.turn):
                    moves.append((r, c-2))

    def get_piece_moves(self, piece, row, col):
        """get_valid_moves의 재귀 호출을 피하기 위한 간단한 버전"""
        moves = []
        color = piece[0]
        if 'P' in piece:
            direction = -1 if color == 'w' else 1
            if 0 <= row + direction < 8 and self.board[row + direction][col] == '--': moves.append((row + direction, col))
            if (row == 6 if color == 'w' else row == 1) and self.board[row + 2 * direction][col] == '--' and self.board[row + direction][col] == '--': moves.append((row + 2 * direction, col))
            for d_col in [-1, 1]:
                if 0 <= col + d_col < 8 and 0 <= row + direction < 8:
                    target = self.board[row + direction][col + d_col]
                    if target != '--' and not target.startswith(color): 
                        moves.append((row + direction, col + d_col))
                    # 앙파상
                    elif (row + direction, col + d_col) == self.en_passant_possible:
                        moves.append((row + direction, col + d_col))
        if 'R' in piece or 'Q' in piece:
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                for i in range(1, 8):
                    r, c = row + dr * i, col + dc * i
                    if 0 <= r < 8 and 0 <= c < 8:
                        target = self.board[r][c]
                        if target == '--': moves.append((r, c))
                        elif not target.startswith(color): moves.append((r, c)); break
                        else: break
                    else: break
        if 'B' in piece or 'Q' in piece:
            for dr, dc in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
                for i in range(1, 8):
                    r, c = row + dr * i, col + dc * i
                    if 0 <= r < 8 and 0 <= c < 8:
                        target = self.board[r][c]
                        if target == '--': moves.append((r, c))
                        elif not target.startswith(color): moves.append((r, c)); break
                        else: break
                    else: break
        if 'N' in piece:
            for dr, dc in [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]:
                r, c = row + dr, col + dc
                if 0 <= r < 8 and 0 <= c < 8:
                    target = self.board[r][c]
                    if target == '--' or not target.startswith(color): moves.append((r, c))
        if 'K' in piece:
            for dr, dc in [(dr, dc) for dr in [-1, 0, 1] for dc in [-1, 0, 1] if not (dr == 0 and dc == 0)]:
                r, c = row + dr, col + dc
                if 0 <= r < 8 and 0 <= c < 8:
                    target = self.board[r][c]
                    if target == '--' or not target.startswith(color): moves.append((r, c))
        return moves

    def get_valid_moves(self, piece, row, col):
        moves = self.get_piece_moves(piece, row, col)
        if 'K' in piece:
            self.get_castle_moves(row, col, moves)
        
        legal_moves = []
        for move in moves:
            start_pos = (row, col)
            end_pos = move
            
            # --- 시뮬레이션 시작 ---
            captured_piece = self.board[end_pos[0]][end_pos[1]]
            is_en_passant = (piece[1] == 'P' and end_pos == self.en_passant_possible)
            captured_en_passant_pawn = None
            en_passant_pawn_pos = None

            # 가상으로 말 이동
            self.board[end_pos[0]][end_pos[1]] = piece
            self.board[start_pos[0]][start_pos[1]] = '--'
            if is_en_passant:
                en_passant_pawn_pos = (start_pos[0], end_pos[1])
                captured_en_passant_pawn = self.board[en_passant_pawn_pos[0]][en_passant_pawn_pos[1]]
                self.board[en_passant_pawn_pos[0]][en_passant_pawn_pos[1]] = '--'

            # 체크 상태 확인
            if not self.is_in_check(self.turn):
                legal_moves.append(move)

            # --- 보드 원상복구 ---
            self.board[start_pos[0]][start_pos[1]] = piece
            self.board[end_pos[0]][end_pos[1]] = captured_piece
            if is_en_passant:
                self.board[en_passant_pawn_pos[0]][en_passant_pawn_pos[1]] = captured_en_passant_pawn

        return legal_moves

    def is_in_check(self, color):
        """주어진 색의 킹이 체크 상태인지 확인"""
        king_pos = None
        for r in range(ROWS):
            for c in range(COLS):
                if self.board[r][c] == color + 'K':
                    king_pos = (r, c)
                    break
            if king_pos:
                break
        
        if king_pos:
            return self.square_under_attack(king_pos[0], king_pos[1], color)
        return False

    def check_game_over(self):
        """현재 턴의 플레이어가 움직일 수가 없는지 확인하여 체크메이트 또는 스테일메이트를 결정"""
        # get_all_legal_moves는 모든 기물의 모든 '유효한' 움직임을 반환합니다.
        # (자신의 킹을 체크 상태로 만드는 움직임은 제외됨)
        legal_moves = self.get_all_legal_moves(self.turn)

        if not legal_moves:
            if self.is_in_check(self.turn):
                # 움직일 수 없는데 체크 상태이면 체크메이트
                self.game_result = ("백 승리" if self.turn == 'b' else "흑 승리")
                if self.move_log: self.move_log[-1] += '#' # 기보에 체크메이트 표기
            else:
                # 움직일 수 없는데 체크 상태가 아니면 스테일메이트
                self.game_result = "스테일메이트"
            self.game_over = True
        elif self.is_in_check(self.turn):
            # 움직일 수는 있지만 체크 상태이면, 기보에 체크 표기
            if self.move_log: self.move_log[-1] += '+'

    def handle_click(self, pos):
        if self.game_over:
            # 재시작 버튼 클릭 확인
            if hasattr(self, 'restart_button_rect') and self.restart_button_rect.collidepoint(pos):
                self.reset_game()
            return

        # 폰 프로모션 선택 처리
        if self.promotion_pending:
            r, c = self.promotion_pending
            choice_rects = self.draw_promotion_choice() # 사각형 위치 가져오기
            for piece_char, rect in choice_rects.items():
                if rect.collidepoint(pos):
                    color = self.turn
                    self.board[r][c] = color + piece_char
                    self.move_log[-1] += '=' + piece_char # 기보에 승급 표기

                    self.promotion_pending = None
                    self.selected_piece = None
                    self.valid_moves = []
                    
                    # 턴 넘기고 게임 상태 확인
                    self.turn = 'b' if self.turn == 'w' else 'w'
                    self.check_game_over() # 턴 전환 후 게임 종료(체크메이트, 스테일메이트) 확인
                    return
            return # 선택지 외 다른 곳 클릭 시 아무것도 안 함

        col = pos[0] // SQUARE_SIZE
        row = pos[1] // SQUARE_SIZE
        if col >= COLS: # 기보 영역 클릭 무시
            return

        if self.selected_piece:
            start_pos = self.selected_piece[1]
            if (row, col) in self.valid_moves: self.move_piece(start_pos, (row, col))
            else:
                self.selected_piece = None
                self.valid_moves = []
                self.select_piece(row, col)
        else: self.select_piece(row, col)

    def draw_promotion_choice(self):
        if not self.promotion_pending:
            return {}

        r, c = self.promotion_pending
        x_base = c * SQUARE_SIZE
        y_base = r * SQUARE_SIZE

        # 화면 가장자리에 걸치지 않도록 위치 조정
        if r == 0: # 흰색 폰 승급
            y_base = 0
        else: # 검은색 폰 승급
            y_base = HEIGHT - SQUARE_SIZE * 2

        pygame.draw.rect(self.win, (200, 200, 200), (x_base, y_base, SQUARE_SIZE, SQUARE_SIZE * 2))
        
        choices = ['Q', 'R', 'B', 'N']
        choice_rects = {}
        font = pygame.font.SysFont('arial', 40, bold=True)

        for i, char in enumerate(choices):
            text = font.render(char, True, BLACK)
            rect = text.get_rect(center=(x_base + SQUARE_SIZE // 2, y_base + i * (SQUARE_SIZE // 2) + SQUARE_SIZE // 4))
            self.win.blit(text, rect)
            choice_rects[char] = rect
        return choice_rects

    def draw_game_over(self):
        if not self.game_over:
            return

        # 반투명 오버레이
        overlay = pygame.Surface((BOARD_WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        self.win.blit(overlay, (0, 0))

        # 게임 결과 텍스트
        font = pygame.font.SysFont('malgungothic', 60, bold=True)
        text = font.render(self.game_result, True, WHITE)
        text_rect = text.get_rect(center=(BOARD_WIDTH // 2, HEIGHT // 2 - 50))
        self.win.blit(text, text_rect)

        # 재시작 버튼
        button_font = pygame.font.SysFont('malgungothic', 40)
        button_text = button_font.render("재시작", True, BLACK)
        self.restart_button_rect = pygame.Rect(BOARD_WIDTH // 2 - 100, HEIGHT // 2 + 20, 200, 60)
        pygame.draw.rect(self.win, LIGHT_SQUARE, self.restart_button_rect)
        self.win.blit(button_text, self.restart_button_rect.move(50, 10))

    def draw_move_log(self):
        pygame.draw.rect(self.win, (20, 20, 20), (BOARD_WIDTH, 0, LOG_WIDTH, HEIGHT))
        title_text = self.log_font.render("기보", True, WHITE)
        self.win.blit(title_text, (BOARD_WIDTH + 10, 10))

        y_offset = 40
        for i in range(0, len(self.move_log), 2):
            move_number = i // 2 + 1
            white_move = self.move_log[i]
            
            line = f"{move_number}. {white_move}"
            
            # 흑의 수가 있는지 확인
            if i + 1 < len(self.move_log):
                black_move = self.move_log[i+1]
                line += f" {black_move}"

            move_text = self.log_font.render(line, True, WHITE)
            self.win.blit(move_text, (BOARD_WIDTH + 10, y_offset))
            y_offset += 30

    def update(self):
        self.win.fill(BLACK)
        self.draw_board()
        self.draw_valid_moves()
        self.draw_pieces()
        self.draw_move_log()
        self.draw_promotion_choice()
        self.draw_game_over()
        pygame.display.flip()

def main():
    pygame.init()
    win = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Pokemon Chess")
    
    game = Game(win)
    
    run = True
    while run:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                game.handle_click(pos)
        game.update()

    pygame.quit()

if __name__ == '__main__':
    main()