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
    def __init__(self, pos=(0,0)):
        self.rect = Rect(pos[0], pos[1], 90, 104) #x, y, width, height
        self.vx = 0
        self.vy = 0
        self.gravity = 1500
        self.puissance_saut = 600 
        self.speed = 300
        self.on_ground = True  
        self.direction = 1
        self.attacking = False #indique si le joueur est en train d'attaquer
        self.attack_rect = pygame.Rect(0,0,40,40) #zone d'attaque
        self.attack_timer = 0 #temps pour la durée de l'attaque

        self.idle_anim = Animation([pygame.image.load("img/player_idle.png"), pygame.image.load("img/player_idle2.png")], img_dur=20)

        self.animations = {
            "idle" : pygame.image.load("img/player_idle.png"),
            "idle2" : pygame.image.load("img/player_idle2.png"),
            "shine" : pygame.image.load("img/player_shine.png")
        }

    def mouvement(self, dt, keys):
        if keys[K_d]:  #D
            self.vx = self.speed
            self.direction = 1
        elif keys[K_q]:  #Q
            self.vx = -self.speed
            self.direction = -1
        else:
            self.vx = 0

        self.vy += self.gravity * dt

        if keys[K_SPACE] and self.on_ground: #Space 
            self.vy = -self.puissance_saut
            self.on_ground = False
        
        self.rect.x += self.vx * dt
        self.rect.y += self.vy * dt

        if self.rect.bottom > 590: #Sol
            self.rect.bottom = 590
            self.vy = 0
            self.on_ground = True

        if keys[K_f] and not self.attacking:
            self.attacking = True
            self.attack_timer = 0.2

        if self.attacking:
            self.attack_timer -= dt

        if self.direction == 1:
            self.attack_rect.topleft = (self.rect.right, self.rect.y+20)
        else:
            self.attack_rect.topright = (self.rect.left, self.rect.y+20)

        if self.attack_timer <= 0:
            self.attacking = False

    def draw(self, surf):
        img = self.idle_anim.img() #L'animation de base du joueur
        self.idle_anim.update()

        if self.direction == -1:
            img = pygame.transform.flip(img, True, False) #Retourne l'image si le joueur regarde à gauche

        surf.blit(img, self.rect) #Dessine le joueur

        if self.attacking:
            pygame.draw.rect(surf, BLANC, self.attack_rect) 
        

#-----------OBSTACLES-----------

class Platform :
    def __init__(self, x, y, width, height, color):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
    def verifier_collision(self, player):
         if player.rect.colliderect(self.rect):
            if player.vy > 0 and player.rect.bottom <= self.rect.top + 15:
                player.rect.bottom = self.rect.top
                player.on_ground = True
                player.vy = 0
    def draw(self, surf):
        pygame.draw.rect(surf, self.color, self.rect)

class Enemy :
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 60, 60)
        self.vx = 120
        self.alive = True

    def update(self, dt):
        self.rect.x += self.vx * dt

        # change de direction s'il touche un bord
        if self.rect.left < 0 or self.rect.right > WIDTH:
            self.vx *= -1

    def draw(self, surf):
        if self.alive:
            pygame.draw.rect(surf, ROUGE, self.rect)

#-----------ANIMATIONS-----------

class Animation:
    def __init__(self, images, img_dur=5, loop=True):
        self.images = images
        self.loop = loop
        self.img_duration = img_dur
        self.done = False
        self.frame = 0

    def update(self):
        if self.loop:
            self.frame = (self.frame + 1) % (self.img_duration * len(self.images))
        else:
            self.frame = min(self.frame + 1, self.img_duration * len(self.images)-1)
            if self.frame >= self.img_duration * len(self.images) - 1:
                self.done = True

    def img(self):
        return self.images[int(self.frame / self.img_duration)]

#-----------PRINCIPAL-----------

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("kjurhebfdskhb :D")
        self.running = True
        self.clock = pygame.time.Clock()

        self.player = Player((100, 320)) #Position de départ 
        self.enemies = [Enemy(500, 530 - 60)] 

        self.platforms = [
            Platform(200, 500, 100, 20, BLANC),
            Platform(300, 400, 100, 20, GRIS),
            Platform(400, 300, 100, 20, BLEU)
            ] #x, y, width, height

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000  # 60 FPS max 
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

            keys = pygame.key.get_pressed()
            self.player.mouvement(dt, keys)

            for enemy in self.enemies: enemy.update(dt) #mettre à jour les ennemis

            for enemy in self.enemies: #collisions entre le joueur et les ennemis
                if enemy.alive and self.player.attacking:
                    if enemy.rect.colliderect(self.player.attack_rect):
                        enemy.alive = False

            for platform in self.platforms:
                platform.verifier_collision(self.player)
            self.screen.fill(VIOLET)

            for platform in self.platforms:
                platform.draw(self.screen)

            for enemy in self.enemies:
                enemy.draw(self.screen)

            self.player.draw(self.screen)

            pygame.display.flip()

if __name__ == "__main__":
    game = Game()
    game.run()