# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Fabriques d'étapes de cinématique
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Toutes les "fabriques d'étapes" (factory functions) qui construisent les
#  étapes typées passées à Cutscene(). Chaque fabrique renvoie un tuple
#  (type_str, dict_params) prêt à être consommé par Cutscene._exec_step().
#
#  Réexportées par systems/cutscene.py pour préserver la compatibilité avec
#  l'import historique :
#       from systems.cutscene import wait, dialogue, npc_walk, ...
#
#  Contient aussi les helpers internes _trouver_pnj et _trouver_position_pnj
#  utilisés par Cutscene._exec_step.
#
# ─────────────────────────────────────────────────────────────────────────────

# ═════════════════════════════════════════════════════════════════════════════
#  3. FABRIQUES D'ÉTAPES — sucre syntaxique pour des scripts lisibles
# ═════════════════════════════════════════════════════════════════════════════
#
#  Chaque fabrique renvoie un tuple (type, params) prêt à être ajouté à une
#  liste passée à Cutscene(). On préfère écrire :
#       Cutscene([wait(1.0), dialogue([...]), camera_release()])
#  plutôt que :
#       Cutscene([("wait", {"duration": 1.0}), ...])
#
#  Si tu ajoutes un nouveau type d'étape dans la classe, ajoute aussi sa
#  fabrique ici pour rester cohérent.

def wait(duration):
    """Pause passive de `duration` secondes."""
    return ("wait", {"duration": float(duration)})


def dialogue(lines):
    """Affiche un dialogue. `lines` = liste de (texte, orateur) ou de strings.

    L'étape se termine quand le joueur a fait défiler toutes les lignes
    (la boîte de dialogue passe à actif=False)."""
    return ("dialogue", {"lines": list(lines)})


def npc_walk(npc, target, speed=80, tolerance=4.0):
    """Déplace `npc` jusqu'à `target` (x, y monde) à `speed` px/s.

    Suppose que `npc.rect` existe (PNJ standard ou n'importe quelle entité
    avec un rect pygame). L'étape termine à l'arrivée OU au bout de 30 s
    (sécurité anti-blocage)."""
    return ("npc_walk", {
        "npc": npc,
        "target": tuple(target),
        "speed": float(speed),
        "tolerance": float(tolerance),
    })


def camera_focus(target, duration=None, speed=None):
    """Pose la caméra sur un point fixe (x, y monde).

    duration : si None → l'étape est instantanée (la caméra reste focalisée
               jusqu'à camera_release). Si nombre → libération auto à la fin.
    speed    : facteur de lissage du déplacement (0.0 < x ≤ 1.0).
               0.1 = doux (défaut), 0.5 = nerveux, 1.0 = instantané.
               None = garde la vitesse en cours."""
    params = {"target": tuple(target)}
    if duration is not None:
        params["duration"] = float(duration)
    if speed is not None:
        params["speed"] = float(speed)
    return ("camera_focus", params)


def camera_release():
    """Rend la caméra au joueur (suivi normal)."""
    return ("camera_release", {})


def fade(direction="out", duration=1.0):
    """Lance un fondu écran. direction = "out" (vers noir) ou "in" (depuis noir).

    Délègue à game.demarrer_fondu(direction, duration) si elle existe.
    Sinon l'étape se comporte comme un wait(duration)."""
    return ("fade", {"direction": str(direction), "duration": float(duration)})


def set_state(attr, value):
    """Modifie `game.<attr> = value` (utile pour basculer game.state)."""
    return ("set_state", {"attr": attr, "value": value})


def callback(fn):
    """Appelle `fn(ctx)` une fois et passe à l'étape suivante.

    Échappatoire : si on a besoin d'une action ponctuelle qui n'a pas de
    type d'étape dédié (jouer un son, changer de carte, ajouter un item à
    l'inventaire…), on l'enveloppe dans une fonction et on la passe ici."""
    return ("callback", {"fn": fn})


def shake(amplitude=6.0, duration=0.3):
    """Tremblement de caméra. amplitude en px, duration en secondes."""
    return ("shake", {"amplitude": float(amplitude), "duration": float(duration)})


def play_sound(nom, volume=1.0):
    """Joue le son `nom` (déjà chargé via audio/sound_manager.charger)."""
    return ("play_sound", {"nom": str(nom), "volume": float(volume)})


def particles_burst(x, y, nb=12, couleur=(255, 255, 200)):
    """Émet `nb` particules à (x, y). couleur = (r, g, b)."""
    return ("particles_burst", {
        "x": float(x), "y": float(y), "nb": int(nb), "couleur": tuple(couleur),
    })


def player_walk(target, speed=100, tolerance=6.0):
    """Déplace le JOUEUR jusqu'à `target` (x, y monde) à `speed` px/s.

    Le joueur n'est pas piloté par le clavier pendant la cinématique
    (cf. game.cutscene → mouvement_bloque), donc on peut le bouger ici."""
    return ("player_walk", {
        "target": tuple(target),
        "speed": float(speed),
        "tolerance": float(tolerance),
    })


