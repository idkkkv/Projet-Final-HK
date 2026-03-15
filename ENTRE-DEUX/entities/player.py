# ─────────────────────────────────────────
#  ENTRE-DEUX — Joueur
# ─────────────────────────────────────────

import pygame
from pygame.locals import *
import settings
from utils import *
from settings import *
from entities.animation import Animation


class Player:
    def __init__(self, pos=(0, 0)):
        self.rect = pygame.Rect(pos[0], pos[1], 90, 104)
        self.vx = 0
        self.vy = 0
        self.gravity = GRAVITY
        self.puissance_saut = JUMP_POWER
        self.speed = PLAYER_SPEED
        self.on_ground = True
        self.direction = 1   # 1 = droite, -1 = gauche
        self.attacking = False
        self.attack_rect = pygame.Rect(0, 0, 40, 40)
        self.attack_timer = 0

        self.idle_anim = Animation(
            [
                pygame.image.load(find_file("player_idle.png")),
                pygame.image.load(find_file("player_idle2.png"))
            ],
            img_dur=20
        )

    def mouvement(self, dt, keys):
        self.vx = 0

        # Manette
        if abs(settings.axis_x) > DEAD_ZONE:
            self.vx = settings.axis_x * self.speed
            self.direction = -1 if settings.axis_x > 0 else 1

        # Clavier
        if keys[K_d]:
            self.vx = self.speed
            self.direction = -1
        elif keys[K_q]:
            self.vx = -self.speed
            self.direction = 1

        # Gravité
        self.vy += self.gravity * dt

        # Saut clavier
        if keys[K_SPACE] and self.on_ground:
            self.vy = -self.puissance_saut
            self.on_ground = False

        # Saut manette
        if settings.manette and settings.manette.get_button(0) and self.on_ground:
            self.vy = -self.puissance_saut
            self.on_ground = False

        # Mouvement
        self.rect.x += self.vx * dt
        self.rect.y += self.vy * dt

        # Sol dynamique (settings.GROUND_Y est modifiable par l'éditeur)
        if self.rect.bottom > settings.GROUND_Y:
            self.rect.bottom = settings.GROUND_Y
            self.vy = 0
            self.on_ground = True

        # Attaque clavier
        if keys[K_f] and not self.attacking:
            self.attacking = True
            self.attack_timer = ATTACK_DURATION

        # Attaque manette
        if settings.manette and settings.manette.get_button(2) and not self.attacking:
            self.attacking = True
            self.attack_timer = ATTACK_DURATION

        if self.attacking:
            self.attack_timer -= dt

        if self.direction == 1:
            self.attack_rect.topleft = (self.rect.right, self.rect.y + 20)
        else:
            self.attack_rect.topright = (self.rect.left, self.rect.y + 20)

        if self.attack_timer <= 0:
            self.attacking = False

    def draw(self, surf, camera):
        img = self.idle_anim.img()
        self.idle_anim.update()
        if self.direction == -1:
            img = pygame.transform.flip(img, True, False)
        surf.blit(img, camera.apply(self.rect))
        if self.attacking:
            pygame.draw.rect(surf, BLANC, camera.apply(self.attack_rect))