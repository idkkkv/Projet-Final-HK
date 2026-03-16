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

# Ajoute CEILING_Y si absent de settings
if not hasattr(settings, 'CEILING_Y'):
    settings.CEILING_Y = 0


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption(TITLE)
        self.running = True
        self.paused = False
        self.clock = pygame.time.Clock()

        # Fonts
        self.fps_font = pygame.font.SysFont("Consolas", 16)
        self._pause_font = pygame.font.SysFont("Consolas", 28)
        self._pause_small = pygame.font.SysFont("Consolas", 18)

        # Murs de la scène
        self._build_walls()

        # Joueur et caméra
        self.player = Player((100, 400))
        self.camera = Camera(SCENE_WIDTH, SCENE_HEIGHT)

        # Ennemis par défaut
        self.enemies = [Enemy(500, 530 - 60)]

        # Plateformes par défaut
        self.platforms = [
            Platform(200, 500, 100, 20, BLANC),
            Platform(300, 400, 100, 20, GRIS),
            Platform(400, 300, 100, 20, BLEU),
        ]

        # Grille spatiale pour les collisions rapides
        self.platform_grid = SpatialGrid(cell_size=128)
        self._rebuild_grid()

        # Éclairage
        self.lighting = LightingSystem()
        self.lighting.add_light(300, 480, radius=150, type="torch", flicker=True)
        self.lighting.add_light(600, 380, radius=200, type="torch", flicker=True)

        # Éditeur (reçoit le player pour le spawn)
        self.editor = Editor(self.platforms, self.enemies,
                             self.camera, self.lighting, self.player)

        # Cache pour détecter les changements de scène
        self._last_ground_y = settings.GROUND_Y
        self._last_ceiling_y = settings.CEILING_Y
        self._last_scene_w = settings.SCENE_WIDTH

        # Menu pause
        self._pause_selection = 0
        self._pause_options = ["Reprendre", "Quitter"]

        # Nom de la map courante (affiché en bas)
        self.current_map_name = ""

        # Transition fondu noir
        self.fade_speed = 0.4        # secondes pour chaque sens
        self._fade_alpha = 0         # 0 = transparent, 255 = noir
        self._fade_state = "none"    # "none", "out", "in"
        self._fade_surface = None
        self._pending_portal = None

    # ─────────────────────────────────────
    #  Construction des murs
    # ─────────────────────────────────────

    def _build_walls(self):
        """Crée les 4 murs de la scène (sol, plafond, gauche, droit).
        Ils débordent largement pour remplir l'écran de noir."""
        gy = settings.GROUND_Y
        cy = settings.CEILING_Y
        sw = settings.SCENE_WIDTH
        height = gy - cy + 820

        self.walls = [
            Wall(0, gy, sw + 800, 800, visible=True),              # Sol
            Wall(-800, cy - 800, sw + 1600, 800, visible=True),     # Plafond
            Wall(-800, cy - 800, 800, height + 800, visible=True),  # Mur gauche
            Wall(sw, cy - 800, 800, height + 800, visible=True),    # Mur droit
        ]

    def _rebuild_grid(self):
        """Reconstruit la grille spatiale des plateformes."""
        self.platform_grid.rebuild(self.platforms)

    # ─────────────────────────────────────
    #  Trous : annulation de collision
    # ─────────────────────────────────────

    def _is_hole_cancelling(self, wall_rect, entity_rect):
        """Retourne True si un trou annule la collision entre entity et wall.
        Un trou annule un mur quand il touche À LA FOIS le mur et l'entité."""
        for hole in self.editor.holes:
            if hole.colliderect(wall_rect) and hole.colliderect(entity_rect):
                return True
        return False

    # ─────────────────────────────────────
    #  Lumières des ennemis
    # ─────────────────────────────────────

    def _update_enemy_lights(self):
        """Met à jour les lumières attachées aux ennemis."""
        # Supprime les anciennes lumières ennemies
        self.lighting.lights = [
            l for l in self.lighting.lights
            if not l.get("_enemy_light")
        ]
        # Ajoute les nouvelles à la position actuelle
        for enemy in self.enemies:
            if enemy.alive and enemy.has_light:
                lx, ly = enemy.get_light_pos()
                self.lighting.lights.append({
                    "x": lx, "y": ly,
                    "radius": enemy.light_radius,
                    "type": enemy.light_type,
                    "flicker": True,
                    "flicker_speed": 4,
                    "_phase": 0,
                    "_enemy_light": True,
                })

    # ─────────────────────────────────────
    #  Portails + Fondu
    # ─────────────────────────────────────

    def _check_portals(self):
        """Si le joueur entre dans un portail, lance le fondu."""
        if self._fade_state != "none":
            return
        for portal in self.editor.portals:
            if self.player.rect.colliderect(portal.rect):
                self._pending_portal = (
                    portal.target_map, portal.target_x, portal.target_y)
                self._fade_state = "out"
                self._fade_alpha = 0
                return

    def _update_fade(self, dt):
        """Gère le fondu noir entre deux maps."""
        if self._fade_state == "none":
            return

        speed = 255 / max(0.05, self.fade_speed)

        if self._fade_state == "out":
            # Fondu vers le noir
            self._fade_alpha += speed * dt
            if self._fade_alpha >= 255:
                self._fade_alpha = 255
                # Écran noir → charger la map
                if self._pending_portal:
                    target, tx, ty = self._pending_portal
                    if self.editor.load_map_for_portal(target):
                        self.current_map_name = target
                        self._rebuild_grid()
                        self._build_walls()
                        if tx >= 0 and ty >= 0:
                            self.player.rect.x = tx
                            self.player.rect.y = ty
                        else:
                            self.player.respawn()
                        self.player.vy = 0
                        self.player.knockback_vx = 0
                    self._pending_portal = None
                self._fade_state = "in"

        elif self._fade_state == "in":
            # Fondu vers le visible
            self._fade_alpha -= speed * dt
            if self._fade_alpha <= 0:
                self._fade_alpha = 0
                self._fade_state = "none"

    def _draw_fade(self):
        """Dessine l'overlay noir par-dessus tout."""
        if self._fade_alpha <= 0:
            return
        w, h = self.screen.get_size()
        if self._fade_surface is None or self._fade_surface.get_size() != (w, h):
            self._fade_surface = pygame.Surface((w, h), pygame.SRCALPHA)
        self._fade_surface.fill((0, 0, 0, int(self._fade_alpha)))
        self.screen.blit(self._fade_surface, (0, 0))

    # ─────────────────────────────────────
    #  Menu Pause
    # ─────────────────────────────────────

    def _draw_pause(self):
        w, h = self.screen.get_size()

        # Fond assombri
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        # Titre
        title = self._pause_font.render("PAUSE", True, (255, 255, 255))
        self.screen.blit(title, (w // 2 - title.get_width() // 2, h // 2 - 80))

        # Options
        for i, opt in enumerate(self._pause_options):
            color = (0, 255, 120) if i == self._pause_selection else (180, 180, 180)
            prefix = "> " if i == self._pause_selection else "  "
            text = self._pause_small.render(f"{prefix}{opt}", True, color)
            self.screen.blit(text,
                (w // 2 - text.get_width() // 2, h // 2 - 10 + i * 40))

    def _handle_pause_key(self, key):
        if key == pygame.K_UP:
            self._pause_selection = (self._pause_selection - 1) % len(self._pause_options)
        elif key == pygame.K_DOWN:
            self._pause_selection = (self._pause_selection + 1) % len(self._pause_options)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            if self._pause_selection == 0:
                self.paused = False
            elif self._pause_selection == 1:
                self.running = False

    # ─────────────────────────────────────
    #  Boucle principale
    # ─────────────────────────────────────

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000

            # ── Événements ──────────────────────
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                if event.type == pygame.KEYDOWN:
                    # Escape → pause (sauf si saisie texte)
                    if event.key == pygame.K_ESCAPE:
                        if self.editor.active and self.editor._text_mode:
                            self.editor.handle_key(event.key)
                        else:
                            self.paused = not self.paused
                            self._pause_selection = 0
                        continue

                    if self.paused:
                        self._handle_pause_key(event.key)
                        continue

                    # E = éditeur (sauf si saisie texte)
                    if event.key == pygame.K_e and not (
                            self.editor.active and self.editor._text_mode):
                        self.editor.toggle()
                    elif self.editor.active:
                        result = self.editor.handle_key(event.key)
                        if result == "done":
                            self._rebuild_grid()
                            self._build_walls()

                if self.paused:
                    continue

                # Clics en mode éditeur
                if self.editor.active and self.editor._text_mode is None:
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            self.editor.handle_click(event.pos)
                            self._rebuild_grid()
                        elif event.button == 3:
                            self.editor.handle_right_click(event.pos)
                            self._rebuild_grid()
                    if event.type == pygame.MOUSEWHEEL:
                        self.editor.handle_scroll(event.y)

                # Clic molette = afficher coordonnées dans la console
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
                    print(f"Monde x:{settings.wx} y:{settings.wy}")

            # ── Pause → afficher et arrêter ──
            if self.paused:
                self._draw_pause()
                pygame.display.flip()
                continue

            # ── Reconstruire murs si scène a changé ──
            if (settings.GROUND_Y != self._last_ground_y or
                    settings.CEILING_Y != self._last_ceiling_y or
                    settings.SCENE_WIDTH != self._last_scene_w):
                self._last_ground_y = settings.GROUND_Y
                self._last_ceiling_y = settings.CEILING_Y
                self._last_scene_w = settings.SCENE_WIDTH
                self._build_walls()
                self.editor.rebuild_hole_borders()

            # ── Mise à jour ─────────────────────
            keys = pygame.key.get_pressed()
            man_on()
            x_y_man()

            # Joueur (bloqué pendant le fondu)
            if self._fade_state == "none":
                self.player.mouvement(dt, keys, self.editor.holes)
            self.camera.update(self.player.rect)

            # Ennemis (reçoivent murs + trous)
            all_walls = self.walls + self.editor.custom_walls
            for enemy in self.enemies:
                enemy.update(dt, self.platforms, all_walls,
                             self.player.rect, self.editor.holes)

            # Collisions
            check_attack_collisions(self.player, self.enemies)
            check_platform_collisions(self.player, self.platform_grid)

            # Pas de dégâts en mode éditeur
            if not self.editor.active:
                check_player_enemy_collisions(self.player, self.enemies)

            # ── Collision murs : trous annulent PAR MUR ──
            # Si un trou touche un mur ET touche le joueur → ce mur est ignoré
            for wall in self.walls + self.editor.custom_walls:
                if not self._is_hole_cancelling(wall.rect, self.player.rect):
                    wall.verifier_collision(self.player)

            # Bordures des trous → TOUJOURS actives (jamais annulées par les trous)
            for wall in self.editor.hole_borders:
                wall.verifier_collision(self.player)

            # Lumières, portails, fondu
            self.lighting.update(dt)
            self._update_enemy_lights()
            self._check_portals()
            self._update_fade(dt)

            # ── Affichage ───────────────────────
            bg = tuple(self.editor.bg_color)
            self.screen.fill(bg)

            # Murs principaux
            for wall in self.walls:
                if self.camera.is_visible(wall.rect):
                    wall.draw(self.screen, self.camera)

            # Murs custom
            for wall in self.editor.custom_walls:
                if self.camera.is_visible(wall.rect):
                    wall.draw(self.screen, self.camera)

            # Trous : fond par-dessus les murs (perce visuellement)
            for hole in self.editor.holes:
                if self.camera.is_visible(hole):
                    hr = self.camera.apply(hole)
                    pygame.draw.rect(self.screen, bg, hr)
                    # Contour rouge en mode éditeur
                    if self.editor.show_hitboxes or self.editor.active:
                        pygame.draw.rect(self.screen, (255, 80, 80), hr, 2)

            # Bordures des trous (dessinées APRÈS le fond du trou)
            for wall in self.editor.hole_borders:
                if self.camera.is_visible(wall.rect):
                    wall.draw(self.screen, self.camera)

            # Plateformes
            for platform in self.platforms:
                if self.camera.is_visible(platform.rect):
                    platform.draw(self.screen, self.camera)

            # Ennemis
            for enemy in self.enemies:
                if self.camera.is_visible(enemy.rect):
                    enemy.draw(self.screen, self.camera,
                               self.editor.show_hitboxes)

            # Joueur
            self.player.draw(self.screen, self.camera,
                             self.editor.show_hitboxes)

            # Portails (visibles si hitbox ON ou éditeur actif)
            if self.editor.show_hitboxes or self.editor.active:
                font = self.editor._get_font()
                for portal in self.editor.portals:
                    portal.draw(self.screen, self.camera, font)

            # Overlays éditeur (spawn, portails)
            if self.editor.active:
                self.editor.draw_overlays(self.screen)

            # Éclairage
            self.lighting.render(self.screen, self.camera, self.player.rect)

            # Coordonnées (seulement en mode éditeur, sous le panneau)
            if self.editor.active:
                draw_mouse_coords(self.screen, self.camera, y_start=95)
                self.editor.draw_preview(self.screen, pygame.mouse.get_pos())
                self.editor.draw_hud(self.screen)

            # FPS en bas à droite
            fps_surf = self.fps_font.render(
                f"{self.clock.get_fps():.0f} FPS", True, (0, 255, 0))
            self.screen.blit(fps_surf,
                (self.screen.get_width() - fps_surf.get_width() - 10,
                 self.screen.get_height() - 25))

            # Nom de la map en bas à gauche
            if self.current_map_name:
                ms = self.fps_font.render(
                    self.current_map_name, True, (180, 180, 180))
                self.screen.blit(ms, (10, self.screen.get_height() - 25))

            # Fondu noir (par-dessus tout)
            self._draw_fade()

            pygame.display.flip()