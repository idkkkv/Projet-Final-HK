# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Jauge de Peur (réservé / brouillon)
# ─────────────────────────────────────────────────────────────────────────────
#
#  ÉTAT ACTUEL : RÉSERVÉ (mécanique conçue, pas encore branchée au gameplay)
#  ------------------------------------------------------------------------
#  Une JAUGE qui démarre PLEINE (= peur maximale) et qui DESCEND quand le
#  joueur fait certaines actions positives (rallumer une bougie, libérer
#  un compagnon, etc.). À 0, on a vaincu la peur → événement final.
#
#  L'API est volontairement simple : reduce(), increase(), is_zero(),
#  get_ratio(). Quand on branchera la mécanique au jeu, on appellera
#  ces 4 méthodes depuis le bon endroit.
#
#  EXEMPLE D'USAGE PRÉVU
#  ---------------------
#       fear = FearSystem(max_fear=100)        # 100 = peur maximale
#       ...
#       # Le joueur ramène une lueur dans le foyer :
#       fear.reduce(15)                        # peur diminue de 15 points
#
#       # Le joueur tombe dans un piège effrayant :
#       fear.increase(10)
#
#       # Pour la jauge HUD :
#       hud_alpha = int(255 * fear.get_ratio())   # 1.0 → 0.0
#
#       # Fin de jeu / déclenchement final :
#       if fear.is_zero():
#           game.end_credits()
#
#  Petit lexique :
#     - jauge        = barre / pourcentage qui représente une valeur
#                      bornée (vie, faim, peur...). Stockée comme un
#                      simple int / float entre 0 et max.
#     - ratio        = nombre entre 0 et 1, indépendant des unités. Pratique
#                      pour le HUD (largeur de barre = ratio × largeur_max).
#     - clamp        = "borner" un nombre dans [min, max]. Ici via les
#                      max(0, ...) et min(max_fear, ...) pour empêcher
#                      d'aller négatif ou de dépasser le plafond.
#
#  POURQUOI COMMENCER À max_fear (PEUR MAX) ?
#  ------------------------------------------
#  Le joueur découvre un monde HOSTILE. La jauge à fond renforce le ton
#  initial. Chaque action positive l'amenuise, ce qui crée un objectif
#  visuel clair sans dialogue ni tutoriel.
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  PAS ENCORE. Quand on branchera la mécanique :
#       core/game.py instanciera self.fear = FearSystem()
#       ui/hud.py affichera la jauge
#       certaines actions du joueur appelleront fear.reduce() / increase()
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D22]  ratio dans [0, 1] — indépendant du max, pratique pour le HUD
#
# ─────────────────────────────────────────────────────────────────────────────


class FearSystem:
    """Jauge de Peur découpée en 5 stades.

    On garde une valeur interne continue (current ∈ [0, max_fear]) pour que
    la jauge HUD bouge en douceur, MAIS on expose aussi un "stade" entier
    de 0 (calme) à 5 (panique) qui sert au gameplay (zones de peur,
    ralentissement, ambiance sonore, etc.).

    Le stade n'est PAS fixé à la main : il est calculé chaque frame à
    partir du nombre de compagnons proches/loin (voir CompagnonGroup).
    On appelle alors set_target_stade(s), puis update(dt) interpole en
    douceur la jauge vers la valeur cible — pas de saut brutal du HUD.

    API minimale :
       set_target_stade(stade)   ← appelée chaque frame avec la cible
       update(dt)                ← interpole current vers la cible
       get_stade()               ← renvoie l'entier 0..5 (utilisé pour gameplay)
       get_ratio()               ← float 0..1 pour la barre HUD
    """

    NB_STADES = 5    # 0 = calme, 5 = panique. Donc 6 valeurs possibles : 0..5.

    def __init__(self, max_fear=100):
        self.max_fear = max_fear
        # current commence À FOND : sans compagnons le joueur est en panique.
        # Ça fait sens scénario : on découvre un monde hostile.
        self.current  = max_fear
        # Cible à atteindre (en valeur continue, pas en stade). Mise à jour
        # chaque frame par set_target_stade().
        self._target  = max_fear
        # Vitesse d'interpolation (points de peur par seconde). Plus petit
        # = transition plus douce. 60 → on rattrape un écart de 100 en ~1.7s.
        self._vitesse_interp = 60.0

    # ── Réglage du stade cible ───────────────────────────────────────────

    def set_target_stade(self, stade):
        """Fixe la cible (en stade entier 0..5). update(dt) fera tendre
        current vers stade × (max_fear / NB_STADES) progressivement."""
        stade = max(0, min(self.NB_STADES, int(stade)))
        # Stade 0 → cible 0 (calme). Stade 5 → cible max_fear (panique).
        self._target = stade * (self.max_fear / self.NB_STADES)

    def update(self, dt):
        """Interpole current vers _target. À appeler chaque frame."""
        delta = self._target - self.current
        if abs(delta) < 0.5:
            self.current = self._target
            return
        # On avance d'au plus _vitesse_interp × dt vers la cible.
        pas = self._vitesse_interp * dt
        if pas < 0:
            pas = 1
        if delta > 0:
            self.current = min(self._target, self.current + pas)
        else:
            self.current = max(self._target, self.current - pas)

    # ── Lecture ──────────────────────────────────────────────────────────

    def get_stade(self):
        """Stade entier actuel (0..NB_STADES). Utilisé par le gameplay."""
        ratio = self.current / self.max_fear
        return min(self.NB_STADES, int(ratio * self.NB_STADES + 0.5))

    def get_ratio(self):
        """Renvoie un float entre 0 et 1 (pratique pour la jauge HUD)."""
        return self.current / self.max_fear

    def is_zero(self):
        """True quand la peur est totalement vaincue → événement final."""
        return self.current <= 0

    # ── API legacy (toujours utilisée par certains systèmes) ─────────────

    def reduce(self, amount):
        """Diminue immédiatement la peur (sans interpolation). Utilisé par
        ex. quand on rallume une bougie : effet instantané voulu."""
        self.current = max(0, self.current - amount)
        self._target = min(self._target, self.current)

    def increase(self, amount):
        """Augmente immédiatement la peur (effet instantané)."""
        self.current = min(self.max_fear, self.current + amount)
        self._target = max(self._target, self.current)
