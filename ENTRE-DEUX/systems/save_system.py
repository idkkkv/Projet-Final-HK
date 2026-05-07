# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Système de sauvegarde (multi-slots + métadonnées)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Gère TOUTES les opérations sur les fichiers de sauvegarde :
#       - Liste des slots disponibles avec leur métadonnées
#       - Sauvegarde dans un slot
#       - Chargement depuis un slot
#       - Suppression d'un slot
#       - Wipe complet (= "Nouvelle partie")
#       - Slot spécial _autosave utilisé par le hot reload (Ctrl+R)
#
#  ORGANISATION DES FICHIERS
#  -------------------------
#  saves/
#    ├── slot_1.json        ← sauvegarde manuelle 1 (visible dans le menu)
#    ├── slot_2.json        ← sauvegarde manuelle 2
#    ├── slot_3.json        ← sauvegarde manuelle 3
#    └── _autosave.json     ← sauvegarde auto (Ctrl+R + à la fermeture)
#
#  STRUCTURE D'UN SAVE
#  -------------------
#  Le dict sauvé suit la convention :
#       {
#         "_meta": {           # ← affiché dans le menu de sauvegarde
#            "version":     int,
#            "saved_at":    "ISO datetime",
#            "play_time_s": int,
#            "slot_label":  str
#         },
#         "story":     {...},  # mode, map, cinématiques, dialogues
#         "player":    {...},  # position, hp, direction
#         "inventory": {...},  # items + slots
#         "fear":      {...},  # niveau de peur
#         "companions":{...},  # lucioles équipées + sources obtenues
#         "enemies":   {...},  # ennemis tués par map
#         "triggers":  {...},  # triggers déjà activés
#       }
#
#  game.py est responsable de produire/consommer ce dict via ses propres
#  méthodes _construire_save_data() / _appliquer_save_data() — ce module
#  ne fait QUE de l'I/O sur fichiers.
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import datetime


# ═════════════════════════════════════════════════════════════════════════════
#  CHEMINS
# ═════════════════════════════════════════════════════════════════════════════

_BASE       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SAVES_DIR  = os.path.join(_BASE, "saves")
_CONFIG     = os.path.join(_BASE, "game_config.json")

# Slot spécial pour l'auto-save (hot reload, fermeture du jeu)
SLOT_AUTOSAVE = "_autosave"

# Slots manuels disponibles dans le menu (extensible)
SLOTS_MANUELS = [1, 2, 3]

SAVE_VERSION  = 1


# ═════════════════════════════════════════════════════════════════════════════
#  1. UTILITAIRES INTERNES
# ═════════════════════════════════════════════════════════════════════════════

def _chemin_slot(slot):
    """Retourne le chemin du fichier .json pour un slot.

    `slot` peut être un int (1, 2, 3) ou la chaîne "_autosave".
    """
    if isinstance(slot, int):
        nom = f"slot_{slot}.json"
    else:
        nom = f"{slot}.json"
    return os.path.join(_SAVES_DIR, nom)


def _ensure_dir():
    os.makedirs(_SAVES_DIR, exist_ok=True)


# ═════════════════════════════════════════════════════════════════════════════
#  2. SAUVEGARDE / CHARGEMENT D'UN SLOT
# ═════════════════════════════════════════════════════════════════════════════

