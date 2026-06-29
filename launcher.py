#!/usr/bin/env python3
"""TortuMecha console launcher.

Deployed at ~/console/launcher.py on the SBC alongside:
    ~/console/cart/          tortucart contents
    ~/console/tortuengine/   engine package
    ~/console/tortuplayer/   player package

Future: controls config, date/time, system settings.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pygame

ROOT     = Path(__file__).parent
CART_DIR = ROOT / "cart"

BG     = (6,   8,  20)
DIM    = (28,  34,  52)
WHITE  = (210, 225, 255)
GREEN  = (70,  210, 100)
RED    = (210,  70,  70)
YELLOW = (255, 220,  60)

RESCAN_INTERVAL = 2.0   # seconds between cart-presence checks
BLINK_INTERVAL  = 0.55  # seconds per blink half-cycle


def _find_cart() -> Path | None:
    """Return the cart root if a valid tortucart is present in CART_DIR."""
    if not CART_DIR.is_dir():
        return None
    if (CART_DIR / "cart.json").is_file():
        return CART_DIR
    for child in sorted(CART_DIR.iterdir()):
        if child.is_dir() and (child / "cart.json").is_file():
            return child
    return None


def _launch(cart_path: Path) -> None:
    pygame.quit()
    subprocess.run(
        [sys.executable, "-m", "tortuplayer", str(cart_path)],
        cwd=ROOT,
    )
    pygame.init()


def _open_display() -> pygame.Surface:
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("TortuMecha")
    pygame.mouse.set_visible(False)
    return screen


def _init_joystick() -> pygame.joystick.JoystickType | None:
    try:
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            j = pygame.joystick.Joystick(0)
            j.init()
            return j
    except Exception:
        pass
    return None


def main() -> None:
    pygame.init()
    screen = _open_display()
    W, H   = screen.get_size()

    _init_joystick()

    font_title = pygame.font.SysFont("monospace", max(36, H // 10), bold=True)
    font_main  = pygame.font.SysFont("monospace", max(22, H // 18), bold=True)
    font_hint  = pygame.font.SysFont("monospace", max(14, H // 36))

    clock       = pygame.time.Clock()
    blink_acc   = 0.0
    blink_on    = True
    scan_acc    = 0.0
    cart_path   = _find_cart()

    while True:
        dt       = clock.tick(60) / 1000.0
        blink_acc += dt
        scan_acc  += dt

        if blink_acc >= BLINK_INTERVAL:
            blink_acc = 0.0
            blink_on  = not blink_on

        if scan_acc >= RESCAN_INTERVAL:
            scan_acc  = 0.0
            cart_path = _find_cart()

        start_pressed = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                                   pygame.K_SPACE, pygame.K_z):
                    start_pressed = True
            elif event.type == pygame.JOYBUTTONDOWN:
                start_pressed = True
            elif event.type == pygame.JOYDEVICEADDED:
                _init_joystick()

        if start_pressed and cart_path:
            _launch(cart_path)
            screen    = _open_display()
            W, H      = screen.get_size()
            cart_path = _find_cart()
            continue

        # ── Draw ──────────────────────────────────────────────────────────
        screen.fill(BG)

        # Scanline overlay
        for y in range(0, H, 4):
            pygame.draw.line(screen, DIM, (0, y), (W, y))

        # Title
        title_surf = font_title.render("TORTU  MECHA", True, WHITE)
        screen.blit(title_surf, title_surf.get_rect(centerx=W // 2, top=H // 6))

        # Divider
        sep_y = H // 3 + H // 20
        pygame.draw.line(screen, DIM, (W // 4, sep_y), (3 * W // 4, sep_y))

        # Cart status + prompt
        mid_y = H // 2
        if cart_path:
            found = font_main.render("CARTRIDGE  FOUND", True, GREEN)
            screen.blit(found, found.get_rect(centerx=W // 2, centery=mid_y))
            if blink_on:
                prompt = font_main.render("PRESS  START", True, YELLOW)
                screen.blit(prompt, prompt.get_rect(centerx=W // 2,
                                                     centery=mid_y + H // 9))
        else:
            no_cart = font_main.render("NO  CARTRIDGE", True, RED)
            screen.blit(no_cart, no_cart.get_rect(centerx=W // 2, centery=mid_y))
            hint = font_hint.render("place cart in  ~/console/cart/", True, DIM)
            screen.blit(hint, hint.get_rect(centerx=W // 2,
                                             centery=mid_y + H // 12))

        # Bottom ESC hint
        esc = font_hint.render("ESC  quit", True, DIM)
        screen.blit(esc, esc.get_rect(right=W - 16, bottom=H - 12))

        pygame.display.flip()


if __name__ == "__main__":
    main()