def npc_walk_by_name(nom_pnj, target, speed=80, tolerance=4.0):
    """Comme npc_walk, mais on retrouve le PNJ par son NOM (au moment du run).

    Plus pratique que npc_walk(npc=...) qui exige une référence Python : ici
    on stocke juste le nom dans le JSON et on résout au runtime."""
    return ("npc_walk_by_name", {
        "nom_pnj":   str(nom_pnj),
        "target":    tuple(target),
        "speed":     float(speed),
        "tolerance": float(tolerance),
    })


def camera_focus_pnj(nom_pnj, duration=None, speed=None, follow=False):
    """Pose la caméra sur le PNJ dont le nom est `nom_pnj`.

    Si plusieurs PNJ portent le même nom, on prend le premier trouvé.
    Si aucun n'est trouvé, l'étape ne fait rien (mais ne bloque pas).

    duration : durée explicite de l'étape (s).
               Si None → ÉTAPE INSTANTANÉE : la caméra se pose puis on passe
               directement à l'étape suivante (un dialogue par exemple). La
               caméra reste fixée jusqu'au prochain camera_focus ou
               camera_release. C'est ce qui permet d'enchaîner caméra-PNJ-A
               → dialogue-A → caméra-PNJ-B → dialogue-B sans retour au joueur.
    speed    : vitesse du lerp caméra (0.05 lent → 1.0 instantané, défaut 0.1).
    follow   : True = la caméra met à jour sa cible chaque frame pour suivre
               le PNJ s'il bouge (npc_walk_by_name)."""
    params = {"nom": str(nom_pnj)}
    if duration is not None:
        params["duration"] = float(duration)
    if speed is not None:
        params["speed"] = float(speed)
    if follow:
        params["follow"] = True
    return ("camera_focus_pnj", params)


def set_player_pos(x, y):
    """Téléporte le joueur à (x, y) instantanément (en coords monde).

    Reste sur la carte courante. Pour téléporter vers une autre map ou
    un spawn nommé, utiliser teleport_player()."""
    return ("set_player_pos", {"x": float(x), "y": float(y)})


def teleport_player(cible="", x=None, y=None):
    """Téléporte le joueur vers un autre endroit, éventuellement sur une
    autre carte.

    cible : format texte identique aux portails et à revive_player :
        "spawn_nom"          → carte courante, spawn nommé
        "map_nom spawn_nom"  → change de carte ET place sur le spawn
        ""                   → fallback sur (x, y) si fournis
    x, y  : coordonnées explicites (utilisées si cible est vide ou si le
            spawn nommé n'existe pas)."""
    p = {"cible": str(cible)}
    if x is not None:
        p["x"] = float(x)
    if y is not None:
        p["y"] = float(y)
    return ("teleport_player", p)


# ── Apparition / disparition de PNJ ──────────────────────────────────────────

def npc_spawn(nom, x, y, dialogues=None, sprite=None,
              dialogue_mode="boucle_dernier", has_gravity=True, events=None,
              facing=1):
    """Fait apparaître un PNJ au point (x, y).

    Cas typique : à la fin d'un dialogue avec un parchemin, séraphin
    apparaît derrière le joueur pour engager la suite. Combiner avec
    camera_focus_pnj() + dialogue() pour orchestrer la scène.

    nom            : identifiant unique (utilisé par _trouver_pnj /
                     npc_walk_by_name / npc_despawn).
    sprite         : nom du sprite (cf. assets/images/pnj/) ou None
                     pour un rectangle violet de fallback.
    dialogues      : liste de listes (cf. PNJ.__init__).
    dialogue_mode  : "boucle_dernier" (défaut) ou "restart".
    has_gravity    : True (tombe) / False (flottant).
    events         : liste parallèle aux dialogues — événements à
                     déclencher en fin de chaque conv. Voir PNJ.events.
    """
    return ("npc_spawn", {
        "nom": str(nom), "x": float(x), "y": float(y),
        "sprite": sprite,
        "dialogues": list(dialogues or []),
        "dialogue_mode": str(dialogue_mode),
        "has_gravity": bool(has_gravity),
        "events": events,
        "facing": -1 if int(facing) < 0 else 1,
    })


def npc_despawn(nom):
    """Fait disparaître le PNJ nommé `nom` (ex : séraphin remonte
    l'échelle puis quitte la scène). No-op si PNJ inexistant."""
    return ("npc_despawn", {"nom": str(nom)})


# ── Récompenses ───────────────────────────────────────────────────────────────

def grant_skill(value):
    """Débloque une compétence (settings.skill_<value> = True).

    Valeurs valides : double_jump, dash, back_dodge, wall_jump,
                      attack, pogo."""
    return ("grant_skill", {"value": str(value)})


def grant_luciole(source):
    """Ajoute une luciole/compagnon. `source` doit être unique pour
    éviter le double-don au rejouer la cinématique."""
    return ("grant_luciole", {"source": str(source)})


def give_item(name, count=1):
    """Ajoute `count` exemplaires de l'item `name` à l'inventaire
    (stack auto si l'item est stackable, ex. Pomme)."""
    return ("give_item", {"name": str(name), "count": int(count)})


