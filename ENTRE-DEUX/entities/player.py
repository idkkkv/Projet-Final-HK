# ─────────────────────────────────────────
#  ENTRE-DEUX — Joueur
# ─────────────────────────────────────────

import pygame
from pygame.locals import *
import settings
from utils import *
from settings import *
from entities.animation import Animation
from audio import sound_manager


class Player:
    def __init__(self, pos=(0, 0)):
        self.rect = pygame.Rect(pos[0], pos[1], 90, 104)
        self.vx = 0
        self.vy = 0
        self.gravity = GRAVITY
        self.puissance_saut = JUMP_POWER
        self.speed = PLAYER_SPEED
        self.on_ground = True
        self.direction = 1
        self.attacking = False
        self.attack_rect = pygame.Rect(0, 0, 40, 40)
        self.attack_timer = 0

        # Spawn
        self.spawn_x = pos[0]
        self.spawn_y = pos[1]

        # Invincibilité
        self.invincible = False
        self.invincible_timer = 0.0
        self.INVINCIBLE_DURATION = 1.0
        self.knockback_vx = 0.0

        # Vie
        self.max_hp = 5
        self.hp = self.max_hp
        self.dead = False
        self.show_hp_timer = 0.0   # temps restant pour afficher la vie
        self.HP_DISPLAY_DURATION = 2.0  # secondes

        # Regard (pour afficher la vie)
        self.looking_up = False

        self.idle_anim = Animation(
            [
                pygame.image.load(find_file("player_idle.png")),
                pygame.image.load(find_file("player_idle2.png"))
            ],
            img_dur=20
        )

        self._heart_font = None
        self.step_timer = 0.1  #chrono pour ne pas jouer le son de pas trop vite

    def respawn(self):
        self.rect.x = self.spawn_x
        self.rect.y = self.spawn_y
        self.vx = 0
        self.vy = 0
        self.knockback_vx = 0
        self.on_ground = False
        self.hp = self.max_hp
        self.dead = False

    def hit_by_enemy(self, enemy_rect):
        if self.invincible or self.dead:
            return
        if self.rect.centerx < enemy_rect.centerx:
            self.knockback_vx = -300
        else:
            self.knockback_vx = 300
        self.vy = -150
        self.invincible = True
        self.invincible_timer = self.INVINCIBLE_DURATION
        self.hp -= 1
        sound_manager.jouer("degat")
        self.show_hp_timer = self.HP_DISPLAY_DURATION
        if self.hp <= 0:
            self.dead = True
            sound_manager.jouer("mort")

    def mouvement(self, dt, keys, holes=None):
        self.vx = 0
        self.looking_up = False

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

        # Regarder en haut → affiche la vie
        if keys[K_z] or keys[K_UP]:
            self.looking_up = True
            self.show_hp_timer = self.HP_DISPLAY_DURATION

        self.vx += self.knockback_vx
        if abs(self.knockback_vx) > 1:
            self.knockback_vx *= 0.85
        else:
            self.knockback_vx = 0

        # Gravité
        self.vy += self.gravity * dt

        # Saut
        if keys[K_SPACE] and self.on_ground:
            self.vy = -self.puissance_saut
            self.on_ground = False

        if settings.manette and settings.manette.get_button(0) and self.on_ground:
            self.vy = -self.puissance_saut
            self.on_ground = False

        # Mouvement
        self.rect.x += int(self.vx * dt)
        self.rect.y += int(self.vy * dt)

        # Vérifier si le joueur est dans un trou (ignore sol/plafond)
        in_hole = False
        if holes:
            for hole in holes:
                if self.rect.colliderect(hole):
                    in_hole = True
                    break

        # Sol (seulement si pas dans un trou)
        if not in_hole and self.rect.bottom > settings.GROUND_Y:
            self.rect.bottom = settings.GROUND_Y
            self.vy = 0
            self.on_ground = True

        # Plafond (seulement si pas dans un trou)
        if not in_hole and hasattr(settings, 'CEILING_Y'):
            if self.rect.top < settings.CEILING_Y:
                self.rect.top = settings.CEILING_Y
                self.vy = 0

        # Attaque
        if keys[K_f] and not self.attacking:
            self.attacking = True
            sound_manager.jouer("attaque")
            self.attack_timer = ATTACK_DURATION

        if settings.manette and settings.manette.get_button(2) and not self.attacking:
            self.attacking = True
            sound_manager.jouer("attaque")
            self.attack_timer = ATTACK_DURATION

        if self.attacking:
            self.attack_timer -= dt

        if self.direction == 1:
            self.attack_rect.topleft = (self.rect.right, self.rect.y + 20)
        else:
            self.attack_rect.topright = (self.rect.left, self.rect.y + 20)

        if self.attack_timer <= 0:
            self.attacking = False

        # Timers
        if self.invincible:
            self.invincible_timer -= dt
            if self.invincible_timer <= 0:
                self.invincible = False

        if self.show_hp_timer > 0:
            self.show_hp_timer -= dt

        if self.on_ground and abs(self.vx) > 10:
            self.step_timer -= dt
            if self.step_timer <= 0:
                sound_manager.jouer("pas", volume=0.3)
                self.step_timer = 0.35
        else:
            self.step_timer = 0.2 # reset du timer pour éviter de jouer le son de pas dès que le joueur recommence à marcher

    def draw(self, surf, camera, show_hitbox=False):
        img = self.idle_anim.img()
        self.idle_anim.update()
        if self.direction == -1:
            img = pygame.transform.flip(img, True, False)

        if self.invincible:
            if int(self.invincible_timer * 12) % 2 == 0:
                surf.blit(img, camera.apply(self.rect))
        else:
            surf.blit(img, camera.apply(self.rect))

        if self.attacking:
            pygame.draw.rect(surf, BLANC, camera.apply(self.attack_rect))

        # Cœurs au-dessus du joueur
        if self.show_hp_timer > 0:
            self._draw_hearts(surf, camera)

        if show_hitbox:
            pygame.draw.rect(surf, (0, 255, 0), camera.apply(self.rect), 1)

    def _draw_hearts(self, surf, camera):
        if self._heart_font is None:
            self._heart_font = pygame.font.SysFont("Consolas", 18)
        sr = camera.apply(self.rect)
        # Dessine des carrés colorés comme cœurs
        heart_size = 12
        gap = 4
        total_w = self.max_hp * (heart_size + gap) - gap
        start_x = sr.centerx - total_w // 2
        y = sr.top - 20
        for i in range(self.max_hp):
            x = start_x + i * (heart_size + gap)
            if i < self.hp:
                color = (255, 50, 80)  # rouge = plein
            else:
                color = (80, 80, 80)   # gris = vide
            pygame.draw.rect(surf, color, (x, y, heart_size, heart_size))
            pygame.draw.rect(surf, (200, 200, 200), (x, y, heart_size, heart_size), 1)