# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Mixin Debug Panel (overlay story flags, touche F5)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Mixin qui gère le panneau debug des story flags (overlay en haut-droite
#  ouvrable avec F5 en mode éditeur). Permet à l'utilisateur de :
#       - voir tous les flags posés et leur valeur (True/False)
#       - basculer un flag (T)
#       - en supprimer un (D)
#       - en ajouter un (A → popup saisie texte avec Ctrl+V)
#
#  Sert UNIQUEMENT au debug / aux tests rapides. Pas exposé en mode
#  histoire pour ne pas casser l'immersion.
# ─────────────────────────────────────────────────────────────────────────────

import pygame


class DebugPanelMixin:
    """Panneau debug overlay (F5) pour inspecter / éditer les story flags."""

    def _story_flags_panel_handle_key(self, key):
        """Gère les touches quand le panneau debug flags est ouvert.

        Touches :
          ↑↓     naviguer dans la liste
          T      basculer le flag sélectionné (True ↔ False)
          D      supprimer le flag sélectionné
          A      ajouter un nouveau flag (saisie texte interne)
          Esc/F5 fermer

        Renvoie True si la touche est consommée.
        """
        if not hasattr(self, "_story_flags_panel_sel"):
            self._story_flags_panel_sel = 0
        if not hasattr(self, "_story_flags_input_actif"):
            self._story_flags_input_actif = False
            self._story_flags_input_buf   = ""

        # Mode saisie : RETURN valide, ESC annule, BACKSPACE efface.
        if self._story_flags_input_actif:
            if key == pygame.K_RETURN:
                k = self._story_flags_input_buf.strip()
                if k:
                    self.story_flags[k] = True
                self._story_flags_input_actif = False
                self._story_flags_input_buf   = ""
                return True
            if key == pygame.K_ESCAPE:
                self._story_flags_input_actif = False
                self._story_flags_input_buf   = ""
                return True
            if key == pygame.K_BACKSPACE:
                self._story_flags_input_buf = self._story_flags_input_buf[:-1]
                return True
            if key == pygame.K_v and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                # Ctrl+V : colle depuis le presse-papiers
                try:
                    from world.cinematique_editor import _clipboard_get
                    self._story_flags_input_buf += _clipboard_get().strip().replace("\n", "").replace("\r", "")
                except Exception:
                    pass
                return True
            return True

        flags = list(self.story_flags.keys())
        n = len(flags)
        if key == pygame.K_ESCAPE:
            self._story_flags_panel_open = False
            return True
        if key == pygame.K_UP and n:
            self._story_flags_panel_sel = (self._story_flags_panel_sel - 1) % n
            return True
        if key == pygame.K_DOWN and n:
            self._story_flags_panel_sel = (self._story_flags_panel_sel + 1) % n
            return True
        if key == pygame.K_t and n:
            k = flags[self._story_flags_panel_sel]
            self.story_flags[k] = not bool(self.story_flags.get(k, False))
            return True
        if key == pygame.K_d and n:
            k = flags[self._story_flags_panel_sel]
            self.story_flags.pop(k, None)
            self._story_flags_panel_sel = max(
                0, min(self._story_flags_panel_sel, len(self.story_flags) - 1))
            return True
        if key == pygame.K_a:
            self._story_flags_input_actif = True
            self._story_flags_input_buf   = ""
            return True
        return False

    def _story_flags_panel_handle_textinput(self, text):
        """Hook TEXTINPUT pour la saisie d'un nom de flag (accents OK)."""
        if getattr(self, "_story_flags_input_actif", False):
            self._story_flags_input_buf += text
            return True
        return False

    def _dessiner_story_flags_panel(self):
        """Affiche l'overlay debug des story flags si _story_flags_panel_open.

        Rectangle violet semi-transparent en haut-droite avec :
          - titre + raccourcis en haut
          - liste des flags (nom + état coloré vert/rouge)
          - barre de saisie en bas si on est en mode "ajouter"
        """
        if not getattr(self, "_story_flags_panel_open", False):
            return
        w, h = self.screen.get_size()
        pw, ph = 380, 320
        px = w - pw - 16
        py = 80
        # Fond + double bordure
        bg = pygame.Surface((pw, ph), pygame.SRCALPHA)
        bg.fill((16, 10, 30, 235))
        pygame.draw.rect(bg, (180, 150, 220),
                         pygame.Rect(0, 0, pw, ph), 2)
        pygame.draw.rect(bg, (255, 215, 70),
                         pygame.Rect(3, 3, pw - 6, ph - 6), 1)
        self.screen.blit(bg, (px, py))

        font_t = pygame.font.SysFont("Consolas", 14, bold=True)
        font   = pygame.font.SysFont("Consolas", 13)
        font_s = pygame.font.SysFont("Consolas", 11)

        # Titre + aide raccourcis
        self.screen.blit(font_t.render("STORY FLAGS  (F5 ferme)",
                                        True, (255, 215, 70)),
                         (px + 14, py + 10))
        self.screen.blit(font_s.render(
            "[↑↓] naviguer  [T] toggle  [D] supprimer  [A] ajouter",
            True, (170, 170, 200)),
                         (px + 14, py + 32))

        # Liste des flags
        flags = list(self.story_flags.items())
        if not flags:
            self.screen.blit(font.render("(aucun flag posé)",
                                          True, (140, 140, 160)),
                             (px + 14, py + 70))
        else:
            sel = getattr(self, "_story_flags_panel_sel", 0)
            ly = py + 60
            for i, (k, v) in enumerate(flags):
                if i == sel:
                    pygame.draw.rect(self.screen, (50, 35, 80),
                                     pygame.Rect(px + 8, ly - 2, pw - 16, 18))
                col_v = (140, 220, 140) if v else (180, 90, 100)
                txt = font.render(f"{k}", True, (240, 230, 255))
                self.screen.blit(txt, (px + 14, ly))
                etat = font.render("TRUE" if v else "FALSE", True, col_v)
                self.screen.blit(etat, (px + pw - etat.get_width() - 16, ly))
                ly += 18
                if ly > py + ph - 30:
                    break

        # Barre de saisie active ?
        if getattr(self, "_story_flags_input_actif", False):
            box_h = 30
            sx = px + 8
            sy = py + ph - box_h - 8
            pygame.draw.rect(self.screen, (40, 30, 70),
                             pygame.Rect(sx, sy, pw - 16, box_h))
            pygame.draw.rect(self.screen, (255, 215, 70),
                             pygame.Rect(sx, sy, pw - 16, box_h), 1)
            txt = self._story_flags_input_buf + "_"
            self.screen.blit(font.render("Nouveau flag : " + txt, True,
                                          (255, 255, 255)),
                             (sx + 6, sy + 6))
