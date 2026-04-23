"""
Cenas e fluxo principal do projeto.

Este módulo concentra a tela de abertura, a fase principal, a tela de game over
e o objeto principal do jogo. Aqui ficam explícitos vários pontos solicitados, como:

- abertura com linha, círculo, elipse e Flood Fill
- jogo baseado em polígonos com scanline, gradiente e textura
- input por teclado e mouse
- janela, viewport, pan e zoom
- clipping de Cohen-Sutherland nos raios do professor
- animação 2D e lógica de estados da simulação

"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import pygame

from algorithms import Rasterizer, WindowViewport
from entities import ClassroomSeat, Student, Teacher
from settings import (
    AMBER,
    BLACKBOARD,
    BLACKBOARD_BORDER,
    BUTTON_GREEN,
    DANGER,
    EXAM_TARGET,
    INK,
    MENU_BG,
    NAVY,
    NOTEBOOK,
    ORANGE_WOOD,
    PANEL_BLUE,
    PHONE_YELLOW,
    SAFE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SHADOW,
    SOFT_WHITE,
    VIEWPORT,
    WALL_COLOR,
    WORLD_BOUNDS,
)
from ui import Button, blit_centered, draw_panel, draw_wrapped_text


class Scene:
    """Classe base abstrata para todas as cenas do jogo."""
    def __init__(self, game: 'Try2CheatGame') -> None:
        self.game = game


    def handle_event(self, event: pygame.event.Event) -> None:
        """Contrato de tratamento de eventos para as cenas concretas."""
        raise NotImplementedError

    def update(self, dt: float) -> None:
        """Contrato de atualização temporal para as cenas concretas."""
        raise NotImplementedError

    def draw(self, surface: pygame.Surface) -> None:
        """Contrato de desenho para as cenas concretas."""
        raise NotImplementedError


def draw_filled_circle(rasterizer: Rasterizer, surface: pygame.Surface, center: tuple[int, int], radius: int, fill_color, outline_color) -> None:
    """Desenha um círculo preenchido usando várias circunferências rasterizadas."""
    for current_radius in range(radius, 0, -1):
        rasterizer.draw_circle(surface, center, current_radius, fill_color)
    rasterizer.draw_circle(surface, center, radius, outline_color)
    rasterizer.draw_circle(surface, center, max(1, radius - 2), (132, 138, 148))


def draw_split_title(
    surface: pygame.Surface,
    font: pygame.font.Font,
    left_text: str,
    right_text: str,
    y: int,
    left_color,
    right_color,
    shadow_color,
    gap: int = 6,
) -> pygame.Rect:
    """Escreve o título dividido em duas cores para reforçar a identidade visual."""
    left = font.render(left_text, False, left_color)
    right = font.render(right_text, False, right_color)
    total_width = left.get_width() + gap + right.get_width()
    x = (surface.get_width() - total_width) // 2
    shadow_left = font.render(left_text, False, shadow_color)
    shadow_right = font.render(right_text, False, shadow_color)
    surface.blit(shadow_left, (x + 4, y + 4))
    surface.blit(shadow_right, (x + left.get_width() + gap + 4, y + 4))
    surface.blit(left, (x, y))
    surface.blit(right, (x + left.get_width() + gap, y))
    return pygame.Rect(x, y, total_width, max(left.get_height(), right.get_height()))


def draw_wastebasket(
    rasterizer: Rasterizer,
    surface: pygame.Surface,
    center: tuple[int, int],
    *,
    rx: int = 18,
    ry: int = 7,
    body_height: int = 50,
    body_bottom_half_width: int = 12,
) -> None:
    """
    Desenha a lixeira da sala de aula.

    Esta função existe para deixar explícito o requisito da abertura com elipse e
    Flood Fill: a borda superior é desenhada com elipse e o preenchimento é feito
    por flood fill. O corpo usa linhas rasterizadas.
    """
    cx, cy = center
    outline = INK
    shell_fill = (146, 156, 168)
    shell_shadow = (112, 122, 134)
    opening_fill = (62, 70, 82)

    # borda superior elíptica
    rasterizer.draw_ellipse(surface, (cx, cy), rx, ry, outline)
    rasterizer.flood_fill(surface, (cx, cy - 1), shell_fill)

    inner_rx = max(3, rx - 4)
    inner_ry = max(2, ry - 3)
    rasterizer.draw_ellipse(surface, (cx, cy), inner_rx, inner_ry, outline)
    rasterizer.flood_fill(surface, (cx, cy), opening_fill)

    # corpo em trapézio, fechado por linhas rasterizadas
    left_top = (cx - rx + 3, cy + 1)
    right_top = (cx + rx - 3, cy + 1)
    left_bottom = (cx - body_bottom_half_width, cy + body_height)
    right_bottom = (cx + body_bottom_half_width, cy + body_height)
    rasterizer.draw_line(surface, left_top, left_bottom, outline)
    rasterizer.draw_line(surface, right_top, right_bottom, outline)
    rasterizer.draw_line(surface, left_bottom, right_bottom, outline)
    rasterizer.flood_fill(surface, (cx, cy + body_height // 2), shell_shadow)

    # frisos verticais para parecer lixeira metálica
    for offset in (-7, 0, 7):
        top = (cx + offset, cy + 6)
        bottom = (cx + int(offset * 0.6), cy + body_height - 6)
        rasterizer.draw_line(surface, top, bottom, (88, 96, 108))


class MenuScene(Scene):
    """Tela de abertura/menu interativo do projeto."""
    def __init__(self, game: 'Try2CheatGame') -> None:
        super().__init__(game)
        self.button = Button(pygame.Rect(430, 612, 420, 82), 'COMEÇAR')
        self.hovered = False
        self.cached_surface: pygame.Surface | None = None

    def handle_event(self, event: pygame.event.Event) -> None:
        """trata mouse e teclado do menu interativo."""
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.button.contains(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.button.contains(event.pos):
                self.game.start_new_match()
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.game.start_new_match()

    def update(self, dt: float) -> None:
        _ = dt

    def _render_static(self) -> pygame.Surface:
        """
        Monta a tela de abertura estática.

        Nesta cena aparecem os requisitos de rasterização na abertura:
        linhas, círculos, elipse (na lixeira) e flood fill. Também há polígonos
        preenchidos por scanline/gradiente e textura nas carteiras.
        """
        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        r = self.game.rasterizer
        surface.fill(MENU_BG)

        # Fundo principal da sala: polígonos grandes preenchidos por gradiente e scanline.
        wall = [(0, 0), (SCREEN_WIDTH, 0), (SCREEN_WIDTH, 548), (0, 548)]
        floor = [(0, 548), (SCREEN_WIDTH, 548), (SCREEN_WIDTH, SCREEN_HEIGHT), (0, SCREEN_HEIGHT)]
        r.fill_polygon_gradient(surface, wall, [(241, 223, 189), (241, 223, 189), (225, 200, 162), (225, 200, 162)])
        r.fill_polygon_scanline(surface, floor, (154, 101, 62))

        board_rect = pygame.Rect((SCREEN_WIDTH - 934) // 2, 138, 934, 282)
        board = [
            (board_rect.left, board_rect.top),
            (board_rect.right, board_rect.top),
            (board_rect.right, board_rect.bottom),
            (board_rect.left, board_rect.bottom),
        ]
        r.fill_polygon_scanline(surface, board, BLACKBOARD)
        r.draw_polyline(surface, board, BLACKBOARD_BORDER)
        r.fill_polygon_scanline(
            surface,
            [
                (board_rect.left - 6, board_rect.top - 8),
                (board_rect.right + 6, board_rect.top - 8),
                (board_rect.right + 6, board_rect.top + 2),
                (board_rect.left - 6, board_rect.top + 2),
            ],
            BLACKBOARD_BORDER,
        )
        tray = [
            (board_rect.centerx - 172, board_rect.bottom + 2),
            (board_rect.centerx + 172, board_rect.bottom + 2),
            (board_rect.centerx + 172, board_rect.bottom + 10),
            (board_rect.centerx - 172, board_rect.bottom + 10),
        ]
        r.fill_polygon_scanline(surface, tray, BLACKBOARD_BORDER)
        r.draw_polyline(surface, tray, INK)

        # Relógio: exemplo explícito do uso de circunferência na tela de abertura.
        clock_center = (80, 200)
        draw_filled_circle(r, surface, clock_center, 44, (242, 244, 246), INK)
        r.draw_line(surface, clock_center, (clock_center[0], clock_center[1] - 24), INK)
        r.draw_line(surface, clock_center, (clock_center[0] - 17, clock_center[1] + 15), INK)

        shelf = [(1123, 156), (1265, 156), (1265, 296), (1123, 296)]
        r.fill_polygon_gradient(surface, shelf, [(103, 68, 42), (135, 86, 52), (92, 56, 28), (84, 49, 22)])
        r.draw_polyline(surface, shelf, INK)
        for y in (182, 230):
            r.draw_line(surface, (1129, y), (1253, y), INK)
        for x in (1145, 1185, 1215):
            r.draw_line(surface, (x, 160), (x, 278), INK)
        books = [
            (1133, 160, 12, 44, (201, 72, 48)),
            (1149, 160, 14, 44, (68, 91, 176)),
            (1169, 160, 10, 44, (238, 190, 67)),
            (1193, 168, 16, 36, (95, 142, 71)),
            (1135, 208, 12, 56, (98, 125, 181)),
            (1152, 220, 14, 44, (218, 79, 65)),
            (1173, 212, 20, 52, (235, 191, 77)),
            (1197, 216, 14, 48, (95, 142, 71)),
            (1219, 208, 16, 56, (81, 97, 168)),
        ]
        for bx, by, bw, bh, color in books:
            rect = [(bx, by), (bx + bw, by), (bx + bw, by + bh), (bx, by + bh)]
            r.fill_polygon_scanline(surface, rect, color)
            r.draw_polyline(surface, rect, INK)

        # Janela/viewport auxiliar para desenhar carteiras e alunos na abertura.
        temp_camera = WindowViewport(WORLD_BOUNDS, [0.0, 0.0, SCREEN_WIDTH, SCREEN_HEIGHT], VIEWPORT)
        seat_y = 550
        seat_start_x = (SCREEN_WIDTH - (4 * 126 + 56)) // 2 + 18
        seats = [ClassroomSeat(seat_start_x + i * 126, seat_y, 56, 14) for i in range(5)]
        students = [Student(seat_start_x - 20 + i * 126, seat_y + 18, i + 10, scale=1.0) for i in range(5)]
        for seat in seats:
            seat.draw(surface, r, temp_camera, self.game.desk_texture)
        for student in students:
            student.phone_anim = 0.0
            student.draw(surface, r, temp_camera)

        self._draw_teacher_background(surface)

        draw_split_title(surface, self.game.font_xl, 'TRY2', 'CHEAT', 24, (247, 210, 76), (215, 62, 52), INK)

        title_how_y = board_rect.top + 5
        title_how = self.game.font_l.render('COMO JOGAR', False, (255, 214, 66))
        title_how_shadow = self.game.font_l.render('COMO JOGAR', False, INK)
        title_how_x = board_rect.x + (board_rect.width - title_how.get_width()) // 2
        surface.blit(title_how_shadow, (title_how_x + 3, title_how_y + 3))
        surface.blit(title_how, (title_how_x, title_how_y))
        underline_y = board_rect.top + 45
        r.draw_line(surface, (board_rect.x + 160, underline_y), (board_rect.right - 160, underline_y), (210, 196, 130))

        instructions = [
            'Use o celular apenas quando o professor estiver olhando para o notebook.',
            'Se ele olhar para a turma ou caminhar pela sala, esconda o celular.',
            'Complete a barra de COLA antes do tempo acabar.',
        ]
        for y, line in zip((board_rect.top + 50, board_rect.top + 80, board_rect.top + 110), instructions):
            text_rect = pygame.Rect(board_rect.x + 56, y, board_rect.width - 112, 22)
            draw_wrapped_text(
                surface,
                self.game.font_s,
                line,
                text_rect,
                SOFT_WHITE,
                align='center',
                shadow=INK,
                line_gap=0,
            )

        title_controls_y = board_rect.top + 135
        title_controls = self.game.font_l.render('CONTROLES', False, (255, 214, 66))
        title_controls_shadow = self.game.font_l.render('CONTROLES', False, INK)
        title_controls_x = board_rect.x + (board_rect.width - title_controls.get_width()) // 2
        surface.blit(title_controls_shadow, (title_controls_x + 3, title_controls_y + 3))
        surface.blit(title_controls, (title_controls_x, title_controls_y))
        controls = [
            'ESPAÇO - pegar ou guardar o celular',
            'ENTER - iniciar a partida',
            'SETAS - mover a câmera',
            'SCROLL - zoom da câmera',
        ]
        for y, line in zip((board_rect.top + 176, board_rect.top + 204, board_rect.top + 232, board_rect.top + 260), controls):
            draw_wrapped_text(
                surface,
                self.game.font_s,
                line,
                pygame.Rect(board_rect.x + 80, y, board_rect.width - 160, 20),
                SOFT_WHITE,
                align='center',
                shadow=INK,
                line_gap=0,
            )

        return surface

    def _draw_teacher_background(self, surface: pygame.Surface) -> None:
        """Desenha a mesa do professor e a lixeira da abertura."""
        r = self.game.rasterizer

        # mesa do professor no menu
        desk_x = 1062
        desk_top = [(desk_x, 508), (desk_x + 58, 508), (desk_x + 72, 524), (desk_x + 14, 524)]
        desk_front = [(desk_x + 14, 524), (desk_x + 72, 524), (desk_x + 72, 592), (desk_x + 14, 592)]
        desk_side = [(desk_x + 58, 508), (desk_x + 72, 524), (desk_x + 72, 592), (desk_x + 58, 576)]
        desk_leg_left = [(desk_x + 18, 592), (desk_x + 28, 592), (desk_x + 28, 618), (desk_x + 18, 618)]
        desk_leg_right = [(desk_x + 50, 592), (desk_x + 60, 592), (desk_x + 60, 618), (desk_x + 50, 618)]

        # Textura aplicada também no tampo da mesa do professor.
        r.fill_polygon_textured(surface, desk_top, [(0.0, 0.0), (1.2, 0.0), (1.2, 1.0), (0.0, 1.0)], self.game.desk_texture)
        r.draw_polyline(surface, desk_top, INK)

        for poly, colors in (
            (desk_front, [(162, 104, 60), (186, 124, 72), (118, 72, 38), (128, 78, 42)]),
            (desk_side, [(148, 96, 52), (174, 116, 66), (110, 66, 34), (110, 66, 34)]),
        ):
            r.fill_polygon_gradient(surface, poly, colors)
            r.draw_polyline(surface, poly, INK)

        for poly in (desk_leg_left, desk_leg_right):
            r.fill_polygon_scanline(surface, poly, (120, 74, 38))
            r.draw_polyline(surface, poly, INK)

        """
        
         mesmo avatar do professor da tela de jogo, sem notebook/retângulo cinza
         no menu o estado RETURN ignora self.y, então usamos uma pose local
         para baixar o professor e deixá-lo com metade do corpo sobre o chão marrom.
         
        """
        draw_wastebasket(r, surface, (1212, 568), rx=18, ry=7, body_height=48, body_bottom_half_width=12)

        # Janela/viewport auxiliar para desenhar carteiras e alunos na abertura.
        temp_camera = WindowViewport(WORLD_BOUNDS, [0.0, 0.0, SCREEN_WIDTH, SCREEN_HEIGHT], VIEWPORT)
        menu_teacher = Teacher(x=1148.0, y=590.0)
        menu_teacher.pose = lambda state: (menu_teacher.x, 560.0, 4.0)
        menu_teacher.draw(surface, r, temp_camera, 'RETURN', 0.0)

    def draw(self, surface: pygame.Surface) -> None:
        if self.cached_surface is None:
            self.cached_surface = self._render_static()
        surface.blit(self.cached_surface, (0, 0))
        self.button.draw(surface, self.game.rasterizer, self.game.font_l, self.hovered)


class GameScene(Scene):
    """
    Cena principal.

    Reúne os elementos de simulação, HUD, animação, câmera com pan/zoom, clipping
    e a lógica de risco/cola durante a prova.
    """
    def __init__(self, game: 'Try2CheatGame') -> None:
        super().__init__(game)
        self.camera = WindowViewport(WORLD_BOUNDS, [0.0, 0.0, float(SCREEN_WIDTH), float(SCREEN_HEIGHT)], VIEWPORT)
        self.minimap_camera = WindowViewport(WORLD_BOUNDS, [0.0, 0.0, WORLD_BOUNDS[2], WORLD_BOUNDS[3]], (0, 0, 1, 1))
        self.world_camera = WindowViewport(WORLD_BOUNDS, [0.0, 0.0, WORLD_BOUNDS[2], WORLD_BOUNDS[3]], (0, 0, int(WORLD_BOUNDS[2]), int(WORLD_BOUNDS[3])))

        seat_y = 550
        seat_start_x = (SCREEN_WIDTH - (4 * 126 + 56)) // 2 + 18
        self.seats = [ClassroomSeat(seat_start_x + i * 126, seat_y, 56, 14) for i in range(5)]
        self.students = [Student(seat_start_x - 20 + i * 126, seat_y + 18, i if i < 2 else i + 1, scale=1.0) for i in range(5)]
        self.teacher = Teacher(x=1148.0, y=560.0)
        self.background_cache: pygame.Surface | None = None
        self.camera_velocity = [0.0, 0.0]
        self.state = 'LOOK_DOWN'
        self.state_timer = random.uniform(1.0, 1.8)
        self.state_total = self.state_timer
        self.score = 0.0
        self.risk = 0.0
        self.game_time = 52.0
        self.freeze = False
        self.success = False
        self.message = 'Professor olhando para o notebook. Momento seguro.'
        self.anim_clock = 0.0
        self.walk_start_x = 1148.0
        self.walk_target_x = 860.0
        self.catch_roll_timer = 0.0
        self.zoom_velocity = 0.0
        self.zoom_focus = (self.camera.window[0] + self.camera.window[2] * 0.5, self.camera.window[1] + self.camera.window[3] * 0.5)

    def _risk_probability(self) -> float:
        """Converte o preenchimento da barra de risco em probabilidade de punição."""
        if self.risk < 0.33:
            return 0.05
        if self.risk < 0.66:
            return 0.40
        return 0.75

    def _teacher_attention_probability(self) -> float:
        """Define com que frequência o professor sai do notebook para vigiar a turma."""
        base = self._risk_probability()
        if self.player.phone_visible:
            return min(0.96, base + 0.30)
        return max(0.18, base * 0.65)

    def _maybe_get_caught(self, dt: float) -> bool:
        """Executa a checagem probabilística de o jogador ser pego com o celular."""
        if self.state not in {'LOOK_UP', 'WALK_OUT', 'RETURN'}:
            self.catch_roll_timer = 0.0
            return False

        if not self.player.phone_visible:
            self.catch_roll_timer = 0.0
            return False

        self.catch_roll_timer -= dt
        if self.catch_roll_timer <= 0.0:
            self.catch_roll_timer = 0.18
            return random.random() < self._risk_probability()

        return False

    @property
    def player(self) -> Student:
        return self.students[1]

    def handle_event(self, event: pygame.event.Event) -> None:
        """trata teclado do jogo e scroll do mouse para zoom."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE and not self.freeze:
                self.player.toggle_phone()
            elif event.key == pygame.K_ESCAPE:
                self.game.set_scene(MenuScene(self.game))
            elif event.key == pygame.K_r and self.freeze:
                self.game.start_new_match()
        elif event.type == pygame.MOUSEWHEEL:
            mouse_pos = pygame.mouse.get_pos()
            self.zoom_focus = self.camera.device_to_world(mouse_pos)
            self.zoom_velocity = max(-4.0, min(4.0, self.zoom_velocity + event.y * 2.2))

    def update(self, dt: float) -> None:
        """
        Atualiza câmera, animações, IA do professor e regras de gameplay.

        O zoom é está suavizado com velocidade acumulada para evitar travamentos.
        """

        # Input contínuo do teclado para pan da janela de visualização.
        keys = pygame.key.get_pressed()
        move_x = float(keys[pygame.K_RIGHT]) - float(keys[pygame.K_LEFT])
        move_y = float(keys[pygame.K_DOWN]) - float(keys[pygame.K_UP])
        target_speed = 420.0
        smoothing = min(1.0, dt * 9.0)
        self.camera_velocity[0] += (move_x * target_speed - self.camera_velocity[0]) * smoothing
        self.camera_velocity[1] += (move_y * target_speed - self.camera_velocity[1]) * smoothing
        if abs(move_x) < 1e-3:
            self.camera_velocity[0] *= max(0.0, 1.0 - dt * 8.0)
        if abs(move_y) < 1e-3:
            self.camera_velocity[1] *= max(0.0, 1.0 - dt * 8.0)
        dx = self.camera_velocity[0] * dt
        dy = self.camera_velocity[1] * dt
        if abs(dx) > 0.01 or abs(dy) > 0.01:
            self.camera.pan(dx, dy)

        # zoom da janela usando o scroll do mouse.
        if abs(self.zoom_velocity) > 0.01:
            zoom_factor = max(0.84, min(1.16, 1.0 + self.zoom_velocity * dt))
            self.camera.zoom(zoom_factor, self.zoom_focus)
            self.zoom_velocity *= max(0.0, 1.0 - dt * 8.0)
        else:
            self.zoom_velocity = 0.0

        self.anim_clock += dt
        for student in self.students:
            student.update(dt)

        if self.freeze:
            return

        self._update_teacher(dt)
        self.game_time = max(0.0, self.game_time - dt)

        if self.player.phone_visible:
            self.score = min(EXAM_TARGET, self.score + dt * 25.0)

        if self.state == 'LOOK_DOWN':
            if self.player.phone_visible:
                self.risk = min(1.0, self.risk + dt * 0.16)
                self.message = 'Consultando o celular sem chamar atenção...'
            else:
                self.risk = max(0.0, self.risk - dt * 0.22)
                self.message = 'Professor olhando para o notebook. Momento seguro.'
        elif self.state == 'LOOK_UP':
            self.message = 'Professor levantou a cabeça. Guarde o celular!'
            if self.player.phone_visible:
                self.risk = min(1.0, self.risk + dt * 0.60)
            else:
                self.risk = max(0.0, self.risk - dt * 0.10)
        elif self.state == 'WALK_OUT':
            self.message = 'Professor andando pela sala. Seja discreto!'
            if self.player.phone_visible:
                self.risk = min(1.0, self.risk + dt * 0.90)
            else:
                self.risk = max(0.0, self.risk - dt * 0.14)
        else:
            self.message = 'Professor voltando para a mesa. Ainda é perigoso!'
            if self.player.phone_visible:
                self.risk = min(1.0, self.risk + dt * 0.55)
            else:
                self.risk = max(0.0, self.risk - dt * 0.12)

        if self._maybe_get_caught(dt):
            self.game.set_scene(GameOverScene(self.game, self.score))
            return

        if self.score >= EXAM_TARGET:
            self.freeze = True
            self.success = True
            self.message = 'Você terminou a prova sem ser pego! Pressione R para jogar de novo.'
        elif self.game_time <= 0.0:
            self.freeze = True
            self.success = False
            self.message = 'Você não conseguiu colar na prova. O tempo acabou. Pressione R para recomeçar.'

    def _update_teacher(self, dt: float) -> None:
        """Atualiza a máquina de estados do professor e sua caminhada horizontal."""
        self.state_timer -= dt
        if self.state == 'WALK_OUT':
            progress = 1.0 - max(0.0, self.state_timer) / max(self.state_total, 1e-6)
            self.teacher.x = self.walk_start_x + (self.walk_target_x - self.walk_start_x) * progress
        elif self.state == 'RETURN':
            progress = 1.0 - max(0.0, self.state_timer) / max(self.state_total, 1e-6)
            self.teacher.x = self.walk_target_x + (self.walk_start_x - self.walk_target_x) * progress
        else:
            self.teacher.x = self.walk_start_x

        if self.state_timer > 0.0:
            return

        if self.state == 'LOOK_DOWN':
            if random.random() < self._teacher_attention_probability():
                if random.random() < 0.62:
                    self.state = 'LOOK_UP'
                    self.state_timer = random.uniform(1.5, 2.2)
                else:
                    self.state = 'WALK_OUT'
                    self.state_timer = 2.8
            else:
                self.state = 'LOOK_DOWN'
                self.state_timer = random.uniform(0.8, 1.4)
            self.state_total = self.state_timer
        elif self.state == 'LOOK_UP':
            self.state = 'LOOK_DOWN'
            self.state_timer = random.uniform(1.0, 1.8)
            self.state_total = self.state_timer
        elif self.state == 'WALK_OUT':
            self.state = 'RETURN'
            self.state_timer = 2.6
            self.state_total = self.state_timer
        else:
            self.state = 'LOOK_DOWN'
            self.teacher.x = self.walk_start_x
            self.state_timer = random.uniform(0.9, 1.6)
            self.state_total = self.state_timer

    def _invalidate_background(self) -> None:
        self.background_cache = None

    def _render_background(self) -> pygame.Surface:
        """
        Renderiza o fundo do mundo em coordenadas do espaço de mundo.

        Aqui o cenário é construído quase totalmente com polígonos preenchidos por
        scanline e gradiente. As mesas usam textura.
        """
        surface = pygame.Surface((int(WORLD_BOUNDS[2]), int(WORLD_BOUNDS[3])))
        r = self.game.rasterizer
        cam = self.world_camera
        surface.fill(MENU_BG)

        wall = [
            cam.world_to_device((0, 0)),
            cam.world_to_device((SCREEN_WIDTH, 0)),
            cam.world_to_device((SCREEN_WIDTH, 548)),
            cam.world_to_device((0, 548)),
        ]
        floor = [
            cam.world_to_device((0, 548)),
            cam.world_to_device((WORLD_BOUNDS[2], 548)),
            cam.world_to_device((WORLD_BOUNDS[2], WORLD_BOUNDS[3])),
            cam.world_to_device((0, WORLD_BOUNDS[3])),
        ]
        r.fill_polygon_gradient(surface, wall, [(241, 223, 189), (241, 223, 189), (225, 200, 162), (225, 200, 162)])
        r.fill_polygon_scanline(surface, floor, (154, 101, 62))

        board_rect = pygame.Rect((SCREEN_WIDTH - 934) // 2, 138, 934, 282)
        board = [
            cam.world_to_device((board_rect.left, board_rect.top)),
            cam.world_to_device((board_rect.right, board_rect.top)),
            cam.world_to_device((board_rect.right, board_rect.bottom)),
            cam.world_to_device((board_rect.left, board_rect.bottom)),
        ]
        r.fill_polygon_scanline(surface, board, BLACKBOARD)
        r.draw_polyline(surface, board, BLACKBOARD_BORDER)
        r.fill_polygon_scanline(
            surface,
            [
                cam.world_to_device((board_rect.left - 6, board_rect.top - 8)),
                cam.world_to_device((board_rect.right + 6, board_rect.top - 8)),
                cam.world_to_device((board_rect.right + 6, board_rect.top + 2)),
                cam.world_to_device((board_rect.left - 6, board_rect.top + 2)),
            ],
            BLACKBOARD_BORDER,
        )
        tray = [
            cam.world_to_device((board_rect.centerx - 172, board_rect.bottom + 2)),
            cam.world_to_device((board_rect.centerx + 172, board_rect.bottom + 2)),
            cam.world_to_device((board_rect.centerx + 172, board_rect.bottom + 10)),
            cam.world_to_device((board_rect.centerx - 172, board_rect.bottom + 10)),
        ]
        r.fill_polygon_scanline(surface, tray, BLACKBOARD_BORDER)
        r.draw_polyline(surface, tray, INK)

        clock_center = cam.world_to_device((80, 200))
        draw_filled_circle(r, surface, clock_center, 44, (242, 244, 246), INK)
        r.draw_line(surface, clock_center, (clock_center[0], clock_center[1] - 24), INK)
        r.draw_line(surface, clock_center, (clock_center[0] - 17, clock_center[1] + 15), INK)

        shelf = [
            cam.world_to_device((1123, 156)),
            cam.world_to_device((1265, 156)),
            cam.world_to_device((1265, 296)),
            cam.world_to_device((1123, 296)),
        ]
        r.fill_polygon_gradient(surface, shelf, [(103, 68, 42), (135, 86, 52), (92, 56, 28), (84, 49, 22)])
        r.draw_polyline(surface, shelf, INK)
        for y in (182, 230):
            r.draw_line(surface, cam.world_to_device((1129, y)), cam.world_to_device((1253, y)), INK)
        for x in (1145, 1185, 1215):
            r.draw_line(surface, cam.world_to_device((x, 160)), cam.world_to_device((x, 278)), INK)
        books = [
            (1133, 160, 12, 44, (201, 72, 48)),
            (1149, 160, 14, 44, (68, 91, 176)),
            (1169, 160, 10, 44, (238, 190, 67)),
            (1193, 168, 16, 36, (95, 142, 71)),
            (1135, 208, 12, 56, (98, 125, 181)),
            (1152, 220, 14, 44, (218, 79, 65)),
            (1173, 212, 20, 52, (235, 191, 77)),
            (1197, 216, 14, 48, (95, 142, 71)),
            (1219, 208, 16, 56, (81, 97, 168)),
        ]
        for bx, by, bw, bh, color in books:
            poly = [
                cam.world_to_device((bx, by)),
                cam.world_to_device((bx + bw, by)),
                cam.world_to_device((bx + bw, by + bh)),
                cam.world_to_device((bx, by + bh)),
            ]
            r.fill_polygon_scanline(surface, poly, color)
            r.draw_polyline(surface, poly, INK)

        # Polígonos texturizados nas mesas dos alunos.
        for seat in self.seats:
            seat.draw(surface, r, cam, self.game.desk_texture)

        desk_x = 1062
        desk_top = [
            cam.world_to_device((desk_x, 508)),
            cam.world_to_device((desk_x + 58, 508)),
            cam.world_to_device((desk_x + 72, 524)),
            cam.world_to_device((desk_x + 14, 524)),
        ]
        desk_front = [
            cam.world_to_device((desk_x + 14, 524)),
            cam.world_to_device((desk_x + 72, 524)),
            cam.world_to_device((desk_x + 72, 592)),
            cam.world_to_device((desk_x + 14, 592)),
        ]
        desk_side = [
            cam.world_to_device((desk_x + 58, 508)),
            cam.world_to_device((desk_x + 72, 524)),
            cam.world_to_device((desk_x + 72, 592)),
            cam.world_to_device((desk_x + 58, 576)),
        ]
        desk_leg_left = [
            cam.world_to_device((desk_x + 18, 592)),
            cam.world_to_device((desk_x + 28, 592)),
            cam.world_to_device((desk_x + 28, 618)),
            cam.world_to_device((desk_x + 18, 618)),
        ]
        desk_leg_right = [
            cam.world_to_device((desk_x + 50, 592)),
            cam.world_to_device((desk_x + 60, 592)),
            cam.world_to_device((desk_x + 60, 618)),
            cam.world_to_device((desk_x + 50, 618)),
        ]

        # Textura aplicada também no tampo da mesa do professor.
        r.fill_polygon_textured(surface, desk_top, [(0.0, 0.0), (1.2, 0.0), (1.2, 1.0), (0.0, 1.0)], self.game.desk_texture)
        r.draw_polyline(surface, desk_top, INK)

        for poly, colors in (
            (desk_front, [(162, 104, 60), (186, 124, 72), (118, 72, 38), (128, 78, 42)]),
            (desk_side, [(148, 96, 52), (174, 116, 66), (110, 66, 34), (110, 66, 34)]),
        ):
            r.fill_polygon_gradient(surface, poly, colors)
            r.draw_polyline(surface, poly, INK)

        for poly in (desk_leg_left, desk_leg_right):
            r.fill_polygon_scanline(surface, poly, (120, 74, 38))
            r.draw_polyline(surface, poly, INK)

        draw_wastebasket(r, surface, cam.world_to_device((1212, 568)), rx=18, ry=7, body_height=48, body_bottom_half_width=12)

        return surface

    def draw(self, surface: pygame.Surface) -> None:
        """
        Desenha a cena principal a partir da janela atual.

        O recorte da região visível e o escalonamento para a tela concretizam o uso
        de janela/viewport no fluxo visual do jogo.
        """
        if self.background_cache is None:
            self.background_cache = self._render_background()

        win_x = max(0, min(int(round(self.camera.window[0])), self.background_cache.get_width() - 1))
        win_y = max(0, min(int(round(self.camera.window[1])), self.background_cache.get_height() - 1))
        win_w = max(1, int(round(self.camera.window[2])))
        win_h = max(1, int(round(self.camera.window[3])))
        if win_x + win_w > self.background_cache.get_width():
            win_x = self.background_cache.get_width() - win_w
        if win_y + win_h > self.background_cache.get_height():
            win_y = self.background_cache.get_height() - win_h

        view_rect = pygame.Rect(win_x, win_y, win_w, win_h)
        world_view = self.background_cache.subsurface(view_rect).copy()
        if world_view.get_width() != SCREEN_WIDTH or world_view.get_height() != SCREEN_HEIGHT:
            frame = pygame.transform.scale(world_view, (SCREEN_WIDTH, SCREEN_HEIGHT))
        else:
            frame = world_view
        r = self.game.rasterizer

        if self.state in {'LOOK_UP', 'WALK_OUT', 'RETURN'}:
            self._draw_teacher_rays(frame)

        self.teacher.draw(frame, r, self.camera, self.state, self.anim_clock)
        for student in self.students:
            student.draw(frame, r, self.camera)
        self._draw_minimap(frame)
        self._draw_hud(frame)

        if self.freeze:
            self._draw_overlay(frame)

        surface.blit(frame, (0, 0))

    def _draw_teacher_rays(self, surface: pygame.Surface) -> None:
        """Desenha os raios de visão do professor com clipping."""
        r = self.game.rasterizer
        tx, ty, _ = self.teacher.pose(self.state)
        origin = self.camera.world_to_device((tx - 4, ty - 66))
        classroom_rect = (40, 95, SCREEN_WIDTH - 40, SCREEN_HEIGHT - 40)
        for student in self.students:
            end = self.camera.world_to_device((student.x, student.y - 28))
            r.draw_clipped_line(surface, origin, end, classroom_rect, (185, 52, 45))

    def _draw_minimap(self, surface: pygame.Surface) -> None:
        """Viewport secundária (minimapa) desenhada a partir do mesmo mundo."""
        r = self.game.rasterizer
        panel = pygame.Rect(1002, 94, 248, 156)
        draw_panel(surface, r, panel, (24, 32, 50))
        title = self.game.font_s.render('MINIMAPA', False, SOFT_WHITE)
        surface.blit(title, (panel.x + 12, panel.y + 10))

        inner = pygame.Rect(panel.x + 12, panel.y + 34, panel.width - 24, panel.height - 46)
        self.minimap_camera.viewport = (inner.x, inner.y, inner.width, inner.height)

        room = [
            self.minimap_camera.world_to_device((0, 0)),
            self.minimap_camera.world_to_device((1500, 0)),
            self.minimap_camera.world_to_device((1500, 900)),
            self.minimap_camera.world_to_device((0, 900)),
        ]
        r.fill_polygon_scanline(surface, room, (213, 194, 160))
        r.draw_polyline(surface, room, INK)

        board = [
            self.minimap_camera.world_to_device((260, 135)),
            self.minimap_camera.world_to_device((970, 135)),
            self.minimap_camera.world_to_device((970, 360)),
            self.minimap_camera.world_to_device((260, 360)),
        ]
        r.fill_polygon_scanline(surface, board, BLACKBOARD)

        for seat in self.seats:
            poly = [
                self.minimap_camera.world_to_device((seat.x - 16, seat.y - 6)),
                self.minimap_camera.world_to_device((seat.x + seat.width - 12, seat.y - 6)),
                self.minimap_camera.world_to_device((seat.x + seat.width, seat.y + seat.depth)),
                self.minimap_camera.world_to_device((seat.x - 10, seat.y + seat.depth)),
            ]
            r.fill_polygon_scanline(surface, poly, ORANGE_WOOD)

        for student in self.students:
            cx, cy = self.minimap_camera.world_to_device((student.x, student.y - 28))
            color = PHONE_YELLOW if student.phone_visible else SOFT_WHITE
            dot = [(cx - 3, cy - 3), (cx + 3, cy - 3), (cx + 3, cy + 3), (cx - 3, cy + 3)]
            r.fill_polygon_scanline(surface, dot, color)
        tx, ty = self.minimap_camera.world_to_device((self.teacher.x, self.teacher.y - 32))
        teacher_dot = [(tx - 4, ty - 4), (tx + 4, ty - 4), (tx + 4, ty + 4), (tx - 4, ty + 4)]
        r.fill_polygon_scanline(surface, teacher_dot, DANGER if self.state != 'LOOK_DOWN' else AMBER)

        win_x, win_y, win_w, win_h = self.camera.window
        camera_rect = [
            self.minimap_camera.world_to_device((win_x, win_y)),
            self.minimap_camera.world_to_device((win_x + win_w, win_y)),
            self.minimap_camera.world_to_device((win_x + win_w, win_y + win_h)),
            self.minimap_camera.world_to_device((win_x, win_y + win_h)),
        ]
        r.draw_polyline(surface, camera_rect, (120, 212, 255))

    def _draw_hud(self, surface: pygame.Surface) -> None:
        """HUD com barras de tempo, risco e cola."""
        r = self.game.rasterizer
        top_bar = [(0, 0), (SCREEN_WIDTH, 0), (SCREEN_WIDTH, 78), (0, 78)]
        r.fill_polygon_scanline(surface, top_bar, NAVY)
        r.draw_line(surface, (0, 78), (SCREEN_WIDTH, 78), INK)
        self._draw_meter(surface, 20, 20, 180, 28, 'TEMPO', self.game_time / 52.0, SAFE, AMBER, DANGER)
        self._draw_meter(surface, 340, 20, 180, 28, 'RISCO', self.risk, SAFE, AMBER, DANGER)
        self._draw_meter(surface, 660, 20, 180, 28, 'COLA', self.score / EXAM_TARGET, SAFE, AMBER, PHONE_YELLOW)
        hint = self.game.font_s.render('ESPAÇO: celular | SETAS: câmera | ESC: menu', False, SOFT_WHITE)
        surface.blit(hint, (34, 682))

        status_panel = pygame.Rect(216, 622, 848, 52)
        draw_panel(surface, r, status_panel, (24, 31, 49))
        draw_wrapped_text(
            surface,
            self.game.font_s,
            self.message,
            pygame.Rect(status_panel.x + 18, status_panel.y + 12, status_panel.width - 36, 28),
            SOFT_WHITE if not self.freeze else (255, 238, 184),
            align='center',
            shadow=INK,
            line_gap=4,
        )

    def _draw_meter(self, surface: pygame.Surface, x: int, y: int, w: int, h: int, label: str, value: float, c1, c2, c3) -> None:
        """Desenha barras preenchidas com gradiente para representar o estado do jogo."""
        r = self.game.rasterizer
        value = max(0.0, min(1.0, value))
        label_surface = self.game.font_m.render(f'{label}:', False, SOFT_WHITE)
        surface.blit(label_surface, (x, y + 2))
        px = x + 96
        outline = [(px, y), (px + w, y), (px + w, y + h), (px, y + h)]
        r.fill_polygon_scanline(surface, outline, (12, 18, 28))
        r.draw_polyline(surface, outline, INK)
        fill_w = int((w - 6) * value)
        if fill_w > 0:
            bar = [(px + 3, y + 3), (px + 3 + fill_w, y + 3), (px + 3 + fill_w, y + h - 3), (px + 3, y + h - 3)]
            mid = tuple(int((a + b) * 0.5) for a, b in zip(c1, c2))
            r.fill_polygon_gradient(surface, bar, [c1, c2, c3, mid])

    def _draw_overlay(self, surface: pygame.Surface) -> None:
        """Painel final exibido quando a prova termina ou o tempo acaba."""
        r = self.game.rasterizer
        panel = pygame.Rect(250, 188, 780, 250)
        draw_panel(surface, r, panel, (26, 34, 56))
        title = 'PESCA CONCLUÍDA!' if self.success else 'TEMPO ACABOU!'
        title_color = SAFE if self.success else DANGER
        blit_centered(surface, self.game.font_xl, title, panel.y + 20, title_color, INK)

        draw_wrapped_text(
            surface,
            self.game.font_m,
            self.message,
            pygame.Rect(panel.x + 46, panel.y + 112, panel.width - 92, 56),
            SOFT_WHITE,
            align='center',
            shadow=INK,
            line_gap=8,
        )


class GameOverScene(Scene):
    """Cena de game over, também construída com polígonos rasterizados."""
    def __init__(self, game: 'Try2CheatGame', score: float) -> None:
        super().__init__(game)
        self.score = score
        self.button = Button(pygame.Rect(450, 610, 380, 76), 'REINICIAR')
        self.hovered = False
        self.cached_surface: pygame.Surface | None = None

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.button.contains(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.button.contains(event.pos):
                self.game.start_new_match()
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_r, pygame.K_SPACE):
            self.game.start_new_match()

    def update(self, dt: float) -> None:
        _ = dt

    def _render_static(self) -> pygame.Surface:
        """
        Monta a tela de abertura estática.

        Nesta cena aparecem os requisitos de rasterização manual na abertura:
        linhas, círculos, elipse (na lixeira) e flood fill. Também há polígonos
        preenchidos por scanline/gradiente e textura nas carteiras.
        """
        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        r = self.game.rasterizer
        surface.fill(WALL_COLOR)
        wall = [(0, 0), (SCREEN_WIDTH, 0), (SCREEN_WIDTH, 520), (0, 520)]
        floor = [(0, 520), (SCREEN_WIDTH, 520), (SCREEN_WIDTH, SCREEN_HEIGHT), (0, SCREEN_HEIGHT)]
        r.fill_polygon_gradient(surface, wall, [(244, 225, 186), (244, 225, 186), (222, 197, 156), (222, 197, 156)])
        r.fill_polygon_scanline(surface, floor, (150, 96, 58))

        board = [(120, 152), (1160, 152), (1160, 352), (120, 352)]
        r.fill_polygon_scanline(surface, board, BLACKBOARD)
        r.draw_polyline(surface, board, BLACKBOARD_BORDER)

        panel = pygame.Rect(246, 92, 788, 132)
        draw_panel(surface, r, panel, (46, 52, 70))
        blit_centered(surface, self.game.font_xl, 'VOCÊ FOI PEGO!', 116, (255, 231, 93), INK)

        tri = [(618, 300), (674, 400), (562, 400)]
        r.fill_polygon_gradient(surface, tri, [(255, 214, 96), (252, 170, 66), (230, 118, 44)])
        r.draw_polyline(surface, tri, INK)
        ex = self.game.font_l.render('!', False, INK)
        surface.blit(ex, (611, 318))

        student = [(650, 390), (686, 390), (698, 486), (656, 486)]
        r.fill_polygon_scanline(surface, student, (18, 20, 24))
        head = [(648, 348), (690, 348), (700, 388), (648, 388)]
        hair = [(650, 336), (664, 322), (686, 322), (700, 338), (694, 362), (652, 362)]
        r.fill_polygon_scanline(surface, head, (18, 20, 24))
        r.fill_polygon_scanline(surface, hair, (18, 20, 24))
        for eye in (((658, 362), (668, 362), (668, 370), (658, 370)), ((680, 362), (690, 362), (690, 370), (680, 370))):
            r.fill_polygon_scanline(surface, list(eye), SOFT_WHITE)
        mouth = [(670, 378), (680, 378), (680, 386), (670, 386)]
        r.fill_polygon_scanline(surface, mouth, (235, 110, 96))
        phone = [(706, 396), (728, 396), (728, 434), (706, 434)]
        r.fill_polygon_scanline(surface, phone, PHONE_YELLOW)
        r.draw_polyline(surface, phone, INK)

        chair = [(696, 488), (752, 488), (742, 530), (688, 530)]
        r.fill_polygon_gradient(surface, chair, [ORANGE_WOOD, (218, 128, 60), (112, 58, 22), (112, 58, 22)])
        r.draw_polyline(surface, chair, INK)

        torso = [(386, 366), (430, 366), (442, 496), (392, 496)]
        leg_a = [(392, 496), (416, 496), (418, 592), (386, 592)]
        leg_b = [(420, 496), (444, 496), (458, 592), (426, 592)]
        arm = [(432, 394), (494, 396), (586, 420), (578, 440), (488, 426), (430, 422)]
        head_t = [(398, 312), (442, 312), (452, 360), (398, 360)]
        hair_t = [(398, 306), (412, 292), (436, 290), (452, 306), (446, 326), (400, 326)]
        for poly in (torso, leg_a, leg_b, arm):
            r.fill_polygon_scanline(surface, poly, (26, 28, 34))
        r.fill_polygon_scanline(surface, head_t, (245, 217, 190))
        r.fill_polygon_scanline(surface, hair_t, (84, 40, 18))
        finger = [(578, 422), (622, 418), (624, 430), (578, 434)]
        r.fill_polygon_scanline(surface, finger, (245, 217, 190))
        r.draw_polyline(surface, finger, INK)

        info_panel = pygame.Rect(286, 536, 708, 64)
        draw_panel(surface, r, info_panel, (28, 36, 58))
        draw_wrapped_text(
            surface,
            self.game.font_m,
            f'Progresso antes de ser pego: {int(self.score)}%. Pressione o botão abaixo para tentar novamente.',
            pygame.Rect(info_panel.x + 20, info_panel.y + 14, info_panel.width - 40, 40),
            SOFT_WHITE,
            align='center',
            shadow=INK,
            line_gap=6,
        )
        return surface

    def draw(self, surface: pygame.Surface) -> None:
        if self.cached_surface is None:
            self.cached_surface = self._render_static()
        surface.blit(self.cached_surface, (0, 0))
        self.button.draw(surface, self.game.rasterizer, self.game.font_l, self.hovered)


class Try2CheatGame:
    """Controlador principal do jogo, responsável por assets, fontes e loop."""
    def __init__(self, screen: pygame.Surface) -> None:
        """Inicializa rasterizador, fontes, textura e cena inicial."""
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.rasterizer = Rasterizer()
        self.base_path = Path(__file__).resolve().parent

        self.font_s = pygame.font.SysFont('consolas', 20, bold=True)
        self.font_m = pygame.font.SysFont('consolas', 26, bold=True)
        self.font_l = pygame.font.SysFont('consolas', 38, bold=True)
        self.font_xl = pygame.font.SysFont('consolas', 62, bold=True)
        # A textura é carregada como imagem para ser usada no mapeamento UV das mesas.
        self.desk_texture = pygame.image.load(str(self.base_path / 'assets/desk_texture.png')).convert()
        self.scene: Scene = MenuScene(self)
        self.running = True

    def set_scene(self, scene: Scene) -> None:
        self.scene = scene

    def start_new_match(self) -> None:
        self.scene = GameScene(self)

    def run(self) -> None:
        """Loop principal do pygame: eventos, atualização, desenho e flip da tela."""
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.scene.handle_event(event)
            self.scene.update(dt)
            self.scene.draw(self.screen)
            pygame.display.flip()