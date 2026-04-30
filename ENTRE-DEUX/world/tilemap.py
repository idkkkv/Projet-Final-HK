# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Plateformes, murs et décors
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Trois petites classes qui constituent le DÉCOR du jeu :
#
#       Platform — surface SUR LAQUELLE on marche (sol, plate-forme).
#                  Pousse l'entité quel que soit son sens de déplacement.
#
#       Wall     — mur invisible (en général) qui BLOQUE le passage. Il
#                  ne pousse que dans le bon sens (cf. mode_mur=True), pour
#                  éviter d'éjecter le joueur s'il vient d'en sortir.
#
#       Decor    — élément graphique posé dans le monde. Peut être purement
#                  visuel, OU bloquer le joueur si `collision=True`. Optionnel-
#                  lement : une hitbox plus petite que l'image (collision_box).
#
#  EXEMPLE CONCRET (le sol + un buisson devant)
#  --------------------------------------------
#       sol     = Platform(0, 600, 2000, 40, color=(80, 60, 40))
#       buisson = Decor(120, 560, "assets/buisson.png", "buisson",
#                       collision=False)         # on peut le traverser
#
#       arbre   = Decor(400, 500, "assets/arbre.png", "arbre",
#                       collision=True,
#                       collision_box=(20, 80, 40, 60))  # hitbox = le tronc seul
#       → l'image de l'arbre fait 80×140 px, mais on n'est bloqué QUE par
#         un rectangle 40×60 au niveau du tronc (les feuilles passent au-dessus
#         du joueur visuellement, sans le bloquer).
#
#  Petit lexique :
#     - hitbox        = rectangle invisible utilisé pour la collision. Souvent
#                       PLUS PETITE que le sprite (ex : tronc d'un arbre).
#     - collision_box = ici, hitbox spécifique du Decor : (ox, oy, w, h)
#                       relatifs au coin haut-gauche du sprite. Permet
#                       d'avoir une feuillage qui dépasse sans bloquer.
#     - cache         = "_cache_images" garde les images déjà chargées en
#                       mémoire. Si 50 buissons utilisent buisson.png, on
#                       lit le fichier UNE SEULE FOIS, pas 50.
#     - blit          = "coller une image sur une autre". surf.blit(img, pos)
#                       dessine `img` à la position `pos` sur `surf`.
#     - to_dict()     = méthode qui transforme l'objet en dict prêt à être
#                       sauvegardé en JSON (utilisé par world/editor.py).
#     - @property     = décorateur Python qui transforme une méthode en
#                       attribut. On écrit `decor.collision_rect` (sans
#                       parenthèses) au lieu de `decor.collision_rect()`.
#                       Utile quand l'attribut est CALCULÉ à la volée.
#     - mode_mur      = paramètre de resoudre_collision() — voir
#                       world/collision.py pour la différence.
#     - is_border     = True pour les 4 murs invisibles aux bords de la
#                       scène. Le raycasting d'IA les ignore (sinon les
#                       ennemis "voient" la bordure du monde et zigzaguent).
#     - player_only   = True → seul le joueur est bloqué. Utile pour des
#                       passages que les ennemis traversent (ex : portes
#                       à sens unique).
#
#  POURQUOI UN CACHE D'IMAGES ?
#  ----------------------------
#  pygame.image.load() est LENT (lecture disque + décodage). Si une scène
#  a 30 buissons identiques, on ne veut pas relire le PNG 30 fois. Le
#  cache est un simple dict {chemin: Surface} : la 2ᵉ fois qu'on demande
#  la même image, on renvoie celle déjà chargée. Gain énorme au chargement.
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  world/editor.py crée et place ces objets quand on dessine une scène.
#  systems/save_system.py les sérialise/désérialise via to_dict().
#  core/game.py les boucle pour update() et draw() chaque frame.
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Une plateforme TRAVERSABLE par le bas (one-way) → ajouter un
#       paramètre dans Platform et tester vy>0 dans verifier_collision()
#     - Un Decor ANIMÉ                                  → remplacer self.image
#       par une Animation (cf. entities/animation.py)
#     - Couleur du sol par défaut                       → arg `color` de Platform
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D4]   pygame.Rect    — rect = collision + position + dessin
#     [D14]  Surface        — image en mémoire (chargée par image.load)
#     [D24]  cache module   — _cache_images partagé par toutes les instances
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame
from settings import *
from world.collision import resoudre_collision


