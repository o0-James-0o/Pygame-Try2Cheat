"""
Entidades poligonais do projeto.

As classes deste módulo representam os personagens e o mobiliário da sala.
Elas usam apenas polígonos, scanline, gradiente, textura e transformações 2D.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sin
from typing import List, Sequence, Tuple

import pygame

from algorithms import Rasterizer, Transform2D, WindowViewport, regular_polygon
from settings import (
    INK,
    NOTEBOOK,
    ORANGE_WOOD,
    ORANGE_WOOD_DARK,
    PHONE_YELLOW,
    PLAYER_INDEX,
    SOFT_WHITE,
    STUDENT_BLACK,
    STUDENT_HIGHLIGHT,
    TEACHER_HAIR,
    TEACHER_SKIN,
)

Point = Tuple[float, float]
Color = Tuple[int, int, int]


def map_points(camera: WindowViewport, points: Sequence[Point]) -> List[Tuple[int, int]]:
    """Atalho para mapear vários pontos do mundo para a viewport atual."""
    return [camera.world_to_device(point) for point in points]


@dataclass
class Student:
    """
    Construção do aluno por polígonos.

    A animação do braço/celular usa rotação, enquanto o posicionamento geral usa
    translação e escala.
    """
    x: float
    y: float
    index: int
    scale: float = 1.0
    phone_anim: float = 0.0
    target_phone: float = 0.0

    @property
    def is_player(self) -> bool:
        return self.index == PLAYER_INDEX

    @property
    def phone_visible(self) -> bool:
        return self.phone_anim > 0.55

    def toggle_phone(self) -> None:
        """Alterna a meta da animação do celular do jogador."""
        self.target_phone = 0.0 if self.target_phone > 0.5 else 1.0

    def force_hide(self) -> None:
        self.target_phone = 0.0

    def update(self, dt: float) -> None:
        """Atualiza a interpolação da animação do celular."""
        speed = 3.5
        if self.phone_anim < self.target_phone:
            self.phone_anim = min(self.target_phone, self.phone_anim + dt * speed)
        elif self.phone_anim > self.target_phone:
            self.phone_anim = max(self.target_phone, self.phone_anim - dt * speed)

    def draw(self, surface: pygame.Surface, rasterizer: Rasterizer, camera: WindowViewport) -> None:
        """
        Desenha o aluno em coordenadas de mundo usando polígonos e scanline.

        Nesta rotina aparecem explicitamente: translação, escala e rotação do braço
        em torno do ombro, além do gradiente da seta indicadora do jogador.
        """
        scale = Transform2D.scale(self.scale, self.scale)
        translate = Transform2D.translation(self.x, self.y)
        base = Transform2D.multiply(translate, scale)

        # cabeça
        head_center = (0, -40 - self.phone_anim * 2.0)
        head_points = regular_polygon(head_center, 10.5, 12, rotation_deg=-90)

        # pescoço e tronco
        neck = [(-1.5, -29), (1.5, -29), (1.5, -21), (-1.5, -21)]
        torso = [(-2.5, -21), (2.5, -21), (2.5, -6), (-2.5, -6)]

        # pernas sentadas em estilo stick simples
        thigh_front = [(-1, -5), (11, 4), (9, 8), (-3, 0)]
        shin_front = [(9, 6), (13, 4), (30, 24), (26, 26)]

        thigh_back = [(-3, -4), (5, 4), (3, 8), (-5, 0)]
        shin_back = [(2, 7), (6, 5), (18, 22), (14, 24)]

        # braço esquerdo apoiado na mesa
        arm_left = [(-1, -18), (15, -18), (15, -14), (-1, -14)]

        # braço direito que anima com o celular
        shoulder = (1, -17)
        arm_right = [(0, -19), (14, -19), (14, -15), (0, -15)]
        arm_angle = 18 - self.phone_anim * 92
        arm_matrix = Transform2D.around(Transform2D.rotation(arm_angle), shoulder)
        arm_world = Transform2D.apply_many(Transform2D.multiply(base, arm_matrix), arm_right)

        phone = [(14, -26), (20, -26), (20, -14), (14, -14)]
        phone_world = Transform2D.apply_many(Transform2D.multiply(base, arm_matrix), phone)

        # desenha corpo stick
        for part in (neck, torso, thigh_front, shin_front, thigh_back, shin_back, arm_left):
            rasterizer.fill_polygon_scanline(
                surface,
                map_points(camera, Transform2D.apply_many(base, part)),
                STUDENT_BLACK,
            )

        rasterizer.fill_polygon_scanline(surface, map_points(camera, arm_world), STUDENT_BLACK)

        # cabeça
        rasterizer.fill_polygon_scanline(
            surface,
            map_points(camera, Transform2D.apply_many(base, head_points)),
            TEACHER_SKIN,
        )
        rasterizer.draw_polyline(
            surface,
            map_points(camera, Transform2D.apply_many(base, head_points)),
            INK,
        )

        # olhos simples
        left_eye = [(-4, -42), (-2, -42), (-2, -39), (-4, -39)]
        right_eye = [(2, -42), (4, -42), (4, -39), (2, -39)]
        rasterizer.fill_polygon_scanline(surface, map_points(camera, Transform2D.apply_many(base, left_eye)), INK)
        rasterizer.fill_polygon_scanline(surface, map_points(camera, Transform2D.apply_many(base, right_eye)), INK)

        # celular
        if self.phone_anim > 0.05:
            color = PHONE_YELLOW if self.is_player else (210, 210, 90)
            rasterizer.fill_polygon_scanline(surface, map_points(camera, phone_world), color)
            rasterizer.draw_polyline(surface, map_points(camera, phone_world), INK)

        # indicador do jogador
        if self.is_player:
            arrow = [(-14, -84), (14, -84), (0, -54 - self.phone_anim * 0.4)]
            rasterizer.fill_polygon_gradient(
                surface,
                [camera.world_to_device(pt) for pt in Transform2D.apply_many(base, arrow)],
                [(196, 44, 40), (255, 112, 90), (196, 44, 40)],
            )


@dataclass
class Teacher:
    """
    Professor ingame, modelo por polígonos.

    O professor alterna entre estados de observação e caminhada; sua cabeça é
    rotacionada para reforçar a direção do olhar e o notebook aparece apenas no
    estado em que ele olha para a mesa.
    """
    x: float = 1125.0
    y: float = 510.0
    walk_progress: float = 0.0

    def pose(self, state: str) -> Tuple[float, float, float]:
        """Retorna posição e ângulo da cabeça de acordo com as possibilidades abaixo."""
        if state == 'LOOK_DOWN':
            return self.x, self.y, 16.0
        if state == 'LOOK_UP':
            return self.x, self.y, -6.0
        if state == 'WALK_OUT':
            return self.x, 600, 0.0
        if state == 'RETURN':
            return self.x, 600, 4.0
        return self.x, self.y, 10.0

    def draw(self, surface: pygame.Surface, rasterizer: Rasterizer, camera: WindowViewport, state: str, anim_time: float) -> None:
        """Desenha o professor e sua animação de caminhada em polígonos."""
        tx, ty, head_angle = self.pose(state)
        base = Transform2D.translation(tx, ty)

        torso = [(-18, -48), (12, -48), (16, 2), (-22, 2)]
        hip_y = 2
        stride = 8.0 * sin(anim_time * 6.0) if 'WALK' in state or state == 'RETURN' else 0.0
        leg_left = [(-15, hip_y), (-6, hip_y), (-4 + stride * 0.15, 36), (-14 + stride * 0.15, 36)]
        leg_right = [(0, hip_y), (10, hip_y), (12 - stride * 0.15, 36), (2 - stride * 0.15, 36)]
        arm_left = [(-24, -40), (-15, -40), (-10, -4), (-18, -4)]
        arm_right = [(10, -42), (18, -42), (16, -6), (8, -6)]
        neck = (0, -52)
        head = regular_polygon((0, -66), 14, 12, rotation_deg=-90)
        hair = [(-13, -72), (-6, -82), (5, -84), (14, -74), (8, -64), (-6, -64)]

        head_matrix = Transform2D.around(Transform2D.rotation(head_angle), neck)
        head_world = Transform2D.apply_many(Transform2D.multiply(base, head_matrix), head)
        hair_world = Transform2D.apply_many(Transform2D.multiply(base, head_matrix), hair)

        for part in (torso, leg_left, leg_right, arm_left, arm_right):
            rasterizer.fill_polygon_scanline(surface, map_points(camera, Transform2D.apply_many(base, part)), (22, 24, 30))

        rasterizer.fill_polygon_scanline(surface, map_points(camera, head_world), TEACHER_SKIN)
        rasterizer.fill_polygon_scanline(surface, map_points(camera, hair_world), TEACHER_HAIR)
        rasterizer.draw_polyline(surface, map_points(camera, head_world), INK)
        rasterizer.draw_polyline(surface, map_points(camera, hair_world), INK)

        if state == 'LOOK_DOWN':
            eye_dx, eye_dy = -4.0, 3.0
        elif state == 'LOOK_UP':
            eye_dx, eye_dy = -2.0, -1.0
        else:
            eye_dx, eye_dy = -1.0, 0.0

        pupil = [(-8 + eye_dx, -68 + eye_dy), (-4 + eye_dx, -68 + eye_dy), (-4 + eye_dx, -65 + eye_dy), (-8 + eye_dx, -65 + eye_dy)]
        other = [(0 + eye_dx, -68 + eye_dy), (4 + eye_dx, -68 + eye_dy), (4 + eye_dx, -65 + eye_dy), (0 + eye_dx, -65 + eye_dy)]
        rasterizer.fill_polygon_scanline(surface, map_points(camera, Transform2D.apply_many(Transform2D.multiply(base, head_matrix), pupil)), INK)
        rasterizer.fill_polygon_scanline(surface, map_points(camera, Transform2D.apply_many(Transform2D.multiply(base, head_matrix), other)), INK)

        if state == 'LOOK_DOWN':
            # Notebook.
            notebook_base = [(-74, -50), (-49, -50), (-46, -40), (-77, -40)]
            notebook_screen = [(-73, -50), (-50, -50), (-50, -100), (-73, -100)]
            notebook_screen_inner = [(-70, -54), (-53, -54), (-53, -94), (-70, -94)]

            rasterizer.fill_polygon_gradient(
                surface,
                [camera.world_to_device(pt) for pt in Transform2D.apply_many(base, notebook_screen)],
                [(126, 144, 176), (164, 184, 214), (74, 90, 120), (90, 108, 138)],
            )
            rasterizer.draw_polyline(surface, map_points(camera, Transform2D.apply_many(base, notebook_screen)), INK)

            rasterizer.fill_polygon_gradient(
                surface,
                [camera.world_to_device(pt) for pt in Transform2D.apply_many(base, notebook_screen_inner)],
                [(56, 66, 86), (82, 98, 126), (34, 40, 56), (42, 50, 66)],
            )
            rasterizer.draw_polyline(surface, map_points(camera, Transform2D.apply_many(base, notebook_screen_inner)), INK)

            rasterizer.fill_polygon_gradient(
                surface,
                [camera.world_to_device(pt) for pt in Transform2D.apply_many(base, notebook_base)],
                [NOTEBOOK, (155, 178, 212), (82, 102, 136), NOTEBOOK],
            )
            rasterizer.draw_polyline(surface, map_points(camera, Transform2D.apply_many(base, notebook_base)), INK)
            rasterizer.draw_line(
                surface,
                camera.world_to_device(Transform2D.apply(base, (-74, -50))),
                camera.world_to_device(Transform2D.apply(base, (-49, -50))),
                INK,
            )


@dataclass
class ClassroomSeat:
    """
    Carteira da sala de aula.

    O tampo é utilizado a textura, demonstrando uso de
    scanline e mapeamento de textura em um polígono do cenário.
    """
    x: float
    y: float
    width: float = 56.0
    depth: float = 14.0

    def draw(
        self,
        surface: pygame.Surface,
        rasterizer: Rasterizer,
        camera: WindowViewport,
        desk_texture: pygame.Surface | None = None,
    ) -> None:
        """Desenha a carteira com pernas, cadeira e tampo texturizado."""
        desk = [
            (self.x - 16, self.y - 6),
            (self.x + self.width - 12, self.y - 6),
            (self.x + self.width, self.y + self.depth),
            (self.x - 10, self.y + self.depth),
        ]
        desk_points = [camera.world_to_device(point) for point in desk]
        if desk_texture is not None:
            rasterizer.fill_polygon_textured(
                surface,
                desk_points,
                [(0.0, 0.0), (1.2, 0.0), (1.2, 1.0), (0.0, 1.0)],
                desk_texture,
            )
        else:
            rasterizer.fill_polygon_gradient(
                surface,
                desk_points,
                [
                    (184, 116, 62),
                    (208, 136, 76),
                    (138, 82, 38),
                    (148, 88, 44),
                ],
            )
        rasterizer.draw_polyline(surface, map_points(camera, desk), INK)

        front = [
            (self.x - 10, self.y + self.depth),
            (self.x + self.width, self.y + self.depth),
            (self.x + self.width - 2, self.y + self.depth + 8),
            (self.x - 9, self.y + self.depth + 8),
        ]
        rasterizer.fill_polygon_gradient(
            surface,
            [camera.world_to_device(point) for point in front],
            [ORANGE_WOOD_DARK, ORANGE_WOOD, (110, 58, 22), (110, 58, 22)],
        )
        rasterizer.draw_polyline(surface, map_points(camera, front), INK)

        for dx in (-2, self.width - 2):
            leg = [
                (self.x + dx, self.y + self.depth + 8),
                (self.x + dx + 4, self.y + self.depth + 8),
                (self.x + dx + 2, self.y + 36),
                (self.x + dx - 2, self.y + 36),
            ]
            rasterizer.fill_polygon_scanline(surface, map_points(camera, leg), (70, 62, 70))
            rasterizer.draw_polyline(surface, map_points(camera, leg), INK)

        chair_seat = [
            (self.x - 30, self.y + 6),
            (self.x - 12, self.y + 6),
            (self.x - 8, self.y + 16),
            (self.x - 26, self.y + 16),
        ]
        chair_back = [
            (self.x - 32, self.y - 8),
            (self.x - 24, self.y - 8),
            (self.x - 21, self.y + 8),
            (self.x - 29, self.y + 8),
        ]
        for part in (chair_seat, chair_back):
            rasterizer.fill_polygon_gradient(
                surface,
                [camera.world_to_device(point) for point in part],
                [ORANGE_WOOD, (220, 132, 58), ORANGE_WOOD_DARK, ORANGE_WOOD_DARK],
            )
            rasterizer.draw_polyline(surface, map_points(camera, part), INK)