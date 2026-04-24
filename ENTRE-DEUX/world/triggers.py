# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Zones-déclencheurs (triggers) du monde
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Définit des "zones" invisibles qu'on pose dans la carte et qui FONT
#  QUELQUE CHOSE quand le joueur entre dedans. Deux types pour l'instant :
#
#       TeleportTrigger  → téléporte le joueur (autre carte ou autre point).
#                          Équivalent moderne du Portail historique, en plus
#                          léger : pas de besoin d'un fondu spécifique, on
#                          délègue à game._declencher_fondu si voulu.
#
#       CutsceneTrigger  → lance une cinématique scriptée
#                          (cf. systems/cutscene.py).
#
#  Les deux héritent de TriggerZone, qui s'occupe juste de la collision et
#  du "j'ai déjà été déclenché ?" (one-shot par défaut).
#
#  POURQUOI UN MODULE SÉPARÉ ?
#  ---------------------------
#  Les portails existants (world/scene.py / scene_manager.py) sont liés à
#  la sauvegarde JSON et à l'éditeur. On garde ce module-ci INDÉPENDANT
#  pour pouvoir l'utiliser dans des contextes ad hoc (cinématiques d'intro,
#  scripts pédagogiques, démos, tests). L'intégration éditeur se fera dans
#  un second temps.
#
#  COMMENT L'UTILISER (côté game.py)
#  ---------------------------------
#       from world.triggers import (
#           TriggerZoneGroup, TeleportTrigger, CutsceneTrigger
#       )
#
#       # 1. Construction (au chargement de la map ou pour test ad hoc).
#       self.triggers = TriggerZoneGroup([
#           TeleportTrigger(rect=(1500, 200, 60, 80),
#                           target_map="souvenir_1.json", target_x=100, target_y=400),
#           CutsceneTrigger(rect=(800, 400, 80, 80),
#                           cutscene_factory=construire_cinematique_intro),
#       ])
#
#       # 2. Boucle de jeu (chaque frame).
#       self.triggers.check(self.joueur, ctx={"game": self})
#
#  Le `ctx` est un petit dict passé à la fonction de déclenchement —
#  ça évite à ce module de DÉPENDRE de game.py (pas d'import circulaire).
#  La fonction de déclenchement reçoit ce dict et fait ce qu'il faut
#  (lancer le fondu, créer la cutscene, charger une map, etc.).
#
#  Petit lexique :
#     - trigger     = "déclencheur" — quelque chose qui se déclenche dans
#                     une certaine condition. Ici : "le joueur est entré
#                     dans cette zone".
#     - one-shot    = ne se déclenche QU'UNE fois. Après ça, la zone est
#                     "épuisée". Utile pour les cinématiques d'intro :
#                     on ne veut pas qu'elles rejouent à chaque va-et-vient.
#     - rearmable   = inverse : se déclenche À CHAQUE entrée. Utile pour
#                     les portails (téléportation systématique).
#     - factory     = "fabrique" — une FONCTION qui CRÉE l'objet voulu au
#                     moment d'être déclenchée. On stocke la fabrique
#                     plutôt que la cinématique elle-même : permet de
#                     reconstruire une cinématique fraîche à chaque
#                     déclenchement (utile en mode rearmable).
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D4]   pygame.Rect — collision joueur/zone
#     [D22]  Machine à états — déclenché / pas-déclenché
#     [D33]  List comprehension — filtrage des zones non-épuisées
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame


# ═════════════════════════════════════════════════════════════════════════════
#  1. CLASSE DE BASE
# ═════════════════════════════════════════════════════════════════════════════
#
#  Un TriggerZone, c'est juste :
#       - un Rect (la zone),
#       - un état "déclenché ou pas" (pour le mode one-shot),
#       - une méthode on_enter(ctx) à surcharger dans les sous-classes.
#
#  Pour rester sympathique avec le débogueur visuel : on garde aussi un
#  attribut `nom` (string) qu'on peut afficher en superposition en mode
#  éditeur (à brancher plus tard dans world/editor.py).

