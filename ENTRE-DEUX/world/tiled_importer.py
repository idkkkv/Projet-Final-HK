# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Importeur de cartes Tiled (.tmj)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Permet d'importer une carte créée dans Tiled (logiciel open-source de
#  création de cartes 2D) dans l'éditeur du jeu. Tiled exporte en .tmj
#  (format JSON).
#
#  UTILISATION DANS L'ÉDITEUR
#  --------------------------
#  Dans l'éditeur, appuyer sur [I] → popup "Fichier Tiled :" → taper le nom
#  du fichier (dans le dossier tiled/) → les collisions sont importées en tant
#  que Platforms, et le calque fond (si tileset trouvé) est boulonné comme
#  Decor de fond.
#
#  FORMAT ATTENDU (convention de nommage des calques dans Tiled)
#  -------------------------------------------------------------
#  Créer AU MOINS 2 calques dans Tiled :
#     - "fond"       (ou "Fond", "background") : le décor visuel
#     - "collisions" (ou "Collision", "col")   : les tuiles solides
#
#  Toute tuile non nulle dans le calque "collisions" devient une Platform.
#  Le calque "fond" est rendu comme une image de fond (si le tileset PNG
#  est accessible à côté du fichier .tmj).
#
#  OPTIMISATION
#  ------------
#  Les tuiles de collision consécutives sur une même ligne sont fusionnées
#  en une seule Platform plus large — évite des centaines de petits Rects.
#
#  DOSSIER PAR DÉFAUT
#  ------------------
#  Les fichiers .tmj doivent être placés dans ENTRE-DEUX/tiled/.
#  (créer le dossier si besoin)
#
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import pygame

from world.tilemap import Platform, Decor

TILED_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tiled")
DECORS_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                           "assets", "images", "decors")
BLANC       = (255, 255, 255)


# ═════════════════════════════════════════════════════════════════════════════
#  1. POINT D'ENTRÉE
# ═════════════════════════════════════════════════════════════════════════════

