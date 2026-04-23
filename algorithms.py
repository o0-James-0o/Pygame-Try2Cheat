"""
Módulo de algoritmos gráficos do projeto.

Este arquivo concentra os requisitos centrais do trabalho:

-set pixel manual com surface.set_at
-rasterização de linha, círculo e elipse
-preenchimento por Flood Fill e Scanline
-transformações geométricas 2D
-janela e viewport
-recorte de Cohen-Sutherland
-mapeamento de textura em polígonos

"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, cos, floor, radians, sin
from typing import Iterable, List, Sequence, Tuple

import pygame

Color = Tuple[int, int, int]
Point = Tuple[float, float]
Vertex = Tuple[float, float]
ColorVertex = Tuple[float, float, Color]
UV = Tuple[float, float]


@dataclass
class WindowViewport:
    """
    Representa a transformação de janela do mundo para viewport em dispositivo.

    Este componente atende o requisito de janela/viewport, permitindo:
    - conversão mundo -> dispositivo
    - conversão dispositivo -> mundo
    - descolamento da janela
    - zoom da janela
    """
    world_bounds: Tuple[float, float, float, float]
    window: List[float]
    viewport: Tuple[int, int, int, int]

    def world_to_device(self, point: Point) -> Tuple[int, int]:
        """Mapeia um ponto do espaço de mundo para coordenadas de tela."""
        wx, wy = point
        win_x, win_y, win_w, win_h = self.window
        vp_x, vp_y, vp_w, vp_h = self.viewport

        ndc_x = (wx - win_x) / win_w
        ndc_y = (wy - win_y) / win_h
        dx = vp_x + ndc_x * vp_w
        dy = vp_y + ndc_y * vp_h
        return int(round(dx)), int(round(dy))

    def device_to_world(self, point: Tuple[int, int]) -> Point:
        """Mapeia um ponto da tela de volta para o espaço de mundo."""
        dx, dy = point
        win_x, win_y, win_w, win_h = self.window
        vp_x, vp_y, vp_w, vp_h = self.viewport
        ndc_x = (dx - vp_x) / vp_w
        ndc_y = (dy - vp_y) / vp_h
        return win_x + ndc_x * win_w, win_y + ndc_y * win_h

    def map_points(self, points: Sequence[Point]) -> List[Tuple[int, int]]:
        return [self.world_to_device(point) for point in points]

    def pan(self, dx: float, dy: float) -> None:
        """Translada a janela de visualização no mundo."""
        self.window[0] += dx
        self.window[1] += dy
        self._clamp_window()

    def zoom(self, factor: float, center: Point | None = None) -> None:
        """Aplica escala (zoom) à janela mantendo um ponto de foco."""
        if factor <= 0:
            return
        if center is None:
            center = (
                self.window[0] + self.window[2] * 0.5,
                self.window[1] + self.window[3] * 0.5,
            )
        cx, cy = center
        new_w = self.window[2] / factor
        new_h = self.window[3] / factor
        new_w = max(420.0, min(self.world_bounds[2], new_w))
        new_h = max(236.0, min(self.world_bounds[3], new_h))
        rel_x = (cx - self.window[0]) / self.window[2]
        rel_y = (cy - self.window[1]) / self.window[3]
        self.window[0] = cx - rel_x * new_w
        self.window[1] = cy - rel_y * new_h
        self.window[2] = new_w
        self.window[3] = new_h
        self._clamp_window()

    def _clamp_window(self) -> None:
        min_x, min_y, max_w, max_h = self.world_bounds
        self.window[2] = min(max_w, self.window[2])
        self.window[3] = min(max_h, self.window[3])
        self.window[0] = max(min_x, min(self.window[0], min_x + max_w - self.window[2]))
        self.window[1] = max(min_y, min(self.window[1], min_y + max_h - self.window[3]))

    @property
    def key(self) -> Tuple[int, int, int, int]:
        return tuple(int(round(v)) for v in self.window)


class Transform2D:
    """
    Utilitário de matrizes 3x3 para transformações geométricas 2D.

    Estando presente a translação, escala e rotação usado nos personagens e
    objetos poligonais da cena.
    """
    @staticmethod
    def identity() -> List[List[float]]:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

    @staticmethod
    def translation(tx: float, ty: float) -> List[List[float]]:
        return [[1.0, 0.0, tx], [0.0, 1.0, ty], [0.0, 0.0, 1.0]]

    @staticmethod
    def scale(sx: float, sy: float) -> List[List[float]]:
        return [[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]]

    @staticmethod
    def rotation(angle_deg: float) -> List[List[float]]:
        angle = radians(angle_deg)
        c = cos(angle)
        s = sin(angle)
        return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]

    @staticmethod
    def multiply(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
        result = [[0.0 for _ in range(3)] for _ in range(3)]
        for row in range(3):
            for col in range(3):
                result[row][col] = sum(a[row][k] * b[k][col] for k in range(3))
        return result

    @staticmethod
    def around(matrix: List[List[float]], pivot: Point) -> List[List[float]]:
        px, py = pivot
        return Transform2D.multiply(
            Transform2D.translation(px, py),
            Transform2D.multiply(matrix, Transform2D.translation(-px, -py)),
        )

    @staticmethod
    def apply(matrix: List[List[float]], point: Point) -> Point:
        x, y = point
        return (
            matrix[0][0] * x + matrix[0][1] * y + matrix[0][2],
            matrix[1][0] * x + matrix[1][1] * y + matrix[1][2],
        )

    @staticmethod
    def apply_many(matrix: List[List[float]], points: Sequence[Point]) -> List[Point]:
        return [Transform2D.apply(matrix, point) for point in points]


class CohenSutherlandClipper:
    """Implementação do recorte de reta por Cohen-Sutherland."""
    INSIDE = 0
    LEFT = 1
    RIGHT = 2
    BOTTOM = 4
    TOP = 8

    @staticmethod
    def _code(x: float, y: float, rect: Tuple[int, int, int, int]) -> int:
        xmin, ymin, xmax, ymax = rect
        code = CohenSutherlandClipper.INSIDE
        if x < xmin:
            code |= CohenSutherlandClipper.LEFT
        elif x > xmax:
            code |= CohenSutherlandClipper.RIGHT
        if y < ymin:
            code |= CohenSutherlandClipper.TOP
        elif y > ymax:
            code |= CohenSutherlandClipper.BOTTOM
        return code

    @staticmethod
    def clip_line(
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        rect: Tuple[int, int, int, int],
    ) -> Tuple[int, int, int, int] | None:
        xmin, ymin, xmax, ymax = rect
        code1 = CohenSutherlandClipper._code(x1, y1, rect)
        code2 = CohenSutherlandClipper._code(x2, y2, rect)

        while True:
            if not (code1 | code2):
                return int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))
            if code1 & code2:
                return None
            code_out = code1 or code2
            if code_out & CohenSutherlandClipper.TOP:
                x = x1 + (x2 - x1) * (ymin - y1) / (y2 - y1)
                y = ymin
            elif code_out & CohenSutherlandClipper.BOTTOM:
                x = x1 + (x2 - x1) * (ymax - y1) / (y2 - y1)
                y = ymax
            elif code_out & CohenSutherlandClipper.RIGHT:
                y = y1 + (y2 - y1) * (xmax - x1) / (x2 - x1)
                x = xmax
            else:
                y = y1 + (y2 - y1) * (xmin - x1) / (x2 - x1)
                x = xmin

            if code_out == code1:
                x1, y1 = x, y
                code1 = CohenSutherlandClipper._code(x1, y1, rect)
            else:
                x2, y2 = x, y
                code2 = CohenSutherlandClipper._code(x2, y2, rect)


class Rasterizer:
    """
    Motor de rasterização manual do projeto.

    Reúne as primitivas e preenchimentos: set pixel,
    linhas, círculos, elipses, flood fill, scanline, gradiente e textura.
    """
    def __init__(self) -> None:
        pass

    @staticmethod
    def clamp_color(color: Sequence[float]) -> Color:
        return tuple(max(0, min(255, int(round(channel)))) for channel in color[:3])  # type: ignore[return-value]

    @staticmethod
    def lerp(a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    def set_pixel(self, surface: pygame.Surface, x: int, y: int, color: Color) -> None:
        """Escreve manualmente um pixel na superfície."""
        if 0 <= x < surface.get_width() and 0 <= y < surface.get_height():
            surface.set_at((int(x), int(y)), color)

    def get_pixel(self, surface: pygame.Surface, x: int, y: int) -> Color:
        return surface.get_at((int(x), int(y)))[:3]

    def draw_line(self, surface: pygame.Surface, p1: Tuple[int, int], p2: Tuple[int, int], color: Color) -> None:
        """Rasterização de reta com variação do algoritmo de Bresenham."""
        x1, y1 = p1
        x2, y2 = p2
        dx = abs(x2 - x1)
        dy = -abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx + dy
        while True:
            self.set_pixel(surface, x1, y1, color)
            if x1 == x2 and y1 == y2:
                break
            e2 = err * 2
            if e2 >= dy:
                err += dy
                x1 += sx
            if e2 <= dx:
                err += dx
                y1 += sy

    def draw_polyline(self, surface: pygame.Surface, points: Sequence[Tuple[int, int]], color: Color, closed: bool = True) -> None:
        if len(points) < 2:
            return
        for index in range(len(points) - 1):
            self.draw_line(surface, points[index], points[index + 1], color)
        if closed:
            self.draw_line(surface, points[-1], points[0], color)

    def draw_circle(self, surface: pygame.Surface, center: Tuple[int, int], radius: int, color: Color) -> None:
        """Rasterização manual de circunferência."""
        cx, cy = center
        x = 0
        y = radius
        decision = 1 - radius
        self._plot_circle_points(surface, cx, cy, x, y, color)
        while x < y:
            x += 1
            if decision < 0:
                decision += 2 * x + 1
            else:
                y -= 1
                decision += 2 * (x - y) + 1
            self._plot_circle_points(surface, cx, cy, x, y, color)

    def _plot_circle_points(self, surface: pygame.Surface, cx: int, cy: int, x: int, y: int, color: Color) -> None:
        points = [
            (cx + x, cy + y),
            (cx - x, cy + y),
            (cx + x, cy - y),
            (cx - x, cy - y),
            (cx + y, cy + x),
            (cx - y, cy + x),
            (cx + y, cy - x),
            (cx - y, cy - x),
        ]
        for px, py in points:
            self.set_pixel(surface, px, py, color)

    def draw_ellipse(self, surface: pygame.Surface, center: Tuple[int, int], rx: int, ry: int, color: Color) -> None:
        """Rasterização manual de elipse pelo método do ponto médio."""
        cx, cy = center
        x = 0
        y = ry
        rx_sq = rx * rx
        ry_sq = ry * ry
        dx = 2 * ry_sq * x
        dy = 2 * rx_sq * y
        decision1 = ry_sq - rx_sq * ry + 0.25 * rx_sq
        while dx < dy:
            self._plot_ellipse_points(surface, cx, cy, x, y, color)
            if decision1 < 0:
                x += 1
                dx = 2 * ry_sq * x
                decision1 += dx + ry_sq
            else:
                x += 1
                y -= 1
                dx = 2 * ry_sq * x
                dy = 2 * rx_sq * y
                decision1 += dx - dy + ry_sq
        decision2 = (
            ry_sq * (x + 0.5) * (x + 0.5)
            + rx_sq * (y - 1) * (y - 1)
            - rx_sq * ry_sq
        )
        while y >= 0:
            self._plot_ellipse_points(surface, cx, cy, x, y, color)
            if decision2 > 0:
                y -= 1
                dy = 2 * rx_sq * y
                decision2 += rx_sq - dy
            else:
                y -= 1
                x += 1
                dx = 2 * ry_sq * x
                dy = 2 * rx_sq * y
                decision2 += dx - dy + rx_sq

    def _plot_ellipse_points(self, surface: pygame.Surface, cx: int, cy: int, x: int, y: int, color: Color) -> None:
        points = [
            (cx + x, cy + y),
            (cx - x, cy + y),
            (cx + x, cy - y),
            (cx - x, cy - y),
        ]
        for px, py in points:
            self.set_pixel(surface, px, py, color)

    def flood_fill(self, surface: pygame.Surface, seed: Tuple[int, int], fill_color: Color) -> None:
        """Preenchimento de região por Flood Fill."""
        sx, sy = seed
        if not (0 <= sx < surface.get_width() and 0 <= sy < surface.get_height()):
            return
        target_color = self.get_pixel(surface, sx, sy)
        if target_color == fill_color:
            return
        stack = [(sx, sy)]
        while stack:
            x, y = stack.pop()
            if not (0 <= x < surface.get_width() and 0 <= y < surface.get_height()):
                continue
            if self.get_pixel(surface, x, y) != target_color:
                continue
            self.set_pixel(surface, x, y, fill_color)
            stack.append((x + 1, y))
            stack.append((x - 1, y))
            stack.append((x, y + 1))
            stack.append((x, y - 1))

    def fill_polygon_scanline(self, surface: pygame.Surface, vertices: Sequence[Tuple[int, int]], color: Color) -> None:
        """Preenchimento de polígonos por scanline."""
        if len(vertices) < 3:
            return
        min_y = max(0, min(y for _, y in vertices))
        max_y = min(surface.get_height() - 1, max(y for _, y in vertices))
        edges = list(zip(vertices, vertices[1:] + vertices[:1]))
        for y in range(min_y, max_y + 1):
            intersections: List[float] = []
            for (x1, y1), (x2, y2) in edges:
                if y1 == y2:
                    continue
                if y >= min(y1, y2) and y < max(y1, y2):
                    x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                    intersections.append(x)
            intersections.sort()
            for idx in range(0, len(intersections), 2):
                if idx + 1 >= len(intersections):
                    break
                x_start = int(ceil(intersections[idx]))
                x_end = int(floor(intersections[idx + 1]))
                for x in range(x_start, x_end + 1):
                    self.set_pixel(surface, x, y, color)

    def fill_polygon_gradient(
        self,
        surface: pygame.Surface,
        vertices: Sequence[Point],
        colors: Sequence[Color],
    ) -> None:
        """Preenchimento de polígonos com gradiente por vértice."""
        if len(vertices) < 3 or len(vertices) != len(colors):
            return
        for index in range(1, len(vertices) - 1):
            self.fill_triangle_scanline(
                surface,
                [vertices[0], vertices[index], vertices[index + 1]],
                [colors[0], colors[index], colors[index + 1]],
            )

    def fill_polygon_textured(
        self,
        surface: pygame.Surface,
        vertices: Sequence[Point],
        uvs: Sequence[UV],
        texture: pygame.Surface,
    ) -> None:
        """Preenche um polígono usando mapeamento de textura."""
        if len(vertices) < 3 or len(vertices) != len(uvs):
            return
        for index in range(1, len(vertices) - 1):
            self.fill_triangle_scanline(
                surface,
                [vertices[0], vertices[index], vertices[index + 1]],
                None,
                [uvs[0], uvs[index], uvs[index + 1]],
                texture,
            )

    def fill_triangle_scanline(
        self,
        surface: pygame.Surface,
        vertices: Sequence[Point],
        colors: Sequence[Color] | None = None,
        uvs: Sequence[UV] | None = None,
        texture: pygame.Surface | None = None,
    ) -> None:
        """
        Rotina base de scanline para triângulos.

        Ela é reutilizada tanto para interpolar gradiente de cor quanto para
        interpolar coordenadas de textura (UV).
        """
        if len(vertices) != 3:
            return
        min_y = max(0, int(floor(min(v[1] for v in vertices))))
        max_y = min(surface.get_height() - 1, int(ceil(max(v[1] for v in vertices))))
        triangle = list(zip(vertices, colors or [(255, 255, 255)] * 3, uvs or [(0.0, 0.0)] * 3))
        edges = [
            (triangle[0], triangle[1]),
            (triangle[1], triangle[2]),
            (triangle[2], triangle[0]),
        ]

        for y in range(min_y, max_y + 1):
            scan_y = y + 0.5
            intersections = []
            for (v1, c1, uv1), (v2, c2, uv2) in edges:
                x1, y1 = v1
                x2, y2 = v2
                if abs(y2 - y1) < 1e-6:
                    continue
                ymin = min(y1, y2)
                ymax = max(y1, y2)
                if not (ymin <= scan_y < ymax):
                    continue
                t = (scan_y - y1) / (y2 - y1)
                x = x1 + t * (x2 - x1)
                color = tuple(c1[i] + t * (c2[i] - c1[i]) for i in range(3))
                uv = (uv1[0] + t * (uv2[0] - uv1[0]), uv1[1] + t * (uv2[1] - uv1[1]))
                intersections.append((x, color, uv))
            if len(intersections) < 2:
                continue
            intersections.sort(key=lambda item: item[0])
            left_x, left_color, left_uv = intersections[0]
            right_x, right_color, right_uv = intersections[1]
            if left_x > right_x:
                left_x, right_x = right_x, left_x
                left_color, right_color = right_color, left_color
                left_uv, right_uv = right_uv, left_uv

            x_start = max(0, int(ceil(left_x)))
            x_end = min(surface.get_width() - 1, int(floor(right_x)))
            span = max(right_x - left_x, 1e-6)
            for x in range(x_start, x_end + 1):
                t = ((x + 0.5) - left_x) / span
                if texture is not None and uvs is not None:
                    u = left_uv[0] + t * (right_uv[0] - left_uv[0])
                    v = left_uv[1] + t * (right_uv[1] - left_uv[1])
                    color = self.sample_texture(texture, u, v)
                else:
                    color = self.clamp_color(
                        [left_color[i] + t * (right_color[i] - left_color[i]) for i in range(3)]
                    )
                self.set_pixel(surface, x, y, color)

    def sample_texture(self, texture: pygame.Surface, u: float, v: float) -> Color:
        """Amostra uma cor da textura a partir de coordenadas UV."""
        tx = int(abs(u % 1.0) * (texture.get_width() - 1))
        ty = int(abs(v % 1.0) * (texture.get_height() - 1))
        return texture.get_at((tx, ty))[:3]

    def draw_clipped_line(
        self,
        surface: pygame.Surface,
        p1: Point,
        p2: Point,
        rect: Tuple[int, int, int, int],
        color: Color,
    ) -> None:
        """Desenha uma reta após aplicar clipping de Cohen-Sutherland."""
        clipped = CohenSutherlandClipper.clip_line(p1[0], p1[1], p2[0], p2[1], rect)
        if clipped:
            x1, y1, x2, y2 = clipped
            self.draw_line(surface, (x1, y1), (x2, y2), color)


def regular_polygon(center: Point, radius: float, sides: int, rotation_deg: float = 0.0) -> List[Point]:
    """Gera vértices de um polígono regular usado na construção dos personagens."""
    cx, cy = center
    points = []
    for index in range(sides):
        angle = radians(rotation_deg + index * (360.0 / sides))
        points.append((cx + cos(angle) * radius, cy + sin(angle) * radius))
    return points