class TriggerZone:
    """Zone-déclencheur générique. Hérité par TeleportTrigger / CutsceneTrigger."""

    def __init__(self, rect, nom="", one_shot=True):
        """rect : tuple (x, y, w, h) en coords MONDE, ou pygame.Rect.
        nom  : libellé optionnel pour l'éditeur / le debug.
        one_shot : si True, ne se déclenche qu'UNE fois (défaut).
                   Pour un comportement "à chaque entrée", passer False
                   ET surcharger _on_exit pour réarmer."""

        if isinstance(rect, pygame.Rect):
            self.rect = pygame.Rect(rect)        # copie
        else:
            x, y, w, h = rect
            self.rect = pygame.Rect(x, y, w, h)

        self.nom        = nom
        self.one_shot   = one_shot
        self.declenchee = False
        # Mémorise si le joueur était DÉJÀ dans la zone à la frame précédente.
        # Utilisé pour ne déclencher qu'à L'ENTRÉE (front montant), pas à
        # chaque frame où il reste dedans.
        self._dedans_avant = False

    # ─────────────────────────────────────────────────────────────────────────
    #  Test de collision + déclenchement
    # ─────────────────────────────────────────────────────────────────────────

    def check(self, joueur, ctx):
        """À appeler chaque frame. ctx = dict de contexte passé à on_enter."""

        # One-shot et déjà fait → on ignore complètement.
        if self.one_shot and self.declenchee:
            return

        dedans_maintenant = self.rect.colliderect(joueur.rect)

        # Front montant : il vient juste d'entrer.
        if dedans_maintenant and not self._dedans_avant:
            self.declenchee = True
            self.on_enter(ctx)

        # Front descendant : il vient juste de sortir → utile pour réarmer
        # un trigger non-one-shot (autorise le re-déclenchement à la
        # prochaine entrée).
        elif not dedans_maintenant and self._dedans_avant:
            self.on_exit(ctx)
            if not self.one_shot:
                self.declenchee = False

        self._dedans_avant = dedans_maintenant

    # ─────────────────────────────────────────────────────────────────────────
    #  Hooks à surcharger
    # ─────────────────────────────────────────────────────────────────────────

    def on_enter(self, ctx):
        """Appelé UNE FOIS quand le joueur entre dans la zone.
        À surcharger dans les sous-classes. Par défaut : ne fait rien."""
        pass

    def on_exit(self, ctx):
        """Appelé quand le joueur sort de la zone (front descendant).
        Par défaut : ne fait rien — utile pour les triggers rearmables."""
        pass

    # ─────────────────────────────────────────────────────────────────────────
    #  Rendu de debug (mode éditeur)
    # ─────────────────────────────────────────────────────────────────────────

    # Couleur RGB par défaut — surchargée dans les sous-classes pour qu'on
    # voie d'un coup d'œil la nature du trigger (vert = télé, jaune = cutscene).
    _COULEUR_DEBUG = (200, 200, 200)

    def draw_debug(self, surface, camera, font=None):
        """Affiche le rectangle de la zone (semi-transparent) + le nom.
        À appeler UNIQUEMENT en mode éditeur. surface = écran, camera =
        Camera (offset_x/offset_y), font = pygame.font.Font (optionnel)."""

        # Conversion monde → écran via la caméra.
        ox = getattr(camera, "offset_x", 0)
        oy = getattr(camera, "offset_y", 0)
        rect_ecran = pygame.Rect(
            self.rect.x - ox, self.rect.y - oy,
            self.rect.w, self.rect.h
        )

        # Remplissage semi-transparent (calque dédié — pygame n'aime pas
        # l'alpha sur draw.rect direct).
        couleur = self._COULEUR_DEBUG
        calque = pygame.Surface((rect_ecran.w, rect_ecran.h), pygame.SRCALPHA)
        # Plus pâle si déjà déclenché : feedback visuel "consommé".
        alpha_fond   = 30 if self.declenchee else 70
        alpha_bord   = 120 if self.declenchee else 220
        calque.fill((couleur[0], couleur[1], couleur[2], alpha_fond))
        surface.blit(calque, (rect_ecran.x, rect_ecran.y))

        # Bordure pleine.
        pygame.draw.rect(
            surface,
            (couleur[0], couleur[1], couleur[2]),
            rect_ecran, 2
        )

        # Libellé (au centre, si on a une police).
        if font is not None and self.nom:
            txt = font.render(self.nom, True, (255, 255, 255))
            surface.blit(
                txt,
                (rect_ecran.centerx - txt.get_width() // 2,
                 rect_ecran.centery - txt.get_height() // 2)
            )


# ═════════════════════════════════════════════════════════════════════════════
#  2. TÉLÉPORTATION
# ═════════════════════════════════════════════════════════════════════════════
#
#  Téléporte le joueur — soit dans la même carte (autre point), soit dans
#  une autre carte. Dans les deux cas on délègue à game.py :
#       - même carte : ctx["game"].teleporter_joueur((tx, ty))
#       - autre carte : ctx["game"]._declencher_fondu_carte((map, tx, ty))
#                       (la fonction existante peut s'appeler autrement —
#                       on essaie plusieurs noms pour rester tolérant.)
#
#  On NE charge PAS la carte ici : c'est le rôle de game.py / scene_manager.

class TeleportTrigger(TriggerZone):
    """Téléporte le joueur. Si target_map est None → même carte, sinon change.

    Par défaut, la téléportation est REARMABLE (one_shot=False) : si on
    revient dans la zone, on est re-téléporté. C'est en général ce qu'on
    veut pour un portail. Passer one_shot=True pour les téléportations
    "à usage unique" (ex : tomber dans un trou narratif)."""

    # Vert pomme : "ça t'envoie ailleurs" — facile à repérer sur fond sombre.
    _COULEUR_DEBUG = (90, 220, 130)

    def __init__(self, rect, target_x, target_y, target_map=None,
                 nom="", one_shot=False):
        super().__init__(rect, nom=nom, one_shot=one_shot)
        self.target_x   = float(target_x)
        self.target_y   = float(target_y)
        self.target_map = target_map        # None = même carte

    def on_enter(self, ctx):
        game = ctx.get("game")
        if game is None:
            return

        cible = (self.target_x, self.target_y)

        # Cas 1 : autre carte. On essaie plusieurs noms de méthode pour rester
        # robuste au refactor. Si rien ne matche, on tombe en téléportation
        # locale (mieux que rien).
        if self.target_map:
            for nom_methode in ("declencher_fondu_carte", "_declencher_fondu_carte",
                                "charger_carte"):
                fn = getattr(game, nom_methode, None)
                if callable(fn):
                    fn(self.target_map, self.target_x, self.target_y)
                    return
            # Fallback : on stocke un "_portail_en_attente" — l'attribut
            # historiquement utilisé dans game.py pour déclencher la
            # téléportation au prochain frame (cf. _verifier_portails).
            if hasattr(game, "_portail_en_attente"):
                game._portail_en_attente = (self.target_map, int(self.target_x),
                                            int(self.target_y))
                return

        # Cas 2 : même carte → téléportation immédiate.
        joueur = getattr(game, "joueur", None)
        if joueur is not None and hasattr(joueur, "rect"):
            joueur.rect.x = int(self.target_x)
            joueur.rect.y = int(self.target_y)


# ═════════════════════════════════════════════════════════════════════════════
#  3. DÉCLENCHEUR DE CINÉMATIQUE
# ═════════════════════════════════════════════════════════════════════════════
#
#  Démarre une cinématique (cf. systems/cutscene.py) en bascule game.state
#  vers "cinematic" si l'attribut existe.
#
#  On ne stocke PAS l'objet Cutscene tel quel mais une FABRIQUE. Pourquoi ?
#       1. Une cinématique est un objet à état — la rejouer demande un
#          objet "frais" pour repartir à l'étape 0.
#       2. La fabrique peut prendre `ctx` en argument et adapter la
#          cinématique au contexte (PNJ présents, objets ramassés...).
#
#  Si on veut une cutscene FIXE qui ne se rejoue jamais : passer
#  one_shot=True (défaut). Si on veut qu'elle se rejoue à chaque entrée
#  (debug, ambiance) : one_shot=False.

class CutsceneTrigger(TriggerZone):
    """Démarre une cinématique quand le joueur entre dans la zone.

    cutscene_factory : fonction `f(ctx) -> Cutscene` qui construit la
                       cinématique au moment où on en a besoin. Garder
                       léger : ne pas charger d'assets dedans (fait au
                       démarrage du jeu), juste assembler les étapes."""

    # Jaune doré : "ici, il se passe quelque chose de scénarisé".
    _COULEUR_DEBUG = (240, 200, 80)

    def __init__(self, rect, cutscene_factory, nom="", one_shot=True):
        super().__init__(rect, nom=nom, one_shot=one_shot)
        self.cutscene_factory = cutscene_factory

    def on_enter(self, ctx):
        game = ctx.get("game")
        if game is None or not callable(self.cutscene_factory):
            return

        scene = self.cutscene_factory(ctx)
        if scene is None:
            return

        # Pose la cinématique dans game.cutscene si l'attribut existe.
        # Si game.state existe, bascule vers "cinematic" pour que la boucle
        # du jeu sache qu'il faut figer le joueur. On reste tolérant : si
        # ces attributs n'existent pas encore (refactor en cours), on se
        # contente de poser la cutscene → game.py la traitera quand il sera
        # prêt à l'utiliser.
        game.cutscene = scene
        if hasattr(game, "state"):
            game.state = "cinematic"


# ═════════════════════════════════════════════════════════════════════════════
#  4. GROUPE DE TRIGGERS — un seul check() pour toutes les zones d'une carte
# ═════════════════════════════════════════════════════════════════════════════
#
#  Sucre syntaxique : permet d'écrire `self.triggers.check(joueur, ctx)`
#  au lieu de boucler à la main dans game.py. Aussi pratique pour le
#  rendu de debug (afficher tous les rects en éditeur).

class TriggerZoneGroup:
    """Conteneur léger pour une liste de TriggerZone."""

    def __init__(self, zones=None):
        self.zones = list(zones) if zones else []

    def add(self, zone):
        """Ajoute une zone au groupe. Renvoie la zone (chaînage)."""
        self.zones.append(zone)
        return zone

    def check(self, joueur, ctx):
        """Teste toutes les zones contre le joueur (chaque frame)."""
        for zone in self.zones:
            zone.check(joueur, ctx)

    def reset(self):
        """Remet à zéro tous les triggers (déclenchée=False).
        Utile au respawn ou au rechargement de la carte."""
        for zone in self.zones:
            zone.declenchee = False
            zone._dedans_avant = False

    def actives(self):
        """Liste des zones encore "armées" (pas encore déclenchées une fois
        en mode one_shot, ou rearmables). [D33]"""
        return [z for z in self.zones if not (z.one_shot and z.declenchee)]

    def __iter__(self):
        return iter(self.zones)

    def __len__(self):
        return len(self.zones)

    def draw_debug(self, surface, camera, font=None):
        """Dessine toutes les zones (mode éditeur uniquement).
        Délègue à TriggerZone.draw_debug() pour chaque zone."""
        for zone in self.zones:
            zone.draw_debug(surface, camera, font)
