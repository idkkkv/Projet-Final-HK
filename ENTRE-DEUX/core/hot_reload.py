# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Hot reload du jeu (Ctrl+R)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Permet de modifier le code source du jeu PENDANT qu'il tourne, et de
#  recharger sans perdre sa position ni son état :
#
#       1. Le jeu tourne, le joueur est en plein milieu d'une map.
#       2. Tu modifies un fichier (ex: settings.py, player.py, game.py).
#       3. Tu reviens dans la fenêtre du jeu.
#       4. Tu appuies sur Ctrl+R.
#       5. Le jeu se ferme/relance avec le NOUVEAU code chargé, et te
#          replace au même endroit (même map, même position, mêmes PV).
#
#  Avantages : tu n'as plus à fermer le jeu, le rouvrir, charger ta map,
#  marcher jusqu'à l'endroit que tu testais. Gain de temps énorme en dev.
#
#  COMMENT ÇA MARCHE TECHNIQUEMENT ?
#  ---------------------------------
#  On NE recharge PAS les modules Python en mémoire (importlib.reload est
#  buggy avec les classes : les anciennes instances gardent les méthodes
#  de l'ancien module, on a 2 versions de chaque classe en mémoire, et les
#  isinstance() partent en sucette).
#
#  À la place, on fait propre :
#       1. Sauvegarde de l'état important du joueur dans un fichier
#          temporaire (`_hot_reload_state.json`).
#       2. Appel à os.execv() qui REMPLACE le process Python actuel par
#          un nouveau Python frais (sys.argv repris à l'identique).
#       3. Au démarrage, on détecte le fichier `_hot_reload_state.json`,
#          on charge l'état dedans, on l'applique au jeu, et on supprime
#          le fichier (pour ne pas re-restaurer au prochain démarrage
#          normal).
#
#  Pourquoi os.execv et pas subprocess ? execv REMPLACE le process en
#  place — pas de double instance Pygame, pas de fenêtre fantôme. C'est
#  exactement ce qu'on veut.
#
#  ÉTAT SAUVEGARDÉ
#  ---------------
#  Pour rester simple, on garde le minimum vital :
#       - nom de la map courante (carte de départ → recharge auto)
#       - position du joueur (x, y)
#       - PV courants
#       - direction du regard
#
#  Tout le reste (anims, timers, vitesse, etc.) est ré-initialisé à
#  l'identique au démarrage normal. Vu qu'on est en plein dev, c'est
#  largement suffisant.
#
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import sys


# Le fichier de state vit à la racine du projet (à côté de save.json),
# il est éphémère : créé par déclenchement, lu et supprimé au démarrage.
_DOSSIER       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOT_STATE_PATH = os.path.join(_DOSSIER, "_hot_reload_state.json")


# ═════════════════════════════════════════════════════════════════════════════
#  1. SAUVEGARDE + RELANCE (appelée par Ctrl+R)
# ═════════════════════════════════════════════════════════════════════════════

def declencher_hot_reload(game):
    """Sauvegarde l'état COMPLET du joueur et redémarre le process Python.

    On utilise le même système de save data que la sauvegarde manuelle
    (game._construire_save_data) pour que TOUT soit restauré identique
    après le reload : inventaire, peur, ennemis tués, etc.

    Appelée depuis le handler de Ctrl+R dans game.py. Cette fonction NE
    REND PAS LA MAIN : os.execv remplace le process. Tout ce qui suit
    n'est donc jamais exécuté (le nouveau Python boote à la place).
    """
    # On délègue la construction du dict à game.py — état exhaustif.
    state = game._construire_save_data()

    try:
        with open(HOT_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[HotReload] Échec sauvegarde state : {e}")
        return

    print(f"[HotReload] State sauvegardé → relance du process...")
    # Important : flusher les sorties standard avant exec (sinon perdues).
    sys.stdout.flush()
    sys.stderr.flush()

    # os.execv remplace le process : sys.executable = chemin de l'interp
    # Python actuel, sys.argv = arguments de lancement (incluant main.py).
    # Sur Windows, os.execv lance bien un nouveau process et ferme l'ancien.
    try:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        # Cas tordu (droits, etc.) : on retombe sur subprocess + sortie.
        print(f"[HotReload] os.execv impossible ({e}) → fallback subprocess")
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)


# ═════════════════════════════════════════════════════════════════════════════
#  2. RESTAURATION (appelée au démarrage du nouveau process)
# ═════════════════════════════════════════════════════════════════════════════

def consommer_state_si_present(game):
    """Si un fichier de hot-reload existe, applique son état complet au Game.

    Délègue à game._appliquer_save_data() : tout l'état (inventaire, peur,
    ennemis tués, etc.) est restauré identique.

    Doit être appelée APRÈS que la map de départ soit chargée (sinon le
    joueur serait téléporté puis la map écraserait sa position).

    Le fichier est SUPPRIMÉ après lecture (réussie ou pas) pour ne pas
    interférer avec un démarrage normal suivant.
    """
    if not os.path.exists(HOT_STATE_PATH):
        return False

    try:
        with open(HOT_STATE_PATH, encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        print(f"[HotReload] State illisible ({e}) — ignoré")
        _supprimer_state()
        return False

    try:
        game._appliquer_save_data(state)
    except Exception as e:
        print(f"[HotReload] Application du state échouée : {e}")
        _supprimer_state()
        return False

    j = game.joueur
    print(f"[HotReload] Restauré pos=({j.rect.x},{j.rect.y}) hp={j.hp}")
    _supprimer_state()
    return True


def _supprimer_state():
    try:
        os.remove(HOT_STATE_PATH)
    except OSError:
        pass
