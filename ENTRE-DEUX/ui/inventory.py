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

ITEMS = {
    "Pomme": {
        "category":   "Consommable",
        "image":      "pomme.png",
        # Stackable : un seul slot accumule un compteur.
        # Effet de consommation : +heal_hp PV à l'utilisation rapide.
        "stackable":  True,
        "max_stack":  99,
        "consumable": True,
        "heal_hp":    2,
    },
    "Cassette": {
        "category":   "Matériel",
        "image":      "cassette.png",
        "contenu visuel": "video_cassette.mp4",
        "contenu sonore": "video_cassette.mp3",
        "stackable":  False,
    },
    "CleJaune": {
        "category": "Matériel",
        "image": "keys.png"
    },
    "CleRouge": {
        "category": "Matériel",
        "image": "keyspink.png"
    },
    "CleBleue": {
        "category": "Matériel",
        "image": "keysblue.png"
    },
    "Epee": {
        "category": "Équipement",
        "image": "epee.png",
        "actif": False
    },
    "Bouclier": {
        "category": "Équipement",
        "image": "bouclier.png",
        "actif": False
    }
}

CATEGORIES = ["Consommable", "Équipement", "Matériel"]

VITESSE_ANIMATION = 0.2 # 0 à 1, + grand = + rapide
VITESSE_DEFILEMENT_PAGE = 0.2

class InventoryItem:
    """Item d'inventaire stackable.

    count       — quantité dans ce slot (>=1 ; 0 = à supprimer)
    stackable   — True : peut accumuler plusieurs unités sur 1 slot
                  False : 1 unité = 1 slot (ex. Cassette)
    max_stack   — borne supérieure du compteur (Pomme : 99)
    """
    def __init__(self, name, image, category="Consommable",
                 count=1, stackable=False, max_stack=1):
        self.name      = name
        self.image     = image
        self.category  = category
        self.count     = max(1, int(count))
        self.stackable = bool(stackable)
        self.max_stack = max(1, int(max_stack))

