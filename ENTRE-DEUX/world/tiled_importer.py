# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Importeur de cartes Tiled (.tmj / .tmx)  [v3]
# ─────────────────────────────────────────────────────────────────────────────
#
#  SUPPORTE :
#   ✔ .tmj (JSON Tiled)          ✔ .tmx (XML Tiled, CSV + base64 [+zlib/gzip])
#   ✔ Maps "infinite" (chunks)
#   ✔ Flip flags H / V / Diagonal sur les tuiles
#   ✔ Tilesets embarqués + externes (.tsx XML / .tsj JSON)
#   ✔ MULTIPLES tilesets dans une même carte (matching firstgid)
#   ✔ 3 FAÇONS DE DÉFINIR LES COLLISIONS :
#        (a) Calque NOMMÉ *_collision / _col / _wall / _mur  (toutes tuiles = solides)
#        (b) Propriété de TILE "collidable" / "collision" / "solid" = true
#            dans le tileset  → la tuile EST solide où qu'elle soit placée
#        (c) Object Layer : rectangles avec name/type = "collision" / "wall" / "solid"
#            (ou calque d'objets dont le NOM contient "collision" → tous les rects)
#   ✔ Décors avec parallax automatique (bg, bg2, bg3, bg4, sky) ou réglé
#     dans Tiled (Layer Properties → Parallax Factor X/Y)
#   ✔ Foreground (devant joueur) : *_fg / _foreground, ou property foreground=true
#   ✔ Offset (x, y) au moment de l'import pour placer la carte
#
#  IMPORT DANS L'ÉDITEUR :   [I] → "nom" ou "nom X Y"
#  (X et Y en pixels ; "village 400 200" décale tout de (400, 200))
#
# ─────────────────────────────────────────────────────────────────────────────

import base64
import json
import os
import re
import struct
import xml.etree.ElementTree as ET
import zlib

import pygame

from settings      import DECORS_DIR, TILED_DIR
from world.tilemap import Platform, Decor

BLANC       = (255, 255, 255)


# ═════════════════════════════════════════════════════════════════════════════
#  OPTIMISATION FPS : opacité + sauvegarde
# ═════════════════════════════════════════════════════════════════════════════
#
#  Les fonds Tiled (fond, bg_end, ciel…) sont souvent TOTALEMENT OPAQUES.
#  Blitter une surface SRCALPHA opaque est ~6x plus lent que blitter une
#  surface convertie (convert() vs convert_alpha()).
#
#  Stratégie :
#    1) À la fin du bake d'un chunk, on regarde si le canal alpha est plein.
#    2) Si oui → on sauve le PNG SANS alpha (RGB 24-bit). Au reload, pygame
#       charge une surface sans SRCALPHA et Decor choisit convert() (rapide).
#    3) Si non → on sauve avec alpha (PNG 32-bit RGBA) et Decor utilise
#       convert_alpha() comme avant.
#
#  Gain mesuré : de ~30 fps à 70+ fps sur une map Tiled scale=2 avec 5-6
#  calques de background opaques.

