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

import json
import os
import pygame

# Dossier des cinématiques (fichiers JSON).
CINEMATIQUES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "cinematiques"
)


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

    def to_dict(self):
        """Sérialise la zone pour la sauvegarde JSON (map ou snapshot)."""
        return {
            "type":     "base",
            "x":        self.rect.x,
            "y":        self.rect.y,
            "w":        self.rect.width,
            "h":        self.rect.height,
            "nom":      self.nom,
            "one_shot": self.one_shot,
        }

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

    def to_dict(self):
        d = super().to_dict()
        d["type"]       = "teleport"
        d["target_x"]   = self.target_x
        d["target_y"]   = self.target_y
        d["target_map"] = self.target_map
        return d

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

    def __init__(self, rect, cutscene_nom="", cutscene_factory=None,
                 nom="", one_shot=True, max_plays=1):
        """cutscene_nom  : nom du fichier JSON dans cinematiques/ (ex: "intro").
        cutscene_factory : fabrique Python optionnelle (rétrocompatibilité).
                           Si fournie, elle a priorité sur le chargement JSON.
        max_plays        : nombre TOTAL de lectures dans toute la partie.
                           1 = unique (défaut). 0 = illimité. Compteur stocké
                           dans la sauvegarde, reset à `Nouvelle partie`."""
        super().__init__(rect, nom=nom or cutscene_nom, one_shot=one_shot)
        self.cutscene_nom     = cutscene_nom
        self.cutscene_factory = cutscene_factory
        self.max_plays        = int(max_plays)

    def _charger_scene(self, ctx):
        """Construit la Cutscene : fabrique Python d'abord, fichier JSON ensuite."""
        if callable(self.cutscene_factory):
            return self.cutscene_factory(ctx)
        if self.cutscene_nom:
            return _charger_cutscene_fichier(self.cutscene_nom, ctx)
        return None

    def on_enter(self, ctx):
        game = ctx.get("game")
        if game is None:
            return

        # Compteur persistant : si on a déjà joué cette cinématique le nombre
        # max de fois autorisé (toute la partie confondue), on ne refait rien.
        # max_plays=0 = illimité.
        if self.max_plays > 0 and self.cutscene_nom:
            joues = getattr(game, "cinematiques_jouees", {})
            deja  = joues.get(self.cutscene_nom, 0)
            if deja >= self.max_plays:
                return

        scene = self._charger_scene(ctx)
        if scene is None:
            return

        game.cutscene = scene
        if hasattr(game, "state"):
            game.state = "cinematic"

        # Incrémente le compteur (et le marque pour sauvegarde).
        if self.cutscene_nom and hasattr(game, "cinematiques_jouees"):
            game.cinematiques_jouees[self.cutscene_nom] = \
                game.cinematiques_jouees.get(self.cutscene_nom, 0) + 1

    def to_dict(self):
        d = super().to_dict()
        d["type"]         = "cutscene"
        d["cutscene_nom"] = self.cutscene_nom
        d["max_plays"]    = self.max_plays
        return d


# ═════════════════════════════════════════════════════════════════════════════
#  3b. ZONE DE PEUR (fear_zone) — limite l'accès selon le stade de peur
# ═════════════════════════════════════════════════════════════════════════════
#
#  Mécanique de gameplay :
#    - Quand le joueur ENTRE dans la zone, on affiche un overlay "fear_text"
#      (un petit texte qui fade in/out).
#    - Tant qu'il est DANS la zone et que son stade de peur > peur_max
#      requise, sa vitesse est divisée par 2 par stade au-dessus
#      (= ralentissement progressif).
#    - Si stade > peur_max ET le joueur essaie de SORTIR par le côté
#      "direction_mur" (par défaut: droite), il est BLOQUÉ comme par
#      une plateforme invisible.
#
#  Exemple : peur_max=0 → il faut être à stade 0 (calme, 5 compagnons
#  proches) pour traverser librement. Avec stade 2, on est ralenti
#  ×0.25 et on bute sur le mur.
#
#  L'overlay et le wall sont gérés par game.py au moment du check —
#  ce trigger ne fait QUE stocker les paramètres et exposer une méthode
#  d'aide. Pas d'effet en propre dans on_enter / on_exit (sinon ça se
#  déclencherait une seule fois alors qu'on veut un effet CONTINU).