# ═════════════════════════════════════════════════════════════════════════════
#  CACHE D'IMAGES (partagé par tous les Decor)
# ═════════════════════════════════════════════════════════════════════════════
#
# Préfixe _ = "privé au module". Les autres fichiers ne devraient pas y
# toucher directement — c'est un détail d'implémentation de Decor.

_cache_images = {}   # {chemin_fichier: pygame.Surface}


# ═════════════════════════════════════════════════════════════════════════════
#  1. PLATFORM — sol/plate-forme sur lequel on marche
# ═════════════════════════════════════════════════════════════════════════════

class Platform:
    """Surface bloquante "douce" : on est repoussé peu importe d'où on vient.
    Idéal pour les sols et les plateformes classiques."""

    def __init__(self, x, y, width, height, color):
        self.rect  = pygame.Rect(x, y, width, height)
        self.color = color

    def verifier_collision(self, entite):
        # mode_mur=False → on pousse sans regarder la direction.
        resoudre_collision(entite, self.rect, mode_mur=False)

    def draw(self, surf, camera):
        """Dessine la plateforme à l'écran.

        Convention importante du projet :
          • color = None  → plateforme TOTALEMENT INVISIBLE en jeu.
            Utile pour les collisions Tiled : le visuel vient du calque
            de décor (image de fond), et la Platform ne sert qu'à la
            physique. Sans ce skip, on verrait un rectangle blanc
            par-dessus le joli fond.
          • color = (R,G,B) → plateforme peinte avec cette couleur
            (debug, prototypage, plateformes "nues").

        L'éditeur ajoute un contour GRIS discret (dans core/game.py) pour
        qu'on puisse quand même voir et sélectionner les plateformes
        invisibles pendant l'édition.
        """
        if self.color is None:
            return
        # camera.apply(rect) → convertit les coords MONDE en coords ÉCRAN.
        pygame.draw.rect(surf, self.color, camera.apply(self.rect))



# ═════════════════════════════════════════════════════════════════════════════
#  2. WALL — mur (invisible par défaut) qui bloque le passage
# ═════════════════════════════════════════════════════════════════════════════

class Wall:
    """Bloque dans la direction du déplacement (mode_mur=True). Évite
    qu'un joueur appuyé contre un mur soit "éjecté" dans le décor."""

    def __init__(self, x, y, width, height, visible=False,
                 player_only=False, is_border=False):
        self.rect        = pygame.Rect(x, y, width, height)
        self.visible     = visible        # debug : afficher le mur en noir
        self.player_only = player_only    # True → ennemis passent au travers
        self.is_border   = is_border      # True → ignoré par le raycasting d'IA

    def verifier_collision(self, entite):
        # mode_mur=True : pousse seulement si l'entité allait VERS le mur.
        resoudre_collision(entite, self.rect, mode_mur=True)

    def draw(self, surf, camera):
        # Affichage debug uniquement (les murs sont invisibles en jeu normal).
        if self.visible:
            pygame.draw.rect(surf, (0, 0, 0), camera.apply(self.rect))


# ═════════════════════════════════════════════════════════════════════════════
#  3. DECOR — élément graphique du monde (avec ou sans collision)
# ═════════════════════════════════════════════════════════════════════════════

