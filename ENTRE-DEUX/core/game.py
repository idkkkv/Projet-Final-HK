# ─────────────────────────────────────────
#  ENTRE-DEUX — Boucle principale du jeu
# ─────────────────────────────────────────

import pygame
from settings import *
from core.camera import Camera
from entities.player import Player
from entities.enemy import Enemy
from world.tilemap import Platform
from world.collision import check_attack_collisions, check_platform_collisions

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption(TITLE)
        self.running = True
        self.clock = pygame.time.Clock()

        self.player = Player((100, 320))
        self.camera = Camera(SCENE_WIDTH, SCENE_HEIGHT)
        self.enemies = [Enemy(500, 530 - 60)]
        self.platforms = [
            Platform(200, 500, 100, 20, BLANC),
            Platform(300, 400, 100, 20, GRIS),
            Platform(400, 300, 100, 20, BLEU),
        ]

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000

            # Événements
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

            # Mise à jour
            keys = pygame.key.get_pressed()
            self.player.mouvement(dt, keys)
            self.camera.update(self.player.rect)


            for enemy in self.enemies:
                enemy.update(dt)

            check_attack_collisions(self.player, self.enemies)
            check_platform_collisions(self.player, self.platforms)

            # Affichage
            self.screen.fill(VIOLET)

            for platform in self.platforms:
                if self.camera.is_visible(platform.rect):
                    platform.draw(self.screen, self.camera)

            for enemy in self.enemies:
                if self.camera.is_visible(enemy.rect):
                    enemy.draw(self.screen, self.camera)

            self.player.draw(self.screen, self.camera)

            pygame.display.flip()