class ItemContainer:
    # liste de slots pour stocker les items
    def __init__(self, size):
        self.slots = [None] * size

    def add_item(self, item):
        """Ajoute un item à l'inventaire.

        Si l'item est stackable et qu'un slot existant contient déjà le
        même nom (et n'est pas plein), on incrémente le compteur. Sinon
        on cherche un slot libre.

        Retour : True ajouté, False inventaire plein.
        """
        # 1) tentative de stack sur un slot existant
        if getattr(item, "stackable", False):
            for s in self.slots:
                if (s is not None and s.name == item.name
                        and s.stackable and s.count < s.max_stack):
                    place = s.max_stack - s.count
                    pris  = min(place, item.count)
                    s.count    += pris
                    item.count -= pris
                    if item.count <= 0:
                        return True
        # 2) sinon, slot libre
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
    
    def utiliser(self, name):
        """utilise l'item mais ne la retire pas"""
        for s in self.slots:
            if s is not None and s.name == name:
                return True
        return False

    def consommer(self, name, n=1):
        """Retire n unités d'un item nommé (cumule sur tous les slots).

        Renvoie True si on a pu retirer la totalité, False si pas assez
        (et dans ce cas on ne retire rien — atomique)."""
        # Compte la quantité dispo
        total = 0
        for s in self.slots:
            if s is not None and s.name == name:
                total += s.count
        if total < n:
            return False
        # Retire effectivement
        restant = n
        for i, s in enumerate(self.slots):
            if restant <= 0:
                break
            if s is not None and s.name == name:
                pris = min(s.count, restant)
                s.count -= pris
                restant -= pris
                if s.count <= 0:
                    self.slots[i] = None
        return True

    def quantite(self, name):
        """Quantité totale d'un item donné (somme sur tous les slots)."""
        return sum(s.count for s in self.slots
                   if s is not None and s.name == name)

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
        self.drag_start_pos = (0, 0)

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

        # ── images des items ─────────────────
        self.images = {}

        for name, data in ITEMS.items():
            img = pygame.image.load(find_file(data["image"])).convert_alpha()
            self.images[name] = pygame.transform.scale(
                img, (self.slot_size - 10, self.slot_size - 10)
            )

        # ── items effects ────────────────────
        self.cassette_a_jouer = None
        self.epee_active = False
        self.bouclier_actif = False

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

    def add_item(self, objet, count=1):
        """ajoute un item à l'inventaire (stack auto si stackable)."""

        data = ITEMS[objet]  # objet = "Pomme"

        item = InventoryItem(
            objet, self.images[objet], data["category"],
            count=count,
            stackable=bool(data.get("stackable", False)),
            max_stack=int(data.get("max_stack", 1)),
        )

        return super().add_item(item)

    # ─────────────────────────────────────────
    # DRAG & DROP + INTERACTIONS
    # ─────────────────────────────────────────

    def drag_drop(self, events):
        """Gère les clics pour drag/drop dans l'inventaire"""
        if not self.open:
            return
        #miam pour marquer jusqu'ou faire retour
        
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
                            self.drag_start_pos = event.pos
                            self.dragging_pos = event.pos
                            self.slots[i] = None #vide le slot
                        break
                
            # ── déplacer drag ──────────────────────────────
            if event.type == pygame.MOUSEMOTION :
                if self.dragging_item is not None:
                    self.dragging_pos = event.pos

            # ── drop ──────────────────────────────────────
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1 :
                if self.dragging_item is not None:

                    dx = event.pos[0] - self.drag_start_pos[0]
                    dy = event.pos[1] - self.drag_start_pos[1]
                    moved = abs(dx) > 5 or abs(dy) > 5

                    if not moved:
                        # video cassette
                        if self.dragging_item.name == "Cassette":
                            data = ITEMS[self.dragging_item.name]
                            self.cassette_a_jouer = (data["contenu visuel"], data["contenu sonore"])
                            self.slots[self.dragging_index] = self.dragging_item
                            self.dragging_item = None
                            return
                        
                        # Epee
                        if self.dragging_item.name == "Epee":
                            self.epee_active = not self.epee_active

                        if self.dragging_item.name == "Bouclier":
                            self.bouclier_actif = not self.bouclier_actif

                        self.slots[self.dragging_index] = self.dragging_item
                        self.dragging_item = None
                        return
                        
                    placed = False
                    for i, rect in enumerate(self.slot_rects):
                        if rect and rect.collidepoint(event.pos):
                            self.slots[self.dragging_index] = self.slots[i]
                            self.slots[i] = self.dragging_item
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

            x = self.inv_x + int(self.slide_offset) + self.slot_margin + col * (self.slot_size + self.slot_margin)
            y = self.inv_y + 80 + self.slot_margin + row * (self.slot_size + self.slot_margin)

            rect = pygame.Rect(x, y, self.slot_size, self.slot_size)
            self.slot_rects[i] = rect

            local_x = x - self.inv_x - int(self.slide_offset)
            local_y = y - self.inv_y
            local_rect = pygame.Rect(local_x, local_y, self.slot_size, self.slot_size)

            # couleur slot dépend si vide ou plein
            if item is not None:
                slot_color, border_color = (180, 150, 80), (220, 190, 100)
            else:
                slot_color, border_color = (50, 65, 90), (70, 90, 120)
                
            pygame.draw.rect(surface, slot_color, local_rect)
            pygame.draw.rect(surface, border_color, local_rect, 2)

            if item is not None:
                img_rect = item.image.get_rect(center=local_rect.center)
                surface.blit(item.image, img_rect)
                # Compteur en bas-droite si stackable et > 1
                if getattr(item, "stackable", False) and item.count > 1:
                    fnt = pygame.font.SysFont("Consolas", 14, bold=True)
                    txt = fnt.render(f"x{item.count}", True, (255, 255, 255))
                    # Ombre noire pour lisibilité.
                    sh  = fnt.render(f"x{item.count}", True, (0, 0, 0))
                    bx = local_rect.right - txt.get_width() - 4
                    by = local_rect.bottom - txt.get_height() - 2
                    surface.blit(sh,  (bx + 1, by + 1))
                    surface.blit(txt, (bx, by))

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

        # drag drop
        if self.dragging_item:
            drag_surface = self.dragging_item.image.copy()
            drag_surface.set_alpha(180)
            drag_rect = drag_surface.get_rect(center=self.dragging_pos)
            screen.blit(drag_surface, drag_rect)