class FearZoneTrigger(TriggerZone):
    """Zone qui ralentit (et finit par bloquer) le joueur quand sa peur
    est trop élevée. one_shot=False par défaut : effet permanent tant
    qu'on est dedans."""

    # Rouge orangé : couleur "alerte/danger" en éditeur.
    _COULEUR_DEBUG = (240, 90, 70)

    def __init__(self, rect, peur_max=0, direction_mur="d",
                 texte="Vous avez trop peur pour avancer...",
                 nom="", one_shot=False):
        """rect          : rectangle de la zone (coords monde).
        peur_max         : stade de peur MAX toléré pour traverser librement
                           (0..5). Plus c'est bas, plus c'est exigeant.
        direction_mur    : "g"/"d"/"h"/"b" → côté de la zone qui bloque
                           le joueur quand il a trop peur. "d" = droite.
        texte            : message affiché à l'overlay au 1er passage.
        """
        super().__init__(rect, nom=nom, one_shot=one_shot)
        # Borne peur_max dans [0, 5] (NB_STADES) pour éviter les valeurs
        # absurdes (un peur_max=10 rendrait la zone toujours franchissable).
        self.peur_max      = max(0, min(5, int(peur_max)))
        # Borne la direction à une lettre valide. "d" par défaut = on bloque
        # le côté droit, le joueur peut quand même reculer vers la gauche.
        if direction_mur not in ("g", "d", "h", "b"):
            direction_mur = "d"
        self.direction_mur = direction_mur
        self.texte         = texte

    # ── Calcul du ralentissement ────────────────────────────────────────

    def facteur_vitesse(self, stade):
        """Renvoie le multiplicateur de vitesse appliqué CONTRE LE MUR.

        C'est le pire cas : le joueur est tout au bord du `direction_mur`.
        Ailleurs dans la zone, la vitesse est moins pénalisée (cf.
        `facteur_vitesse_progressif()`).

        - Stade <= peur_max → 1.0 (vitesse normale, on passe sans souci).
        - Sinon → réduction LINÉAIRE proportionnelle au "trop-plein" de
          peur, avec un PLANCHER pour qu'on puisse toujours marcher
          (sinon on resterait coincé dans la zone).

        Formule (cf. settings.py FEAR_ZONE_VITESSE_MIN / _REDUCTION_PAR_STADE) :
            mult = max(MIN, 1.0 - REDUCTION × (stade - peur_max))

        Exemples avec les défauts (MIN = 0.35, REDUCTION = 0.18) :
            +1 stade  → 0.82
            +2 stades → 0.64
            +3 stades → 0.46
            +4 stades → 0.35   (plancher)

        Le plancher garantit qu'on peut TOUJOURS marcher pour rebrousser
        chemin — la zone est dissuasive, pas une prison.
        """
        # Lecture tardive de settings → si tu changes les valeurs en cours
        # de partie via l'éditeur de constantes, l'effet est immédiat.
        try:
            import settings as _s
            mini      = _s.FEAR_ZONE_VITESSE_MIN
            reduction = _s.FEAR_ZONE_REDUCTION_PAR_STADE
        except (ImportError, AttributeError):
            mini      = 0.35
            reduction = 0.18

        diff = stade - self.peur_max
        if diff <= 0:
            return 1.0
        mult = 1.0 - reduction * diff
        if mult < mini:
            mult = mini
        return mult

    # ─────────────────────────────────────────────────────────────────────
    #  RALENTISSEMENT PROGRESSIF SELON LA DISTANCE AU MUR
    # ─────────────────────────────────────────────────────────────────────
    #
    #  Idée : plus le joueur s'approche du `direction_mur`, plus il est
    #  ralenti. Plus il s'éloigne (vers le côté opposé de la zone), plus
    #  il retrouve sa vitesse normale.
    #
    #  POURQUOI ? Pour donner un FEEDBACK CLAIR au joueur :
    #     - "Je vais plus vite quand je m'éloigne du mur" → message :
    #       "ce mur me repousse, j'ai trop peur pour y aller".
    #     - "Je rampe quand je suis collé au mur" → message :
    #       "il faut vraiment que je sorte de là".
    #  C'est un guide kinesthétique, sans HUD ni texte explicite.
    #
    #  FORMULE :
    #     prog = position relative dans la zone, depuis le côté opposé
    #            au mur (0 = à l'opposé, 1 = collé contre le mur)
    #     mult = 1.0 - prog × (1.0 - mult_au_mur)
    #     mult = max(MIN_ABSOLU, mult)
    #
    #  Exemples avec stade = peur_max + 3 (mult_au_mur = 0.46) :
    #     prog 0.0 (opposé)  → mult 1.00 (pleine vitesse)
    #     prog 0.5 (milieu)  → mult 0.73
    #     prog 1.0 (au mur)  → mult 0.46

    def facteur_vitesse_progressif(self, stade, joueur_rect):
        """Comme facteur_vitesse, mais module selon la distance au mur.

        Renvoie 1.0 si stade <= peur_max (pas de pénalité du tout).
        Sinon, interpole entre 1.0 (à l'opposé du mur) et
        facteur_vitesse(stade) (collé contre le mur).
        """
        if stade <= self.peur_max:
            return 1.0

        # Multiplicateur "au mur" = pire cas (cf. facteur_vitesse).
        mult_au_mur = self.facteur_vitesse(stade)

        # Calcul de la "progression" (0 = côté opposé au mur, 1 = au mur).
        # On utilise le centre du joueur pour éviter les sauts d'1 pixel.
        r = self.rect
        cote = self.direction_mur
        if cote == "d":
            # Mur à droite → prog = 0 quand joueur est à gauche, 1 à droite
            if r.width <= 0:
                prog = 1.0
            else:
                prog = (joueur_rect.centerx - r.left) / r.width
        elif cote == "g":
            # Mur à gauche → prog = 0 quand joueur est à droite
            if r.width <= 0:
                prog = 1.0
            else:
                prog = (r.right - joueur_rect.centerx) / r.width
        elif cote == "b":
            if r.height <= 0:
                prog = 1.0
            else:
                prog = (joueur_rect.centery - r.top) / r.height
        else:  # "h"
            if r.height <= 0:
                prog = 1.0
            else:
                prog = (r.bottom - joueur_rect.centery) / r.height

        # Borne dans [0, 1] (au cas où le joueur soit légèrement hors zone
        # à cause d'un float ou d'un push).
        if prog < 0.0:
            prog = 0.0
        if prog > 1.0:
            prog = 1.0

        # ── Courbe NON-LINÉAIRE (concave) pour un effet TRÈS marqué ─────────
        # On élève prog à une puissance < 1 pour OBTENIR une courbe qui
        # monte vite près de l'entrée puis ralentit. Conséquence :
        #
        #     prog 0.0  →  pénalité 0 %      (libre)
        #     prog 0.1  →  pénalité ~25 %    (déjà ressenti dès l'entrée)
        #     prog 0.3  →  pénalité ~49 %    (clairement difficile)
        #     prog 0.5  →  pénalité ~66 %    (la moitié de la marge)
        #     prog 0.7  →  pénalité ~81 %
        #     prog 1.0  →  pénalité 100 %    (plancher au mur)
        #
        # Avantage : le joueur SENT le ralentissement immédiatement quand
        # il rentre dans la zone, ce qui rend l'effet lisible visuellement.
        # Avant (linéaire), il fallait être à mi-zone pour voir une vraie
        # différence — le joueur croyait "rien ne change".
        # Si tu veux ajuster : 0.5 → courbe plus pentue (très marquée),
        #                      0.7 → courbe douce, 1.0 → linéaire d'origine.
        EXPOSANT_COURBE = 0.6
        prog_courbe = prog ** EXPOSANT_COURBE

        # Interpolation : 1.0 (loin) → mult_au_mur (proche), avec courbe.
        mult = 1.0 - prog_courbe * (1.0 - mult_au_mur)

        # Plancher absolu de sécurité (ne descend jamais en dessous).
        try:
            import settings as _s
            mini = _s.FEAR_ZONE_VITESSE_MIN
        except (ImportError, AttributeError):
            mini = 0.35
        if mult < mini:
            mult = mini
        return mult

    # ── Mur invisible : RECTANGLE FIN sur le côté `direction_mur` ───────

    def rect_mur(self, epaisseur=8):
        """Renvoie le rect (coords monde) du mur invisible. Utilisé par
        game.py pour bloquer le joueur si stade > peur_max."""
        r = self.rect
        if self.direction_mur == "d":     # bloque la sortie par la DROITE
            return pygame.Rect(r.right - epaisseur, r.y, epaisseur, r.h)
        if self.direction_mur == "g":
            return pygame.Rect(r.x, r.y, epaisseur, r.h)
        if self.direction_mur == "h":
            return pygame.Rect(r.x, r.y, r.w, epaisseur)
        # "b"
        return pygame.Rect(r.x, r.bottom - epaisseur, r.w, epaisseur)

    # ── Sérialisation ───────────────────────────────────────────────────

    def to_dict(self):
        d = super().to_dict()
        d["type"]          = "fear"
        d["peur_max"]      = self.peur_max
        d["direction_mur"] = self.direction_mur
        d["texte"]         = self.texte
        return d


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


