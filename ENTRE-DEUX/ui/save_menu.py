# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Menu de sauvegarde / chargement (multi-slots)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Affiche un overlay listant les slots de sauvegarde, en mode SAVE ou LOAD :
#
#       SAVE → l'utilisateur choisit un slot dans lequel ÉCRIRE la partie
#              en cours. Si le slot existe déjà, on demande confirmation.
#
#       LOAD → l'utilisateur choisit un slot existant à CHARGER. Slots
#              vides désactivés (rouges).
#
#  USAGE DANS game.py
#  ------------------
#       from ui.save_menu import SaveMenu
#
#       # Création (au démarrage)
#       self.save_menu = SaveMenu()
#
#       # Ouverture (depuis le menu pause)
#       self.save_menu.open(mode="save")  # ou "load"
#
#       # Chaque frame :
#       if self.save_menu.visible:
#           res = self.save_menu.handle_key(key)
#           if res:
#               # res = ("save", 2) ou ("load", 1) ou ("close", None)
#               ...
#
#       self.save_menu.update(dt)
#       self.save_menu.draw(screen)
#
#  Le menu se DESSINE PAR-DESSUS le jeu (semi-transparent), ne fige pas la
#  simulation (à game.py de gérer l'état pause si besoin).
# ─────────────────────────────────────────────────────────────────────────────

import pygame

from systems.save_system import (
    lister_saves, slot_existe, SLOTS_MANUELS,
    formater_temps_jeu, formater_date,
)


# ═════════════════════════════════════════════════════════════════════════════
#  CONSTANTES VISUELLES
# ═════════════════════════════════════════════════════════════════════════════

_BG_OVERLAY      = (10, 12, 20, 200)   # voile sombre semi-transparent
_PANEL_BG        = (24, 28, 40, 230)
_PANEL_BORDER    = (180, 190, 220)
_TEXT_COLOR      = (230, 235, 245)
_TEXT_DIM        = (140, 150, 170)
_TEXT_RED        = (220, 90,  100)
_SELECTION_BG    = (60, 80, 130, 200)
_SELECTION_LINE  = (160, 200, 255)
_CONFIRM_BG      = (50, 30, 30, 240)


