# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Inventaire
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Une grille de slots (par défaut 30) qu'on ouvre avec [Tab] pour voir
#  ce qu'on a ramassé (pour l'instant : des pommes). Le joueur peut
#  draguer-déposer un item pour le déplacer d'un slot à l'autre.
#
#  Chaque slot contient soit None (vide), soit un InventoryItem.
#  InventoryItem est une mini-classe qui n'a que deux champs : name, image.
#  ItemContainer est une classe de base qui gère les fonctions basiques des items (add/remove)
#  Inventory hérite de ItemContainer et ajoute la logique d'affichage, d'animation, de drag & drop, etc.
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  core/game.py crée l'inventaire :
#       self.inventory = Inventory()
#  La touche [Tab] appelle self.inventory.changer_etat_fenetre().
#  Quand le joueur passe sur une pomme dans la map → self.inventory.add_pomme().
#
#  Chaque frame, si l'inventaire est ouvert :
#       self.inventory.drag_drop(events)              # gère les clics
#       self.inventory.draw(screen, colonnes, lignes) # rend la grille
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Nombre de slots         → [None] * 30 dans __init__
#     - Taille / espacement     → self.slot_size / self.slot_margin
#     - Couleurs des slots      → littéraux RGB dans draw()
#     - Ajouter un nouvel item  → méthode add_X (sur le modèle de add_pomme)
#                                  + image chargée dans __init__
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D1]  pygame.Surface       — overlay semi-transparent
#     [D2]  SRCALPHA             — transparence du fond
#     [D3]  blit                 — collage des images d'items
#     [D4]  pygame.Rect          — slot_rects pour détecter les clics
#     [D5]  collidepoint         — quel slot est cliqué ?
#     [D6]  pygame.draw.rect     — fond et bordure des slots
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame
from settings import *
from utils import find_file

CATEGORIES = ["Consommable", "Équipement", "Matériel"]

VITESSE_ANIMATION = 0.2 # 0 à 1, + grand = + rapide
VITESSE_DEFILEMENT_PAGE = 0.2

class InventoryItem:
    # item = nom + image + catégorie
    def __init__(self, name, image, category="Consommable"):
        self.name = name
        self.image = image
        self.category = category

class ItemContainer:
    # liste de slots pour stocker les items
    def __init__(self, size):
        self.slots = [None] * size

    def add_item(self, item):
        """Ajoute un item à l'inventaire
        True = ajouté
        False = inventaire plein"""
        for i in range(len(self.slots)):
            if self.slots[i] is None:
                self.slots[i] = item
                return True
        return False

    def remove_item(self, index):
        """Retire un item de l'inventaire à un index donné"""
        if 0 <= index < len(self.slots) and self.slots[index] is not None:
            self.slots[index] = None
            return True
        return False

