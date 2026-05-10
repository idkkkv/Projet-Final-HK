import cv2
import pygame
import time
from utils import find_file
import threading

import ui.inventory as inventory
from ui.inventory import ITEMS

def play_cassette(visuel, sonore, screen):
    if not pygame.mixer.get_init():
        pygame.mixer.init()

    if isinstance(sonore, list):
        sonore = sonore[0]

    path_son = find_file(sonore)
    path_video = find_file(visuel)
    
    try:
        pygame.mixer.music.load(path_son)
        pygame.mixer.music.set_volume(1.0)
        pygame.mixer.music.play()
    except Exception as e:
        print(f"Erreur audio : {e}")

    cap = cv2.VideoCapture(path_video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    clock = pygame.time.Clock()
    sw, sh = screen.get_size()
    playing = True

    while playing and cap.isOpened():
        ret, img = cap.read()

        if not ret: 
            break
        
        # Full screen
        frame_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        vh, vw = frame_rgb.shape[:2]
        scale = min(sw / vw, sh / vh)
        nw, nh = int(vw * scale), int(vh * scale)
        frame_resized = cv2.resize(frame_rgb, (nw, nh))

        surf = pygame.surfarray.make_surface(frame_resized.transpose(1, 0, 2))
        
        # Center
        screen.fill((0, 0, 0)) # Fond noir
        screen.blit(surf, ((sw - nw) // 2, (sh - nh) // 2))
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    playing = False
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()

        clock.tick(fps) 

    cap.release()
    pygame.mixer.music.stop()