class SaveMenu:
    """Overlay de sélection de slot pour sauvegarder / charger."""

    # ─── État ────────────────────────────────────────────────────────────────

    def __init__(self):
        self.visible        = False
        self.mode           = "save"     # "save" ou "load"
        self.selection      = 0          # index dans SLOTS_MANUELS (0..2)
        self._confirming    = False      # popup de confirmation d'écrasement
        self._slots_cache   = []         # mis à jour à chaque ouverture
        self._fonts         = None       # lazy init

    # ─── API publique ────────────────────────────────────────────────────────

    def open(self, mode="save"):
        """Affiche le menu. `mode` : "save" ou "load"."""
        if mode not in ("save", "load"):
            mode = "save"
        self.mode        = mode
        self.visible     = True
        self.selection   = 0
        self._confirming = False
        self._refresh()

    def close(self):
        self.visible     = False
        self._confirming = False

    def _refresh(self):
        """Re-lit les slots depuis le disque (après une sauvegarde)."""
        self._slots_cache = lister_saves()

    # ─── Update (animations futures, particules, etc.) ──────────────────────

    def update(self, dt):
        pass  # rien à animer pour l'instant

    # ─── Saisie clavier ─────────────────────────────────────────────────────

    def handle_key(self, key):
        """Gère les flèches + Entrée + Échap.

        Retourne :
            ("save", slot)   → l'utilisateur veut sauvegarder dans ce slot
            ("load", slot)   → l'utilisateur veut charger ce slot
            ("close", None)  → fermeture du menu
            None             → rien à faire
        """
        if not self.visible:
            return None

        # ── Confirmation d'écrasement (popup modale) ──
        if self._confirming:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_y):
                slot = SLOTS_MANUELS[self.selection]
                self._confirming = False
                self.visible     = False
                return (self.mode, slot)
            if key in (pygame.K_ESCAPE, pygame.K_n):
                self._confirming = False
            return None

        # ── Navigation ──
        if key == pygame.K_UP:
            self.selection = (self.selection - 1) % len(SLOTS_MANUELS)
            return None
        if key == pygame.K_DOWN:
            self.selection = (self.selection + 1) % len(SLOTS_MANUELS)
            return None

        # ── Échap → fermer ──
        if key == pygame.K_ESCAPE:
            self.visible = False
            return ("close", None)

        # ── Validation ──
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            slot = SLOTS_MANUELS[self.selection]
            if self.mode == "save":
                # Si le slot est déjà occupé, on demande confirmation.
                if slot_existe(slot):
                    self._confirming = True
                    return None
                self.visible = False
                return ("save", slot)
            else:  # load
                # On ne peut charger qu'un slot existant.
                if not slot_existe(slot):
                    return None
                self.visible = False
                return ("load", slot)

        return None

    # ─── Rendu ──────────────────────────────────────────────────────────────

    def draw(self, surf):
        if not self.visible:
            return
        self._lazy_init_fonts()

        w, h = surf.get_size()

        # ── Voile sombre ─────────────────────────────────────────────────
        voile = pygame.Surface((w, h), pygame.SRCALPHA)
        voile.fill(_BG_OVERLAY)
        surf.blit(voile, (0, 0))

        # ── Panneau central ──────────────────────────────────────────────
        panel_w = 580
        panel_h = 380
        panel_x = (w - panel_w) // 2
        panel_y = (h - panel_h) // 2
        panneau = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panneau.fill(_PANEL_BG)
        pygame.draw.rect(panneau, _PANEL_BORDER, panneau.get_rect(), 2)
        surf.blit(panneau, (panel_x, panel_y))

        # ── Titre ────────────────────────────────────────────────────────
        titre_txt = "SAUVEGARDER" if self.mode == "save" else "CHARGER"
        titre = self._fonts["titre"].render(titre_txt, True, _TEXT_COLOR)
        surf.blit(titre, (panel_x + (panel_w - titre.get_width()) // 2,
                          panel_y + 20))

        # ── Liste des slots ──────────────────────────────────────────────
        slot_h    = 80
        slot_x    = panel_x + 30
        slot_w    = panel_w - 60
        slots_y0  = panel_y + 80

        for i, info in enumerate(self._slots_cache):
            sy = slots_y0 + i * (slot_h + 8)
            self._draw_slot(surf, info, slot_x, sy, slot_w, slot_h,
                            selectionne=(i == self.selection))

        # ── Footer (raccourcis) ──────────────────────────────────────────
        footer = "↑↓ choisir   Entrée valider   Échap annuler"
        ftxt   = self._fonts["small"].render(footer, True, _TEXT_DIM)
        surf.blit(ftxt, (panel_x + (panel_w - ftxt.get_width()) // 2,
                         panel_y + panel_h - 28))

        # ── Confirmation d'écrasement ────────────────────────────────────
        if self._confirming:
            self._draw_confirmation(surf, w, h)

    # ─── Helpers internes ───────────────────────────────────────────────────

    def _lazy_init_fonts(self):
        if self._fonts is not None:
            return
        self._fonts = {
            "titre":  pygame.font.SysFont("Georgia",  28, bold=True),
            "label":  pygame.font.SysFont("Consolas", 18, bold=True),
            "info":   pygame.font.SysFont("Consolas", 14),
            "small":  pygame.font.SysFont("Consolas", 12),
            "vide":   pygame.font.SysFont("Consolas", 16, italic=True),
        }

    def _draw_slot(self, surf, info, x, y, w, h, selectionne):
        # Fond de la ligne (surligné si sélectionné)
        rect = pygame.Rect(x, y, w, h)
        if selectionne:
            sel_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            sel_surf.fill(_SELECTION_BG)
            surf.blit(sel_surf, (x, y))
            pygame.draw.rect(surf, _SELECTION_LINE, rect, 2)
        else:
            pygame.draw.rect(surf, (90, 100, 120), rect, 1)

        # Label slot (Slot 1, Slot 2, …)
        label = self._fonts["label"].render(f"SLOT {info['slot']}", True,
                                             _TEXT_COLOR)
        surf.blit(label, (x + 14, y + 10))

        if not info["existe"]:
            # Slot vide
            vide_text = "<vide>"
            color     = _TEXT_DIM
            if self.mode == "load":
                color = _TEXT_RED
            vide = self._fonts["vide"].render(vide_text, True, color)
            surf.blit(vide, (x + 14, y + 40))
            return

        # Slot rempli : affiche les infos résumées
        ligne1 = (f"Map : {info['map'] or '?':<14}  "
                  f"PV : {info['hp']}/{info['max_hp']}  "
                  f"Lucioles : {info['fireflies']}")
        ligne2 = (f"Sauvé le {formater_date(info['saved_at'])}  "
                  f"Temps de jeu : {formater_temps_jeu(info['play_time_s'])}")
        l1 = self._fonts["info"].render(ligne1, True, _TEXT_COLOR)
        l2 = self._fonts["info"].render(ligne2, True, _TEXT_DIM)
        surf.blit(l1, (x + 14, y + 36))
        surf.blit(l2, (x + 14, y + 56))

    def _draw_confirmation(self, surf, w, h):
        # Petit panneau modal au-dessus
        cw, ch = 380, 130
        cx, cy = (w - cw) // 2, (h - ch) // 2
        c = pygame.Surface((cw, ch), pygame.SRCALPHA)
        c.fill(_CONFIRM_BG)
        pygame.draw.rect(c, _TEXT_RED, c.get_rect(), 2)
        surf.blit(c, (cx, cy))

        txt = self._fonts["label"].render("Écraser cette sauvegarde ?",
                                           True, _TEXT_COLOR)
        surf.blit(txt, (cx + (cw - txt.get_width()) // 2, cy + 30))
        sub = self._fonts["info"].render("Entrée = oui   Échap = non",
                                          True, _TEXT_DIM)
        surf.blit(sub, (cx + (cw - sub.get_width()) // 2, cy + 75))