class Inventory(ItemContainer):
    def __init__(self):
        super().__init__(30) # 30 slots

        # ── UI GRID ─────────────────────────
        self.slot_size = 64 # taille des slots
        self.slot_margin = 10 # marge entre les slots

        # ── état inventaire ─────────────────
        self.open = False 

        # ── drag & drop ─────────────────────
        self.dragging_index = None 
        self.dragging_item = None
        self.dragging_pos = (0, 0)
        self.slot_rects = [None] * 30

        # ── filtre catégorie ────────────────
        self.categorie_actuelle = 0 # 0 = Consommable, 1 = Équipement, 2 = Matériel

        # ── position interface globale ──────
        self.inv_x = 0
        self.inv_y = 0
        
        # ── animation ───────────────────────
        self.slide_offset = 0.0   # position debut
        self.slide_target = 0.0   # position fin
        self.is_sliding = False
        self.inv_w = 0            # largeur de l'inventaire
        self.tab_rects = []       # rectangles des onglets pour détection clics

        # ──  item ────────────────────────
        pomme = pygame.image.load(find_file("pomme.png")).convert_alpha()
        self.pomme_image = pygame.transform.scale(pomme, (self.slot_size - 10, self.slot_size - 10))
        self.nb_pommes = 0

    # ─────────────────────────────────────────
    # LOGIQUE INVENTAIRE
    # ─────────────────────────────────────────

    def filtrer_par_categorie(self, category):
        """Retourne les items de l'inventaire qui appartiennent à une catégorie donnée"""
        result = []
        for item in self.slots :
            if item is not None and item.category == category:
                result.append(item)
        return result
    
    def changer_categorie(self, nouvelle_categorie, direction):
        """Change la catégorie active (0, 1 ou 2)"""
        if self.categorie_actuelle == nouvelle_categorie :
            return
        
        self.categorie_actuelle = nouvelle_categorie
        self.slide_offset = float(self.inv_w) * direction  # commence hors écran
        self.slide_target = 0.0
        self.is_sliding = True

    def changer_etat_fenetre(self):
        """Ouvre ou ferme l'inventaire"""
        self.open = not self.open

    def is_open(self):
        """Inventaire ouvert ou pas"""
        return self.open

    def add_pomme(self):
        """ajoute une pomme à l'inventaire"""
        item = InventoryItem("Pomme", self.pomme_image)
        if self.add_item(item):
            self.nb_pommes += 1
            return True
        return False

    # ─────────────────────────────────────────
    # DRAG & DROP + INTERACTIONS
    # ─────────────────────────────────────────

    def drag_drop(self, events):
        """Gère les clics pour drag/drop dans l'inventaire"""
        if not self.open:
            return
        
        for event in events:
            # ── clic sur onglets ──────────────────────────
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, rect in enumerate(self.tab_rects):
                    if rect and rect.collidepoint(event.pos):
                        direction = 1 if i > self.categorie_actuelle else -1
                        self.changer_categorie(i, direction)
                        return
            
            # ── drag ──────────────────────────────────────
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, rect in enumerate(self.slot_rects):
                    if rect and rect.collidepoint(event.pos): #clic sur un slot
                        if self.slots[i] is not None:
                            self.dragging_index = i #index
                            self.dragging_item = self.slots[i] #item
                            self.slots[i] = None #vide le slot
                        break
                
            # ── déplacer drag ──────────────────────────────
            if event.type == pygame.MOUSEMOTION :
                if self.dragging_item is not None:
                    self.dragging_pos = event.pos

            # ── drop ──────────────────────────────────────
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging_item is not None:
                placed = False
                for i, rect in enumerate(self.slot_rects):
                    if rect and rect.collidepoint(event.pos):
                        self.slots[i], self.dragging_item = self.dragging_item, self.slots[i]
                        placed = True
                        break
                if not placed:
                    self.slots[self.dragging_index] = self.dragging_item

                self.dragging_index = None
                self.dragging_item = None

    # ─────────────────────────────────────────
    # DRAW + ANIMATION
    # ─────────────────────────────────────────

    def draw_grille(self, surface, cols, rows):
        """Affiche la grille filtrée"""
        self.slot_rects = [None] * len(self.slots)
        cat = CATEGORIES[self.categorie_actuelle]

        # filtrer les items à afficher selon la catégorie active (les autres = None)
        slots_affichage = []
        for item in self.slots:
            if item is None or item.category == cat:
                slots_affichage.append(item)
            else:
                slots_affichage.append(None)

        for i, item in enumerate(slots_affichage):
            col = i % cols
            row = i // cols

            if row >= rows:
                break

            x = self.slot_margin + col * (self.slot_size + self.slot_margin)
            y = 80 + self.slot_margin + row * (self.slot_size + self.slot_margin)

            rect = pygame.Rect(x, y, self.slot_size, self.slot_size)
            self.slot_rects[i] = rect

            # couleur slot dépend si vide ou plein
            if item is not None:
                slot_color, border_color = (180, 150, 80), (220, 190, 100)
            else:
                slot_color, border_color = (50, 65, 90), (70, 90, 120)

            pygame.draw.rect(surface, slot_color, rect)
            pygame.draw.rect(surface, border_color, rect, 2)

            if item is not None:
                img_rect = item.image.get_rect(center=rect.center)
                surface.blit(item.image, img_rect)
        
    def update_rects(self, cols, rows):
        """met à jour les rectangles de chaque slot en fonction de la catégorie active et de la grille"""
        for i in range(len(self.slots)):

            col = i % cols
            row = i // cols

            if row >= rows:
                self.slot_rects[i] = None
                continue

            x = self.inv_x + self.slot_margin + col * (self.slot_size + self.slot_margin)
            y = self.inv_y + 80 + self.slot_margin + row * (self.slot_size + self.slot_margin)

            self.slot_rects[i] = pygame.Rect(x, y, self.slot_size, self.slot_size)

    def draw_bg(self, screen, cols, rows):
        """Affiche le fond de l'inventaire (cadre + arrière-plan)"""
        self.inv_w = cols * self.slot_size + (cols + 1) * self.slot_margin
        self.inv_h = rows * self.slot_size + (rows + 1) * self.slot_margin + 100

        overlay = pygame.Surface((self.inv_w, self.inv_h), pygame.SRCALPHA)
        overlay.fill((30, 30, 40, 220))

        pygame.draw.rect(overlay, (200, 200, 200), (0, 0, self.inv_w, self.inv_h), 2)

        screen.blit(overlay, (self.inv_x, self.inv_y))
        
    def draw_title(self, screen):
        """Affiche le titre de l'inventaire"""

        title = pygame.font.SysFont("Consolas", 24).render("ITEMS", True, BLANC)

        screen.blit(title, (self.inv_x + (self.inv_w - title.get_width()) // 2, self.inv_y + 8))

    def draw_tabs(self, screen):
        """Affiche les onglets de catégories en haut de l'inventaire"""
        TAB_H = 24
        TAB_Y = self.inv_y + 40
        tab_w = self.inv_w // len(CATEGORIES)

        font = pygame.font.SysFont("Consolas", 14)

        self.tab_rects = []

        for i, cat in enumerate(CATEGORIES):

            x = self.inv_x + i * tab_w
            rect = pygame.Rect(x, TAB_Y, tab_w, TAB_H)
            self.tab_rects.append(rect)

            bg = (60,60,80) if i == self.categorie_actuelle else (45,45,60)

            pygame.draw.rect(screen, bg, rect)

            color = (255,255,255) if i == self.categorie_actuelle else (180,180,200)

            text = font.render(cat, True, color)

            screen.blit(text, (
                x + (tab_w - text.get_width()) // 2,
                TAB_Y + (TAB_H - text.get_height()) // 2
            ))

    def draw(self, screen, cols, rows):
        """Affiche l'inventaire avec onglets et animation"""
        if not self.open:
            return 

        w, h = screen.get_size()

        self.inv_w = cols * self.slot_size + (cols + 1) * self.slot_margin
        self.inv_h = rows * self.slot_size + (rows + 1) * self.slot_margin + 100
        self.inv_x = (w - self.inv_w) // 2
        self.inv_y = (h - self.inv_h) // 2

        self.draw_bg(screen, cols, rows)
        self.draw_title(screen)
        self.draw_tabs(screen)
        
        #animation 
        if self.is_sliding:
            self.slide_offset += (self.slide_target - self.slide_offset) * VITESSE_DEFILEMENT_PAGE
            if abs(self.slide_offset - self.slide_target) < 1:
                self.slide_offset = 0.0
                self.is_sliding = False

        # grille
        grid = pygame.Surface((self.inv_w, self.inv_h), pygame.SRCALPHA)
        self.draw_grille(grid, cols, rows)
        screen.blit(grid, (self.inv_x + int(self.slide_offset), self.inv_y))

        for i, rect in enumerate(self.slot_rects):
            if rect is not None:
                self.slot_rects[i] = rect.move(self.inv_x, self.inv_y)

        # drag drop
        if self.dragging_item:
            drag_surface = self.dragging_item.image.copy()
            drag_surface.set_alpha(180)
            drag_rect = drag_surface.get_rect(center=self.dragging_pos)
            screen.blit(drag_surface, drag_rect)