def sauvegarder_slot(slot, data, slot_label=None):
    """Écrit `data` (dict produit par game._construire_save_data) dans le slot.

    On INJECTE/REMPLACE la section "_meta" avec timestamp + version pour que
    le menu puisse afficher l'heure / temps de jeu / etc. proprement.
    `play_time_s` est lu depuis data si game l'a fourni, sinon 0.
    """
    _ensure_dir()
    play_time_s = int(data.get("_meta", {}).get("play_time_s", 0))
    data["_meta"] = {
        "version":     SAVE_VERSION,
        "saved_at":    datetime.datetime.now().isoformat(timespec="seconds"),
        "play_time_s": play_time_s,
        "slot_label":  slot_label or _label_par_defaut(slot),
    }
    with open(_chemin_slot(slot), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def charger_slot(slot):
    """Lit le slot et renvoie le dict complet, ou None si introuvable / corrompu."""
    chemin = _chemin_slot(slot)
    if not os.path.exists(chemin):
        return None
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def supprimer_slot(slot):
    """Efface un slot précis."""
    chemin = _chemin_slot(slot)
    if os.path.exists(chemin):
        os.remove(chemin)


def slot_existe(slot):
    return os.path.exists(_chemin_slot(slot))


# ═════════════════════════════════════════════════════════════════════════════
#  3. LISTE DES SAVES (pour le menu)
# ═════════════════════════════════════════════════════════════════════════════

def lister_saves():
    """Renvoie la liste des slots manuels avec leurs métadonnées résumées.

    Retourne une liste DE MÊME LONGUEUR que SLOTS_MANUELS, dans l'ordre.
    Chaque entrée contient :
        {
            "slot":         int,      # numéro de slot (1, 2, 3)
            "existe":       bool,     # False si le fichier n'existe pas
            "saved_at":     str|None, # ISO timestamp
            "play_time_s":  int,      # temps de jeu cumulé
            "hp":           int,      # PV au moment de la sauvegarde
            "max_hp":       int,
            "map":          str,      # nom de la map courante
            "fireflies":    int,      # nombre de lucioles
        }

    Sert au menu : tu sais quoi afficher pour chaque ligne.
    """
    resultats = []
    for slot in SLOTS_MANUELS:
        data = charger_slot(slot)
        if data is None:
            resultats.append({
                "slot":         slot,
                "existe":       False,
                "saved_at":     None,
                "play_time_s":  0,
                "hp":           0,
                "max_hp":       0,
                "map":          "",
                "fireflies":    0,
            })
        else:
            meta   = data.get("_meta",   {})
            player = data.get("player",  {})
            story  = data.get("story",   {})
            comps  = data.get("companions", {})
            resultats.append({
                "slot":         slot,
                "existe":       True,
                "saved_at":     meta.get("saved_at"),
                "play_time_s":  int(meta.get("play_time_s", 0)),
                "hp":           int(player.get("hp", 0)),
                "max_hp":       int(player.get("max_hp", 0)),
                "map":          story.get("current_map", ""),
                "fireflies":    int(comps.get("count", 0)),
            })
    return resultats


# ═════════════════════════════════════════════════════════════════════════════
#  4. WIPE COMPLET ("Nouvelle partie")
# ═════════════════════════════════════════════════════════════════════════════

def slot_le_plus_recent():
    """Retourne le numéro du slot manuel sauvé en DERNIER (par saved_at).

    Pratique pour le bouton "Continuer" du menu titre : on n'oblige pas le
    joueur à choisir, on charge automatiquement sa partie la plus récente.
    Renvoie None si aucun slot manuel n'existe.
    """
    plus_recent      = None
    plus_recent_date = ""
    for slot in SLOTS_MANUELS:
        data = charger_slot(slot)
        if data is None:
            continue
        date = data.get("_meta", {}).get("saved_at", "")
        if date > plus_recent_date:
            plus_recent_date = date
            plus_recent = slot
    return plus_recent


def au_moins_une_save():
    """True si AU MOINS un slot manuel contient une sauvegarde.

    Sert à savoir s'il faut afficher "Continuer" dans le menu titre.
    """
    return any(slot_existe(s) for s in SLOTS_MANUELS)


def supprimer_tout():
    """Efface TOUS les slots (manuels + autosave).

    Appelé quand le joueur clique sur "Nouvelle partie" et confirme :
    on repart d'une page blanche, plus aucune sauvegarde antérieure.
    """
    if not os.path.isdir(_SAVES_DIR):
        return
    for nom in os.listdir(_SAVES_DIR):
        if nom.endswith(".json"):
            try:
                os.remove(os.path.join(_SAVES_DIR, nom))
            except OSError:
                pass


# ═════════════════════════════════════════════════════════════════════════════
#  5. RACCOURCIS POUR L'AUTOSAVE (hot reload, fermeture)
# ═════════════════════════════════════════════════════════════════════════════

def sauvegarder_autosave(data):
    """Raccourci : écrit dans le slot _autosave."""
    sauvegarder_slot(SLOT_AUTOSAVE, data, slot_label="Auto")


def charger_autosave():
    """Raccourci : lit le slot _autosave."""
    return charger_slot(SLOT_AUTOSAVE)


def supprimer_autosave():
    supprimer_slot(SLOT_AUTOSAVE)


def autosave_existe():
    return slot_existe(SLOT_AUTOSAVE)


# ═════════════════════════════════════════════════════════════════════════════
#  6. CONFIG PERSISTANTE (game_config.json) — INCHANGÉE
# ═════════════════════════════════════════════════════════════════════════════
#
#  La config (résolution, volumes, carte de départ…) reste séparée des saves :
#  elle persiste entre toutes les parties.

def lire_config():
    if not os.path.exists(_CONFIG):
        return {}
    try:
        with open(_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def ecrire_config(data):
    try:
        with open(_CONFIG, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════════════
#  7. COMPATIBILITÉ ASCENDANTE (ancienne API à 1 slot)
# ═════════════════════════════════════════════════════════════════════════════
#
#  Plein de code historique appelle encore `sauvegarder(data)` / `charger()`
#  / `supprimer()` sans préciser de slot. On garde ces fonctions comme alias
#  vers le slot manuel n°1, le temps de migrer progressivement.
#
#  → À supprimer une fois que tout est passé sur l'API multi-slot.

_LEGACY_SLOT = 1


def sauvegarder(data):
    """[LEGACY] Alias vers le slot manuel 1 — à remplacer par sauvegarder_slot()."""
    sauvegarder_slot(_LEGACY_SLOT, data)


def charger():
    """[LEGACY] Alias vers le slot manuel 1 — à remplacer par charger_slot()."""
    return charger_slot(_LEGACY_SLOT)


def supprimer():
    """[LEGACY] Alias vers le slot manuel 1 — à remplacer par supprimer_slot()."""
    supprimer_slot(_LEGACY_SLOT)


# ═════════════════════════════════════════════════════════════════════════════
#  8. UTILITAIRE DE FORMATAGE (pour le menu)
# ═════════════════════════════════════════════════════════════════════════════

def formater_temps_jeu(secondes):
    """Convertit `secondes` en "HHh MMm" ou "MMm SSs" pour l'affichage UI."""
    secondes = max(0, int(secondes))
    h = secondes // 3600
    m = (secondes % 3600) // 60
    s = secondes % 60
    if h > 0:
        return f"{h}h {m:02d}m"
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def formater_date(iso_str):
    """ISO → "30/04/2026 15:42" lisible humain."""
    if not iso_str:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso_str


def _label_par_defaut(slot):
    if slot == SLOT_AUTOSAVE:
        return "Auto"
    return f"Slot {slot}"
