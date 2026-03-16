# ─────────────────────────────────────────
#  ENTRE-DEUX — Inventaire (la Cape + les Lueurs)
# ─────────────────────────────────────────

import pygame
from settings import *
from utils import find_file


class InventoryItem:
    def __init__(self, name, image):
        self.name = name
        self.image = image


class Inventory:
    def __init__(self):
        self.inventory_slots = [None] * 6  # 6 emplacements
        self.slot_size = 64
        self.slot_margin = 10
        self.open = False

        pomme = pygame.image.load(find_file("pomme.png")).convert_alpha()
        self.pomme_image = pygame.transform.scale(pomme, (self.slot_size - 10, self.slot_size - 10))
        self.nb_pommes = 0

    def changer_etat_fenetre(self):
        """Ouvre ou ferme l'inventaire"""
        self.open = not self.open

    def is_open(self):
        """Inventaire ouvert ou pas"""
        return self.open

    def add_item(self, item):
        """Ajoute un item à l'inventaire
        True = ajouté
        False = inventaire plein"""
        for i in range(len(self.inventory_slots)):
            if self.inventory_slots[i] is None:
                self.inventory_slots[i] = item
                return True
        return False

    def add_pomme(self):
        """ajoute une pomme à l'inventaire"""
        item = InventoryItem("Pomme", self.pomme_image)
        if self.add_item(item):
            self.nb_pommes += 1
            return True
        return False

    def remove_item(self, index):
        """Retire un item de l'inventaire à un index donné"""
        if 0 <= index < len(self.inventory_slots) and self.inventory_slots[index] is not None:
            self.inventory_slots[index] = None
            return True
        return False

    def draw(self, screen):
        """Affiche l'inventaire"""
        if not self.open:
            return 

        w, h = screen.get_size()
        inv_w = min(3 * self.slot_size + 4 * self.slot_margin, w) #3 colonnes + 4 marges
        inv_h = min(2 * self.slot_size + 4 * self.slot_margin + 30, h) #2 lignes + 4 marges
        inv_x = (w - inv_w) // 2 #centre la fenetre sur l'ecran
        inv_y = (h - inv_h) // 2 + 20

        overlay = pygame.Surface((inv_w, inv_h), pygame.SRCALPHA) #pygame.SRCALPHA pour activer la transparence
        overlay.fill((30, 30, 40, 220)) #couleur, opacité
        pygame.draw.rect(overlay, (200, 200, 200), (0, 0, inv_w, inv_h), 2)
        screen.blit(overlay, (inv_x, inv_y))

        title = pygame.font.SysFont("Consolas", 24).render("Inventaire ;D", True, BLANC)
        screen.blit(title, (inv_x + (inv_w - title.get_width()) // 2, inv_y + 8))

        for i in range(len(self.inventory_slots)):
            col = i % 3
            row = i // 3

            slot_x = inv_x + self.slot_margin + col * (self.slot_size + self.slot_margin)
            slot_y = inv_y + 40 + self.slot_margin + row * (self.slot_size + self.slot_margin)

            pygame.draw.rect(screen, (100, 100, 120), (slot_x, slot_y, self.slot_size, self.slot_size)) 
            pygame.draw.rect(screen, (180, 180, 200), (slot_x, slot_y, self.slot_size, self.slot_size), 2)

            if self.inventory_slots[i] is not None:
                item_image = self.inventory_slots[i].image
                img_rect = item_image.get_rect(center=(slot_x + self.slot_size // 2, slot_y + self.slot_size // 2)) #get_rect(center=..) pour centrer l'image dans le slot
                screen.blit(item_image, img_rect)

