# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Fonctions utilitaires
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Petit "fourre-tout" de fonctions qui n'appartiennent à aucun système
#  particulier mais qui servent à plusieurs endroits du jeu :
#
#       _get_font(name, size) — fournit une police pygame, avec CACHE.
#       find_file(...)        — cherche un fichier sous assets/ par son nom.
#       draw_mouse_coords(...) — affiche en haut à gauche les coords souris
#                                (debug / éditeur).
#
#  EXEMPLE CONCRET
#  ---------------
#       # Trouver un sprite quelque part dans assets/, sans connaître son
#       # sous-dossier (sprites/ennemis/slime.png ? ou /persos/slime.png ?)
#       chemin = find_file("slime.png")
#       # → on récupère le chemin complet vers le 1er fichier trouvé.
#
#       # Pendant l'éditeur, voir où on pointe :
#       draw_mouse_coords(screen, camera)
#       # → en jaune : coords ÉCRAN (souris brute)
#       # → en vert  : coords MONDE (souris + offset caméra)
#
#  Petit lexique :
#     - cache de polices = pygame.font.SysFont() est LENT (recherche système).
#                          On garde {(nom, taille): Font} pour ne pas recréer
#                          la même police 60 fois par seconde.
#     - os.walk          = parcourt récursivement un dossier. Renvoie pour
#                          chaque sous-dossier : (chemin, sous-dossiers, fichiers).
#                          Pratique pour chercher "ce fichier, où qu'il soit".
#     - render(...)      = pygame : "transforme un texte en image (Surface)".
#                          Coût non négligeable → si tu rends à chaque frame,
#                          ça additionne ; mais ici (mode debug) c'est OK.
#     - settings.wx/wy   = variables MODULE de settings.py utilisées comme
#                          "tableau d'affichage global" — l'éditeur les lit
#                          pour savoir où on pointe à la souris dans le monde.
#                          C'est moche mais pratique pour du debug.
#
#  POURQUOI find_file LÈVE UNE EXCEPTION ?
#  ---------------------------------------
#  Parce qu'un sprite manquant DOIT casser tôt et fort, avec un message
#  clair. Renvoyer None obligerait à tester partout `if chemin is None`,
#  et un oubli de test → un NoneType plus tard, traceback obscur.
#  Avec FileNotFoundError : message immédiat, on sait quoi corriger.
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  entities/player.py, entities/enemy.py : find_file() pour les sprites.
#  world/editor.py                       : draw_mouse_coords() en debug.
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D24]  module avec état partagé — _font_cache vit ici, partagé partout
#
# ─────────────────────────────────────────────────────────────────────────────

import os
import pygame
import settings


# ═════════════════════════════════════════════════════════════════════════════
#  CACHE DE POLICES
# ═════════════════════════════════════════════════════════════════════════════

_font_cache = {}


def _get_font(name, size):
    """Renvoie une pygame.Font depuis le cache, créée si pas encore vue.
    Le préfixe _ indique "à usage interne" (les autres fichiers passent
    par les fonctions qui l'utilisent)."""
    key = (name, size)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont(name, size)
    return _font_cache[key]


# ═════════════════════════════════════════════════════════════════════════════
#  RECHERCHE DE FICHIER (avec cache pour gros gains de perf)
# ═════════════════════════════════════════════════════════════════════════════

# Cache : {nom_fichier: chemin_complet}. Construit à la 1ʳᵉ recherche en
# faisant UN SEUL os.walk de tout le dossier assets/. Les recherches
# suivantes deviennent O(1) au lieu de re-walker à chaque appel.
# IMPORTANT : ça évitait avant que le chargement du joueur (200+ frames)
# fasse 200+ os.walk de tout le dossier → temps de démarrage très long.
_file_cache_per_dir = {}   # {search_dir: {filename: full_path}}


def _build_file_cache(search_dir):
    """Construit le cache des fichiers de search_dir en UN seul os.walk."""
    base = os.path.dirname(os.path.abspath(__file__))
    search_path = os.path.join(base, search_dir)
    cache = {}
    for root, dirs, files in os.walk(search_path):
        for f in files:
            # 1ʳᵉ occurrence gagne (comme l'ancien comportement).
            if f not in cache:
                cache[f] = os.path.join(root, f)
    return cache


def find_file(filename, search_dir="assets"):
    """Trouve `filename` quelque part sous le dossier `search_dir`.

    Très pratique pour les sprites : on dit "trouve-moi slime.png" sans
    se soucier de savoir s'il est dans assets/sprites/ennemis/ ou
    assets/persos/. La 1ʳᵉ correspondance trouvée gagne.

    Le résultat est CACHÉ : le 1er appel walk tout `search_dir` (lent),
    les suivants sont en O(1) via dict (instantanés).

    Lève FileNotFoundError si rien trouvé (cf. encart du header).
    """
    cache = _file_cache_per_dir.get(search_dir)
    if cache is None:
        cache = _build_file_cache(search_dir)
        _file_cache_per_dir[search_dir] = cache

    path = cache.get(filename)
    if path is None:
        raise FileNotFoundError(f"Fichier '{filename}' introuvable dans '{search_dir}'")
    return path


def reset_file_cache():
    """Invalide le cache (utile si on ajoute des fichiers à chaud)."""
    _file_cache_per_dir.clear()


# ═════════════════════════════════════════════════════════════════════════════
#  DEBUG : COORDONNÉES SOURIS À L'ÉCRAN
# ═════════════════════════════════════════════════════════════════════════════

def draw_mouse_coords(surf, camera=None, y_start=10):
    """Affiche en haut à gauche les coordonnées de la souris (debug / éditeur).

    Avec `camera` fourni, on affiche AUSSI les coords MONDE (= souris
    + offset caméra). Sinon seulement les coords ÉCRAN.

    `y_start` permet de décaler verticalement (ex : 95 = sous le panneau
    d'éditeur déjà occupé en haut).
    """
    font = _get_font("Consolas", 16)
    mx, my = pygame.mouse.get_pos()

    # Coords ÉCRAN (jaune)
    text_screen = font.render(f"Ecran  x:{mx}  y:{my}", True, (255, 255, 0))
    surf.blit(text_screen, (10, y_start))

    # Coords MONDE (vert) — on stocke aussi dans settings pour que d'autres
    # parties du jeu (l'éditeur) puissent lire la dernière position pointée.
    if camera:
        wx = settings.wx = int(mx + camera.offset_x)
        wy = settings.wy = int(my + camera.offset_y)
        text_world = font.render(f"Monde  x:{wx}  y:{wy}", True, (0, 255, 180))
        surf.blit(text_world, (10, y_start + 20))
