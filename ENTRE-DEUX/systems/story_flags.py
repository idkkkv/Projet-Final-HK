# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Story flags avec compteurs
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Gestion centralisée des "story flags" : des marqueurs de progression
#  narrative. Contrairement aux booléens simples, chaque flag a un COMPTEUR :
#
#       current  = nombre d'activations actuelles
#       required = nombre d'activations nécessaires pour que le flag soit
#                  "complet" (et donc déclenchable)
#
#  Exemple : "tiroir_indices" required=2, current=0
#       → le joueur ouvre tiroir 1 → current=1  (pas encore complet)
#       → le joueur ouvre tiroir 2 → current=2  (complet !)
#       → la cinématique se déclenche
#
#  RÉTROCOMPATIBILITÉ :
#  -------------------
#  Les flags "booléens" existants (True/False) sont normalisés en
#  {"current": 1, "required": 1} ou {"current": 0, "required": 1}.
#  L'API existante (game.story_flags["key"] = True) continue de fonctionner.
#
#  REGISTRE :
#  ----------
#  Un fichier story_flags_registry.json liste les flags avec leur required.
#  L'éditeur PNJ peut y ajouter des flags au moment de leur création.
#  Cela permet à game.py de créer le flag avec le bon required dès la première
#  incrémentation, même si le flag n'a pas encore été initialisé.
#
# ─────────────────────────────────────────────────────────────────────────────

import json
import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH    = os.path.join(_BASE_DIR, "story_flags_registry.json")
CINEMATIQUES_DIR = os.path.join(_BASE_DIR, "cinematiques")


# ═════════════════════════════════════════════════════════════════════════════
#  1. REGISTRE — liste persistante des flags connus
# ═════════════════════════════════════════════════════════════════════════════