# ═════════════════════════════════════════════════════════════════════════════
#  5. UTILITAIRES — sérialisation / chargement de cinématiques depuis JSON
# ═════════════════════════════════════════════════════════════════════════════

def creer_depuis_dict(data):
    """Reconstruit un TriggerZone depuis un dict (issu de to_dict / JSON carte).

    Utilisé par game.py pour reconstruire les triggers après chaque chargement
    de carte (via _sync_triggers_depuis_editeur)."""
    rect     = (data["x"], data["y"], data["w"], data["h"])
    nom      = data.get("nom", "")
    one_shot = data.get("one_shot", True)
    t        = data.get("type", "base")

    if t == "cutscene":
        return CutsceneTrigger(
            rect,
            cutscene_nom=data.get("cutscene_nom", ""),
            nom=nom,
            one_shot=one_shot,
            max_plays=int(data.get("max_plays", 1)),
        )
    if t == "teleport":
        return TeleportTrigger(
            rect,
            target_x=data.get("target_x", 0),
            target_y=data.get("target_y", 0),
            target_map=data.get("target_map"),
            nom=nom,
            one_shot=one_shot,
        )
    if t == "fear":
        return FearZoneTrigger(
            rect,
            peur_max=data.get("peur_max", 0),
            direction_mur=data.get("direction_mur", "d"),
            texte=data.get("texte", "Vous avez trop peur pour avancer..."),
            nom=nom,
            # one_shot doit rester False pour les fear_zones : effet continu
            # tant qu'on est dedans, et on veut le revoir à chaque entrée.
            one_shot=False,
        )
    return TriggerZone(rect, nom=nom, one_shot=one_shot)