def importer_tiled(nom_fichier):
    """Charge nom_fichier.tmj depuis tiled/ et renvoie un dict de résultats :

    {
        "platforms":  [Platform, ...],   # collisions importées
        "decors":     [Decor, ...]       # fond visuel (vide si tileset absent)
        "world_w":    int,               # largeur du monde en pixels
        "world_h":    int,               # hauteur du monde en pixels
        "erreur":     str | None,        # message d'erreur éventuel
    }
    """
    if not nom_fichier.endswith(".tmj"):
        nom_fichier += ".tmj"

    chemin = os.path.join(TILED_DIR, nom_fichier)
    if not os.path.exists(chemin):
        return _erreur(f"Fichier introuvable : {chemin}")

    try:
        with open(chemin, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return _erreur(f"Erreur lecture JSON : {e}")

    map_w  = data.get("width",      0)   # largeur en tuiles
    map_h  = data.get("height",     0)   # hauteur en tuiles
    tile_w = data.get("tilewidth",  32)
    tile_h = data.get("tileheight", 32)

    if map_w == 0 or map_h == 0:
        return _erreur("Carte vide ou dimensions manquantes dans le .tmj")

    layers = data.get("layers", [])

    # Trouver les calques par nom (insensible à la casse, prefixe "col"/"fond")
    layers_col = _trouver_calques(layers, ["collision", "col", "wall", "solid",
                                            "mur", "platform"])
    layer_fond = _trouver_calque(layers,  ["fond", "background", "bg", "sol"])

    platforms = []
    if layers_col:
        # On supporte PLUSIEURS calques de collision : leurs platforms sont
        # ajoutées les unes après les autres (utile si l'utilisateur sépare
        # collisions de mur, de sol, de plafond...).
        for lc in layers_col:
            platforms.extend(_calque_vers_platforms(lc, map_w, tile_w, tile_h))
        # Fusion verticale : transforme les 'lignes empilées' en gros rect
        # (économise les Platform et fait un peu de spatial indexing).
        platforms = _fusionner_vertical(platforms)
    elif layers:
        # Aucun calque "collision" trouvé → on essaie le 2e calque (fallback
        # historique, cas où l'utilisateur n'a pas nommé ses calques).
        if len(layers) >= 2:
            platforms = _calque_vers_platforms(layers[1], map_w, tile_w, tile_h)
            platforms = _fusionner_vertical(platforms)
            print("[Tiled] Aucun calque nommé 'collision' — fallback sur le 2e calque. "
                  "Renomme ton calque pour éviter les surprises.")
        else:
            print("[Tiled] Aucun calque de collision détecté. Crée un calque "
                  "nommé 'collision' (ou 'col', 'wall', 'mur', 'solid', 'platform').")

    decors = []
    tilesets = data.get("tilesets", [])
    if layer_fond and tilesets:
        try:
            decors = _calque_vers_decor_fond(
                layer_fond, map_w, map_h, tile_w, tile_h,
                tilesets, chemin, nom_fichier,
            )
        except Exception as e:
            print(f"[Tiled] Import fond échoué ({e}) — collisions importées quand même")

    return {
        "platforms": platforms,
        "decors":    decors,
        "world_w":   map_w * tile_w,
        "world_h":   map_h * tile_h,
        "erreur":    None,
    }


# ═════════════════════════════════════════════════════════════════════════════
#  2. HELPERS CALQUES
# ═════════════════════════════════════════════════════════════════════════════

def _trouver_calque(layers, mots_cles):
    """Renvoie le PREMIER calque dont le nom contient un des mots-clés
    (insensible à la casse), ou None si rien ne correspond."""
    for layer in layers:
        nom = layer.get("name", "").lower()
        if any(mc in nom for mc in mots_cles):
            return layer
    return None


def _trouver_calques(layers, mots_cles):
    """Comme _trouver_calque mais renvoie TOUS les calques qui matchent
    (insensible à la casse). Utile quand l'utilisateur a séparé ses
    collisions en plusieurs calques (sol / mur / plafond / décor solide)."""
    trouves = []
    for layer in layers:
        if layer.get("type") != "tilelayer":
            continue                # ignore les calques d'objets, groupes, etc.
        nom = layer.get("name", "").lower()
        if any(mc in nom for mc in mots_cles):
            trouves.append(layer)
    return trouves


def _fusionner_vertical(platforms):
    """Fusionne les Platforms verticalement adjacentes (même x, même w)
    pour réduire le nombre de rect (économie spatial grid + collisions).

    Ex : 5 plateformes 32x32 empilées en colonne deviennent 1 plateforme 32x160.
    Ne change pas le résultat des collisions — juste l'efficacité."""
    if not platforms:
        return platforms

    # Tri par (x, w, y) pour grouper les colonnes alignées.
    plats = sorted(platforms,
                   key=lambda p: (p.rect.x, p.rect.w, p.rect.y))
    fusionnees = []
    courante   = None

    for p in plats:
        if (courante is not None
                and p.rect.x == courante.rect.x
                and p.rect.w == courante.rect.w
                and p.rect.y == courante.rect.bottom):
            # Plateforme exactement collée en bas → on étend la courante.
            courante.rect.h += p.rect.h
        else:
            if courante is not None:
                fusionnees.append(courante)
            courante = p

    if courante is not None:
        fusionnees.append(courante)
    return fusionnees


def _calque_vers_platforms(layer, map_w, tile_w, tile_h):
    """Convertit un calque de tuiles en liste de Platforms.

    Algorithme : pour chaque ligne, on fusionne les tuiles non-nulles
    consécutives en une seule Platform (économise les Rect)."""
    raw = layer.get("data", [])
    if not raw:
        return []

    platforms = []
    row_count = len(raw) // map_w if map_w > 0 else 0

    for row in range(row_count):
        col_start = None
        for col in range(map_w):
            idx  = row * map_w + col
            tuile = raw[idx] if idx < len(raw) else 0

            if tuile != 0:
                if col_start is None:
                    col_start = col
            else:
                if col_start is not None:
                    # Ferme le run
                    x = col_start * tile_w
                    y = row       * tile_h
                    w = (col - col_start) * tile_w
                    platforms.append(Platform(x, y, w, tile_h, BLANC))
                    col_start = None

        # Fin de ligne : fermer le dernier run si ouvert
        if col_start is not None:
            x = col_start * tile_w
            y = row       * tile_h
            w = (map_w - col_start) * tile_w
            platforms.append(Platform(x, y, w, tile_h, BLANC))

    return platforms


# ═════════════════════════════════════════════════════════════════════════════
#  3. RENDU DU CALQUE FOND EN IMAGE
# ═════════════════════════════════════════════════════════════════════════════

def _calque_vers_decor_fond(layer, map_w, map_h, tile_w, tile_h,
                             tilesets, chemin_tmj, nom_fichier):
    """Bake le calque fond en une seule image PNG et renvoie un [Decor].

    Nécessite que pygame.display soit initialisé (on est dans l'éditeur).
    Le PNG est sauvegardé dans assets/images/decors/ avec le nom de la map."""

    raw = layer.get("data", [])
    if not raw:
        return []

    # Charger l'image du tileset
    ts_info   = tilesets[0]
    firstgid  = ts_info.get("firstgid", 1)
    ts_img_rel = ts_info.get("image", "")

    if not ts_img_rel:
        # Tileset externe : on essaie de charger le .tsj
        ts_source = ts_info.get("source", "")
        if ts_source:
            ts_dir = os.path.dirname(chemin_tmj)
            ts_chemin = os.path.join(ts_dir, ts_source)
            try:
                with open(ts_chemin, encoding="utf-8") as f:
                    ts_data = json.load(f)
                ts_img_rel   = ts_data.get("image", "")
                ts_info      = ts_data
            except Exception:
                return []

    if not ts_img_rel:
        return []

    ts_dir    = os.path.dirname(chemin_tmj)
    ts_img_ch = os.path.join(ts_dir, ts_img_rel)
    if not os.path.exists(ts_img_ch):
        return []

    tileset_img = pygame.image.load(ts_img_ch).convert_alpha()
    ts_cols     = ts_info.get("columns",     tileset_img.get_width()  // tile_w)
    # ts_rows   = ts_info.get("tilecount", 0) // max(ts_cols, 1)

    # Créer la surface de destination
    surf = pygame.Surface((map_w * tile_w, map_h * tile_h), pygame.SRCALPHA)

    for i, gid in enumerate(raw):
        if gid == 0:
            continue
        local_id = gid - firstgid
        if local_id < 0:
            continue
        ts_col   = local_id % max(ts_cols, 1)
        ts_row   = local_id // max(ts_cols, 1)
        src_rect = pygame.Rect(ts_col * tile_w, ts_row * tile_h, tile_w, tile_h)
        dst_x    = (i % map_w) * tile_w
        dst_y    = (i // map_w) * tile_h
        surf.blit(tileset_img, (dst_x, dst_y), src_rect)

    # Sauvegarder le PNG dans decors/
    os.makedirs(DECORS_DIR, exist_ok=True)
    nom_base  = os.path.splitext(nom_fichier)[0]
    nom_png   = f"tiled_{nom_base}_fond.png"
    chemin_png = os.path.join(DECORS_DIR, nom_png)
    pygame.image.save(surf, chemin_png)

    decor = Decor(0, 0, chemin_png, nom_png, collision=False)
    return [decor]


# ═════════════════════════════════════════════════════════════════════════════
#  4. UTILITAIRE
# ═════════════════════════════════════════════════════════════════════════════

def _erreur(msg):
    return {"platforms": [], "decors": [], "world_w": 0, "world_h": 0, "erreur": msg}