def _surface_est_opaque(surf):
    """True si TOUS les pixels de `surf` ont alpha == 255.

    Utilise surfarray (numpy) quand disponible — très rapide. Fallback
    sur un échantillonnage grille sinon (moins précis mais zéro-dépendance).
    """
    # Surface sans flag SRCALPHA → par définition opaque.
    if not (surf.get_flags() & pygame.SRCALPHA):
        return True
    try:
        import pygame.surfarray as _sa
        alpha = _sa.pixels_alpha(surf)
        result = bool((alpha == 255).all())
        del alpha  # libère le lock sur la surface
        return result
    except (ImportError, pygame.error):
        # Fallback : échantillonnage grille 20×20 (~400 pixels testés).
        w, h = surf.get_size()
        step_x = max(1, w // 20)
        step_y = max(1, h // 20)
        for y in range(0, h, step_y):
            for x in range(0, w, step_x):
                if surf.get_at((x, y))[3] < 255:
                    return False
        return True


def _saver_surface_optimise(surf, chemin_png):
    """Sauve `surf` en PNG, en strippant l'alpha s'il est plein.

    Retourne la surface effectivement sauvegardée (peut être différente de
    l'originale si conversion RGB). L'appelant n'en a pas besoin en général :
    c'est surtout pour permettre une vérif si souhaitée.
    """
    if _surface_est_opaque(surf):
        # Convertit en RGB 24-bit sans canal alpha. pygame.image.save()
        # écrira un PNG opaque → au reload, pas de flag SRCALPHA → Decor
        # utilisera convert() (chemin rapide, ~6x plus rapide au blit).
        rgb = pygame.Surface(surf.get_size())   # sans SRCALPHA = RGB 24-bit
        rgb.fill((0, 0, 0))
        rgb.blit(surf, (0, 0))
        pygame.image.save(rgb, chemin_png)
        return rgb
    pygame.image.save(surf, chemin_png)
    return surf

# ── Tiled : flags de retournement sur les GIDs (3 bits hauts) ────────────
FLIP_H       = 0x80000000
FLIP_V       = 0x40000000
FLIP_DIAG    = 0x20000000
GID_MASK     = 0x1FFFFFFF

# ── Mots-clés reconnus ────────────────────────────────────────────────────
MOTS_COLLISION  = {"collision", "collisions", "col", "wall", "walls",
                   "solid", "mur", "murs", "platform", "platforms"}
MOTS_FOREGROUND = {"fg", "foreground", "avant", "devant",
                   "premier_plan", "premierplan"}
PARALLAX_PAR_NOM = {
    "bg":  1.0, "bg1": 1.0, "fond": 1.0, "background": 1.0, "decor": 1.0,
    "bg2": 0.7,
    "bg3": 0.4,
    "bg4": 0.2, "sky": 0.2, "ciel":  0.2,
}
# Propriétés de TILE qui déclenchent une collision automatique
PROPS_COLLIDABLE = {"collidable", "collision", "solid", "wall", "mur",
                    "platform", "bloquant"}

_SEP = re.compile(r"[_\-\s/.]+")


# ═════════════════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ═════════════════════════════════════════════════════════════════════════════

def importer_tiled(nom_fichier, offset_x=0, offset_y=0, scale=1.0):
    """Charge nom_fichier.tmj ou .tmx depuis tiled/.

    scale : facteur d'agrandissement de la map (1.0 = taille native Tiled,
            2.0 = tout est 2x plus grand dans le monde du jeu, 0.5 = tout
            est 2x plus petit). Multiplie tile size, positions des plateformes,
            taille des décors, offsets, tout. Utile pour adapter l'échelle
            d'une map Tiled au reste du jeu (joueur de 90px etc.).

    Retour : dict { platforms, decors, world_w, world_h, tilesets_ko, erreur }
    """
    chemin = _resoudre_chemin(nom_fichier)
    if chemin is None:
        return _erreur(f"Fichier introuvable : {nom_fichier} (ni .tmj ni .tmx)")

    try:
        carte = _lire_carte(chemin)
    except Exception as e:
        return _erreur(f"Erreur lecture carte : {e}")

    # Borne le scale pour éviter les valeurs absurdes
    scale = max(0.1, min(20.0, float(scale or 1.0)))

    tile_w_native = carte["tile_w"]
    tile_h_native = carte["tile_h"]
    # Tile size APRÈS scale : ce qui sera utilisé pour positionner les
    # platforms et calculer la taille des bake de décor.
    tile_w = max(1, int(round(tile_w_native * scale)))
    tile_h = max(1, int(round(tile_h_native * scale)))

    # Heuristique sur le NOM DU FICHIER (rétro-compat)
    base = os.path.splitext(os.path.basename(chemin))[0]
    mots_f = _decouper_mots(base)
    fichier_collision  = any(m in MOTS_COLLISION for m in mots_f)
    fichier_fg_default = any(m in MOTS_FOREGROUND for m in mots_f)
    fichier_bg_default = None
    for m in mots_f:
        if m in PARALLAX_PAR_NOM:
            fichier_bg_default = PARALLAX_PAR_NOM[m]
            break

    # Charger tous les tilesets (image + métadonnées + propriétés de tile)
    ts_loaded, ts_ko = _charger_tilesets(carte["tilesets"], chemin,
                                         tile_w, tile_h)

    # ─── PLATFORMS ────────────────────────────────────────────────────────
    # On utilise un SET (col, row) pour dédupliquer les collisions qui
    # viennent de plusieurs calques superposés. Sans ça, 6 calques
    # superposés = 6 Platforms par tuile, et la fusion h/v se casse
    # (doublons exacts qui empêchent la détection d'adjacence).
    cases_collision = set()

    # (a) Calques de tuiles marqués collision (par NOM ou par FICHIER)
    # (b) Tuiles individuelles avec propriété "collidable=true"
    for layer in carte["layers"]:
        if layer["type"] != "tilelayer":
            continue
        force_col = _calque_est_collision(layer, fichier_collision)
        for col, row, gid_raw in layer["tuiles"]:
            gid = gid_raw & GID_MASK
            if gid == 0:
                continue
            tuile_solide = force_col or _tuile_est_solide(gid, ts_loaded)
            if not tuile_solide:
                continue
            cases_collision.add((col, row))

    platforms = []
    for col, row in cases_collision:
        x = col * tile_w + offset_x
        y = row * tile_h + offset_y
        # color=None → plateforme INVISIBLE (le visuel vient du calque fond).
        # Voir Platform.draw dans tilemap.py (skip si color is None).
        platforms.append(Platform(x, y, tile_w, tile_h, None))

    # (c) Object layers avec rectangles de collision
    for layer in carte["layers"]:
        if layer["type"] != "objectgroup":
            continue
        nom_mots = _decouper_mots(layer.get("name", ""))
        layer_est_col = any(m in MOTS_COLLISION for m in nom_mots)
        for obj in layer["objects"]:
            obj_mots = _decouper_mots(obj.get("name", "") + " " + obj.get("type", ""))
            obj_est_col = any(m in MOTS_COLLISION for m in obj_mots)
            if not (layer_est_col or obj_est_col):
                continue
            w = int(obj.get("width", 0))
            h = int(obj.get("height", 0))
            if w <= 0 or h <= 0:
                continue
            # Scale appliqué : la map est agrandie comme un tout.
            x = int(round(obj.get("x", 0) * scale)) + offset_x
            y = int(round(obj.get("y", 0) * scale)) + offset_y
            w = max(1, int(round(w * scale)))
            h = max(1, int(round(h * scale)))
            platforms.append(Platform(x, y, w, h, None))

    platforms = _fusionner_horizontal(platforms)
    platforms = _fusionner_vertical(platforms)

    # ─── DÉCORS ───────────────────────────────────────────────────────────
    decors = []
    for layer in carte["layers"]:
        ltype = layer["type"]
        if ltype == "tilelayer":
            # Si le calque entier est collision, on ne crée pas de décor.
            if _calque_est_collision(layer, fichier_collision):
                continue
            try:
                decor = _calque_vers_decor(
                    layer, tile_w, tile_h, ts_loaded,
                    os.path.basename(chemin),
                    offset_x, offset_y,
                    fichier_bg_default, fichier_fg_default,
                    scale=scale,
                )
                if decor is not None:
                    decors.append(decor)
            except Exception as e:
                print(f"[Tiled] Calque '{layer.get('name')}' décor KO : {e}")
        elif ltype == "imagelayer":
            try:
                decor = _imagelayer_vers_decor(
                    layer, chemin, offset_x, offset_y,
                    fichier_bg_default, fichier_fg_default,
                    scale=scale,
                )
                if decor is not None:
                    decors.append(decor)
            except Exception as e:
                print(f"[Tiled] ImageLayer '{layer.get('name')}' KO : {e}")

    # Tri par parallax (plus loin d'abord)
    decors.sort(key=lambda d: (d.parallax_x, d.parallax_y))

    # ─── TAILLE DU MONDE ──────────────────────────────────────────────────
    bounds = _calculer_bornes(carte["layers"], tile_w, tile_h)
    if bounds is None:
        world_w = carte["w"] * tile_w + max(0, offset_x)
        world_h = carte["h"] * tile_h + max(0, offset_y)
    else:
        mx, my = bounds
        world_w = mx + offset_x
        world_h = my + offset_y

    return {
        "platforms":   platforms,
        "decors":      decors,
        "world_w":     world_w,
        "world_h":     world_h,
        "tilesets_ko": ts_ko,
        "bg_color":    carte.get("bg_color"),
        "erreur":      None,
    }


# ═════════════════════════════════════════════════════════════════════════════
#  RÉSOLUTION DU NOM DE FICHIER (.tmj / .tmx / ext auto)
# ═════════════════════════════════════════════════════════════════════════════

def _resoudre_chemin(nom):
    """Accepte nom.tmj, nom.tmx, ou nom (sans extension).
    Cherche dans TILED_DIR. Renvoie le chemin ou None."""
    if os.path.isabs(nom) and os.path.exists(nom):
        return nom
    candidats = []
    base, ext = os.path.splitext(nom)
    if ext.lower() in (".tmj", ".tmx"):
        candidats.append(nom)
    else:
        candidats.append(base + ".tmj")
        candidats.append(base + ".tmx")
    for cand in candidats:
        p = os.path.join(TILED_DIR, cand)
        if os.path.exists(p):
            return p
    return None


# ═════════════════════════════════════════════════════════════════════════════
#  LECTURE DE LA CARTE (.tmj → JSON) OU (.tmx → XML)
# ═════════════════════════════════════════════════════════════════════════════

def _lire_carte(chemin):
    """Lit une carte Tiled et renvoie un dict canonique :
        {
          "w": int, "h": int, "tile_w": int, "tile_h": int,
          "infinite": bool,
          "tilesets": [ {firstgid, source|None, embedded_dict|None}, ... ],
          "layers":   [
              {"type":"tilelayer", "name":str, "visible":bool,
               "parallaxx":float|None, "parallaxy":float|None,
               "properties":[{name,value}], "tuiles":[(col,row,gid_raw),...]},
              {"type":"objectgroup", "name":str, "visible":bool,
               "properties":[...], "objects":[{x,y,width,height,name,type,properties}]}
          ]
        }
    """
    if chemin.lower().endswith(".tmx"):
        return _lire_tmx(chemin)
    return _lire_tmj(chemin)


# ── .tmj (JSON) ─────────────────────────────────────────────────────────────
def _lire_tmj(chemin):
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)

    tile_w = int(data.get("tilewidth",  32))
    tile_h = int(data.get("tileheight", 32))
    infinite = bool(data.get("infinite", False))

    tilesets = []
    for ts in data.get("tilesets", []):
        tilesets.append({
            "firstgid":        int(ts.get("firstgid", 1)),
            "source":          ts.get("source"),
            "embedded":        ts if "image" in ts or "tiles" in ts else None,
        })

    layers = []
    for L in data.get("layers", []):
        typ = L.get("type")
        if typ == "tilelayer":
            tuiles = _tuiles_tmj(L, infinite)
            layers.append({
                "type":       "tilelayer",
                "name":       L.get("name", ""),
                "visible":    L.get("visible", True),
                "parallaxx":  L.get("parallaxx"),
                "parallaxy":  L.get("parallaxy"),
                "properties": L.get("properties") or [],
                "tuiles":     tuiles,
            })
        elif typ == "objectgroup":
            objects = []
            for o in L.get("objects", []):
                objects.append({
                    "x":          float(o.get("x", 0)),
                    "y":          float(o.get("y", 0)),
                    "width":      float(o.get("width", 0)),
                    "height":     float(o.get("height", 0)),
                    "name":       o.get("name", ""),
                    "type":       o.get("type", "") or o.get("class", ""),
                    "properties": o.get("properties") or [],
                })
            layers.append({
                "type":       "objectgroup",
                "name":       L.get("name", ""),
                "visible":    L.get("visible", True),
                "properties": L.get("properties") or [],
                "objects":    objects,
            })
        elif typ == "imagelayer":
            layers.append({
                "type":       "imagelayer",
                "name":       L.get("name", ""),
                "visible":    L.get("visible", True),
                "image":      L.get("image", ""),
                "offsetx":    float(L.get("offsetx", 0) or 0) + float(L.get("x", 0) or 0),
                "offsety":    float(L.get("offsety", 0) or 0) + float(L.get("y", 0) or 0),
                "parallaxx":  L.get("parallaxx"),
                "parallaxy":  L.get("parallaxy"),
                "properties": L.get("properties") or [],
            })

    return {
        "w":        int(data.get("width",  0)),
        "h":        int(data.get("height", 0)),
        "tile_w":   tile_w,
        "tile_h":   tile_h,
        "infinite": infinite,
        "tilesets": tilesets,
        "layers":   layers,
        "bg_color": data.get("backgroundcolor"),
    }


def _tuiles_tmj(layer, infinite):
    tuiles = []
    if infinite or "chunks" in layer:
        for chunk in (layer.get("chunks") or []):
            cx, cy = int(chunk.get("x", 0)), int(chunk.get("y", 0))
            cw = int(chunk.get("width", 0))
            raw = chunk.get("data") or []
            for i, gid in enumerate(raw):
                if gid == 0:
                    continue
                tuiles.append((cx + (i % cw), cy + (i // cw), int(gid)))
    else:
        w = int(layer.get("width", 0))
        raw = layer.get("data") or []
        if w > 0:
            for i, gid in enumerate(raw):
                if gid == 0:
                    continue
                tuiles.append((i % w, i // w, int(gid)))
    return tuiles


# ── .tmx (XML) ──────────────────────────────────────────────────────────────
def _lire_tmx(chemin):
    tree = ET.parse(chemin)
    root = tree.getroot()                 # <map ...>
    tile_w = int(root.get("tilewidth",  32))
    tile_h = int(root.get("tileheight", 32))
    infinite = root.get("infinite", "0") in ("1", "true", "True")

    tilesets = []
    for ts in root.findall("tileset"):
        entry = {
            "firstgid": int(ts.get("firstgid", 1)),
            "source":   ts.get("source"),
            "embedded": None,
        }
        if entry["source"] is None:
            # Tileset embedded dans le .tmx → on convertit l'XML en dict
            entry["embedded"] = _ts_tmx_vers_dict(ts)
        tilesets.append(entry)

    layers = []
    for L in list(root):
        tag = L.tag
        if tag == "layer":
            tuiles = _tuiles_tmx(L, tile_w, tile_h, infinite)
            layers.append({
                "type":       "tilelayer",
                "name":       L.get("name", ""),
                "visible":    L.get("visible", "1") != "0",
                "parallaxx":  _float_or_none(L.get("parallaxx")),
                "parallaxy":  _float_or_none(L.get("parallaxy")),
                "properties": _parse_props_xml(L.find("properties")),
                "tuiles":     tuiles,
            })
        elif tag == "objectgroup":
            objects = []
            for o in L.findall("object"):
                objects.append({
                    "x":          float(o.get("x", 0) or 0),
                    "y":          float(o.get("y", 0) or 0),
                    "width":      float(o.get("width", 0) or 0),
                    "height":     float(o.get("height", 0) or 0),
                    "name":       o.get("name", "") or "",
                    "type":       (o.get("type") or o.get("class") or ""),
                    "properties": _parse_props_xml(o.find("properties")),
                })
            layers.append({
                "type":       "objectgroup",
                "name":       L.get("name", ""),
                "visible":    L.get("visible", "1") != "0",
                "properties": _parse_props_xml(L.find("properties")),
                "objects":    objects,
            })
        elif tag == "imagelayer":
            img_e = L.find("image")
            img_src = img_e.get("source", "") if img_e is not None else ""
            layers.append({
                "type":       "imagelayer",
                "name":       L.get("name", ""),
                "visible":    L.get("visible", "1") != "0",
                "image":      img_src,
                "offsetx":    float(L.get("offsetx", 0) or 0),
                "offsety":    float(L.get("offsety", 0) or 0),
                "parallaxx":  _float_or_none(L.get("parallaxx")),
                "parallaxy":  _float_or_none(L.get("parallaxy")),
                "properties": _parse_props_xml(L.find("properties")),
            })

    return {
        "w":        int(root.get("width",  0)),
        "h":        int(root.get("height", 0)),
        "tile_w":   tile_w,
        "tile_h":   tile_h,
        "infinite": infinite,
        "tilesets": tilesets,
        "layers":   layers,
        "bg_color": root.get("backgroundcolor"),
    }


def _ts_tmx_vers_dict(ts_elem):
    """Convertit un <tileset> embedded XML en dict (même format que tsj)."""
    d = {
        "tilewidth":  int(ts_elem.get("tilewidth",  0) or 0),
        "tileheight": int(ts_elem.get("tileheight", 0) or 0),
        "columns":    int(ts_elem.get("columns",    0) or 0),
        "tilecount":  int(ts_elem.get("tilecount",  0) or 0),
    }
    img_e = ts_elem.find("image")
    if img_e is not None:
        d["image"]       = img_e.get("source", "")
        d["imagewidth"]  = int(img_e.get("width",  0) or 0)
        d["imageheight"] = int(img_e.get("height", 0) or 0)
    # Propriétés de tile : <tile id="5"><properties>...</properties></tile>
    tiles = []
    for t in ts_elem.findall("tile"):
        props = _parse_props_xml(t.find("properties"))
        if props:
            tiles.append({"id": int(t.get("id", 0)), "properties": props})
    if tiles:
        d["tiles"] = tiles
    return d


def _tuiles_tmx(layer_elem, tile_w, tile_h, infinite):
    """Extrait les tuiles d'un <layer> XML (CSV ou base64 [+zlib/gzip])."""
    tuiles = []
    w = int(layer_elem.get("width", 0))
    h = int(layer_elem.get("height", 0))

    del h  # silence linter; taille connue via width et data
    if infinite:
        data_elem = layer_elem.find("data")
        if data_elem is None:
            return tuiles
        encoding    = data_elem.get("encoding", "")
        compression = data_elem.get("compression", "")
        for chunk in data_elem.findall("chunk"):
            cx = int(chunk.get("x", 0))
            cy = int(chunk.get("y", 0))
            cw = int(chunk.get("width", 0))
            gids = _decoder_data(chunk.text or "", encoding, compression)
            for i, gid in enumerate(gids):
                if gid == 0:
                    continue
                tuiles.append((cx + (i % cw), cy + (i // cw), gid))
    else:
        data_elem = layer_elem.find("data")
        if data_elem is None:
            return tuiles
        encoding    = data_elem.get("encoding", "")
        compression = data_elem.get("compression", "")
        # Cas legacy : enfants <tile gid="..."/>
        enfants = data_elem.findall("tile")
        if enfants and not encoding:
            for i, t in enumerate(enfants):
                gid = int(t.get("gid", 0))
                if gid == 0:
                    continue
                tuiles.append((i % w, i // w, gid))
        else:
            gids = _decoder_data(data_elem.text or "", encoding, compression)
            for i, gid in enumerate(gids):
                if gid == 0 or w == 0:
                    continue
                tuiles.append((i % w, i // w, gid))
    return tuiles


def _decoder_data(texte, encoding, compression):
    """Décode la section <data> d'un calque TMX.
    Retourne une liste d'entiers (GIDs 32 bits non-signés, flip flags inclus).
    """
    if encoding == "csv":
        return [int(x.strip()) for x in texte.split(",") if x.strip()]
    if encoding == "base64":
        raw = base64.b64decode(texte.strip())
        if compression == "zlib":
            raw = zlib.decompress(raw)
        elif compression == "gzip":
            raw = zlib.decompress(raw, 16 + zlib.MAX_WBITS)
        elif compression == "zstd":
            try:
                import zstandard as zstd  # optionnel
                raw = zstd.ZstdDecompressor().decompress(raw)
            except Exception:
                raise RuntimeError(
                    "Compression zstd non supportée. Dans Tiled, change "
                    "'Tile Layer Format' en base64 zlib / gzip ou CSV."
                )
        # 4 octets little-endian par tuile (GID non signé)
        n = len(raw) // 4
        return list(struct.unpack("<" + "I" * n, raw[: n * 4]))
    # Pas d'encoding : probablement traité via enfants <tile> en amont
    return []


def _parse_props_xml(props_elem):
    """<properties><property name=".." value=".."/>...</properties>"""
    if props_elem is None:
        return []
    out = []
    for p in props_elem.findall("property"):
        val = p.get("value")
        typ = p.get("type", "string")
        # Conversion basique des types Tiled
        if typ == "bool":
            val = val in ("true", "1", "True")
        elif typ in ("int",):
            try:
                val = int(val)
            except (TypeError, ValueError):
                pass
        elif typ in ("float",):
            try:
                val = float(val)
            except (TypeError, ValueError):
                pass
        out.append({"name": p.get("name", ""), "value": val})
    return out


def _float_or_none(x):
    try:
        return None if x is None else float(x)
    except ValueError:
        return None


# ═════════════════════════════════════════════════════════════════════════════
#  CLASSIFICATION DES CALQUES / TUILES
# ═════════════════════════════════════════════════════════════════════════════

def _decouper_mots(nom):
    return [m for m in _SEP.split((nom or "").lower()) if m]


def _calque_est_collision(layer, fichier_collision_default):
    """Un calque de TUILES est traité collision si son nom contient un
    mot-clé collision, ou (défaut) si le fichier entier s'appelle 'collisions'.
    """
    mots = _decouper_mots(layer.get("name", ""))
    if any(m in MOTS_COLLISION for m in mots):
        return True
    if any(m in PARALLAX_PAR_NOM for m in mots):
        return False
    if any(m in MOTS_FOREGROUND for m in mots):
        return False
    return bool(fichier_collision_default)


def _tuile_est_solide(gid_clean, ts_loaded):
    """True si la tuile (gid sans flags) a une propriété collidable/solid."""
    ts, local = _ts_pour_gid(ts_loaded, gid_clean)
    if ts is None:
        return False
    props = ts["tile_props"].get(local)
    if not props:
        return False
    for prop_name, prop_val in props.items():
        if prop_name.lower() in PROPS_COLLIDABLE and _est_truthy(prop_val):
            return True
    return False


def _est_truthy(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "oui", "y")
    return bool(v)


def _detecter_parallax_et_foreground(layer, fichier_bg_default=None,
                                     fichier_fg_default=False):
    mots = _decouper_mots(layer.get("name", ""))

    px = layer.get("parallaxx")
    py = layer.get("parallaxy")

    foreground = False
    for prop in (layer.get("properties") or []):
        if prop.get("name", "").lower() == "foreground" and _est_truthy(prop.get("value")):
            foreground = True

    if any(m in MOTS_FOREGROUND for m in mots):
        foreground = True
        if px is None:
            px = 1.0
        if py is None:
            py = 1.0

    if px is None or py is None:
        facteur = None
        priorite = ("sky", "ciel", "bg4", "bg3", "bg2",
                    "bg1", "bg", "fond", "background", "decor")
        for mc in priorite:
            if mc in mots and mc in PARALLAX_PAR_NOM:
                facteur = PARALLAX_PAR_NOM[mc]
                break
        if facteur is None:
            facteur = fichier_bg_default if fichier_bg_default is not None else 1.0
        if px is None:
            px = facteur
        if py is None:
            py = facteur

    if fichier_fg_default and not foreground:
        foreground = True

    return float(px), float(py), foreground


# ═════════════════════════════════════════════════════════════════════════════
#  FUSION DES PLATFORMS (optimisation)
# ═════════════════════════════════════════════════════════════════════════════

def _fusionner_horizontal(platforms):
    if not platforms:
        return platforms
    plats = sorted(platforms, key=lambda p: (p.rect.y, p.rect.h, p.rect.x))
    fus, cur = [], None
    for p in plats:
        if (cur is not None and p.rect.y == cur.rect.y
                and p.rect.h == cur.rect.h and p.rect.x == cur.rect.right):
            cur.rect.w += p.rect.w
        else:
            if cur is not None:
                fus.append(cur)
            cur = Platform(p.rect.x, p.rect.y, p.rect.w, p.rect.h, p.color)
    if cur is not None:
        fus.append(cur)
    return fus


def _fusionner_vertical(platforms):
    if not platforms:
        return platforms
    plats = sorted(platforms, key=lambda p: (p.rect.x, p.rect.w, p.rect.y))
    fus, cur = [], None
    for p in plats:
        if (cur is not None and p.rect.x == cur.rect.x
                and p.rect.w == cur.rect.w and p.rect.y == cur.rect.bottom):
            cur.rect.h += p.rect.h
        else:
            if cur is not None:
                fus.append(cur)
            cur = Platform(p.rect.x, p.rect.y, p.rect.w, p.rect.h, p.color)
    if cur is not None:
        fus.append(cur)
    return fus


def _calculer_bornes(layers, tile_w, tile_h):
    min_col = min_row = 0
    max_col = max_row = -1
    max_obj_x = max_obj_y = 0
    found = False
    for L in layers:
        if L["type"] == "tilelayer":
            for col, row, _gid in L["tuiles"]:
                if not found:
                    min_col = max_col = col
                    min_row = max_row = row
                    found = True
                    continue
                if col > max_col:
                    max_col = col
                if row > max_row:
                    max_row = row
                if col < min_col:
                    min_col = col
                if row < min_row:
                    min_row = row
        elif L["type"] == "objectgroup":
            for o in L["objects"]:
                rx = int(o["x"] + o["width"])
                ry = int(o["y"] + o["height"])
                if rx > max_obj_x:
                    max_obj_x = rx
                if ry > max_obj_y:
                    max_obj_y = ry
    mx_tiles = (max_col + 1) * tile_w if found else 0
    my_tiles = (max_row + 1) * tile_h if found else 0
    mx = max(mx_tiles, max_obj_x)
    my = max(my_tiles, max_obj_y)
    if mx == 0 and my == 0:
        return None
    return mx, my


# ═════════════════════════════════════════════════════════════════════════════
#  CHARGEMENT DES TILESETS (avec propriétés de tile)
# ═════════════════════════════════════════════════════════════════════════════

def _charger_tilesets(tilesets, chemin_carte, tile_w_def, tile_h_def):
    """Précharge tous les tilesets. Chaque entrée chargée contient aussi
    `tile_props` : dict {local_id: {prop_name: prop_value}} pour la
    détection de tuiles "collidable"."""
    base_dir = os.path.dirname(chemin_carte)
    loaded, ko = [], []

    for ts_ref in tilesets:
        firstgid = ts_ref["firstgid"]
        ts = None
        if ts_ref.get("embedded") is not None:
            ts = _ts_depuis_dict(ts_ref["embedded"], base_dir,
                                 tile_w_def, tile_h_def)
        elif ts_ref.get("source"):
            src = ts_ref["source"]
            ts_path = os.path.normpath(os.path.join(base_dir, src))
            ts = _charger_tileset_externe(ts_path, tile_w_def, tile_h_def)

        if ts is None:
            ko.append(ts_ref.get("source") or "?")
            continue
        ts["firstgid"] = firstgid
        loaded.append(ts)

    loaded.sort(key=lambda t: -t["firstgid"])   # DESC pour matching rapide
    return loaded, ko


def _ts_depuis_dict(ts_dict, base_dir, tile_w_def, tile_h_def):
    """Construit un tileset depuis un dict (format tsj / embedded JSON)."""
    img_rel = ts_dict.get("image", "")
    if not img_rel:
        return None
    img_path = os.path.normpath(os.path.join(base_dir, img_rel))
    if not os.path.exists(img_path):
        alt = os.path.join(base_dir, os.path.basename(img_rel))
        img_path = alt if os.path.exists(alt) else None
    if not img_path:
        return None
    try:
        surface = pygame.image.load(img_path).convert_alpha()
    except Exception:
        return None

    tile_w = int(ts_dict.get("tilewidth",  tile_w_def) or tile_w_def)
    tile_h = int(ts_dict.get("tileheight", tile_h_def) or tile_h_def)
    columns = int(ts_dict.get("columns") or max(1, surface.get_width() // max(1, tile_w)))
    tilecount = int(ts_dict.get("tilecount") or
                    columns * (surface.get_height() // max(1, tile_h)))

    # Propriétés par tile : "tiles": [{"id":5, "properties":[{name,value},...]}]
    tile_props = {}
    for t in ts_dict.get("tiles") or []:
        tid = t.get("id")
        props_list = t.get("properties") or []
        if tid is None or not props_list:
            continue
        d = {}
        for p in props_list:
            d[p.get("name", "")] = p.get("value")
        tile_props[int(tid)] = d

    return {
        "image":      surface,
        "columns":    columns,
        "tile_w":     tile_w,
        "tile_h":     tile_h,
        "tilecount":  tilecount,
        "tile_props": tile_props,
    }


def _charger_tileset_externe(path, tile_w_def, tile_h_def):
    """Charge un .tsx (XML) ou .tsj (JSON) depuis un chemin absolu."""
    if not os.path.exists(path):
        return None
    base_dir = os.path.dirname(path)

    if path.lower().endswith((".tsj", ".json")):
        try:
            with open(path, encoding="utf-8") as f:
                return _ts_depuis_dict(json.load(f), base_dir,
                                       tile_w_def, tile_h_def)
        except Exception:
            return None

    # .tsx XML
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        d = _ts_tmx_vers_dict(root)
        return _ts_depuis_dict(d, base_dir, tile_w_def, tile_h_def)
    except Exception:
        return None


def _ts_pour_gid(ts_loaded, gid_clean):
    for ts in ts_loaded:
        if gid_clean >= ts["firstgid"]:
            local = gid_clean - ts["firstgid"]
            if local < ts["tilecount"]:
                return ts, local
            return None, 0
    return None, 0


# ═════════════════════════════════════════════════════════════════════════════
#  BAKE D'UN CALQUE DE TUILES EN PNG → DECOR
# ═════════════════════════════════════════════════════════════════════════════

def _calque_vers_decor(layer, tile_w, tile_h, ts_loaded, nom_fichier,
                       offset_x, offset_y,
                       fichier_bg_default=None, fichier_fg_default=False,
                       scale=1.0):
    """Convertit un calque de tuiles Tiled en UN Decor.

    1) Bake de toutes les tuiles sur UNE surface SRCALPHA à la taille native.
    2) Scale final de la surface (une seule fois) si scale != 1.0.
    3) Sauvegarde en PNG — stripped-alpha si le calque est 100% opaque
       (fonds, sols pleins) → blit runtime ~6x plus rapide.
    """
    tuiles = layer["tuiles"]
    if not tuiles or not ts_loaded:
        return None

    # Taille native du tileset (on bake à cette taille, on scale à la fin).
    ts0 = ts_loaded[0]
    native_tw = ts0["tile_w"]
    native_th = ts0["tile_h"]

    # Bounding box de toutes les tuiles non-vides → taille exacte du bake.
    min_col = min(c for c, _, _ in tuiles)
    max_col = max(c for c, _, _ in tuiles)
    min_row = min(r for _, r, _ in tuiles)
    max_row = max(r for _, r, _ in tuiles)

    w_tiles = max_col - min_col + 1
    h_tiles = max_row - min_row + 1
    surf = pygame.Surface((w_tiles * native_tw, h_tiles * native_th),
                          pygame.SRCALPHA)

    # Cache : la même tuile peut apparaître 100× dans un calque — on ne
    # subsurface/flip qu'une fois.
    cache = {}
    def get_tile(ts, local_id, fh, fv, fd):
        key = (id(ts["image"]), local_id, fh, fv, fd)
        c = cache.get(key)
        if c is not None:
            return c
        cols = ts["columns"]
        sx = (local_id %  cols) * ts["tile_w"]
        sy = (local_id // cols) * ts["tile_h"]
        sub = ts["image"].subsurface(
            pygame.Rect(sx, sy, ts["tile_w"], ts["tile_h"])
        ).copy()
        if fd:
            sub = pygame.transform.rotate(
                pygame.transform.flip(sub, True, False), -90)
        if fh:
            sub = pygame.transform.flip(sub, True, False)
        if fv:
            sub = pygame.transform.flip(sub, False, True)
        cache[key] = sub
        return sub

    nb = 0
    for col, row, gid_raw in tuiles:
        fh = bool(gid_raw & FLIP_H)
        fv = bool(gid_raw & FLIP_V)
        fd = bool(gid_raw & FLIP_DIAG)
        gid = gid_raw & GID_MASK
        if gid == 0:
            continue
        ts, local = _ts_pour_gid(ts_loaded, gid)
        if ts is None:
            continue
        try:
            tsurf = get_tile(ts, local, fh, fv, fd)
        except (ValueError, pygame.error):
            continue
        dst_x = (col - min_col) * native_tw
        dst_y = (row - min_row) * native_th - (ts["tile_h"] - native_th)
        surf.blit(tsurf, (dst_x, dst_y))
        nb += 1

    if nb == 0:
        return None

    # Scale final UNE fois (bien plus rapide et net que de scaler chaque tuile).
    if scale != 1.0:
        new_w = max(1, int(round(surf.get_width()  * scale)))
        new_h = max(1, int(round(surf.get_height() * scale)))
        surf = pygame.transform.scale(surf, (new_w, new_h))

    # Nom du PNG : suffixe scale uniquement si != 1 (évite collision de cache
    # sur des ré-imports à échelles différentes).
    os.makedirs(DECORS_DIR, exist_ok=True)
    base = os.path.splitext(nom_fichier)[0]
    nom_c = re.sub(r"[^A-Za-z0-9_-]+", "_", layer.get("name", "calque"))
    suffixe_scale = f"_x{scale:.2f}".replace(".", "p") if scale != 1.0 else ""
    nom_png = f"tiled_{base}_{nom_c}{suffixe_scale}.png"
    chemin_png = os.path.join(DECORS_DIR, nom_png)
    _saver_surface_optimise(surf, chemin_png)

    # Position monde cohérente avec les Platforms (même formule x*tile_w*scale).
    world_x = int(round(min_col * native_tw * scale)) + offset_x
    world_y = int(round(min_row * native_th * scale)) + offset_y
    px, py, fg = _detecter_parallax_et_foreground(
        layer, fichier_bg_default, fichier_fg_default)

    try:
        return Decor(world_x, world_y, chemin_png, nom_png, collision=False,
                     parallax_x=px, parallax_y=py, foreground=fg)
    except TypeError:
        # Ancienne signature de Decor (sans parallax) — fallback défensif.
        decor = Decor(world_x, world_y, chemin_png, nom_png, collision=False)
        decor.parallax_x = px
        decor.parallax_y = py
        decor.foreground = fg
        return decor


# ═════════════════════════════════════════════════════════════════════════════
#  IMAGE LAYER (calque d'image Tiled) → DECOR
# ═════════════════════════════════════════════════════════════════════════════

def _imagelayer_vers_decor(layer, chemin_carte, offset_x, offset_y,
                           fichier_bg_default=None, fichier_fg_default=False,
                           scale=1.0):
    """Convertit un calque d'IMAGE Tiled (imagelayer = un gros PNG posé)
    en UN Decor. Parallax et foreground fonctionnent comme un calque de tuiles.

    Le PNG source est copié (et scalé si besoin) dans DECORS_DIR, en mode
    opaque si possible pour des blits runtime rapides.
    """
    img_rel = layer.get("image", "")
    if not img_rel:
        return None
    base_dir = os.path.dirname(chemin_carte)
    img_path = os.path.normpath(os.path.join(base_dir, img_rel))
    if not os.path.exists(img_path):
        alt = os.path.join(base_dir, os.path.basename(img_rel))
        if not os.path.exists(alt):
            print(f"[Tiled] ImageLayer : image introuvable : {img_rel}")
            return None
        img_path = alt

    os.makedirs(DECORS_DIR, exist_ok=True)
    nom_base   = os.path.splitext(os.path.basename(chemin_carte))[0]
    nom_calque = re.sub(r"[^A-Za-z0-9_-]+", "_", layer.get("name", "imagelayer"))
    suffixe_scale = f"_x{scale:.2f}".replace(".", "p") if scale != 1.0 else ""
    nom_png    = f"tiled_{nom_base}_{nom_calque}{suffixe_scale}.png"
    chemin_png = os.path.join(DECORS_DIR, nom_png)

    # Charge + scale + sauve le PNG une seule fois (sauf si déjà présent).
    if not os.path.exists(chemin_png):
        try:
            img = pygame.image.load(img_path).convert_alpha()
        except Exception as e:
            print(f"[Tiled] ImageLayer : lecture échouée : {e}")
            return None
        if scale != 1.0:
            new_w = max(1, int(round(img.get_width()  * scale)))
            new_h = max(1, int(round(img.get_height() * scale)))
            img = pygame.transform.scale(img, (new_w, new_h))
        _saver_surface_optimise(img, chemin_png)

    world_x = int(round(layer.get("offsetx", 0) * scale)) + offset_x
    world_y = int(round(layer.get("offsety", 0) * scale)) + offset_y
    px, py, fg = _detecter_parallax_et_foreground(
        layer, fichier_bg_default, fichier_fg_default)

    try:
        return Decor(world_x, world_y, chemin_png, nom_png, collision=False,
                     parallax_x=px, parallax_y=py, foreground=fg)
    except TypeError:
        decor = Decor(world_x, world_y, chemin_png, nom_png, collision=False)
        decor.parallax_x = px
        decor.parallax_y = py
        decor.foreground = fg
        return decor


# ═════════════════════════════════════════════════════════════════════════════
#  UTILITAIRE
# ═════════════════════════════════════════════════════════════════════════════

def _erreur(msg):
    return {"platforms": [], "decors": [], "world_w": 0, "world_h": 0,
            "tilesets_ko": [], "bg_color": None, "erreur": msg}

