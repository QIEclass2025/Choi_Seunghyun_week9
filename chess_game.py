import pygame
import requests
import io
from pokemon_data import POKEMON_DATA

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
SELECTION_BG_COLOR = (230, 230, 230)
HIGHLIGHT_COLOR = (255, 255, 51, 150)
HIGHLIGHT_MOVE_COLOR = (105, 105, 105, 150) # 투명도 추가
HIGHLIGHT_CAPTURE_COLOR = (255, 0, 0, 150) # 캡처 색상

# --- 기물 타입 ---
PIECE_TYPES = ['K', 'Q', 'B', 'N', 'R', 'P']

class Piece:
    """체스 기물의 상태를 저장하는 클래스 (진화 정보 포함)"""
    def __init__(self, color, piece_type, pokemon_family, evolution_stage=0):
        self.color = color
        self.piece_type = piece_type
        self.pokemon_family = pokemon_family # [('english', 'korean'), ...]
        self.evolution_stage = evolution_stage

    def get_current_pokemon_name(self):
        """현재 진화 단계에 맞는 포켓몬 이름을 (영어 이름, 한글 이름) 튜플로 반환"""
        return self.pokemon_family[self.evolution_stage][0] # 영어 이름으로 스프라이트 로드

    def get_current_korean_name(self):
        """현재 진화 단계에 맞는 포켓몬의 한글 이름을 반환"""
        return self.pokemon_family[self.evolution_stage][1]

    def evolve(self):
        """기물을 다음 단계로 진화시키고, 진화 메시지를 반환"""
        if self.evolution_stage < len(self.pokemon_family) - 1:
            prev_name = self.get_current_korean_name()
            self.evolution_stage += 1
            current_name = self.get_current_korean_name()
            
            prev_particle = "이" if self.has_jongseong(prev_name) else ""
            current_particle = "으로" if self.has_jongseong(current_name) else "로"
            return f"{prev_name}{prev_particle} 진화! → {current_name}"
        return None

    def has_jongseong(self, text):
        """한글 마지막 글자에 종성이 있는지 확인"""
        if not text:
            return False
        last_char = text[-1]
        if '가' <= last_char <= '힣':
            # 유니코드 한글 문자 범위: 0xAC00 ~ 0xD7A3
            return (ord(last_char) - 0xAC00) % 28 > 0
        return False
    
    def __repr__(self):
        return f"({self.color}{self.piece_type}:{self.get_current_korean_name()})"

def load_pokemon_sprites(white_team_type, black_team_type):
    """선택된 팀 타입에 따라 모든 관련 포켓몬 스프라이트를 로드"""
    sprites = {}
    
    types_to_load = [white_team_type, black_team_type]
    all_pokemon_tuples = set()

    # 로드해야 할 모든 포켓몬 이름 튜플 수집
    for team_type in types_to_load:
        if not team_type: continue
        for piece_type in PIECE_TYPES:
            pokemon_family = POKEMON_DATA[team_type][piece_type]
            for pokemon_tuple in pokemon_family: # 튜플 형태로 저장
                all_pokemon_tuples.add(pokemon_tuple)

    print(f"Loading sprites for: {', '.join([k for e, k in all_pokemon_tuples])}")

    for english_name, korean_name in all_pokemon_tuples:
        print(f"Downloading sprite for {korean_name} ({english_name})...")
        try:
            # 1. 포켓몬 정보 요청 (ID를 얻기 위함)
            res = requests.get(f"https://pokeapi.co/api/v2/pokemon/{english_name}") # 영어 이름으로 요청
            res.raise_for_status()
            data = res.json()
            
            # 모든 스프라이트에 대해 기본(front_default) 스프라이트 사용
            sprite_url = data['sprites']['front_default']

            if not sprite_url:
                print(f"No sprite URL found for {name}.")
                sprites[name] = None
                continue

            # 3. 이미지 데이터 다운로드
            img_res = requests.get(sprite_url)
            img_res.raise_for_status()
            img_data = img_res.content
            
            # 4. 이미지 데이터를 Pygame Surface로 변환
            img_file = io.BytesIO(img_data)
            surface = pygame.image.load(img_file).convert_alpha()
            
            # 5. 크기 조절
            scaled_surface = pygame.transform.scale(surface, (SQUARE_SIZE, SQUARE_SIZE))
            sprites[english_name] = scaled_surface
            print(f"Success: {korean_name}")

        except requests.exceptions.RequestException as e:
            print(f"Error downloading {korean_name}: {e}")
            sprites[english_name] = None
            
    return sprites




