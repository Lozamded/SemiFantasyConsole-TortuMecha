"""Greedy word-wrap shared by text_font.py and sprite_font.py's block renderers."""

from __future__ import annotations

from typing import Callable


def wrap_text(text: str, max_width: int, char_width: Callable[[str], int]) -> list[str]:
    """Split `text` into lines no wider than `max_width`, breaking on spaces.

    A single word wider than `max_width` is kept whole on its own line rather
    than broken mid-word. Existing `\n` characters always start a new line.
    """
    if max_width <= 0:
        return text.split("\n")

    space_width = char_width(" ")
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current_words: list[str] = []
        current_width = 0
        for word in words:
            word_width = sum(char_width(c) for c in word)
            extra = (space_width if current_words else 0) + word_width
            if current_words and current_width + extra > max_width:
                lines.append(" ".join(current_words))
                current_words = [word]
                current_width = word_width
            else:
                current_words.append(word)
                current_width += extra
        lines.append(" ".join(current_words))
    return lines


def autofit_scale(
    text: str,
    box_width: int,
    box_height: int,
    line_height: float,
    char_width: Callable[[str], int],
    *,
    min_scale: float,
    max_scale: float,
    iterations: int = 14,
) -> tuple[float, list[str]]:
    """Find the largest scale in [min_scale, max_scale] that word-wraps `text`
    into `box_width` (screen px) without the wrapped block exceeding
    `box_height` (screen px), re-wrapping at each candidate scale since a
    smaller scale fits more font-space pixels — and therefore more words —
    into the same on-screen box width.

    Falls back to `min_scale` (still re-wrapped at that scale) if nothing in
    the range fits; the caller is expected to crop the overflow.
    """
    if min_scale > max_scale:
        min_scale, max_scale = max_scale, min_scale
    min_scale = max(min_scale, 0.01)

    def wrap_at(scale: float) -> tuple[bool, list[str]]:
        font_width = max(1, round(box_width / scale))
        lines = wrap_text(text, font_width, char_width)
        height = line_height * len(lines) * scale
        return height <= box_height, lines

    fits, lines = wrap_at(max_scale)
    if fits:
        return max_scale, lines

    lo, hi = min_scale, max_scale
    best_scale, best_lines = min_scale, wrap_at(min_scale)[1]
    for _ in range(iterations):
        mid = (lo + hi) / 2
        fits, lines = wrap_at(mid)
        if fits:
            best_scale, best_lines = mid, lines
            lo = mid
        else:
            hi = mid
    return best_scale, best_lines
