# ─────────────────────────────────────────
#  ENTRE-DEUX — Ennemi de base
# ─────────────────────────────────────────

import pygame
import settings
from settings import *
from entities.animation import Animation
from utils import *


class Enemy:
    def __init__(self, x, y, has_gravity=True, has_collision=True):
        # La hitbox est centrée sur le sprite
        # On peut ajuster hitbox_w et hitbox_h si le sprite est différent
        self.hitbox_w = 40
        self.hitbox_h = 50
        # Le rect est la HITBOX (pas le sprite entier)
        self.rect = pygame.Rect(x, y, self.hitbox_w, self.hitbox_h)
        # Le sprite est plus grand que la hitbox (60×60)
        self.sprite_w = 60
        self.sprite_h = 60

        self.vx = 120
        self.vy = 0

        self.alive = True
        self.on_ground = False
        self.has_gravity = has_gravity
        self.has_collision = has_collision

        self.idle_anim = Animation([
            pygame.image.load(find_file("monstre_perdu.png"))
        ], img_dur=20)

    def update(self, dt, platforms=None, walls=None):
        if not self.alive:
            return

        # ── Déplacement horizontal ──
        self.rect.x += int(self.vx * dt)

        # Collision murs latéraux (walls[2] = gauche, walls[3] = droit)
        if walls and len(walls) > 3:
            if self.rect.colliderect(walls[2].rect):
                self.rect.left = walls[2].rect.right
                self.vx = abs(self.vx)
            if self.rect.colliderect(walls[3].rect):
                self.rect.right = walls[3].rect.left
                self.vx = -abs(self.vx)

        # ── Gravité ──
        if self.has_gravity:
            self.vy += GRAVITY * dt
            self.rect.y += int(self.vy * dt)

            # Sol
            if self.rect.bottom > settings.GROUND_Y:
                self.rect.bottom = settings.GROUND_Y
                self.vy = 0
                self.on_ground = True
            else:
                self.on_ground = False

        # ── Collision plateformes ──
        if self.has_collision and platforms:
            for p in platforms:
                plat = p.rect if hasattr(p, 'rect') else p
                if self.rect.colliderect(plat):
                    if self.vy >= 0 and self.rect.bottom <= plat.top + 20:
                        self.rect.bottom = plat.top
                        self.vy = 0
                        self.on_ground = True

    def draw(self, surf, camera, show_hitbox=False):
        if not self.alive:
            return

        img = self.idle_anim.img()
        if self.vx < 0:
            img = pygame.transform.flip(img, True, False)
        self.idle_anim.update()

        # Le sprite est centré sur la hitbox (le rect)
        sprite_x = self.rect.centerx - self.sprite_w // 2
        sprite_y = self.rect.bottom - self.sprite_h  # pieds alignés au bas de la hitbox
        sprite_rect = pygame.Rect(sprite_x, sprite_y,
                                  self.sprite_w, self.sprite_h)
        surf.blit(img, camera.apply(sprite_rect))

        # Hitbox rouge (optionnel)
        if show_hitbox:
            pygame.draw.rect(surf, (255, 0, 0), camera.apply(self.rect), 1)

    def to_dict(self):
        return {
            "x": self.rect.x, "y": self.rect.y,
            "has_gravity": self.has_gravity,
            "has_collision": self.has_collision,
        }