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


# ═════════════════════════════════════════════════════════════════════════════
#  1. ITEM (mini-classe : juste un nom + une image)
# ═════════════════════════════════════════════════════════════════════════════

class InventoryItem:
    """Un item d'inventaire = un nom (str) + une image (pygame.Surface)."""

    def __init__(self, name, image):
        self.name  = name
        self.image = image


# ═════════════════════════════════════════════════════════════════════════════
#  2. INVENTAIRE (grille de slots + drag-drop)
# ═════════════════════════════════════════════════════════════════════════════

class Inventory:
    """Inventaire 30 slots avec drag & drop."""

    def __init__(self):
        # 30 emplacements, chacun pouvant contenir None ou un InventoryItem.
        self.inventory_slots = [None] * 30

        # Géométrie d'un slot (en pixels)
        self.slot_size   = 64    # côté du carré
        self.slot_margin = 10    # gap entre deux slots et avec le bord

        # État d'affichage / interaction
        self.open            = False
        self.dragging_index  = None    # slot d'origine de l'item en cours de drag
        self.dragging_item   = None    # item en cours de drag (ou None)
        self.dragging_pos    = (0, 0)  # position souris pendant le drag

        # Rectangles des slots — recalculés à chaque draw, utilisés par
        # drag_drop() pour savoir si un clic tombe sur un slot.
        self.slot_rects = [None] * len(self.inventory_slots)

        # ── Pré-chargement des images d'items ────────────────────────────────
        # On scale ici pour ne pas avoir à le refaire à chaque draw.
        # find_file() (utils.py) cherche le fichier dans assets/images/.
        pomme = pygame.image.load(find_file("pomme.png")).convert_alpha()
        self.pomme_image = pygame.transform.scale(
            pomme, (self.slot_size - 10, self.slot_size - 10)
        )
        self.nb_pommes = 0   # compteur pour l'UI / les statistiques

    # ═════════════════════════════════════════════════════════════════════════
    #  3. OUVERTURE / FERMETURE
    # ═════════════════════════════════════════════════════════════════════════

    def changer_etat_fenetre(self):
        """Bascule l'inventaire ouvert ↔ fermé (touche Tab)."""
        self.open = not self.open

    def is_open(self):
        """True si l'inventaire est actuellement ouvert."""
        return self.open

    # ═════════════════════════════════════════════════════════════════════════
    #  4. AJOUT / SUPPRESSION D'ITEMS
    # ═════════════════════════════════════════════════════════════════════════

    def add_item(self, item):
        """Ajoute un item dans le premier slot vide.

        Renvoie True si ajouté, False si l'inventaire est plein."""

        for i in range(len(self.inventory_slots)):
            if self.inventory_slots[i] is None:
                self.inventory_slots[i] = item
                return True
        return False

    def add_pomme(self):
        """Ajoute une pomme à l'inventaire (et incrémente le compteur)."""
        item = InventoryItem("Pomme", self.pomme_image)
        if self.add_item(item):
            self.nb_pommes += 1
            return True
        return False

    def remove_item(self, index):
        """Retire l'item à l'index donné. Renvoie True si quelque chose a été retiré."""
        if 0 <= index < len(self.inventory_slots) and self.inventory_slots[index] is not None:
            self.inventory_slots[index] = None
            return True
        return False

    # ═════════════════════════════════════════════════════════════════════════
    #  5. DRAG & DROP (clic gauche pour attraper, déplacer, lâcher)
    # ═════════════════════════════════════════════════════════════════════════

    def drag_drop(self, events):
        """Gère les clics pour drag/drop dans l'inventaire.

        Reçoit la liste d'events de la frame (pas un seul event) car il
        faut potentiellement consommer plusieurs events dans la même frame
        (ex : MOUSEBUTTONDOWN suivi d'un MOUSEMOTION)."""

        # Garde-fous : inventaire fermé ou pas encore dessiné une fois
        # (slot_rects pas encore initialisés) → on ne fait rien.
        if not self.open or None in self.slot_rects:
            return

        for event in events:

            # ── Appui sur le clic gauche → on attrape l'item du slot cliqué ──
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, rect in enumerate(self.slot_rects):
                    if rect and rect.collidepoint(event.pos):
                        if self.inventory_slots[i] is not None:
                            self.dragging_index = i                       # index d'origine
                            self.dragging_item  = self.inventory_slots[i] # ce qu'on tient
                            self.inventory_slots[i] = None                # vide le slot
                        break  # un seul slot peut être cliqué — on sort

            # ── Mouvement souris pendant un drag → on suit le curseur ────────
            elif event.type == pygame.MOUSEMOTION:
                if self.dragging_item is not None:
                    self.dragging_pos = event.pos

            # ── Relâchement du clic → on dépose l'item ───────────────────────
            elif (event.type == pygame.MOUSEBUTTONUP
                  and event.button == 1
                  and self.dragging_item is not None):
                placed = False
                # Le curseur est-il sur un slot ?
                for i, rect in enumerate(self.slot_rects):
                    if rect and rect.collidepoint(event.pos):
                        # Note : si le slot cible est plein, on l'écrase
                        # (l'item d'origine est perdu). À améliorer si on
                        # veut un swap d'items.
                        self.inventory_slots[i] = self.dragging_item
                        placed = True
                        break

                # Pas de slot sous le curseur → on remet l'item à sa place.
                if not placed:
                    self.inventory_slots[self.dragging_index] = self.dragging_item

                # Reset de l'état de drag
                self.dragging_index = None
                self.dragging_item  = None

    # ═════════════════════════════════════════════════════════════════════════
    #  6. RENDU (overlay + slots + drag visuel)
    # ═════════════════════════════════════════════════════════════════════════

    def draw(self, screen, colonnes, lignes):
        """Dessine l'inventaire si ouvert.

        colonnes / lignes : forme de la grille à afficher (ex : 6 × 5 = 30)."""

        if not self.open:
            return

        w, h = screen.get_size()

        # ── Dimensions et position de la fenêtre (centrée à l'écran) ─────────
        # +50 = espace pour le titre "ITEMS" en haut.
        inv_w = min(colonnes * self.slot_size + (colonnes + 1) * self.slot_margin, w)
        inv_h = min(lignes   * self.slot_size + (lignes   + 1) * self.slot_margin + 50, h)
        inv_x = (w - inv_w) // 2
        inv_y = (h - inv_h) // 2

        # ── Fond semi-transparent + bordure ──────────────────────────────────
        # SRCALPHA pour pouvoir mettre un alpha (220 ≈ 86 % d'opacité).
        overlay = pygame.Surface((inv_w, inv_h), pygame.SRCALPHA)
        overlay.fill((30, 30, 40, 220))
        pygame.draw.rect(overlay, (200, 200, 200), (0, 0, inv_w, inv_h), 2)
        screen.blit(overlay, (inv_x, inv_y))

        # ── Titre "ITEMS" centré en haut ─────────────────────────────────────
        title = pygame.font.SysFont("Consolas", 24).render("ITEMS", True, BLANC)
        screen.blit(title, (inv_x + (inv_w - title.get_width()) // 2, inv_y + 8))

        # ── Slots (boucle sur les 30 emplacements) ───────────────────────────
        for i in range(len(self.inventory_slots)):
            # Coordonnées (col, row) à partir de l'index linéaire.
            col = i % colonnes
            row = i // colonnes

            slot_x = inv_x + self.slot_margin + col * (self.slot_size + self.slot_margin)
            slot_y = inv_y + 40 + self.slot_margin + row * (self.slot_size + self.slot_margin)

            # On stocke le rect → drag_drop l'utilisera au prochain clic.
            self.slot_rects[i] = pygame.Rect(slot_x, slot_y, self.slot_size, self.slot_size)

            # Couleurs différentes pour slot vide / plein → repère visuel.
            if self.inventory_slots[i] is not None:
                slot_color   = (180, 150,  80)   # plein : doré
                border_color = (220, 190, 100)
            else:
                slot_color   = ( 50,  65,  90)   # vide : bleu sombre
                border_color = ( 70,  90, 120)

            pygame.draw.rect(screen, slot_color,   self.slot_rects[i])
            pygame.draw.rect(screen, border_color, self.slot_rects[i], 2)

            # Image de l'item s'il est présent (centrée dans le slot).
            if self.inventory_slots[i] is not None:
                item_image = self.inventory_slots[i].image
                # get_rect(center=...) = rectangle de l'image centré sur ce point.
                img_rect = item_image.get_rect(center=(slot_x + self.slot_size // 2,
                                                       slot_y + self.slot_size // 2))
                screen.blit(item_image, img_rect)

        # ── Visuel pendant le drag (image qui suit le curseur) ───────────────
        if self.dragging_item is not None:
            # On copie l'image pour ne pas modifier l'alpha de l'original
            # (sinon l'image deviendrait définitivement semi-transparente).
            drag_surface = self.dragging_item.image.copy()
            drag_surface.set_alpha(180)
            drag_rect = drag_surface.get_rect(center=self.dragging_pos)
            screen.blit(drag_surface, drag_rect)
