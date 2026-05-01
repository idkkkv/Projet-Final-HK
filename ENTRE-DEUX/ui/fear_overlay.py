# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Overlay "fear text" (texte d'avertissement)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Petit composant UI qui affiche un texte en haut de l'écran quand le
#  joueur entre dans une fear_zone et que sa peur est trop grande pour
#  passer. Volontairement DISCRET (pas un dialogue qui bloque la partie).
#
#  STYLE VISÉ : MYSTÉRIEUX
#  -----------------------
#  - Police italique en serif (Georgia / fallback) → moins "informatique",
#    plus "littéraire", évoque un narrateur intérieur plutôt qu'une UI.
#  - Couleur off-white légèrement bleutée → moins criard que blanc pur,
#    fait penser à de la brume ou à une lueur lunaire.
#  - Alpha max RÉDUIT (140 au lieu de 220) → texte semi-transparent qui
#    se fond dans la scène, comme une voix dans le crâne du personnage.
#  - Fade-in plus lent (0.7 s au lieu de 0.4 s) → le texte "infuse"
#    dans la conscience du joueur au lieu de claquer.
#
#  MULTI-LIGNES
#  ------------
#  Tu peux passer un texte avec des sauts de ligne (\n) ou avec le
#  séparateur "|" (plus pratique à taper dans l'éditeur). Les deux sont
#  reconnus. Chaque ligne est dessinée avec son alpha, centrée, et
#  espacée de l'INTERLIGNE (cf. constante).
#
#  Comportement :
#     show(texte)          → fait apparaître le texte (fade in)
#     update(dt)           → gère le fade in/out chaque frame
#     skip()               → fait disparaître immédiatement (touche Espace)
#     draw(surface)        → affiche le texte centré en haut, avec alpha

import pygame