class Decor:
    """Image posée dans le monde. Bloque le joueur si collision=True.

    collision_box : (ox, oy, w, h) relatif au coin haut-gauche de l'image.
                    Si None → la hitbox = l'image entière.
                    Permet d'avoir une feuillage qui dépasse sans bloquer.
    """

    def __init__(self, x, y, chemin_image, nom_sprite, collision=False,
                 echelle=1.0, collision_box=None,
                 parallax_x=1.0, parallax_y=1.0, foreground=False):
        self.nom_sprite = nom_sprite
        self.collision  = collision
        self.echelle    = echelle
        self.parallax_x = parallax_x
        self.parallax_y = parallax_y
        self.foreground = foreground

        # ── Chargement avec cache + conversion au format écran ───────────
        # Pourquoi convert / convert_alpha ? Sans ça pygame convertit le format
        # de pixel à CHAQUE blit → ~3-5× plus lent sur les grandes images.
        #
        # OPTIMISATION FPS (crucial pour les fonds Tiled) : convert_alpha() est
        # jusqu'à 6× PLUS LENT que convert() pour les images SANS transparence.
        # Les PNG de backgrounds (fond, bg_end, sky…) sont généralement opaques
        # et doivent utiliser convert() pour ne pas tuer les FPS. Pygame indique
        # la présence d'alpha via le flag SRCALPHA sur la surface chargée.
        if chemin_image not in _cache_images:
            img = pygame.image.load(chemin_image)
            try:
                if img.get_flags() & pygame.SRCALPHA:
                    img = img.convert_alpha()      # transparence → chemin alpha
                else:
                    img = img.convert()            # opaque → chemin rapide
            except pygame.error:
                # Display mode pas encore actif (rare) : on laisse tel quel,
                # pygame re-convertira à la volée au 1er blit.
                pass
            _cache_images[chemin_image] = img
        base = _cache_images[chemin_image]

        # ── Mise à l'échelle si demandée ─────────────────────────────────────
        if echelle != 1.0:
            w = max(1, int(base.get_width()  * echelle))
            h = max(1, int(base.get_height() * echelle))
            self.image = pygame.transform.scale(base, (w, h))
        else:
            self.image = base

        self.rect = pygame.Rect(x, y, self.image.get_width(), self.image.get_height())

        # Hitbox personnalisée (None = image entière).
        self.collision_box = collision_box

    @property
    def collision_rect(self):
        """Calcule à la volée le rect de collision DANS LE MONDE.
        @property → on l'utilise comme un attribut : `decor.collision_rect`.
        """
        if self.collision_box:
            ox, oy, cw, ch = self.collision_box
            return pygame.Rect(self.rect.x + ox, self.rect.y + oy, cw, ch)
        return self.rect

    def verifier_collision(self, entite):
        # Pas de collision configurée → on laisse traverser (simple visuel).
        if self.collision:
            resoudre_collision(entite, self.collision_rect, mode_mur=False)

    def draw(self, surf, camera):
        # Parallax : plus parallax_x/y est petit, moins le décor bouge
        # quand la caméra se déplace → effet de profondeur.
        if self.parallax_x == 1.0 and self.parallax_y == 1.0:
            surf.blit(self.image, camera.apply(self.rect))
            return
        sx = int(self.rect.x - camera.offset_x * self.parallax_x)
        sy = int(self.rect.y - camera.offset_y * self.parallax_y)
        surf.blit(self.image, (sx, sy))

    # ─────────────────────────────────────────────────────────────────────────
    #  SÉRIALISATION (pour la sauvegarde JSON via world/editor.py)
    # ─────────────────────────────────────────────────────────────────────────

    def to_dict(self):
        """Convertit l'objet en dict prêt à être écrit dans un JSON.

        Pourquoi pas de `chemin_image` ? Parce qu'on enregistre seulement
        le `sprite` (= nom court). Le chemin est reconstitué au chargement
        à partir d'un registre de sprites (cf. editor.py).
        """
        d = {
            "x":         self.rect.x,
            "y":         self.rect.y,
            "sprite":    self.nom_sprite,
            "collision": self.collision,
            "echelle":   self.echelle,
        }
        if self.collision_box:
            d["collision_box"] = list(self.collision_box)
        if self.parallax_x != 1.0 or self.parallax_y != 1.0:
            d["parallax"] = [self.parallax_x, self.parallax_y]
        if self.foreground:
            d["foreground"] = True

        return d
