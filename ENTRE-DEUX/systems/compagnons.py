# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Groupe de compagnons (CompagnonGroup)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Une classe : CompagnonGroup, qui gère TOUS les compagnons ensemble :
#
#       - les créer / les supprimer (set_nb)
#       - les rappeler dans la cape ou les faire ressortir (toggler_cape)
#       - les remettre près du joueur (respawn)
#       - calculer leur effet sur la jauge de peur (affecter_peur)
#       - les mettre à jour et les dessiner (update / draw)
#
#  Un "compagnon" individuel (son comportement, son dessin) est aujourd'hui
#  une LUCIOLE, définie dans :
#       entities/luciole.py   →  classe Luciole
#  Ici on s'occupe seulement du GROUPE et des règles globales.
#
#  NOTE HISTORIQUE : ce fichier s'appelle compagnons.py et la classe s'appelle
#  CompagnonGroup parce qu'à l'origine c'étaient des petits fantômes (cf.
#  entities/compagnon.py, conservé). On a gardé les noms "compagnon" un peu
#  partout pour ne pas tout casser — mais conceptuellement maintenant ce sont
#  des lucioles. C'est un détail d'implémentation, pas un piège.
#
#  RÈGLES DU JEU (sur la jauge de peur) :
#  --------------------------------------
#     - Tous les compagnons dans la cape → peur baisse VITE
#     - Compagnon proche du joueur       → peur baisse DOUCEMENT
#     - Compagnon trop loin              → peur MONTE (mauvais !)
#
#  Les vitesses exactes sont dans settings.py :
#       PEUR_VITESSE_BAISSE_CAPE
#       PEUR_VITESSE_BAISSE_PROCHE
#       PEUR_VITESSE_HAUSSE_LOIN
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  Une seule instance dans core/game.py :
#       self.compagnons = CompagnonGroup(nb=...)
#  Chaque frame, game.py appelle :
#       self.compagnons.update(dt, self.joueur)
#       self.compagnons.affecter_peur(self.peur, self.joueur, dt)
#       self.compagnons.draw(self.screen, self.camera, self.joueur)
#  La touche [C] déclenche :
#       self.compagnons.toggler_cape()
#  Le menu Paramètres → Compagnons appelle :
#       self.compagnons.set_nb(nouveau_nombre)
#       self.compagnons.respawn(self.joueur)
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Effet d'un compagnon sur la peur → affecter_peur() + settings.py
#     - Comportement de la touche C      → toggler_cape()
#     - Position de respawn              → respawn()
#     - Limite max de compagnons         → settings.COMPAGNON_NB_MAX
#     - Apparence / orbite des lucioles  → entities/luciole.py (constantes
#                                          en haut du fichier : couleur,
#                                          rayon orbite, vitesse, halo)
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D10] dt                   — vitesses peur × dt = par seconde
#     [D11] math.hypot           — utilisé indirectement via Luciole.distance_au_joueur
#     [D22] Machine à états      — dans_cape (par compagnon, géré ici en groupe)
#
# ─────────────────────────────────────────────────────────────────────────────

import settings
# ── Choix de l'entité "compagnon" ────────────────────────────────────────────
# Historiquement on utilisait entities.compagnon.Compagnon (un petit fantôme
# blanc avec une IA "suit / court / pause"). On l'a remplacé par Luciole, qui
# est juste une lumière flottant en orbite autour du joueur (pas de collision
# → plus de bug près des murs ; rendu plus joli ; cohérent avec l'esthétique).
#
# La classe Luciole expose la MÊME API publique que Compagnon (mêmes méthodes,
# mêmes attributs lus depuis ce fichier), donc le reste du code n'a rien à
# changer. Si on veut revenir à l'ancien rendu, il suffit de remplacer
# l'import ci-dessous par :
#       from entities.compagnon import Compagnon as Luciole
from entities.luciole import Luciole


