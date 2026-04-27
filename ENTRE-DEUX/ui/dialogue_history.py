# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Journal des dialogues
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI ÇA SERT ?
#  ----------------
#  En mode boucle_dernier, un PNJ ne re-dit que sa dernière phrase une fois
#  qu'on a tout entendu. Mais le joueur peut vouloir RELIRE ce qui a été dit.
#  Le journal garde la trace de TOUS les dialogues complétés, organisés par
#  carte, accessibles via une touche dédiée.
#
#  Stocké dans self.historique_dialogues (dict) côté game.py, persisté dans
#  save.json, reset à "Nouvelle partie".
#
#  STRUCTURE DES DONNÉES
#  ---------------------
#       {
#         "Marc": {
#           "village": [
#             [["Bonjour !", "Marc"], ["Tu es nouveau ici ?", "Marc"]],
#             [["Tiens, te revoilà.", "Marc"]]
#           ],
#           "foret": [
#             [["Que fais-tu si loin ?", "Marc"]]
#           ]
#         },
#         "Théa": { ... }
#       }
#
#  Chaque CONVERSATION (liste de lignes [(texte, orateur), ...]) est ajoutée
#  une seule fois dans la map où elle a été déclenchée.
#
#  ON L'OUVRE COMMENT ?
#  --------------------
#  En jeu (mode histoire), touche [J] (Journal).
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame


class DialogueHistory:
    """Affiche le journal des dialogues déjà entendus avec chaque PNJ.

    Ne stocke PAS les données : elles sont dans game.historique_dialogues
    (sauvé/chargé via save.json). On lui passe juste une référence."""

    def __init__(self):
        self.actif      = False
        self._data      = {}        # référence au dict de game (pas une copie)
        # Navigation à 2 niveaux :
        #   "pnj"   = liste des PNJ rencontrés
        #   "convs" = liste des conversations d'un PNJ donné (toutes maps)
        self.niveau     = "pnj"
        self.pnj_idx    = 0
        self.conv_idx   = 0

        # Polices lazy
        self._font   = None
        self._fontsm = None
        self._fontti = None

    def ouvrir(self, donnees):
        """donnees = dict {nom_pnj: {nom_map: [conv, conv, ...]}}.
        Référence (pas copie) → si game met à jour le dict, on le voit."""
        self.actif    = True
        self._data    = donnees if donnees is not None else {}
        self.niveau   = "pnj"
        self.pnj_idx  = 0
        self.conv_idx = 0

    def fermer(self):
        self.actif = False

    # ─────────────────────────────────────────────────────────────────────────
    #  Polices
    # ─────────────────────────────────────────────────────────────────────────

    def _get_fonts(self):
        if self._font is None:
            self._font   = pygame.font.SysFont("Consolas", 17)
            self._fontsm = pygame.font.SysFont("Consolas", 13)
            self._fontti = pygame.font.SysFont("Georgia", 24, bold=True)
        return self._font, self._fontsm, self._fontti

    # ─────────────────────────────────────────────────────────────────────────
    #  Helpers d'accès aux données
    # ─────────────────────────────────────────────────────────────────────────

    def _liste_pnj(self):
        """Liste triée des noms de PNJ rencontrés."""
        return sorted(self._data.keys())

    def _convs_pnj_courant(self):
        """Renvoie [(nom_map, conv), ...] pour le PNJ courant, dans l'ordre."""
        noms = self._liste_pnj()
        if not (0 <= self.pnj_idx < len(noms)):
            return []
        nom_pnj  = noms[self.pnj_idx]
        par_map  = self._data.get(nom_pnj, {})
        resultat = []
        for nom_map in sorted(par_map.keys()):
            for conv in par_map[nom_map]:
                resultat.append((nom_map, conv))
        return resultat

    # ─────────────────────────────────────────────────────────────────────────
    #  Entrée clavier
    # ─────────────────────────────────────────────────────────────────────────

    def handle_textinput(self, text):
        """Pas de saisie de texte dans le journal (no-op).
        Méthode requise par le routage events de game.py."""
        pass

    def handle_key(self, key, mods=0):
        if not self.actif:
            return False
        if key == pygame.K_ESCAPE:
            if self.niveau == "convs":
                self.niveau = "pnj"
            else:
                self.fermer()
            return True
        if self.niveau == "pnj":
            return self._handle_pnj(key)
        return self._handle_convs(key)

    def _handle_pnj(self, key):
        n = len(self._liste_pnj())
        if not n:
            return True
        if key == pygame.K_UP:
            self.pnj_idx = (self.pnj_idx - 1) % n
        elif key == pygame.K_DOWN:
            self.pnj_idx = (self.pnj_idx + 1) % n
        elif key in (pygame.K_RETURN, pygame.K_RIGHT):
            self.niveau   = "convs"
            self.conv_idx = 0
        return True

    def _handle_convs(self, key):
        convs = self._convs_pnj_courant()
        n = len(convs)
        if not n:
            self.niveau = "pnj"
            return True
        if key == pygame.K_UP:
            self.conv_idx = (self.conv_idx - 1) % n
        elif key == pygame.K_DOWN:
            self.conv_idx = (self.conv_idx + 1) % n
        elif key == pygame.K_LEFT:
            self.niveau = "pnj"
        return True

    # ─────────────────────────────────────────────────────────────────────────
    #  Rendu
    # ─────────────────────────────────────────────────────────────────────────

    def update(self, dt):
        pass    # rien à animer pour l'instant

    def draw(self, surf):
        if not self.actif:
            return
        font, fontsm, fontti = self._get_fonts()
        w, h = surf.get_size()

        # Voile sombre
        voile = pygame.Surface((w, h), pygame.SRCALPHA)
        voile.fill((6, 6, 18, 230))
        surf.blit(voile, (0, 0))

        # Cadre
        marge = 60
        cadre = pygame.Rect(marge, marge, w - 2 * marge, h - 2 * marge)
        pygame.draw.rect(surf, (15, 15, 28), cadre)
        pygame.draw.rect(surf, (190, 175, 240), cadre, 2)

        # Titre
        surf.blit(fontti.render("Journal — Dialogues", True, (215, 200, 255)),
                  (cadre.x + 16, cadre.y + 12))

        # Aide
        if self.niveau == "pnj":
            aide = "[↑↓] naviguer  [Entrée] ouvrir  [Esc] fermer"
        else:
            aide = "[↑↓] conv  [←] retour PNJ  [Esc] fermer"
        surf.blit(fontsm.render(aide, True, (140, 140, 140)),
                  (cadre.x + 16, cadre.y + 50))

        # Contenu
        if self.niveau == "pnj":
            self._draw_pnj_list(surf, font, cadre)
        else:
            self._draw_convs_list(surf, font, fontsm, cadre)

    def _draw_pnj_list(self, surf, font, cadre):
        noms = self._liste_pnj()
        y = cadre.y + 80
        if not noms:
            surf.blit(font.render(
                "(aucun dialogue mémorisé — parle à un PNJ pour commencer)",
                True, (140, 140, 140)),
                (cadre.x + 16, y))
            return
        for i, nom in enumerate(noms):
            nb_total = sum(len(convs) for convs in self._data[nom].values())
            if i == self.pnj_idx:
                pygame.draw.rect(surf, (60, 60, 90),
                                 (cadre.x + 12, y - 2, cadre.width - 24, 24))
            color = (255, 255, 255) if i == self.pnj_idx else (200, 200, 220)
            txt = f"{nom}   ({nb_total} conversation(s))"
            surf.blit(font.render(txt, True, color), (cadre.x + 16, y))
            y += 24
            if y > cadre.bottom - 20:
                break

    def _draw_convs_list(self, surf, font, fontsm, cadre):
        noms = self._liste_pnj()
        if not (0 <= self.pnj_idx < len(noms)):
            return
        nom_pnj = noms[self.pnj_idx]
        convs   = self._convs_pnj_courant()

        # Sous-titre
        surf.blit(font.render(f"› {nom_pnj}", True, (215, 200, 255)),
                  (cadre.x + 16, cadre.y + 80))

        # Colonne gauche : liste compacte des conversations
        y = cadre.y + 110
        col_w = 280
        for i, (nom_map, conv) in enumerate(convs):
            if i == self.conv_idx:
                pygame.draw.rect(surf, (60, 60, 90),
                                 (cadre.x + 12, y - 2, col_w, 22))
            color = (255, 255, 255) if i == self.conv_idx else (200, 200, 220)
            apercu = ""
            if conv:
                apercu = (conv[0][0] or "")[:24]
            txt = f"[{nom_map}] {apercu}"
            surf.blit(fontsm.render(txt, True, color), (cadre.x + 16, y))
            y += 22
            if y > cadre.bottom - 20:
                break

        # Colonne droite : détail de la conversation sélectionnée
        if 0 <= self.conv_idx < len(convs):
            nom_map, conv = convs[self.conv_idx]
            x_det = cadre.x + col_w + 30
            y_det = cadre.y + 110
            surf.blit(fontsm.render(f"Carte : {nom_map}", True, (180, 200, 230)),
                      (x_det, y_det))
            y_det += 26
            for ligne in conv:
                if isinstance(ligne, (list, tuple)) and len(ligne) >= 2:
                    texte, orateur = ligne[0], ligne[1]
                else:
                    texte, orateur = str(ligne), ""
                # Orateur
                if orateur:
                    surf.blit(fontsm.render(f"— {orateur} :", True, (240, 200, 80)),
                              (x_det, y_det))
                    y_det += 18
                # Texte (wrap simple : on tronque si trop long)
                wrapped = self._wrap(texte, font, cadre.right - x_det - 16)
                for ligne_w in wrapped:
                    surf.blit(font.render(ligne_w, True, (230, 230, 240)),
                              (x_det + 12, y_det))
                    y_det += font.get_height() + 2
                y_det += 4
                if y_det > cadre.bottom - 20:
                    break

    def _wrap(self, text, font, max_width):
        """Word-wrap basique pour ne pas déborder du cadre."""
        if not text:
            return [""]
        mots   = text.split(" ")
        lignes = []
        cur    = ""
        for mot in mots:
            essai = (cur + " " + mot) if cur else mot
            if font.size(essai)[0] <= max_width:
                cur = essai
            else:
                if cur:
                    lignes.append(cur)
                cur = mot
        if cur:
            lignes.append(cur)
        return lignes