def charger_registre():
    """Retourne le dict registre ou {} si inexistant / illisible."""
    try:
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def sauver_registre(reg):
    """Écrit le registre sur disque."""
    try:
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(reg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[StoryFlags] Erreur sauvegarde registre : {e}")


def flag_dans_registre(key):
    """True si le flag existe dans le registre."""
    return key in charger_registre()


def ajouter_au_registre(key, required=1, description=""):
    """Ajoute / met à jour un flag dans le registre."""
    reg = charger_registre()
    reg[key] = {"required": max(1, int(required)), "description": str(description)}
    sauver_registre(reg)


def required_depuis_registre(key):
    """Nombre d'activations requises pour `key` selon le registre (1 si absent)."""
    return charger_registre().get(key, {}).get("required", 1)


def lister_registre():
    """Retourne la liste triée des (key, required, description)."""
    reg = charger_registre()
    return sorted(
        [(k, v.get("required", 1), v.get("description", ""))
         for k, v in reg.items()],
        key=lambda t: t[0],
    )


# ═════════════════════════════════════════════════════════════════════════════
#  2. NORMALISATION (rétrocompatibilité bool / int → dict)
# ═════════════════════════════════════════════════════════════════════════════

def _normaliser(val):
    """Normalise n'importe quelle valeur de flag en dict {current, required}."""
    if isinstance(val, dict) and "required" in val:
        return {
            "current":  int(val.get("current", 0)),
            "required": int(val.get("required", 1)),
        }
    if isinstance(val, bool):
        return {"current": 1 if val else 0, "required": 1}
    if isinstance(val, int):
        return {"current": val, "required": 1}
    return {"current": 0, "required": 1}


# ═════════════════════════════════════════════════════════════════════════════
#  3. API FLAGS
# ═════════════════════════════════════════════════════════════════════════════

def flag_incrementer(flags_dict, key, delta=1, required=None):
    """Incrémente `key` de `delta` dans `flags_dict`.

    - Crée le flag si absent, avec `required` (ou valeur du registre si None).
    - Retourne True si le flag VIENT DE SE COMPLÉTER (transition →complet).
    """
    if key not in flags_dict:
        req = required if required is not None else required_depuis_registre(key)
        flags_dict[key] = {"current": 0, "required": max(1, int(req))}

    f = _normaliser(flags_dict[key])
    etait_complet = f["current"] >= f["required"]
    f["current"] += int(delta)
    flags_dict[key] = f
    est_complet = f["current"] >= f["required"]
    return (not etait_complet) and est_complet   # True = vient de se compléter


def flag_complet(flags_dict, key):
    """True si le flag existe et current >= required."""
    if key not in flags_dict:
        return False
    f = _normaliser(flags_dict[key])
    return f["current"] >= f["required"]


def flag_valeur(flags_dict, key):
    """Retourne (current, required) ou (0, 1) si absent."""
    if key not in flags_dict:
        return (0, 1)
    f = _normaliser(flags_dict[key])
    return (f["current"], f["required"])


def flag_poser(flags_dict, key, value=True):
    """Pose un flag boolean (rétrocompatibilité avec l'ancien système).

    True  → current = required (complet)
    False → current = 0 (incomplet)
    """
    if key in flags_dict:
        f = _normaliser(flags_dict[key])
    else:
        f = {"current": 0, "required": 1}
    f["current"] = f["required"] if value else 0
    flags_dict[key] = f


# ═════════════════════════════════════════════════════════════════════════════
#  4. TEST DE CONDITION
# ═════════════════════════════════════════════════════════════════════════════

def tester_condition(flags_dict, condition):
    """Teste une condition sur les flags. Retourne True ou False.

    Formats supportés :
        None / {}                      → toujours vrai
        {"flag": "k"}                  → flag k est complet (current >= required)
        {"flag": "k", "value": False}  → flag k est incomplet / absent
        {"flag": "k", "min": N}        → flag k a current >= N
        {"any": ["k1","k2"]}           → au moins 1 complet
        {"all": ["k1","k2"]}           → tous complets
    """
    if not condition:
        return True

    if "flag" in condition:
        k = condition["flag"]
        v = condition.get("value", True)
        if "min" in condition:
            cur, _ = flag_valeur(flags_dict, k)
            return cur >= int(condition["min"])
        return flag_complet(flags_dict, k) if v else not flag_complet(flags_dict, k)

    if "any" in condition:
        return any(flag_complet(flags_dict, k) for k in condition.get("any", []))

    if "all" in condition:
        return all(flag_complet(flags_dict, k) for k in condition.get("all", []))

    return True


def parser_condition_texte(texte):
    """Convertit une chaîne de condition en dict (ou None).

    Formats acceptés (identiques à ceux du PNJEditor) :
        (vide)          → None
        flag:key        → {"flag": "key"}
        flag:key=0      → {"flag": "key", "value": False}
        flag:key=N      → {"flag": "key", "min": N}  si N > 0
        any:k1,k2,k3    → {"any": ["k1","k2","k3"]}
        all:k1,k2,k3    → {"all": ["k1","k2","k3"]}
    """
    t = texte.strip()
    if not t:
        return None
    if t.startswith("flag:"):
        rest = t[5:].strip()
        if "=" in rest:
            k, val = rest.split("=", 1)
            k = k.strip()
            val = val.strip()
            if val in ("0", "false", "False"):
                return {"flag": k, "value": False}
            try:
                n = int(val)
                if n > 0:
                    return {"flag": k, "min": n}
                return {"flag": k, "value": False}
            except ValueError:
                return {"flag": k}
        return {"flag": rest}
    if t.startswith("any:"):
        return {"any": [k.strip() for k in t[4:].split(",") if k.strip()]}
    if t.startswith("all:"):
        return {"all": [k.strip() for k in t[4:].split(",") if k.strip()]}
    return None


def formater_condition_texte(cond):
    """Convertit un dict condition en texte éditable."""
    if not cond:
        return ""
    if "flag" in cond:
        k = cond["flag"]
        if "min" in cond:
            return f"flag:{k}={cond['min']}"
        v = cond.get("value", True)
        return f"flag:{k}" if v else f"flag:{k}=0"
    if "any" in cond:
        return "any:" + ",".join(cond.get("any", []))
    if "all" in cond:
        return "all:" + ",".join(cond.get("all", []))
    return ""


# ═════════════════════════════════════════════════════════════════════════════
#  5. SCAN DES CINÉMATIQUES CONDITIONNELLES
# ═════════════════════════════════════════════════════════════════════════════

def charger_cinematiques_conditionnelles():
    """Scanne cinematiques/ et retourne les entrées ayant une condition.

    Format retourné :
        [
            {
                "nom":       "foret/intro",
                "condition": {"flag": "tiroir_indices"},
                "delay":     1.0,
                "one_shot":  True,
            },
            ...
        ]

    Utilisé par game.py pour savoir quelles cinématiques surveiller
    après chaque changement de flag.
    """
    if not os.path.isdir(CINEMATIQUES_DIR):
        return []

    resultats = []
    for racine, _, fichiers in os.walk(CINEMATIQUES_DIR):
        for nom_fichier in fichiers:
            if not nom_fichier.endswith(".json"):
                continue
            chemin = os.path.join(racine, nom_fichier)
            try:
                with open(chemin, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            # Format "enrichi" : dict avec "condition" + "steps"
            if not isinstance(data, dict) or "condition" not in data:
                continue
            nom_rel = os.path.relpath(chemin, CINEMATIQUES_DIR)
            nom_rel = nom_rel.replace("\\", "/")[:-5]   # retire .json
            af = data.get("auto_fire", None)
            resultats.append({
                "nom":       nom_rel,
                "condition": data["condition"],
                "delay":     float(data.get("delay", 1.0)),
                "one_shot":  bool(data.get("one_shot", True)),
                # auto_fire : None (heuristique), True (toujours), False (jamais)
                "auto_fire": (None if af is None else bool(af)),
            })
    return resultats