class CompagnonGroup:
    """Gère une liste de compagnons et leur effet sur le jeu."""

    # ═════════════════════════════════════════════════════════════════════════
    #  1. CONSTRUCTION
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Appelé depuis core/game.py :
    #       self.compagnons = CompagnonGroup(nb=nb_compagnons)
    #  où nb_compagnons est lu dans game_config.json (préférence persistante).

    def __init__(self, nb=0):
        # Liste des compagnons (objets Luciole). Vide au départ ;
        # on délègue à set_nb() la création initiale.
        self.compagnons = []
        self.set_nb(nb)

    # ═════════════════════════════════════════════════════════════════════════
    #  2. CHANGER LE NOMBRE DE COMPAGNONS
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Utilisé par :
    #     - le constructeur
    #     - le menu Paramètres → Compagnons (← / → pour ajuster)
    #
    #  Algorithme : si on demande plus → on en crée autant qu'il manque ;
    #  si on demande moins → on retire les derniers de la liste.
    #  Si on dépasse COMPAGNON_NB_MAX (settings.py) : on plafonne.

    def set_nb(self, n):
        """Ajuste le nombre de compagnons à exactement `n`."""

        # Borne : pas moins de 0, pas plus que le max autorisé.
        if n < 0:
            n = 0
        if n > settings.COMPAGNON_NB_MAX:
            n = settings.COMPAGNON_NB_MAX

        # Trop de compagnons → on retire les derniers.
        # pop() sans argument retire le dernier élément de la liste.
        while len(self.compagnons) > n:
            self.compagnons.pop()

        # Pas assez → on ajoute les manquants. Chaque nouvelle luciole
        # reçoit un idx unique = sa position dans la liste au moment de
        # la création (sert dans Luciole.__init__ pour étaler les phases
        # initiales sur le cercle d'orbite — sinon toutes les lucioles
        # partiraient au même endroit).
        while len(self.compagnons) < n:
            idx = len(self.compagnons)
            nouveau = Luciole(x=0, y=0, idx=idx)
            self.compagnons.append(nouveau)

    # ═════════════════════════════════════════════════════════════════════════
    #  3. REPLACER TOUS LES COMPAGNONS À CÔTÉ DU JOUEUR
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Utilisé quand :
    #     - on démarre une nouvelle partie
    #     - on change de carte
    #     - on vient d'ajouter des compagnons via le menu Paramètres
    #  (sinon ils restent à leur ancienne position ou à (0,0) pour les neufs).

    def respawn(self, joueur):
        """Téléporte tous les compagnons à la position du joueur, visibles."""
        for c in self.compagnons:
            c.x = float(joueur.rect.centerx)
            c.y = float(joueur.rect.bottom - 8)
            c.vx = 0.0
            c.vy = 0.0
            c.dans_cape = False
            c.visibilite = 1.0   # totalement visible
            c.etat = "suit"

    # ═════════════════════════════════════════════════════════════════════════
    #  4. CAPE : RAPPELER / RESSORTIR
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Déclenché par la touche [C] (géré dans core/game.py dans _update_jeu).
    #  Règle : si au moins un compagnon est DEHORS, [C] les rappelle TOUS.
    #          Sinon (tous déjà dedans), [C] les fait TOUS sortir.

    def toggler_cape(self):
        """Bascule l'état "tous dans la cape" / "tous dehors"."""

        # Aucun compagnon → rien à faire.
        if len(self.compagnons) == 0:
            return

        if self.tous_dans_cape():
            self.sortir_de_cape()
        else:
            self.appeler_dans_cape()

    def appeler_dans_cape(self):
        """Tous les compagnons rentrent dans la cape (animation gérée par eux)."""
        for c in self.compagnons:
            c.dans_cape = True

    def sortir_de_cape(self):
        """Tous les compagnons ressortent de la cape, état "suit" par défaut."""
        for c in self.compagnons:
            c.dans_cape = False
            c.etat = "suit"

    def tous_dans_cape(self):
        """Renvoie True si TOUS les compagnons sont dans la cape.

        False sinon, ou s'il n'y a pas de compagnon (cas particulier :
        on ne peut pas dire "tous dans la cape" quand l'ensemble est vide,
        ça causerait toggler_cape à essayer de faire sortir le néant)."""

        if len(self.compagnons) == 0:
            return False
        # On vérifie un par un : dès qu'on en trouve un dehors, on s'arrête
        # (court-circuit — pas besoin de tout parcourir).
        for c in self.compagnons:
            if not c.dans_cape:
                return False
        return True

    # ═════════════════════════════════════════════════════════════════════════
    #  5. UPDATE (déléguée à chaque compagnon)
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Appelé chaque frame par core/game.py. On délègue simplement à
    #  chaque compagnon — toute l'IA est dans entities/compagnon.py.

    def update(self, dt, joueur):
        """Avance l'IA de chaque compagnon. dt = temps écoulé [D10]."""
        for c in self.compagnons:
            c.update(dt, joueur)

    # ═════════════════════════════════════════════════════════════════════════
    #  6. EFFET SUR LA JAUGE DE PEUR
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Appelé chaque frame par core/game.py juste après update().
    #     peur            = instance de FearSystem (systems/fear_system.py)
    #     peur.reduce(x)   → fait baisser la peur de x
    #     peur.increase(x) → fait monter la peur de x
    #
    #  Les vitesses sont définies dans settings.py
    #  (PEUR_VITESSE_BAISSE_CAPE / _PROCHE / _HAUSSE_LOIN). On les
    #  multiplie par dt → "vitesse par seconde" cohérente quel que soit
    #  le framerate.

    def affecter_peur(self, peur, joueur, dt):
        """Cumule l'effet apaisant ou angoissant de chaque compagnon sur la peur."""

        # Pas de compagnons ou pas de jauge → rien à faire.
        if len(self.compagnons) == 0 or peur is None:
            return

        # ── Cas 1 : TOUS dans la cape → la peur fond vite ────────────────────
        # Cas séparé pour qu'un appel unique remplace N appels reduce(),
        # et pour récompenser le joueur qui regroupe ses Lueurs.
        if self.tous_dans_cape():
            peur.reduce(settings.PEUR_VITESSE_BAISSE_CAPE * dt)
            return

        # ── Cas 2 : au moins un dehors → on calcule pour chacun ──────────────
        for c in self.compagnons:

            if c.dans_cape:
                # Dans la cape → effet apaisant doux (compte comme "proche")
                peur.reduce(settings.PEUR_VITESSE_BAISSE_PROCHE * dt)
                continue

            # Pas dans la cape → on regarde la distance au joueur [D11].
            distance = c.distance_au_joueur(joueur)
            if distance <= settings.COMPAGNON_DIST_RASSURANT:
                # Assez proche → rassurant → peur baisse.
                peur.reduce(settings.PEUR_VITESSE_BAISSE_PROCHE * dt)
            else:
                # Trop loin → angoissant → peur monte.
                peur.increase(settings.PEUR_VITESSE_HAUSSE_LOIN * dt)

    # ═════════════════════════════════════════════════════════════════════════
    #  7. RENDU — en deux passes pour l'effet de profondeur
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Les lucioles ont une profondeur Z (cf. entities/luciole.py) qui
    #  dérive lentement entre -1 (derrière le joueur) et +1 (devant).
    #  Pour rendre cet effet visible, core/game.py appelle :
    #
    #       compagnons.draw_derriere(...)   ← AVANT le draw du joueur
    #       (le joueur se dessine)
    #       compagnons.draw_devant(...)     ← APRÈS le draw du joueur
    #
    #  Comme ça, les lucioles "derrière" sont occultées par le joueur
    #  (illusion 3D bon marché), celles "devant" recouvrent le joueur.
    #
    #  draw() (sans suffixe) reste disponible : elle dessine TOUTES les
    #  lucioles dans une seule passe, comme avant. Utile pour les écrans
    #  où on n'a pas la séparation (par ex. menu, ou debug).

    def draw_derriere(self, surf, camera, joueur):
        """Dessine UNIQUEMENT les lucioles dont z < 0 (derrière le joueur)."""
        for c in self.compagnons:
            # Compatible avec l'ancienne classe Compagnon (qui n'a pas
            # est_devant_joueur) : si la méthode n'existe pas, on
            # considère que la luciole est devant (rien à dessiner ici).
            if hasattr(c, "est_devant_joueur") and not c.est_devant_joueur():
                c.draw(surf, camera, joueur)

    def draw_devant(self, surf, camera, joueur):
        """Dessine UNIQUEMENT les lucioles dont z >= 0 (devant le joueur)."""
        for c in self.compagnons:
            # Compatible Compagnon : pas de est_devant_joueur → toujours devant.
            if not hasattr(c, "est_devant_joueur") or c.est_devant_joueur():
                c.draw(surf, camera, joueur)

    def draw(self, surf, camera, joueur):
        """Dessine TOUTES les lucioles d'un coup (sans z-order).

        Utile pour les écrans simples où on ne sépare pas avant/après le
        joueur. Pour le rendu jeu normal, préférer draw_derriere / draw_devant."""
        for c in self.compagnons:
            c.draw(surf, camera, joueur)