class Game:
    def __init__(self, win):
        self.win = win
        # 게임 상태 관리 (main 함수의 game_state와 동기화)
        self.game_state = 0 # 0: TYPE_SELECTION, 1: LOADING, 2: PLAYING, 3: GAME_OVER

        # 타입 선택 화면 관련
        self.white_team_type = None
        self.black_team_type = None
        self.available_types = ["Fire", "Water", "Grass"] # 선택 가능한 타입
        self.type_selection_rects = [] # 타입 선택 버튼들의 클릭 영역
        self.type_selection_turn = 'b' # 흑팀이 먼저 선택

        self.selection_font = pygame.font.SysFont('malgungothic', 24)
        self.selection_title_font = pygame.font.SysFont('malgungothic', 36, bold=True)


        # 게임 플레이 관련 (선택 완료 후 초기화)
        self.board = None
        self.selected_piece = None
        self.turn = 'w'
        self.valid_moves = []
        self.move_log = []
        self.en_passant_possible = ()
        self.promotion_pending = None
        self.castling_rights = {'w_king': True, 'w_queen': True, 'b_king': True, 'b_queen': True}
        self.game_over = False
        self.game_result = ""
        self.label_font = pygame.font.SysFont('arial', 18, bold=True)
        self.log_font = pygame.font.SysFont('malgungothic', 20)
        self.feedback_message = "" # 피드백 메시지
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
        self.feedback_message = ""
        self.feedback_timer = 0

    def draw_type_selection_screen(self):
        self.win.fill(SELECTION_BG_COLOR)

        title_text = self.selection_title_font.render("팀 타입 선택", True, BLACK)
        title_rect = title_text.get_rect(center=(WIDTH // 2, 50))
        self.win.blit(title_text, title_rect)

        # 현재 선택 중인 팀 표시
        team_display_name = "흑팀" if self.type_selection_turn == 'b' else "백팀"
        status_text = self.selection_font.render(f"{team_display_name} 차례", True, BLACK)
        status_rect = status_text.get_rect(center=(WIDTH // 2, 100))
        self.win.blit(status_text, status_rect)

        # 이미 선택된 타입 표시
        y_offset = 150
        if self.black_team_type:
            black_type_text = self.selection_font.render(f"흑팀: {self.black_team_type} (선택 완료)", True, BLACK)
            self.win.blit(black_type_text, (50, y_offset))
            y_offset += 30
        if self.white_team_type:
            white_type_text = self.selection_font.render(f"백팀: {self.white_team_type} (선택 완료)", True, BLACK)
            self.win.blit(white_type_text, (50, y_offset))
            y_offset += 30

        # 선택 가능한 타입 버튼 표시
        self.type_selection_rects = []
        button_width, button_height = 200, 70
        button_spacing = 30
        total_height = len(self.available_types) * (button_height + button_spacing) - button_spacing
        start_y = HEIGHT // 2 - total_height // 2

        korean_type_names = {"Fire": "불꽃", "Water": "물", "Grass": "풀"}

        for i, type_name_eng in enumerate(self.available_types):
            type_name_kor = korean_type_names.get(type_name_eng, type_name_eng) # 한글 이름 가져오기
            rect = pygame.Rect(WIDTH // 2 - button_width // 2, start_y + i * (button_height + button_spacing), button_width, button_height)
            self.type_selection_rects.append((type_name_eng, rect)) # 실제 선택에는 영어 이름 사용

            pygame.draw.rect(self.win, (100, 100, 200) if type_name_eng == "Water" else (200, 100, 100) if type_name_eng == "Fire" else (100, 200, 100), rect)
            type_text = self.selection_title_font.render(type_name_kor, True, WHITE) # 버튼 텍스트는 한글
            text_rect = type_text.get_rect(center=rect.center)
            self.win.blit(type_text, text_rect)

    def handle_type_selection_click(self, pos):
        for type_name, rect in self.type_selection_rects:
            if rect.collidepoint(pos):
                if self.type_selection_turn == 'b':
                    self.black_team_type = type_name
                    self.type_selection_turn = 'w'
                else: # 'w'
                    self.white_team_type = type_name
                    # 모든 타입 선택 완료
                    return "TYPES_SELECTED"
                
                self.available_types.remove(type_name) # 선택된 타입은 목록에서 제거
                return # 클릭 처리 완료
        return None # 아무것도 선택되지 않음

    def draw_loading_screen(self):
        """로딩 화면을 표시"""
        self.win.fill(BLACK)
        font = pygame.font.SysFont('malgungothic', 40)
        text = font.render("포켓몬 스프라이트를 불러오는 중...", True, WHITE)
        text_rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self.win.blit(text, text_rect)
        pygame.display.flip()
        self.feedback_message = ""
        self.feedback_timer = 0



    def setup_board(self):
        board = [[None for _ in range(COLS)] for _ in range(ROWS)]

        # 흑팀 기물 설정 (8등~7등 행)
        for col, piece_type_char in enumerate(['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']):
            pokemon_family = POKEMON_DATA[self.black_team_type][piece_type_char]
            board[0][col] = Piece('b', piece_type_char, pokemon_family)
        for col in range(COLS):
            pokemon_family = POKEMON_DATA[self.black_team_type]['P']
            board[1][col] = Piece('b', 'P', pokemon_family)

        # 백팀 기물 설정 (1등~2등 행)
        for col, piece_type_char in enumerate(['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']):
            pokemon_family = POKEMON_DATA[self.white_team_type][piece_type_char]
            board[7][col] = Piece('w', piece_type_char, pokemon_family)
        for col in range(COLS):
            pokemon_family = POKEMON_DATA[self.white_team_type]['P']
            board[6][col] = Piece('w', 'P', pokemon_family)
        
        return board
    def draw_board(self):
        for row in range(ROWS):
            for col in range(COLS):
                color = LIGHT_SQUARE if (row + col) % 2 == 0 else DARK_SQUARE
                display_r, display_c = self._get_display_coords(row, col) # 시점 전환 적용
                pygame.draw.rect(self.win, color, (display_c * SQUARE_SIZE, display_r * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))

    def draw_pieces(self):
        """다운로드한 포켓몬 이미지와 기물 텍스트를 보드에 그림"""
        for row in range(ROWS):
            for col in range(COLS):
                piece = self.board[row][col]
                if piece: # Piece 객체가 있는 경우
                    display_r, display_c = self._get_display_coords(row, col) # 시점 전환 적용
                    
                    # 포켓몬 스프라이트 그리기
                    pokemon_name = piece.get_current_pokemon_name()
                    sprite = self.piece_sprites.get(pokemon_name)
                    if sprite:
                        rect = sprite.get_rect(center=(display_c * SQUARE_SIZE + SQUARE_SIZE // 2, display_r * SQUARE_SIZE + SQUARE_SIZE // 2))
                        self.win.blit(sprite, rect)

                    # 기물 종류(Q, R 등)를 팀 색상에 맞게 그리기
                    piece_type = piece.piece_type
                    pos = (display_c * SQUARE_SIZE + 5, display_r * SQUARE_SIZE + 5) # 시점 전환 적용

                    # 모든 기물 텍스트를 흰색 글씨에 검은 테두리로 통일
                    border_surface = self.label_font.render(piece_type, True, BLACK)
                    offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)] # 상하좌우
                    for dx, dy in offsets:
                        self.win.blit(border_surface, (pos[0] + dx, pos[1] + dy))

                    # 원래 흰색 글씨 그리기
                    text_surface = self.label_font.render(piece_type, True, WHITE)
                    self.win.blit(text_surface, pos)

    def draw_valid_moves(self):
        if self.selected_piece:
            # 선택된 칸 하이라이트
            highlight_surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
            highlight_surface.fill(HIGHLIGHT_COLOR)
            
            selected_r, selected_c = self.selected_piece[1]
            display_selected_r, display_selected_c = self._get_display_coords(selected_r, selected_c) # 시점 전환 적용
            self.win.blit(highlight_surface, (display_selected_c * SQUARE_SIZE, display_selected_r * SQUARE_SIZE))
            
            # 유효한 움직임 표시
            for move in self.valid_moves:
                r, c = move
                is_capture = self.board[r][c] is not None or move == self.en_passant_possible
                color = HIGHLIGHT_CAPTURE_COLOR if is_capture else HIGHLIGHT_MOVE_COLOR
                
                display_r, display_c = self._get_display_coords(r, c) # 시점 전환 적용

                # 원을 그릴 Surface 생성
                circle_surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
                pygame.draw.circle(circle_surface, color, (SQUARE_SIZE // 2, SQUARE_SIZE // 2), 15)
                self.win.blit(circle_surface, (display_c * SQUARE_SIZE, display_r * SQUARE_SIZE))

    # --- 나머지 게임 로직 (select_piece, move_piece, get_valid_moves, handle_click)은 기존과 거의 동일 ---
    # (이 부분은 생략하고 기존 코드를 그대로 사용한다고 가정)
    def select_piece(self, row, col):
        piece = self.board[row][col]
        if self.promotion_pending is None:
            if piece and piece.color == self.turn: # Piece 객체가 있고, 자신의 턴인 기물
                self.selected_piece = (piece, (row, col))
                self.valid_moves = self.get_valid_moves(piece, row, col)
                self.feedback_message = "" # 유효한 선택이므로 메시지 초기화
                return True
            else:
                # 자신의 턴이 아닌 기물을 선택했거나 빈 칸을 선택
                self.feedback_message = "자신의 기물을 선택하세요!" if piece else "빈 칸입니다."
                self.feedback_timer = pygame.time.get_ticks() + 2000 # 2초간 표시
                return False
        return False # 프로모션 대기 중에는 선택 불가

    def update_castling_rights(self, piece, start_pos):
        if piece.piece_type == 'K' and piece.color == 'w':
            self.castling_rights['w_king'] = False
            self.castling_rights['w_queen'] = False
        elif piece.piece_type == 'K' and piece.color == 'b':
            self.castling_rights['b_king'] = False
            self.castling_rights['b_queen'] = False
        elif piece.piece_type == 'R' and piece.color == 'w':
            if start_pos == (7, 0):
                self.castling_rights['w_queen'] = False
            elif start_pos == (7, 7):
                self.castling_rights['w_king'] = False
        elif piece.piece_type == 'R' and piece.color == 'b':
            if start_pos == (0, 0):
                self.castling_rights['b_queen'] = False
            elif start_pos == (0, 7):
                self.castling_rights['b_king'] = False

    def move_piece(self, start_pos, end_pos):
        self.feedback_message = "" # 새 움직임 시 피드백 메시지 초기화
        start_row, start_col = start_pos
        end_row, end_col = end_pos
        moving_piece = self.board[start_row][start_col] # moving_piece는 Piece 객체

        # 잡히는 기물 (있다면)
        captured_piece = self.board[end_row][end_col]
        
        # 앙파상 캡처인 경우, 실제로 잡히는 폰은 다른 칸에 있음
        is_en_passant_move = (moving_piece.piece_type == 'P' and (end_row, end_col) == self.en_passant_possible)
        if is_en_passant_move:
            captured_piece = self.board[start_row][end_col] # 앙파상으로 잡히는 폰
        
        # 기보 기록 (get_chess_notation도 Piece 객체에 맞게 수정 필요)
        move_notation = self.get_chess_notation(start_pos, end_pos, moving_piece)
        self.move_log.append(move_notation)

        # 1. 보드 위에서 말을 먼저 이동
        self.board[end_row][end_col] = moving_piece
        self.board[start_row][start_col] = None

        # 진화 로직: 기물이 다른 기물을 잡으면 진화
        if captured_piece is not None: # captured_piece가 있으면 진화
            evolution_message = moving_piece.evolve()
            if evolution_message:
                self.feedback_message = evolution_message
                self.feedback_timer = pygame.time.get_ticks() + 3000

        # 2. 이번 이동이 앙파상 잡기였는지 확인
        if moving_piece.piece_type == 'P' and (end_row, end_col) == self.en_passant_possible:
            self.board[start_row][end_col] = None # 상대 폰 제거 (Piece 객체)

        # 3. 다음 턴을 위한 앙파상 상태 설정
        if moving_piece.piece_type == 'P' and abs(start_row - end_row) == 2:
            self.en_passant_possible = ((start_row + end_row) // 2, start_col)
        else:
            self.en_passant_possible = ()

        # 캐슬링 시 룩 이동
        if moving_piece.piece_type == 'K' and abs(start_col - end_col) == 2:
            if end_col == 6: # 킹사이드
                rook = self.board[end_row][7]
                self.board[end_row][5] = rook
                self.board[end_row][7] = None
            else: # 퀸사이드
                rook = self.board[end_row][0]
                self.board[end_row][3] = rook
                self.board[end_row][0] = None

        # 캐슬링 권한 업데이트
        self.update_castling_rights(moving_piece, start_pos)

        # 폰 프로모션 확인
        if moving_piece.piece_type == 'P' and (end_row == 0 or end_row == 7):
            self.promotion_pending = (end_row, end_col, moving_piece) # Piece 객체도 함께 저장
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
                if piece and piece.color == color:
                    moves = self.get_valid_moves(piece, r, c)
                    if moves:
                        all_moves.extend(moves)
        return all_moves

    def get_chess_notation(self, start_pos, end_pos, piece):
        def get_rank_file(r, c):
            return chr(ord('a') + c) + str(8 - r)

        # 캐슬링 표기
        if piece.piece_type == 'K' and abs(start_pos[1] - end_pos[1]) == 2:
            return "O-O" if end_pos[1] == 6 else "O-O-O"

        start_sq = get_rank_file(start_pos[0], start_pos[1])
        end_sq = get_rank_file(end_pos[0], end_pos[1])
        piece_char = piece.piece_type if piece.piece_type != 'P' else ''
        
        is_capture = self.board[end_pos[0]][end_pos[1]] is not None
        if piece.piece_type == 'P' and start_pos[1] != end_pos[1] and not is_capture: # 앙파상
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
                if p and p.color == opponent_color:
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
            if self.board[r][c+1] is None and self.board[r][c+2] is None:
                if not self.square_under_attack(r, c+1, self.turn) and not self.square_under_attack(r, c+2, self.turn):
                    moves.append((r, c+2))
        if (self.turn == 'w' and self.castling_rights['w_queen']) or (self.turn == 'b' and self.castling_rights['b_queen']):
            # 퀸사이드 캐슬링
            if self.board[r][c-1] is None and self.board[r][c-2] is None and self.board[r][c-3] is None:
                if not self.square_under_attack(r, c-1, self.turn) and not self.square_under_attack(r, c-2, self.turn):
                    moves.append((r, c-2))

    def get_piece_moves(self, piece, row, col):
        """get_valid_moves의 재귀 호출을 피하기 위한 간단한 버전"""
        moves = []
        color = piece.color
        piece_type = piece.piece_type

        if piece_type == 'P':
            direction = -1 if color == 'w' else 1
            # 전진
            if 0 <= row + direction < 8 and self.board[row + direction][col] is None:
                moves.append((row + direction, col))
            # 첫 이동 2칸 전진
            if (row == 6 if color == 'w' else row == 1) and self.board[row + 2 * direction][col] is None and self.board[row + direction][col] is None:
                moves.append((row + 2 * direction, col))
            # 대각선 공격
            for d_col in [-1, 1]:
                if 0 <= col + d_col < 8 and 0 <= row + direction < 8:
                    target = self.board[row + direction][col + d_col]
                    if target is not None and target.color != color:
                        moves.append((row + direction, col + d_col))
                    # 앙파상
                    elif (row + direction, col + d_col) == self.en_passant_possible:
                        moves.append((row + direction, col + d_col))
        if piece_type == 'P':
            direction = -1 if color == 'w' else 1
            # 전진
            if 0 <= row + direction < 8 and self.board[row + direction][col] is None:
                moves.append((row + direction, col))
            # 첫 이동 2칸 전진
            if (row == 6 if color == 'w' else row == 1) and self.board[row + 2 * direction][col] is None and self.board[row + direction][col] is None:
                moves.append((row + 2 * direction, col))
            # 대각선 공격
            for d_col in [-1, 1]:
                if 0 <= col + d_col < 8 and 0 <= row + direction < 8:
                    target = self.board[row + direction][col + d_col]
                    if target is not None and target.color != color:
                        moves.append((row + direction, col + d_col))
                    # 앙파상
                    elif (row + direction, col + d_col) == self.en_passant_possible:
                        moves.append((row + direction, col + d_col))
        
        # Rook 또는 Queen의 움직임
        if piece_type == 'R' or piece_type == 'Q':
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]: # 상하좌우
                for i in range(1, 8):
                    r, c = row + dr * i, col + dc * i
                    if 0 <= r < 8 and 0 <= c < 8:
                        target = self.board[r][c]
                        if target is None:
                            moves.append((r, c))
                        elif target.color != color:
                            moves.append((r, c))
                            break
                        else:
                            break
                    else:
                        break
        
        # Bishop 또는 Queen의 움직임
        if piece_type == 'B' or piece_type == 'Q':
            for dr, dc in [(1, 1), (1, -1), (-1, 1), (-1, -1)]: # 대각선
                for i in range(1, 8):
                    r, c = row + dr * i, col + dc * i
                    if 0 <= r < 8 and 0 <= c < 8:
                        target = self.board[r][c]
                        if target is None:
                            moves.append((r, c))
                        elif target.color != color:
                            moves.append((r, c))
                            break
                        else:
                            break
                    else:
                        break
        
        elif piece_type == 'N':
            for dr, dc in [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]:
                r, c = row + dr, col + dc
                if 0 <= r < 8 and 0 <= c < 8:
                    target = self.board[r][c]
                    if target is None or target.color != color:
                        moves.append((r, c))
        elif piece_type == 'K':
            for dr, dc in [(dr, dc) for dr in [-1, 0, 1] for dc in [-1, 0, 1] if not (dr == 0 and dc == 0)]:
                r, c = row + dr, col + dc
                if 0 <= r < 8 and 0 <= c < 8:
                    target = self.board[r][c]
                    if target is None or target.color != color:
                        moves.append((r, c))
        return moves

    def get_valid_moves(self, piece, row, col):
        moves = self.get_piece_moves(piece, row, col)
        if piece.piece_type == 'K':
            self.get_castle_moves(row, col, moves)
        
        legal_moves = []
        for move in moves:
            start_pos = (row, col)
            end_pos = move
            
            # --- 시뮬레이션 시작 ---
            captured_piece_at_end_pos = self.board[end_pos[0]][end_pos[1]]
            is_en_passant = (piece.piece_type == 'P' and end_pos == self.en_passant_possible)
            captured_en_passant_pawn = None
            en_passant_pawn_pos = None

            # 가상으로 말 이동
            self.board[end_pos[0]][end_pos[1]] = piece
            self.board[start_pos[0]][start_pos[1]] = None
            if is_en_passant:
                en_passant_pawn_pos = (start_pos[0], end_pos[1])
                captured_en_passant_pawn = self.board[en_passant_pawn_pos[0]][en_passant_pawn_pos[1]]
                self.board[en_passant_pawn_pos[0]][en_passant_pawn_pos[1]] = None

            # 체크 상태 확인
            if not self.is_in_check(self.turn):
                legal_moves.append(move)

            # --- 보드 원상복구 ---
            self.board[start_pos[0]][start_pos[1]] = piece
            self.board[end_pos[0]][end_pos[1]] = captured_piece_at_end_pos
            if is_en_passant:
                self.board[en_passant_pawn_pos[0]][en_passant_pawn_pos[1]] = captured_en_passant_pawn

        return legal_moves

    def is_in_check(self, color):
        """주어진 색의 킹이 체크 상태인지 확인"""
        king_pos = None
        for r in range(ROWS):
            for c in range(COLS):
                piece = self.board[r][c]
                if piece and piece.piece_type == 'K' and piece.color == color:
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
            r, c, pawn_piece = self.promotion_pending # pawn_piece 객체도 함께 가져옴
            choice_rects = self.draw_promotion_choice() # 사각형 위치 가져오기
            for piece_char, rect in choice_rects.items():
                if rect.collidepoint(pos):
                    color = self.turn
                    # 승급될 기물의 포켓몬 패밀리를 선택된 타입에서 가져옴
                    team_type = self.black_team_type if color == 'b' else self.white_team_type
                    pokemon_family = POKEMON_DATA[team_type][piece_char]
                    # 새로운 Piece 객체로 교체
                    self.board[r][c] = Piece(color, piece_char, pokemon_family)
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

        # 화면 좌표를 보드 좌표로 역변환
        if self.turn == 'w':
            board_row, board_col = row, col
        else:
            board_row, board_col = 7 - row, 7 - col

        if self.selected_piece:
            start_pos = self.selected_piece[1]
            # Case 1: Clicked square is a valid move
            if (board_row, board_col) in self.valid_moves:
                self.move_piece(start_pos, (board_row, board_col))
            # Case 2: Clicked square is the same as the selected piece -> Deselect
            elif (board_row, board_col) == start_pos:
                self.selected_piece = None
                self.valid_moves = []
                self.feedback_message = ""
            # Case 3: Clicked square has another of the player's pieces -> Reselect
            elif self.board[board_row][board_col] and self.board[board_row][board_col].color == self.turn:
                self.select_piece(board_row, board_col)
            # Case 4: Any other click is an invalid move
            else:
                self.feedback_message = "유효하지 않은 움직임입니다."
                self.feedback_timer = pygame.time.get_ticks() + 2000
                # Do not change selection state
        else:
            # No piece is selected, so try to select one
            self.select_piece(board_row, board_col)

    def draw_promotion_choice(self):
        if not self.promotion_pending:
            return {}

        r, c, _ = self.promotion_pending
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

    def draw_status_area(self):
        # 턴 표시
        turn_text = "백의 턴" if self.turn == 'w' else "흑의 턴"
        turn_color = WHITE # 항상 흰색으로 설정하여 가시성 확보
        
        # 흑의 턴일 때 글씨가 잘 보이도록 배경색을 어둡게
        if self.turn == 'b':
            pygame.draw.rect(self.win, (50, 50, 50), (BOARD_WIDTH, HEIGHT - 50, LOG_WIDTH, 50))

        turn_surface = self.log_font.render(turn_text, True, turn_color)
        self.win.blit(turn_surface, (BOARD_WIDTH + 10, HEIGHT - 40))

        # 피드백 메시지 표시
        if self.feedback_message and pygame.time.get_ticks() < self.feedback_timer:
            color = (255, 0, 0) # Red color
            pos = (BOARD_WIDTH + 10, HEIGHT - 90)
            max_width = LOG_WIDTH - 20
            words = self.feedback_message.split(' ')
            
            lines = []
            current_line = ""
            for word in words:
                test_line = current_line + word + " "
                if self.log_font.size(test_line)[0] < max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word + " "
            lines.append(current_line)
            
            y_offset = 0
            for line in lines:
                feedback_surface = self.log_font.render(line.strip(), True, color)
                self.win.blit(feedback_surface, (pos[0], pos[1] + y_offset))
                y_offset += self.log_font.get_height()

    def _get_display_coords(self, r, c):
        """현재 턴에 따라 화면에 표시될 (row, col) 좌표를 반환"""
        if self.turn == 'w':
            return r, c
        else: # 흑의 턴일 때는 보드를 뒤집어서 표시
            return 7 - r, 7 - c

    def update(self):
        self.win.fill(BLACK)
        self.draw_board()
        self.draw_pieces() # 기물을 먼저 그림
        self.draw_valid_moves() # 그 위에 유효한 움직임을 그림
        self.draw_move_log()
        self.draw_status_area() # 상태 영역 그리기
        self.draw_promotion_choice()
        self.draw_game_over()
        pygame.display.flip()

def main():
    pygame.init()
    win = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Pokemon Chess")

    # 게임 상태 정의
    TYPE_SELECTION = 0
    LOADING = 1
    PLAYING = 2
    GAME_OVER = 3

    game_state = TYPE_SELECTION # 초기 게임 상태는 타입 선택 화면
    game = Game(win) # Game 객체는 모든 상태를 관리할 수 있도록 초기화

    run = True
    while run:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                if game_state == TYPE_SELECTION:
                    result = game.handle_type_selection_click(pos)
                    if result == "TYPES_SELECTED":
                        game_state = LOADING # 타입 선택 완료, 로딩 상태로 전환
                elif game_state == PLAYING:
                    game.handle_click(pos)
            if event.type == pygame.KEYDOWN:
                if game_state == PLAYING:
                    if event.key == pygame.K_r: # 'r' 키로 게임 리셋
                        game.reset_game()

        if game_state == TYPE_SELECTION:
            game.draw_type_selection_screen()
        elif game_state == LOADING:
            # 로딩 화면 그리기 및 스프라이트 로드
            game.draw_loading_screen() # 로딩 화면 표시
            game.piece_sprites = load_pokemon_sprites(game.white_team_type, game.black_team_type) # 스프라이트 로드
            game.board = game.setup_board() # 보드 초기화
            game_state = PLAYING # 로딩 완료, 플레이 상태로 전환
        elif game_state == PLAYING:
            game.update()
        elif game_state == GAME_OVER:
            game.update()

        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    main()