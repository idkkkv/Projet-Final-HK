# ─────────────────────────────────────────
#  ENTRE-DEUX — Boucle principale du jeu
# ─────────────────────────────────────────

import pygame
import settings
from world.editor import Editor
from core.event_handler import x_y_man, man_on
from settings import *
from core.camera import Camera
from entities.player import Player
from entities.enemy import Enemy
from world.tilemap import Platform, Wall
from systems.lighting import LightingSystem
from systems.spatial_grid import SpatialGrid
from utils import draw_mouse_coords
from world.collision import (check_attack_collisions,
                             check_platform_collisions,
                             check_player_enemy_collisions)


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption(TITLE)
        self.running = True
        self.clock = pygame.time.Clock()
        self.fps_font = pygame.font.SysFont("Consolas", 16)

        self._build_walls()

        self.player = Player((100, 400))
        self.camera = Camera(SCENE_WIDTH, SCENE_HEIGHT)

        self.enemies = [Enemy(500, 530 - 60)]

        self.platforms = [
            Platform(200, 500, 100, 20, BLANC),
            Platform(300, 400, 100, 20, GRIS),
            Platform(400, 300, 100, 20, BLEU),
        ]

        self.platform_grid = SpatialGrid(cell_size=128)
        self._rebuild_grid()

        self.lighting = LightingSystem()
        self.lighting.add_light(300, 480, radius=150,
                                type="torch", flicker=True)
        self.lighting.add_light(600, 380, radius=200,
                                type="torch", flicker=True)

        self.editor = Editor(self.platforms, self.enemies,
                             self.camera, self.lighting)

        self._last_ground_y = settings.GROUND_Y
        self._last_scene_w = settings.SCENE_WIDTH

    def _build_walls(self):
        gy = settings.GROUND_Y
        sw = settings.SCENE_WIDTH
        # Le sol remplit tout en dessous de GROUND_Y (assez épais pour couvrir l'écran)
        self.walls = [
            Wall(0, gy, sw, 800, visible=True),                    # Sol
            Wall(0, -20, sw, 20, visible=True),                    # Plafond
            Wall(0, -20, 20, gy + 820, visible=True),              # Mur gauche
            Wall(sw - 20, -20, 20, gy + 820, visible=True),        # Mur droit
        ]

    def _rebuild_grid(self):
        self.platform_grid.rebuild(self.platforms)

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000

            # ── Événements ──────────────────────────────
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_e:
                        self.editor.toggle()
                    elif self.editor.active:
                        self.editor.handle_key(event.key)
                        if event.key in (pygame.K_s, pygame.K_l):
                            self._rebuild_grid()

                if self.editor.active:
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            self.editor.handle_click(event.pos)
                            self._rebuild_grid()
                        elif event.button == 3:
                            self.editor.handle_right_click(event.pos)
                            self._rebuild_grid()
                    if event.type == pygame.MOUSEWHEEL:
                        self.editor.handle_scroll(event.y)

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 2:
                        print(f"Monde x:{settings.wx} y:{settings.wy}")

            # ── Reconstruire les murs si scène/sol a changé ──
            if (settings.GROUND_Y != self._last_ground_y or
                    settings.SCENE_WIDTH != self._last_scene_w):
                self._last_ground_y = settings.GROUND_Y
                self._last_scene_w = settings.SCENE_WIDTH
                self._build_walls()

            # ── Mise à jour ──────────────────────────────
            keys = pygame.key.get_pressed()
            man_on()
            x_y_man()

            self.player.mouvement(dt, keys)
            self.camera.update(self.player.rect)

            for enemy in self.enemies:
                enemy.update(dt, self.platforms, self.walls)

            check_attack_collisions(self.player, self.enemies,)
            check_platform_collisions(self.player, self.platform_grid)
            check_player_enemy_collisions(self.player, self.enemies, dt)

            for wall in self.walls:
                wall.verifier_collision(self.player)

            self.lighting.update(dt)

            # ── Affichage ────────────────────────────────
            self.screen.fill(VIOLET)

            for wall in self.walls:
                if self.camera.is_visible(wall.rect):
                    wall.draw(self.screen, self.camera)

            for platform in self.platforms:
                if self.camera.is_visible(platform.rect):
                    platform.draw(self.screen, self.camera)

            for enemy in self.enemies:
                if self.camera.is_visible(enemy.rect):
                    enemy.draw(self.screen, self.camera)

            self.player.draw(self.screen, self.camera)

            # Hitbox du joueur (vert)
            pygame.draw.rect(self.screen, (0, 255, 0),
                             self.camera.apply(self.player.rect), 1)

            self.lighting.render(self.screen, self.camera, self.player.rect)

            draw_mouse_coords(self.screen, self.camera)

            if self.editor.active:
                self.editor.draw_preview(self.screen,
                                         pygame.mouse.get_pos())
                self.editor.draw_hud(self.screen)

            # FPS en bas à droite (sous le panneau éditeur)
            fps_surf = self.fps_font.render(
                f"{self.clock.get_fps():.0f} FPS", True, (0, 255, 0))
            self.screen.blit(fps_surf,
                (self.screen.get_width() - fps_surf.get_width() - 10,
                 self.screen.get_height() - 25))

            pygame.display.flip()