def give_coins(amount):
    """Ajoute `amount` pièces au joueur."""
    return ("give_coins", {"amount": int(amount)})


def revive_player(cible=""):
    """Réanime le joueur après une cinématique de mort scriptée.

    cible : spawn nommé où apparaître. Format identique aux portails :
        "mapname spawnname"  → change de carte ET place sur le spawn
        "spawnname"          → reste sur la carte courante
        ""                   → fallback : spawn par défaut de la map

    Effets :
      - PV remis au max
      - écran de mort annulé (joueur.dead = False)
      - téléport vers le spawn nommé (cf. mode 14 de l'éditeur)
      - ennemis de la map d'arrivée ressuscités
      - compagnons replacés autour du joueur

    À utiliser à la FIN d'une cinématique CutsceneTrigger en mode
    on_death : le joueur meurt, le dialogue joue par-dessus l'écran
    noir, puis cette action le téléporte vers un point safe (lit de
    Séraphin par exemple) et lui rend la main.
    """
    return ("revive_player", {"cible": str(cible)})


def unlock_quickuse(pommes=10):
    """Débloque la croix directionnelle de consommables rapides ET
    donne `pommes` pommes au joueur. Macro tout-en-un, à utiliser dans
    la cinématique de Nymbus qui introduit la mécanique.

    Pose story_flags["quickuse_unlocked"] = True (la barre lit ce flag
    pour décider si elle s'affiche)."""
    return ("unlock_quickuse", {"pommes": int(pommes)})


def set_flag(key, value=True):
    """Pose un story flag global. Lu par les PNJ pour conditionner
    leurs dialogues (PNJ.dialogue_conditions). Cf. game.story_flags."""
    return ("set_flag", {"key": str(key), "value": bool(value)})


def flag_increment(key, delta=1, required=None):
    """Incrémente un flag avec compteur. Crée le flag si absent.

    delta    : entier (peut être négatif).
    required : à la CRÉATION du flag, fixe combien d'activations il faut
               pour qu'il soit complet. Si None, lecture du registre.
               Ignoré si le flag existe déjà.
    """
    p = {"key": str(key), "delta": int(delta)}
    if required is not None:
        p["required"] = int(required)
    return ("flag_increment", p)


# ── Attente conditionnelle (gameplay au milieu d'une cinématique) ────────────

def play_music(chemin, volume=0.6, fadeout_ms=1000, fadein_ms=1500):
    """Transition vers une nouvelle piste musicale.

    chemin : chemin vers le fichier (mp3/ogg). "" = fadeout seul (silence).
    volume : 0.0 → 1.0
    fadeout_ms / fadein_ms : durée des fondus.
    """
    return ("play_music", {
        "chemin":     str(chemin),
        "volume":     float(volume),
        "fadeout_ms": int(fadeout_ms),
        "fadein_ms":  int(fadein_ms),
    })


def wait_input(touche="any", timeout=0):
    """Met la cinématique en pause jusqu'à ce que le joueur appuie sur
    `touche`. Idéal pour les écrans "appuyez pour continuer".

    touche  : "any" (n'importe quelle), "space", "enter".
    timeout : 0 = pas de timeout (attend indéfiniment), N = abandonne
              au bout de N secondes.
    """
    return ("wait_input", {
        "touche":  str(touche),
        "timeout": float(timeout),
    })


def wait_for_player_at(x, y, radius=32, timeout=60):
    """Pause la cinématique en RENDANT LA MAIN AU JOUEUR jusqu'à ce
    qu'il atteigne (x, y) ± radius.

    Idéal pour scènes mixtes : "le joueur doit ouvrir le tiroir",
    "le joueur doit monter à l'échelle", etc. Le drapeau interne
    `game._cutscene_player_libre` est posé à True pendant l'étape.

    timeout : abandon de l'étape au bout de N secondes (défaut 60).
    """
    return ("wait_for_player_at", {
        "x": float(x), "y": float(y),
        "radius": float(radius),
        "timeout": float(timeout),
    })


# ═════════════════════════════════════════════════════════════════════════════
#  4. UTILITAIRES INTERNES
# ═════════════════════════════════════════════════════════════════════════════

def _trouver_position_pnj(ctx, nom_pnj):
    """Renvoie (x, y) du PNJ nommé `nom_pnj` ou None s'il n'existe pas.

    Cherche dans ctx.pnjs (peuplé par CutsceneContext depuis editeur.pnjs).
    Insensible à la casse pour la souplesse."""
    pnj = _trouver_pnj(ctx, nom_pnj)
    if pnj is None:
        return None
    r = getattr(pnj, "rect", None)
    return (r.centerx, r.centery) if r is not None else None


def _trouver_pnj(ctx, nom_pnj):
    """Renvoie l'OBJET PNJ nommé `nom_pnj` (insensible à la casse) ou None."""
    if not nom_pnj:
        return None
    cible = nom_pnj.lower().strip()
    for pnj in (ctx.pnjs or []):
        nom = getattr(pnj, "nom", "")
        if nom and nom.lower().strip() == cible:
            return pnj
    return None