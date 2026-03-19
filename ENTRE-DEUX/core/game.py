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
from ui.inventory import Inventory

if not hasattr(settings, 'CEILING_Y'):
    settings.CEILING_Y = 0


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption(TITLE)
        self.running = True
        self.paused  = False
        self.clock   = pygame.time.Clock()
        self.fps_font     = pygame.font.SysFont("Consolas", 16)
        self._pause_font  = pygame.font.SysFont("Consolas", 28)
        self._pause_small = pygame.font.SysFont("Consolas", 18)

        self.inventory = Inventory()
        self.inventory.add_pomme()

        self.player  = Player((100, 400))
        self.camera  = Camera(SCENE_WIDTH, SCENE_HEIGHT)
        self.enemies = [Enemy(500, 530 - 60)]
        self.platforms = [
            Platform(200, 500, 100, 20, BLANC),
            Platform(300, 400, 100, 20, GRIS),
            Platform(400, 300, 100, 20, BLEU),
        ]
        self.platform_grid = SpatialGrid(cell_size=128)
        self._rebuild_grid()

        self.lighting = LightingSystem()
        self.lighting.add_light(300, 480, radius=150, type="torch", flicker=True)
        self.lighting.add_light(600, 380, radius=200, type="torch", flicker=True)

        self.editor = Editor(self.platforms, self.enemies,
                             self.camera, self.lighting, self.player)
        self.editor.build_border_segments()

        self._pause_selection = 0
        self._pause_options   = ["Reprendre", "Quitter"]
        self.current_map_name = ""

        self.fade_speed      = 0.4
        self._fade_alpha     = 0
        self._fade_state     = "none"
        self._fade_surface   = None
        self._pending_portal = None

        # Cache walls pour éviter de reconstruire la liste chaque frame
        self._walls_cache      = None
        self._walls_cache_dirty = True

    def _rebuild_grid(self):
        self.platform_grid.rebuild(self.platforms)

    def _dirty_walls(self):
        """Marque le cache walls comme périmé — à appeler quand les walls changent."""
        self._walls_cache_dirty = True

    def _all_walls(self):
        if self._walls_cache_dirty:
            self._walls_cache = self.editor.all_segments() + self.editor.custom_walls
            self._walls_cache_dirty = False
        return self._walls_cache

    def _update_enemy_lights(self):
        self.lighting.lights = [l for l in self.lighting.lights
                                if not l.get("_enemy_light")]
        for enemy in self.enemies:
            if enemy.alive and enemy.has_light:
                lx, ly = enemy.get_light_pos()
                self.lighting.lights.append({
                    "x":lx,"y":ly,"radius":enemy.light_radius,
                    "type":enemy.light_type,"flicker":True,"flicker_speed":4,
                    "_phase":0,"_alpha":210,"_enemy_light":True,
                })

    # ── Portails ──────────────────────────────────────────────────────────
    def _check_portals(self):
        if self._fade_state != "none": return
        for portal in self.editor.portals:
            if self.player.rect.colliderect(portal.rect):
                self._pending_portal = (portal.target_map, portal.target_x, portal.target_y)
                self._fade_state = "out"; self._fade_alpha = 0; return

    def _update_fade(self, dt):
        if self._fade_state == "none": return
        speed = 255 / max(0.05, self.fade_speed)
        if self._fade_state == "out":
            self._fade_alpha += speed * dt
            if self._fade_alpha >= 255:
                self._fade_alpha = 255
                if self._pending_portal:
                    target, tx, ty = self._pending_portal
                    if self.editor.load_map_for_portal(target):
                        self.current_map_name = target
                        self._rebuild_grid()
                        self._dirty_walls()
                        if tx >= 0 and ty >= 0:
                            self.player.rect.x = tx; self.player.rect.y = ty
                        else: self.player.respawn()
                        self.player.vy = 0; self.player.knockback_vx = 0
                    self._pending_portal = None
                self._fade_state = "in"
        elif self._fade_state == "in":
            self._fade_alpha -= speed * dt
            if self._fade_alpha <= 0:
                self._fade_alpha = 0; self._fade_state = "none"

    def _draw_fade(self):
        if self._fade_alpha <= 0: return
        w, h = self.screen.get_size()
        if self._fade_surface is None or self._fade_surface.get_size() != (w,h):
            self._fade_surface = pygame.Surface((w,h), pygame.SRCALPHA)
        self._fade_surface.fill((0,0,0,int(self._fade_alpha)))
        self.screen.blit(self._fade_surface, (0,0))

    # ── Pause ─────────────────────────────────────────────────────────────
    def _draw_pause(self):
        w,h = self.screen.get_size()
        overlay = pygame.Surface((w,h), pygame.SRCALPHA)
        overlay.fill((0,0,0,160)); self.screen.blit(overlay,(0,0))
        title = self._pause_font.render("PAUSE",True,(255,255,255))
        self.screen.blit(title,(w//2-title.get_width()//2,h//2-80))
        for i,opt in enumerate(self._pause_options):
            c = (0,255,120) if i==self._pause_selection else (180,180,180)
            p = "> " if i==self._pause_selection else "  "
            t = self._pause_small.render(f"{p}{opt}",True,c)
            self.screen.blit(t,(w//2-t.get_width()//2,h//2-10+i*40))

    def _handle_pause_key(self, key):
        if key==pygame.K_UP:
            self._pause_selection=(self._pause_selection-1)%len(self._pause_options)
        elif key==pygame.K_DOWN:
            self._pause_selection=(self._pause_selection+1)%len(self._pause_options)
        elif key in(pygame.K_RETURN,pygame.K_SPACE):
            if self._pause_selection==0: self.paused=False
            elif self._pause_selection==1: self.running=False

    # ── Boucle ────────────────────────────────────────────────────────────
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000
            events = pygame.event.get()
            
            for event in events :
                if event.type == pygame.QUIT:
                    self.running = False

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.editor.active and self.editor._text_mode:
                            self.editor.handle_key(event.key)
                        else:
                            self.paused = not self.paused
                            self._pause_selection = 0
                        continue
                    if self.paused:
                        self._handle_pause_key(event.key); continue
                    if event.key == pygame.K_TAB:
                        self.inventory.changer_etat_fenetre()
                    if event.key == pygame.K_e and not (
                            self.editor.active and self.editor._text_mode):
                        self.editor.toggle()
                    elif self.editor.active:
                        result = self.editor.handle_key(event.key)
                        if result in ("done", "undo", "structure"):
                            self._rebuild_grid()
                            self._dirty_walls()

                if self.paused: continue

                if self.editor.active and self.editor._text_mode is None:
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            prev_plat_count = len(self.platforms)
                            self.editor.handle_click(event.pos)
                            # Rebuild grid seulement si les plateformes ont changé
                            if len(self.platforms) != prev_plat_count:
                                self._rebuild_grid()
                            self._dirty_walls()
                        elif event.button == 3:
                            prev_plat_count = len(self.platforms)
                            self.editor.handle_right_click(event.pos)
                            if len(self.platforms) != prev_plat_count:
                                self._rebuild_grid()
                            self._dirty_walls()
                    if event.type == pygame.MOUSEWHEEL:
                        self.editor.handle_scroll(event.y)

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
                    print(f"Monde x:{settings.wx} y:{settings.wy}")

            if self.paused:
                self._draw_pause(); pygame.display.flip(); continue

            # ── Mise à jour ───────────────────────────────────────────────
            keys = pygame.key.get_pressed()
            man_on(); x_y_man()

            holes     = self.editor.holes
            all_walls = self._all_walls()

            if self._fade_state == "none":
                self.player.mouvement(dt, keys, holes=holes)
            self.camera.update(self.player.rect)

            for enemy in self.enemies:
                enemy.update(dt, self.platforms, all_walls,
                             self.player.rect, holes=holes)

            check_attack_collisions(self.player, self.enemies)
            check_platform_collisions(self.player, self.platform_grid)
            if not self.editor.active:
                check_player_enemy_collisions(self.player, self.enemies)

            for wall in all_walls:
                wall.verifier_collision(self.player)

            self.lighting.update(dt)
            self._update_enemy_lights()
            self._check_portals()
            self._update_fade(dt)

            # ── Affichage ─────────────────────────────────────────────────
            bg = tuple(self.editor.bg_color)
            self.screen.fill(bg)

            for wall in self.editor.all_segments():
                if self.camera.is_visible(wall.rect):
                    wall.draw(self.screen, self.camera)

            for wall in self.editor.custom_walls:
                if self.camera.is_visible(wall.rect):
                    wall.draw(self.screen, self.camera)

            # Trous : redessine bg par-dessus les segments
            for hole in self.editor.holes:
                if self.camera.is_visible(hole):
                    hr = self.camera.apply(hole)
                    pygame.draw.rect(self.screen, bg, hr)
                    if self.editor.active and self.editor.show_hitboxes:
                        pygame.draw.rect(self.screen, (255,80,80), hr, 2)

            for platform in self.platforms:
                if self.camera.is_visible(platform.rect):
                    platform.draw(self.screen, self.camera)

            for enemy in self.enemies:
                if self.camera.is_visible(enemy.rect):
                    enemy.draw(self.screen, self.camera, self.editor.show_hitboxes)

            self.player.draw(self.screen, self.camera, self.editor.show_hitboxes)

            if self.editor.show_hitboxes or self.editor.active:
                font = self.editor._get_font()
                for portal in self.editor.portals:
                    portal.draw(self.screen, self.camera, font)

            if self.editor.active:
                self.editor.draw_overlays(self.screen)

            self.lighting.render(self.screen, self.camera, self.player.rect)

            if self.editor.active:
                draw_mouse_coords(self.screen, self.camera, y_start=110)
                self.editor.draw_preview(self.screen, pygame.mouse.get_pos())
                self.editor.draw_hud(self.screen, dt)

            fps_surf = self.fps_font.render(
                f"{self.clock.get_fps():.0f} FPS", True, (0,255,0))
            self.screen.blit(fps_surf,
                (self.screen.get_width()-fps_surf.get_width()-10,
                 self.screen.get_height()-25))
            if self.current_map_name:
                ms = self.fps_font.render(self.current_map_name, True, (180,180,180))
                self.screen.blit(ms, (10, self.screen.get_height()-25))

            self.inventory.draw(self.screen, 5, 6)
            self.inventory.drag_drop(events)

            self._draw_fade()
            pygame.display.flip()
