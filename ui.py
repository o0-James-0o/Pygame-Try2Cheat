"""
Componentes auxiliares de interface.

Mesmo na UI, as molduras e painéis são desenhados com o Rasterizer do projeto,
para manter o padrão de uso de linhas e preenchimento poligonal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import pygame

from algorithms import Rasterizer
from settings import BUTTON_GREEN, BUTTON_GREEN_DARK, INK, PANEL_BLUE, SOFT_WHITE

Color = Tuple[int, int, int]


@dataclass
class Button:
    """Botão interativo usado no menu e na tela de game over."""
    rect: pygame.Rect
    label: str

    def contains(self, pos: Tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)

    def draw(self, surface: pygame.Surface, rasterizer: Rasterizer, font: pygame.font.Font, hovered: bool) -> None:
        x, y, w, h = self.rect
        top = tuple(min(255, c + 30) for c in BUTTON_GREEN)
        bottom = BUTTON_GREEN_DARK if not hovered else tuple(max(0, c - 10) for c in BUTTON_GREEN_DARK)
        rasterizer.fill_polygon_gradient(
            surface,
            [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
            [top, top, bottom, bottom],
        )
        border = [
            (x, y),
            (x + w, y),
            (x + w, y + h),
            (x, y + h),
        ]
        rasterizer.draw_polyline(surface, [(int(px), int(py)) for px, py in border], INK)
        rasterizer.draw_line(surface, (x + 3, y + h - 4), (x + w - 4, y + h - 4), (50, 70, 20))
        text = font.render(self.label, False, SOFT_WHITE)
        tx = x + (w - text.get_width()) // 2
        ty = y + (h - text.get_height()) // 2
        shadow = font.render(self.label, False, INK)
        surface.blit(shadow, (tx + 2, ty + 2))
        surface.blit(text, (tx, ty))


def draw_panel(surface: pygame.Surface, rasterizer: Rasterizer, rect: pygame.Rect, fill: Color = PANEL_BLUE) -> None:
    """Desenha um painel retangular usando polígono preenchido e contorno rasterizado."""
    x, y, w, h = rect
    border = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    rasterizer.draw_polyline(surface, border, (230, 232, 238))
    inner = [(x + 2, y + 2), (x + w - 2, y + 2), (x + w - 2, y + h - 2), (x + 2, y + h - 2)]
    rasterizer.fill_polygon_scanline(surface, [(int(px), int(py)) for px, py in inner], fill)
    rasterizer.draw_polyline(surface, [(int(px), int(py)) for px, py in inner], (25, 31, 48))


def blit_centered(surface: pygame.Surface, font: pygame.font.Font, text: str, y: int, color: Color, shadow: Color | None = None) -> pygame.Rect:
    """Centraliza texto horizontalmente na superfície."""
    rendered = font.render(text, False, color)
    x = (surface.get_width() - rendered.get_width()) // 2
    if shadow is not None:
        shadow_rendered = font.render(text, False, shadow)
        surface.blit(shadow_rendered, (x + 3, y + 3))
    surface.blit(rendered, (x, y))
    return pygame.Rect(x, y, rendered.get_width(), rendered.get_height())


def wrap_text(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    """Quebra texto em linhas para caber na largura disponível."""
    words = text.split()
    if not words:
        return ['']
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f'{current} {word}'
        if font.size(trial)[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def draw_wrapped_text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    rect: pygame.Rect,
    color: Color,
    *,
    align: str = 'left',
    shadow: Color | None = None,
    line_gap: int = 6,
) -> int:
    """Renderiza texto quebrado em múltiplas linhas, com alinhamento opcional."""
    lines = wrap_text(font, text, rect.width)
    y = rect.y
    for line in lines:
        rendered = font.render(line, False, color)
        if align == 'center':
            x = rect.x + (rect.width - rendered.get_width()) // 2
        elif align == 'right':
            x = rect.right - rendered.get_width()
        else:
            x = rect.x
        if shadow is not None:
            shadow_rendered = font.render(line, False, shadow)
            surface.blit(shadow_rendered, (x + 2, y + 2))
        surface.blit(rendered, (x, y))
        y += rendered.get_height() + line_gap
    return y
