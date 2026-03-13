# ─────────────────────────────────────────
#  ENTRE-DEUX — PNJ (personnages non-joueurs)
# ─────────────────────────────────────────

import pygame
from settings import *

class NPC:
    def __init__(self, x, y, dialogues):
        self.rect = pygame.Rect(x, y, 60, 80)
        self.dialogues = dialogues  # liste de strings
        self.dialogue_index = 0

    def interact(self):
        if self.dialogue_index < len(self.dialogues):
            line = self.dialogues[self.dialogue_index]
            self.dialogue_index += 1
            return line
        return None  # Plus rien à dire

    # À compléter : affichage, animation, détection de proximité
