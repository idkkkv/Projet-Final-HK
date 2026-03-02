import pygame, random
from pygame.locals import *

#-----------CONSTANTES-----------

BLEU = (98, 143, 217)
ROUGE = (217, 108, 98)
GRIS = (178, 171, 184)
VIOLET = (38, 19, 46)
BLANC = (255, 255, 255)

WIDTH, HEIGHT = 800, 640

#-----------PERSONNAGES-----------

class Player :
    def __init__(self, pos):
        self.rect = Rect(pos[0], pos[1], 32, 32) #x, y, width, height
        self.vx = 0
        self.vy = 0
        self.gravity = 1200
        self.puissance_saut = 600 
        self.speed = 300
        self.on_ground = True

    def mouvement(self, dt, keys):
        if keys[K_d]:  #D
            self.vx = self.speed
        elif keys[K_q]:  #Q
            self.vx = -self.speed
        else:
            self.vx = 0

        self.vy += self.gravity * dt

        if keys[K_SPACE] and self.on_ground: #Space 
            self.vy = -self.puissance_saut
            self.on_ground = False
        
        self.rect.x += self.vx * dt
        self.rect.y += self.vy * dt

        if self.rect.bottom > 600:
            self.rect.bottom = 600
            self.vy = 0
            self.on_ground = True

    def draw(self, surf):
        pygame.draw.rect(surf, BLANC, self.rect)  # Personnage (le carré blanc)

#-----------PRINCIPAL-----------
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("kjurhebfdskhb :D")
        self.running = True
        self.clock = pygame.time.Clock()

        self.player = Player((400, 500)) #position de départ 

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000  # 60 FPS max 
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
            
            keys = pygame.key.get_pressed()
            self.player.mouvement(dt, keys)
            
            self.screen.fill(VIOLET) 
            self.player.draw(self.screen)
            pygame.display.flip()

if __name__ == "__main__":
    game = Game()
    game.run()