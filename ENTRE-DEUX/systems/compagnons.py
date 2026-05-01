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
# ── Entité "compagnon" du jeu : la Luciole ──────────────────────────────────
# Une Luciole est une lumière qui flotte en orbite autour du joueur. Elle
# n'a pas de collision (= pas de bug d'IA contre les murs) et son rendu
# est cohérent avec l'esthétique du jeu (foyer, brume, peur).
#
# Tout le code en aval (HUD, jauge de peur, sauvegarde…) parle de
# "compagnon" mais manipule en fait des Luciole : c'est purement une
# question de vocabulaire de design. Si un jour on ajoute un autre type
# de compagnon, on pourra introduire une classe parente — pour l'instant
# on garde l'archi simple.
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
    #  3b. GAGNER UNE NOUVELLE LUCIOLE (récompense de gameplay)
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  À APPELER quand le joueur DÉBLOQUE une luciole — par exemple :
    #     - après avoir vaincu un boss
    #     - lors d'un échange particulier avec un villageois
    #     - en récompense d'une énigme résolue
    #     - ... toute action narrative qui mérite une récompense rare
    #
    #  RÈGLES :
    #     - Maximum 5 lucioles dans tout le jeu (settings.COMPAGNON_NB_MAX).
    #       Si on est déjà au max, la fonction renvoie False et ne fait rien
    #       (à toi de prévoir un message côté narratif si tu veux le signaler).
    #     - La nouvelle luciole apparaît directement à côté du joueur, déjà
    #       visible (pas d'écran de transition). Effet "pop" simple et net.
    #     - On synchronise aussi `nb_compagnons` dans la config si tu veux
    #       que la sauvegarde soit cohérente après un quit/restart — voir
    #       l'argument `sauvegarder` plus bas.
    #
    #  EXEMPLES D'USAGE :
    #     # Après un boss vaincu, dans game.py :
    #     if boss.vient_de_mourir():
    #         self.compagnons.gagner_luciole(self.joueur, source="boss")
    #
    #     # Après un échange avec un villageois (dans un dialogue) :
    #     if self.compagnons.gagner_luciole(self.joueur, source="villageois"):
    #         show_message("Une luciole te rejoint !")
    #     else:
    #         show_message("Tu en as déjà cinq, tes mains sont pleines.")
    #
    #  VALEUR DE RETOUR :
    #     True  → une nouvelle luciole a été créée et est visible
    #     False → on était déjà au maximum, rien n'a été fait

    def gagner_luciole(self, joueur=None, source="generic", sauvegarder=False):
        """Ajoute UNE nouvelle luciole, jusqu'à la limite de 5.

        Arguments :
            joueur       : l'objet Player (sert à savoir où faire apparaître
                           la nouvelle luciole). Optionnel : si None, elle
                           apparaît à (0, 0) et viendra se positionner toute
                           seule à la prochaine frame.
            source       : étiquette libre pour les logs ("boss", "villageois",
                           "enigme", ...). N'a pas d'effet sur le gameplay.
            sauvegarder  : si True, met aussi à jour game_config.json pour
                           que le gain persiste après une fermeture du jeu.
                           Désactivé par défaut : à toi de décider quand
                           sauvegarder (souvent on le fait déjà après un
                           checkpoint ou en quittant la partie).

        Renvoie True si la luciole a été créée, False si déjà au max.
        """

        # Déjà au maximum (5 par défaut) → rien à faire, on signale par False.
        # Le joueur "narrativement" doit avoir un message ailleurs ; ici on
        # ne fait QUE la mécanique.
        if len(self.compagnons) >= settings.COMPAGNON_NB_MAX:
            return False

        # idx = sa position dans la liste, sert à étaler les phases initiales
        # (couleur, taille, ancres aléatoires...) d'une luciole à l'autre.
        idx = len(self.compagnons)

        # Position de spawn : pile sur le joueur si on l'a, sinon (0, 0).
        # La luciole va de toute façon se "stabiliser" à son ancre dans
        # quelques frames (cf. entities/luciole.py).
        if joueur is not None:
            sx = float(joueur.rect.centerx)
            sy = float(joueur.rect.centery)
        else:
            sx, sy = 0.0, 0.0

        nouvelle = Luciole(x=sx, y=sy, idx=idx)
        # Elle apparaît visible immédiatement (sinon le fade-in serait
        # confus : "j'ai gagné quoi ?"). On peut imaginer plus tard un
        # effet de particules autour de la spawn — pour l'instant on
        # garde simple, à toi de brancher un effet visuel si tu veux.
        nouvelle.dans_cape  = False
        nouvelle.visibilite = 1.0
        nouvelle.etat       = "suit"
        self.compagnons.append(nouvelle)

        # Optionnel : on persiste le gain dans la config (compteur joueur).
        # Sans ça, relancer le jeu repart avec l'ancien nombre. Utiliser
        # avec parcimonie — souvent on préfère sauvegarder seulement aux
        # points de contrôle (cf. core/state_manager).
        if sauvegarder:
            try:
                from systems.save_system import lire_config, ecrire_config
                cfg = lire_config()
                cfg["nb_compagnons"] = len(self.compagnons)
                ecrire_config(cfg)
            except Exception as e:
                # On ne doit JAMAIS planter le jeu pour un souci de save :
                # on log et on continue. Le gain reste valide en mémoire.
                print(f"[gagner_luciole] sauvegarde ignorée ({source}) : {e}")

        # Log discret (utile pour debug : on voit dans la console quelle
        # source a déclenché le gain). Tu peux supprimer si trop bavard.
        print(f"[gagner_luciole] +1 luciole (source={source}, total={len(self.compagnons)})")
        return True

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
        """Cumule l'effet apaisant ou angoissant de chaque compagnon sur la peur.

        OBSOLÈTE : remplacé par calcul_stade_peur() + FearSystem.set_target_stade().
        Conservé pour ne pas casser un appel existant côté core/game.py — la
        nouvelle logique discrète passe par calcul_stade_peur().
        """

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
    #  6b. STADE DE PEUR DISCRET (5 stades, lié au nb de compagnons)
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Règle de jeu :
    #     - Stade de base = NB_STADES (5) → joueur seul = panique max.
    #     - Chaque compagnon PROCHE (cape ou ≤ COMPAGNON_DIST_RASSURANT)
    #       enlève 1 stade.
    #     - Chaque compagnon LOIN (> COMPAGNON_DIST_RASSURANT) AJOUTE 1 stade.
    #     - Résultat clampé dans [0, NB_STADES].
    #
    #  Exemples (avec NB_STADES = 5) :
    #     0 compagnons               → stade 5  (panique)
    #     5 compagnons tous proches  → stade 0  (calme)
    #     3 proches, 2 loin          → stade 5 - 3 + 2 = 4
    #     1 proche, 1 loin           → stade 5 - 1 + 1 = 5

    def calcul_stade_peur(self, joueur, nb_stades=5):
        """Renvoie le stade entier 0..nb_stades selon les compagnons présents.
        À appeler chaque frame, puis passer le résultat à FearSystem.set_target_stade()."""

        nb_proches = 0
        nb_loin    = 0
        for c in self.compagnons:
            if c.dans_cape:
                nb_proches += 1
                continue
            distance = c.distance_au_joueur(joueur)
            if distance <= settings.COMPAGNON_DIST_RASSURANT:
                nb_proches += 1
            else:
                nb_loin += 1

        stade = nb_stades - nb_proches + nb_loin
        return max(0, min(nb_stades, stade))

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