class FearOverlay:
    """Texte d'avertissement transparent affiché en haut de l'écran."""

    # ── Réglages d'apparence ────────────────────────────────────────────
    DUREE_FADE_IN  = 0.7    # un peu plus lent → "infusion" mystérieuse (avant 0.4)
    DUREE_VISIBLE  = 3.0    # durée pleine visibilité (s)
    DUREE_FADE_OUT = 1.4    # disparition douce (avant 1.0)
    ALPHA_MAX      = 140    # opacité maximale (avant 220) — semi-transparent voulu
    MARGE_HAUT     = 70     # distance depuis le haut de l'écran (px)
    INTERLIGNE     = 6      # espace vertical entre 2 lignes (px)

    # Couleur off-white légèrement bleutée → impression de brume / froid.
    # Plus subtile qu'un blanc pur (255,255,255).
    COULEUR        = (220, 220, 235)
    # Ombre très douce (presque pas noire) — sert juste à détacher du fond
    # sans donner un effet "BD" trop appuyé.
    COULEUR_OMBRE  = (10, 10, 20)
    # Décalage de l'ombre (px). Petit pour rester discret.
    OMBRE_OFFSET   = 1

    # Polices à essayer DANS L'ORDRE (la 1ʳᵉ trouvée gagne).
    # Choisies pour leur côté "littéraire/manuscrit" :
    #   - Georgia : serif élégant, dispo sur la plupart des OS
    #   - Garamond, Palatino, Cambria, Constantia : alternatives serif
    #   - Fallback : SysFont par défaut (toujours dispo)
    POLICES_PREFEREES = ("georgia", "garamond", "palatinolinotype",
                         "cambria", "constantia")
    TAILLE_POLICE     = 26

    def __init__(self, font=None):
        # font : pygame.font.Font (optionnelle).
        # Si None, on tentera de créer une police "mystérieuse" au 1er
        # appel à draw() (lazy init pour éviter pygame.font.init() trop tôt).
        self.font     = font
        self._font_auto_chargee = False    # True si on a déjà essayé
        self.texte    = ""
        self.actif    = False
        # _temps : seconde courante depuis le show(). Sert à doser fade.
        self._temps   = 0.0
        self._skipped = False

    def set_font(self, font):
        """Permet d'injecter la police après coup (depuis game.py).

        Si tu ne fais rien, l'overlay choisira lui-même une jolie police
        au premier draw (cf. _charger_police_mystere)."""
        self.font = font
        self._font_auto_chargee = True   # on respecte le choix de l'appelant

    # ── Initialisation paresseuse de la police "mystère" ────────────────
    #
    #  On essaie chaque candidat dans POLICES_PREFEREES, en italique. Si
    #  aucune n'est dispo (système exotique), on retombe sur la police
    #  par défaut de pygame, qui marche partout.

    def _charger_police_mystere(self):
        """Choisit une police italique parmi POLICES_PREFEREES.

        Renvoie un pygame.font.Font. Toujours réussir (fallback ultime
        sur SysFont(None) = police par défaut)."""
        # On itère sur les noms et on s'arrête au premier qui n'est pas
        # le fallback "freesansbold" (qui veut dire "police inconnue").
        # SysFont accepte un nom et renvoie quelque chose même si absent
        # (la police par défaut), donc cette détection reste utile.
        polices_disponibles = set(pygame.font.get_fonts())
        for nom in self.POLICES_PREFEREES:
            # pygame.font.get_fonts() renvoie des noms en minuscules sans
            # espaces. Notre liste est déjà sous cette forme — direct ok.
            if nom in polices_disponibles:
                return pygame.font.SysFont(nom, self.TAILLE_POLICE,
                                           italic=True)
        # Aucune des polices "stylisées" trouvée → fallback générique en
        # italique. Mieux qu'une Consolas non italique, qui ferait "code".
        return pygame.font.SysFont(None, self.TAILLE_POLICE, italic=True)

    def _ensure_font(self):
        """Garantit que self.font est un pygame.font.Font utilisable."""
        if self.font is not None:
            return
        if not self._font_auto_chargee:
            self.font = self._charger_police_mystere()
            self._font_auto_chargee = True

    # ── Contrôle ─────────────────────────────────────────────────────────

    def show(self, texte):
        """Démarre l'affichage du texte. Si déjà actif avec le même texte,
        on ne ré-anime pas (évite le clignotement quand on reste dans la
        zone)."""
        if self.actif and self.texte == texte and not self._skipped:
            return
        self.texte    = texte
        self.actif    = True
        self._temps   = 0.0
        self._skipped = False

    def hide(self):
        """Force la disparition (sans animation). Appelé quand on sort
        de la zone, par exemple."""
        self.actif    = False
        self._temps   = 0.0
        self._skipped = False

    def skip(self):
        """Demande un fade-out immédiat (touche Espace)."""
        if self.actif and not self._skipped:
            self._skipped = True
            # On saute directement à la phase fade out.
            self._temps = self.DUREE_FADE_IN + self.DUREE_VISIBLE

    # ── Mise à jour & rendu ──────────────────────────────────────────────

    def update(self, dt):
        """Avance le temps. À appeler chaque frame."""
        if not self.actif:
            return
        self._temps += dt
        # Fin de l'animation totale → on désactive.
        total = self.DUREE_FADE_IN + self.DUREE_VISIBLE + self.DUREE_FADE_OUT
        if self._temps >= total:
            self.actif = False

    def _alpha_courant(self):
        """Calcule l'alpha (0..255) selon la phase d'animation."""
        t = self._temps
        if t < self.DUREE_FADE_IN:
            # Fade in : 0 → ALPHA_MAX (courbe douce via puissance, plus
            # mystérieuse qu'un linéaire — le texte "émerge" au lieu
            # d'apparaître à vitesse constante).
            ratio = t / self.DUREE_FADE_IN
            return int(self.ALPHA_MAX * (ratio ** 1.5))
        if t < self.DUREE_FADE_IN + self.DUREE_VISIBLE:
            # Plein visible
            return self.ALPHA_MAX
        # Fade out : ALPHA_MAX → 0 (linéaire, pour ne pas traîner trop)
        t_out = t - self.DUREE_FADE_IN - self.DUREE_VISIBLE
        ratio = max(0.0, 1.0 - t_out / self.DUREE_FADE_OUT)
        return int(self.ALPHA_MAX * ratio)

    # ── Découpage du texte en lignes ────────────────────────────────────
    #
    #  Le texte stocké peut contenir :
    #     - des "\n" classiques (peu pratique à taper dans l'éditeur)
    #     - le pipe "|" (utilisé comme séparateur dans pnj_dialogue,
    #       réutilisé ici pour cohérence)
    #
    #  On accepte les deux et on filtre les lignes vides.

    def _lignes(self):
        """Renvoie la liste des lignes à dessiner (au moins une)."""
        if not self.texte:
            return []
        # Remplace les "|" par "\n" puis split. Ainsi un texte tapé avec
        # un mélange des deux (rare mais possible) reste cohérent.
        brut = self.texte.replace("|", "\n")
        # On préserve les lignes vides INTÉRIEURES (au cas où l'auteur
        # voudrait un saut de ligne expressif), mais on enlève celles
        # purement vides aux extrémités (résultat de "|" final, etc.).
        lignes = brut.split("\n")
        while lignes and not lignes[0].strip():
            lignes.pop(0)
        while lignes and not lignes[-1].strip():
            lignes.pop()
        return lignes

    def draw(self, surface):
        """Dessine le texte au centre-haut de l'écran avec ombre + alpha.

        Supporte le multi-ligne (séparateur "|" ou "\\n"). Chaque ligne
        est centrée individuellement, les lignes sont empilées avec
        INTERLIGNE px d'écart."""
        if not self.actif or not self.texte:
            return

        # Charge la police "mystère" si on n'en a pas reçu une.
        self._ensure_font()
        if self.font is None:
            return

        alpha = self._alpha_courant()
        if alpha <= 0:
            return

        lignes = self._lignes()
        if not lignes:
            return

        # On rend chaque ligne, on récupère sa hauteur pour empiler.
        # Pour respecter l'alpha, on utilise set_alpha sur chaque surf.
        sw = surface.get_width()
        y = self.MARGE_HAUT

        for ligne in lignes:
            if not ligne:
                # Ligne vide → on saute juste la hauteur d'une ligne pour
                # créer un "blanc" (utile si l'auteur veut un espace).
                y += self.font.get_height() + self.INTERLIGNE
                continue

            # Ombre (très subtile) + texte principal.
            ombre = self.font.render(ligne, True, self.COULEUR_OMBRE)
            ombre.set_alpha(alpha)
            principal = self.font.render(ligne, True, self.COULEUR)
            principal.set_alpha(alpha)

            x = sw // 2 - principal.get_width() // 2
            surface.blit(ombre, (x + self.OMBRE_OFFSET, y + self.OMBRE_OFFSET))
            surface.blit(principal, (x, y))

            y += principal.get_height() + self.INTERLIGNE
