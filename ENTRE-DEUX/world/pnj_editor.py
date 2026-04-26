# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Éditeur de dialogues PNJ in-game
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Une interface dédiée pour gérer les conversations d'un PNJ : avant, on
#  ne pouvait qu'AJOUTER une conversation entière sur une seule ligne avec
#  des `|` comme séparateurs. Désormais on peut :
#     - voir TOUTES les conversations d'un PNJ
#     - éditer une conversation existante (ajouter/supprimer/modifier des lignes)
#     - supprimer une conversation
#     - changer l'orateur de chaque ligne (multi-orateur)
#     - changer le mode du PNJ (boucle / restart)
#
#  ON L'OUVRE COMMENT ?
#  --------------------
#  Dans l'éditeur, en mode 11 (PNJ), survol d'un PNJ + [F3].
#
#  STRUCTURE
#  ---------
#  2 niveaux de navigation :
#     1) Liste des CONVERSATIONS du PNJ (vue globale)
#     2) Liste des LIGNES d'une conversation (édition fine)
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame


class PNJEditor:
    """Mini-éditeur de dialogues pour un PNJ.

    Modes internes :
        None         = navigation (niveau conv / niveau ligne selon self.niveau)
        "edit_line"  = saisie texte (édition d'une ligne)
        "edit_orator"= saisie texte (édition de l'orateur d'une ligne)
        "confirm"    = confirmation (suppression d'une conversation)
    """

    def __init__(self):
        self.actif       = False
        self.pnj         = None        # référence au PNJ en cours d'édition
        self.niveau      = "conv"      # "conv" (liste convs) | "line" (lignes d'une conv)

        self.conv_idx    = 0           # index de la conversation sélectionnée
        self.line_idx    = 0           # index de la ligne (en mode "line")

        self.mode        = None        # cf. docstring
        self._input      = ""
        self._input_for  = ""          # "line" | "orator"

        # Polices lazy
        self._font   = None
        self._fontsm = None

        self._msg       = ""
        self._msg_timer = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    #  Cycle de vie
    # ─────────────────────────────────────────────────────────────────────────

    def ouvrir(self, pnj):
        if pnj is None:
            return
        self.actif    = True
        self.pnj      = pnj
        self.niveau   = "conv"
        self.conv_idx = 0
        self.line_idx = 0
        self.mode     = None

    def fermer(self):
        self.actif = False
        self.pnj   = None
        self.mode  = None

    def _msg_show(self, msg, duration=2.0):
        self._msg       = msg
        self._msg_timer = duration

    # ─────────────────────────────────────────────────────────────────────────
    #  Polices
    # ─────────────────────────────────────────────────────────────────────────

    def _get_fonts(self):
        if self._font is None:
            self._font   = pygame.font.SysFont("Consolas", 17)
            self._fontsm = pygame.font.SysFont("Consolas", 13)
        return self._font, self._fontsm

    # ─────────────────────────────────────────────────────────────────────────
    #  Helpers d'accès aux conversations
    # ─────────────────────────────────────────────────────────────────────────

    def _convs(self):
        if self.pnj is None:
            return []
        return self.pnj._dialogues

    def _conv_courante(self):
        convs = self._convs()
        if 0 <= self.conv_idx < len(convs):
            return convs[self.conv_idx]
        return None

    # ─────────────────────────────────────────────────────────────────────────
    #  Entrée clavier
    # ─────────────────────────────────────────────────────────────────────────

    def handle_key(self, key, mods=0):
        if not self.actif:
            return False

        if key == pygame.K_ESCAPE:
            if self.mode is not None:
                self.mode   = None
                self._input = ""
            elif self.niveau == "line":
                self.niveau = "conv"
            else:
                self.fermer()
            return True

        if self.mode in ("edit_line", "edit_orator"):
            return self._handle_key_text(key)

        if self.niveau == "conv":
            return self._handle_key_convs(key, mods)
        else:
            return self._handle_key_lines(key, mods)

    def handle_textinput(self, text):
        if not self.actif:
            return
        if self.mode in ("edit_line", "edit_orator"):
            self._input += text

    def _handle_key_text(self, key):
        if key == pygame.K_RETURN:
            self._confirmer_saisie()
        elif key == pygame.K_BACKSPACE:
            self._input = self._input[:-1]
        return True

    # ── Niveau 1 : liste des conversations ───────────────────────────────────

    def _handle_key_convs(self, key, mods):
        convs = self._convs()
        n = len(convs)
        ctrl = bool(mods & pygame.KMOD_CTRL)

        if key == pygame.K_UP and n:
            self.conv_idx = (self.conv_idx - 1) % n
        elif key == pygame.K_DOWN and n:
            self.conv_idx = (self.conv_idx + 1) % n
        elif key == pygame.K_RETURN and n:
            # Entrer dans la conversation
            self.niveau   = "line"
            self.line_idx = 0
        elif key in (pygame.K_a, pygame.K_KP_PLUS, pygame.K_PLUS, pygame.K_EQUALS):
            # Nouvelle conversation : avec une ligne vide pour démarrer
            convs.append([("", self.pnj.nom)])
            self.conv_idx = len(convs) - 1
            self.niveau   = "line"
            self.line_idx = 0
            self._commencer_edition_ligne()
        elif key in (pygame.K_d, pygame.K_KP_MINUS, pygame.K_MINUS,
                     pygame.K_DELETE) and n:
            # Supprimer la conversation sélectionnée
            convs.pop(self.conv_idx)
            if self.conv_idx >= len(convs):
                self.conv_idx = max(0, len(convs) - 1)
        elif key == pygame.K_w:
            # Cycle entre boucle_dernier et restart
            modes = ["boucle_dernier", "restart"]
            cur   = self.pnj.dialogue_mode
            idx   = modes.index(cur) if cur in modes else 0
            self.pnj.dialogue_mode = modes[(idx + 1) % len(modes)]
            self._msg_show(f"Mode : {self.pnj.dialogue_mode}")
        return True

    # ── Niveau 2 : lignes d'une conversation ─────────────────────────────────

    def _handle_key_lines(self, key, mods):
        conv = self._conv_courante()
        if conv is None:
            self.niveau = "conv"
            return True
        n     = len(conv)
        shift = bool(mods & pygame.KMOD_SHIFT)

        # Réordonner avec Maj+↑/↓
        if shift and key == pygame.K_UP and n and self.line_idx > 0:
            conv[self.line_idx], conv[self.line_idx - 1] = \
                conv[self.line_idx - 1], conv[self.line_idx]
            self.line_idx -= 1
        elif shift and key == pygame.K_DOWN and n and self.line_idx < n - 1:
            conv[self.line_idx], conv[self.line_idx + 1] = \
                conv[self.line_idx + 1], conv[self.line_idx]
            self.line_idx += 1

        elif key == pygame.K_UP and n:
            self.line_idx = (self.line_idx - 1) % n
        elif key == pygame.K_DOWN and n:
            self.line_idx = (self.line_idx + 1) % n
        elif key == pygame.K_RETURN and n:
            self._commencer_edition_ligne()
        elif key == pygame.K_o and n:
            # [O] = changer l'orateur
            self._commencer_edition_orateur()
        elif key in (pygame.K_a, pygame.K_KP_PLUS, pygame.K_PLUS, pygame.K_EQUALS):
            # Nouvelle ligne (insère APRÈS la sélection)
            conv.insert(self.line_idx + 1, ("", self.pnj.nom))
            self.line_idx += 1
            self._commencer_edition_ligne()
        elif key in (pygame.K_d, pygame.K_KP_MINUS, pygame.K_MINUS,
                     pygame.K_DELETE) and n:
            conv.pop(self.line_idx)
            if self.line_idx >= len(conv):
                self.line_idx = max(0, len(conv) - 1)
            # Si la conv est vide, on revient au niveau 1
            if not conv:
                convs = self._convs()
                convs.pop(self.conv_idx)
                if self.conv_idx >= len(convs):
                    self.conv_idx = max(0, len(convs) - 1)
                self.niveau = "conv"
        return True

    # ─────────────────────────────────────────────────────────────────────────
    #  Saisie de texte
    # ─────────────────────────────────────────────────────────────────────────

    def _commencer_edition_ligne(self):
        conv = self._conv_courante()
        if conv is None or not (0 <= self.line_idx < len(conv)):
            return
        texte, _ = conv[self.line_idx]
        self.mode       = "edit_line"
        self._input_for = "line"
        self._input     = texte

    def _commencer_edition_orateur(self):
        conv = self._conv_courante()
        if conv is None or not (0 <= self.line_idx < len(conv)):
            return
        _, orateur = conv[self.line_idx]
        self.mode       = "edit_orator"
        self._input_for = "orator"
        self._input     = orateur

    def _confirmer_saisie(self):
        conv = self._conv_courante()
        if conv is None or not (0 <= self.line_idx < len(conv)):
            self.mode = None
            return
        texte, orateur = conv[self.line_idx]
        if self._input_for == "line":
            conv[self.line_idx] = (self._input, orateur)
        elif self._input_for == "orator":
            conv[self.line_idx] = (texte, self._input or self.pnj.nom)
        self.mode   = None
        self._input = ""

    # ─────────────────────────────────────────────────────────────────────────
    #  Rendu
    # ─────────────────────────────────────────────────────────────────────────

    def update(self, dt):
        if self._msg_timer > 0:
            self._msg_timer -= dt

    def draw(self, surf):
        if not self.actif or self.pnj is None:
            return
        font, fontsm = self._get_fonts()
        w, h = surf.get_size()

        # Voile
        voile = pygame.Surface((w, h), pygame.SRCALPHA)
        voile.fill((0, 0, 0, 200))
        surf.blit(voile, (0, 0))

        # Cadre
        marge = 60
        cadre = pygame.Rect(marge, marge, w - 2 * marge, h - 2 * marge)
        pygame.draw.rect(surf, (25, 25, 35), cadre)
        pygame.draw.rect(surf, (190, 175, 240), cadre, 2)

        # Titre
        chemin = f"PNJ > {self.pnj.nom}"
        if self.niveau == "line":
            chemin += f" > Conversation {self.conv_idx + 1}"
        surf.blit(font.render(chemin, True, (190, 175, 240)),
                  (cadre.x + 16, cadre.y + 12))

        # Aide contextuelle
        if self.niveau == "conv":
            aide = ("[↑↓] | [Entrée] ouvrir | [A] nouvelle conv | [D] supprimer | "
                    "[W] mode | [Esc] fermer")
        else:
            aide = ("[↑↓] | [Entrée] éditer texte | [O] orateur | [A] +ligne | "
                    "[D] -ligne | [Maj+↑↓] reordonner | [Esc] retour")
        surf.blit(fontsm.render(aide, True, (140, 140, 140)),
                  (cadre.x + 16, cadre.y + 38))

        # Mode info
        info = f"Mode : {self.pnj.dialogue_mode}  |  {len(self._convs())} conversation(s)"
        surf.blit(fontsm.render(info, True, (180, 200, 230)),
                  (cadre.x + 16, cadre.y + 60))

        # Contenu selon niveau
        y = cadre.y + 90
        if self.niveau == "conv":
            self._draw_convs(surf, font, cadre, y)
        else:
            self._draw_lines(surf, font, cadre, y)

        # Message
        if self._msg_timer > 0 and self._msg:
            ms = font.render(self._msg, True, (255, 220, 120))
            surf.blit(ms, (cadre.centerx - ms.get_width() // 2, cadre.bottom - 30))

        # Popup d'édition
        if self.mode in ("edit_line", "edit_orator"):
            self._draw_popup_edit(surf, font, fontsm)

    def _draw_convs(self, surf, font, cadre, y):
        convs = self._convs()
        if not convs:
            surf.blit(font.render("(aucune conversation — [A] pour en créer une)",
                                  True, (140, 140, 140)),
                      (cadre.x + 16, y))
            return
        for i, conv in enumerate(convs):
            if i == self.conv_idx and self.mode is None:
                pygame.draw.rect(surf, (60, 60, 90),
                                 (cadre.x + 12, y - 2, cadre.width - 24, 22))
            color = (255, 255, 255) if i == self.conv_idx else (200, 200, 220)
            apercu = "(vide)"
            if conv:
                apercu = (conv[0][0] or "")[:60]
                if len(conv) > 1:
                    apercu += f"  …  ({len(conv)} lignes)"
            surf.blit(font.render(f"{i+1:2d}. {apercu}", True, color),
                      (cadre.x + 16, y))
            y += 22
            if y > cadre.bottom - 30:
                break

    def _draw_lines(self, surf, font, cadre, y):
        conv = self._conv_courante()
        if conv is None:
            return
        if not conv:
            surf.blit(font.render("(conversation vide — [A] pour ajouter une ligne)",
                                  True, (140, 140, 140)),
                      (cadre.x + 16, y))
            return
        for i, (texte, orateur) in enumerate(conv):
            if i == self.line_idx and self.mode is None:
                pygame.draw.rect(surf, (60, 60, 90),
                                 (cadre.x + 12, y - 2, cadre.width - 24, 22))
            color  = (255, 255, 255) if i == self.line_idx else (200, 200, 220)
            label  = f"{i+1:2d}. [{orateur}] {texte}"
            # Tronque visuellement si trop long
            if font.size(label)[0] > cadre.width - 40:
                while label and font.size(label + "…")[0] > cadre.width - 40:
                    label = label[:-1]
                label += "…"
            surf.blit(font.render(label, True, color),
                      (cadre.x + 16, y))
            y += 22
            if y > cadre.bottom - 30:
                break

    def _draw_popup_edit(self, surf, font, fontsm):
        sw, sh = surf.get_size()
        bw, bh = 700, 130
        box = pygame.Rect(sw // 2 - bw // 2, sh // 2 - bh // 2, bw, bh)
        pygame.draw.rect(surf, (30, 30, 45), box)
        pygame.draw.rect(surf, (190, 175, 240), box, 2)
        titre = ("Texte de la ligne :" if self._input_for == "line"
                 else "Orateur (qui parle) :")
        surf.blit(font.render(titre, True, (190, 175, 240)),
                  (box.x + 16, box.y + 12))
        surf.blit(font.render(self._input + "_", True, (255, 255, 255)),
                  (box.x + 16, box.y + 50))
        surf.blit(fontsm.render("[Enter] valider | [Esc] annuler",
                                True, (140, 140, 140)),
                  (box.x + 16, box.y + 90))