def _charger_cutscene_fichier(nom, ctx):
    """Charge cinematiques/<nom>.json et renvoie un objet Cutscene.

    Renvoie None si le fichier est introuvable ou invalide (log console)."""
    from systems.cutscene import Cutscene

    chemin = os.path.join(CINEMATIQUES_DIR, f"{nom}.json")
    try:
        with open(chemin, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[Trigger] Cinématique introuvable : {chemin}")
        return None
    except Exception as e:
        print(f"[Trigger] Erreur chargement '{nom}' : {e}")
        return None

    return Cutscene(_steps_depuis_data(data))


def _steps_depuis_data(data):
    """Convertit une liste de dicts JSON en étapes Cutscene.

    Types supportés (cf. systems/cutscene.py pour la sémantique) :
        wait, dialogue, fade, camera_focus, camera_focus_pnj, camera_release,
        shake, play_sound, particles_burst, player_walk, set_player_pos
    """
    from systems.cutscene import (
        wait, dialogue, fade, camera_focus, camera_focus_pnj, camera_release,
        shake, play_sound, particles_burst, player_walk, npc_walk_by_name,
        set_player_pos,
        # Nouvelles actions (apparition PNJ, récompenses, story flags, …)
        npc_spawn, npc_despawn,
        grant_skill, grant_luciole, give_item, give_coins,
        set_flag, wait_for_player_at,
        play_music, wait_input,
        unlock_quickuse,
    )

    def _opt_float(v):
        """Convertit en float, ou None si vide/None (pour les durées optionnelles)."""
        if v is None or v == "" or v == "None":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _f(v, defaut=0.0):
        """Convertit en float avec un défaut si invalide."""
        try:
            return float(v) if v not in (None, "", "None") else float(defaut)
        except (TypeError, ValueError):
            return float(defaut)

    def _i(v, defaut=0):
        try:
            return int(float(v)) if v not in (None, "", "None") else int(defaut)
        except (TypeError, ValueError):
            return int(defaut)

    steps = []
    for step in data:
        t = step.get("type", "")
        if t == "wait":
            steps.append(wait(_f(step.get("duration"), 1.0)))
        elif t == "dialogue":
            lines = [(l["texte"], l.get("auteur", ""))
                     for l in step.get("lignes", [])]
            steps.append(dialogue(lines))
        elif t == "fade":
            steps.append(fade(step.get("direction", "out"),
                              _f(step.get("duration"), 1.0)))
        elif t == "camera_focus":
            steps.append(camera_focus(
                (_f(step.get("x")), _f(step.get("y"))),
                _opt_float(step.get("duration")),
                speed=_opt_float(step.get("speed")),
            ))
        elif t == "camera_focus_pnj":
            steps.append(camera_focus_pnj(
                step.get("nom", ""),
                _opt_float(step.get("duration")),
                speed=_opt_float(step.get("speed")),
                follow=bool(step.get("follow", False)),
            ))
        elif t == "camera_release":
            steps.append(camera_release())
        elif t == "shake":
            steps.append(shake(
                _f(step.get("amplitude"), 6.0),
                _f(step.get("duration"),  0.3),
            ))
        elif t == "play_sound":
            steps.append(play_sound(
                step.get("nom", ""),
                _f(step.get("volume"), 1.0),
            ))
        elif t == "particles_burst":
            steps.append(particles_burst(
                _f(step.get("x")), _f(step.get("y")),
                _i(step.get("nb"), 12),
                tuple(step.get("couleur", (255, 255, 200))),
            ))
        elif t == "player_walk":
            steps.append(player_walk(
                (_f(step.get("x")), _f(step.get("y"))),
                _f(step.get("speed"), 100),
            ))
        elif t == "npc_walk_by_name":
            steps.append(npc_walk_by_name(
                step.get("nom_pnj", ""),
                (_f(step.get("x")), _f(step.get("y"))),
                _f(step.get("speed"), 80),
            ))
        elif t == "set_player_pos":
            steps.append(set_player_pos(_f(step.get("x")), _f(step.get("y"))))

        # ── Nouvelles actions ──────────────────────────────────────────
        elif t == "npc_spawn":
            steps.append(npc_spawn(
                step.get("nom", "PNJ"),
                _f(step.get("x")), _f(step.get("y")),
                dialogues=step.get("dialogues", []) or [],
                sprite=step.get("sprite") or None,
                dialogue_mode=step.get("dialogue_mode", "boucle_dernier"),
                has_gravity=bool(step.get("has_gravity", 1)),
                events=step.get("events"),
            ))
        elif t == "npc_despawn":
            steps.append(npc_despawn(step.get("nom", "")))
        elif t == "grant_skill":
            steps.append(grant_skill(step.get("value", "")))
        elif t == "grant_luciole":
            steps.append(grant_luciole(step.get("source", "")))
        elif t == "give_item":
            steps.append(give_item(
                step.get("name", ""),
                _i(step.get("count"), 1),
            ))
        elif t == "give_coins":
            steps.append(give_coins(_i(step.get("amount"), 0)))
        elif t == "set_flag":
            steps.append(set_flag(
                step.get("key", ""),
                bool(step.get("value", 1)),
            ))
        elif t == "wait_for_player_at":
            steps.append(wait_for_player_at(
                _f(step.get("x")), _f(step.get("y")),
                radius=_f(step.get("radius"), 32),
                timeout=_f(step.get("timeout"), 60),
            ))
        elif t == "play_music":
            steps.append(play_music(
                step.get("chemin", "") or "",
                volume=_f(step.get("volume"), 0.6),
                fadeout_ms=_i(step.get("fadeout_ms"), 1000),
                fadein_ms=_i(step.get("fadein_ms"), 1500),
            ))
        elif t == "wait_input":
            steps.append(wait_input(
                step.get("touche", "any"),
                timeout=_f(step.get("timeout"), 0),
            ))
        elif t == "unlock_quickuse":
            steps.append(unlock_quickuse(_i(step.get("pommes"), 10)))
    return steps
