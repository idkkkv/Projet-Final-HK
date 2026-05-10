# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Éditeur de cinématiques in-game
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Une interface intégrée au jeu pour CRÉER, ÉDITER, et SAUVEGARDER des
#  cinématiques sans avoir à éditer du JSON à la main.
#
#  ON L'OUVRE COMMENT ?
#  --------------------
#  Dans l'éditeur de niveaux, appuyer sur [F2] (n'importe quel mode).
#  Cela ouvre l'éditeur de cinématiques par-dessus.
#
#  STRUCTURE DE L'INTERFACE
#  ------------------------
#       ┌──────────────────────────────────────────────────────────────┐
#       │  CINEMATIQUE  > [nom_du_fichier]                  [SAUVER]   │
#       ├──────────────────────────────────────────────────────────────┤
#       │  Liste des étapes :                                          │
#       │    1. wait 1.0s                                              │
#       │    2. dialogue (3 lignes)                                    │
#       │  > 3. camera_focus (1500, 200) 1.2s         ← sélectionné    │
#       │    4. fade out 1.0s                                          │
#       │                                                              │
#       │  ↑↓ naviguer | [A] ajouter | [D] supprimer | [Enter] éditer  │
#       │  Maj+↑↓ réordonner | Ctrl+N nouveau | Ctrl+O ouvrir | [Esc]  │
#       └──────────────────────────────────────────────────────────────┘
#
#  RÉPERTOIRE DES CINÉMATIQUES
#  ---------------------------
#  Les fichiers JSON sont rangés dans cinematiques/ avec sous-dossiers
#  optionnels (ex: cinematiques/foret/intro.json). [O]uvrir affiche un
#  navigateur arborescent.
#
#  TYPES D'ÉTAPES SUPPORTÉS
#  ------------------------
#  Pour la doc précise, voir systems/cutscene.py (chaque fabrique a un
#  docstring). Liste : wait, dialogue, fade, camera_focus, camera_focus_pnj,
#  camera_release, shake, play_sound, particles_burst, player_walk,
#  set_player_pos.
#
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import pygame

CINEMATIQUES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "cinematiques"
)


# ═════════════════════════════════════════════════════════════════════════════
#  1. CATALOGUE DES TYPES D'ÉTAPES
# ═════════════════════════════════════════════════════════════════════════════
#
#  Pour chaque type : un libellé, des champs (avec leur type), et une fonction
#  "résumé" qui transforme le dict en texte lisible dans la liste.
#
#  Format des champs : (nom_clé, libellé_humain, type_par_défaut)
#       type_par_défaut sert à la fois de placeholder et d'indication de type
#       (str, float, int, list).

# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS PRESSE-PAPIERS (Ctrl+V / Ctrl+C dans les saisies de texte)
# ─────────────────────────────────────────────────────────────────────────────
#  Pourquoi ? Quand on rédige une histoire dans un Word/Google Doc à côté,
#  on veut pouvoir copier-coller des répliques entières sans tout retaper.
#  Implémentation : tkinter (livré avec Python, pas de dépendance externe).

def _clipboard_get():
    """Renvoie le texte du presse-papiers (ou "" si vide / erreur)."""
    try:
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        try:
            text = r.clipboard_get()
        except Exception:
            text = ""
        r.destroy()
        return text or ""
    except Exception:
        return ""


def _clipboard_set(text):
    """Pose `text` dans le presse-papiers."""
    try:
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(str(text))
        r.update()       # nécessaire pour rendre le contenu accessible
        r.destroy()
    except Exception:
        pass


TYPES_ETAPES = {
    "wait": {
        "libelle": "Attendre",
        "champs":  [("duration", "Durée (s)", 1.0)],
        "resume":  lambda d: f"Attendre {d.get('duration', 1.0)}s",
    },
    "dialogue": {
        "libelle": "Dialogue",
        "champs":  [("lignes_texte", "Lignes (texte|auteur sur 1 ligne, séparer par //)", "")],
        "resume":  lambda d: f"Dialogue ({len(d.get('lignes', []))} lignes)",
    },
    "fade": {
        "libelle": "Fondu",
        "champs":  [
            ("direction", "Direction (out=vers noir, in=depuis noir)", "out"),
            ("duration",  "Durée (s)", 1.0),
        ],
        "resume":  lambda d: f"Fondu {d.get('direction', 'out')} {d.get('duration', 1.0)}s",
    },
    "camera_focus": {
        "libelle": "Caméra → position",
        "champs":  [
            ("x",        "X monde", 0),
            ("y",        "Y monde", 0),
            ("duration", "Durée (s, vide=jusqu'à release)", ""),
            ("speed",    "Vitesse (0.05=très lent, 0.1=doux, 0.3=nerveux, 1=instantané)", ""),
        ],
        "resume":  lambda d: f"Caméra → ({d.get('x', 0)}, {d.get('y', 0)})"
                             + (f" v={d['speed']}" if d.get('speed') else ""),
    },
    "camera_focus_pnj": {
        "libelle": "Caméra → PNJ",
        "champs":  [
            ("nom",      "Nom du PNJ", ""),
            ("duration", "Durée (s, vide=instantané, garde la caméra fixée)", ""),
            ("speed",    "Vitesse (0.05=très lent, 0.1=doux, 0.3=nerveux, 1=instantané)", ""),
            ("follow",   "Suivre le PNJ s'il bouge (1=oui, vide=non)", ""),
        ],
        "resume":  lambda d: f"Caméra → PNJ '{d.get('nom', '?')}'"
                             + (" suivi" if d.get('follow') else "")
                             + (f" v={d['speed']}" if d.get('speed') else ""),
    },
    "camera_release": {
        "libelle": "Caméra → libérer (revient au joueur)",
        "champs":  [],
        "resume":  lambda d: "Caméra libérée",
    },
    "shake": {
        "libelle": "Secousse",
        "champs":  [
            ("amplitude", "Amplitude (px)", 6.0),
            ("duration",  "Durée (s)",      0.3),
        ],
        "resume":  lambda d: f"Secousse amp={d.get('amplitude', 6)} {d.get('duration', 0.3)}s",
    },
    "play_sound": {
        "libelle": "Jouer un son",
        "champs":  [
            ("nom",    "Nom du son chargé", ""),
            ("volume", "Volume (0-1)",      1.0),
        ],
        "resume":  lambda d: f"Son '{d.get('nom', '?')}'",
    },
    "particles_burst": {
        "libelle": "Particules (explosion)",
        "champs":  [
            ("x",  "X monde", 0),
            ("y",  "Y monde", 0),
            ("nb", "Nombre",  12),
        ],
        "resume":  lambda d: f"Particules ({d.get('x', 0)}, {d.get('y', 0)}) ×{d.get('nb', 12)}",
    },
    "player_walk": {
        "libelle": "Joueur marche vers...",
        "champs":  [
            ("x",     "X monde",    0),
            ("y",     "Y monde",    0),
            ("speed", "Vitesse",  100),
        ],
        "resume":  lambda d: f"Joueur → ({d.get('x', 0)}, {d.get('y', 0)})",
    },
    "npc_walk_by_name": {
        "libelle": "PNJ marche vers...",
        "champs":  [
            ("nom_pnj", "Nom du PNJ", ""),
            ("x",       "X monde",     0),
            ("y",       "Y monde",     0),
            ("speed",   "Vitesse",    80),
        ],
        "resume":  lambda d: f"PNJ '{d.get('nom_pnj', '?')}' → ({d.get('x', 0)}, {d.get('y', 0)})",
    },
    "set_player_pos": {
        "libelle": "Téléporter le joueur (même map, x/y)",
        "champs":  [
            ("x", "X monde", 0),
            ("y", "Y monde", 0),
        ],
        "resume":  lambda d: f"Téléport joueur ({d.get('x', 0)}, {d.get('y', 0)})",
    },
    "teleport_player": {
        "libelle": "Téléporter le joueur (autre map / spawn nommé)",
        "champs":  [
            ("cible", "Cible : 'spawn' OU 'map spawn' (vide = utilise x/y)", ""),
            ("x",     "X monde (fallback si pas de spawn nommé)", ""),
            ("y",     "Y monde (fallback si pas de spawn nommé)", ""),
        ],
        "resume":  lambda d: (
            f"Téléport → '{d.get('cible')}'" if d.get('cible')
            else f"Téléport → ({d.get('x','?')}, {d.get('y','?')})"
        ),
    },

    # ── Apparition / disparition de PNJ ──────────────────────────────────
    "npc_spawn": {
        "libelle": "Faire apparaître un PNJ",
        "champs":  [
            ("nom",     "Nom (unique)",                      ""),
            ("x",       "X monde",                            0),
            ("y",       "Y monde",                            0),
            ("sprite",  "Sprite (vide = rectangle violet)",  ""),
            ("dialogues_texte",
                "Dialogues (texte|auteur, // entre lignes, ; entre conv)",
                ""),
            ("events_texte",
                "Events fin dialogue (skill:.. ; tp:map spawn ; coins:50)",
                ""),
            ("dialogue_mode",  "Mode (boucle_dernier / restart)", "boucle_dernier"),
            ("has_gravity",    "Gravité (1=oui, 0=flottant, défaut=1)", 1),
            ("facing",         "Direction regard (1=droite, -1=gauche)", 1),
        ],
        "resume":  lambda d: f"Spawn PNJ '{d.get('nom','?')}' → ({d.get('x',0)},{d.get('y',0)})",
    },
    "npc_despawn": {
        "libelle": "Faire disparaître un PNJ",
        "champs":  [("nom", "Nom du PNJ", "")],
        "resume":  lambda d: f"Despawn PNJ '{d.get('nom','?')}'",
    },

    # ── Récompenses ──────────────────────────────────────────────────────
    "grant_skill": {
        "libelle": "Débloquer une compétence",
        "champs":  [
            ("value",
             "Compétence (double_jump/dash/back_dodge/wall_jump/attack/pogo)",
             ""),
        ],
        "resume":  lambda d: f"Skill: {d.get('value','?')}",
    },
    "grant_luciole": {
        "libelle": "Donner une luciole",
        "champs":  [("source", "Source unique (ex: 'anna_rite')", "")],
        "resume":  lambda d: f"Luciole '{d.get('source','?')}'",
    },
    "give_item": {
        "libelle": "Donner un item",
        "champs":  [
            ("name",  "Nom (Pomme, Cassette, …)", ""),
            ("count", "Quantité",                  1),
        ],
        "resume":  lambda d: f"Item: {d.get('name','?')} ×{d.get('count',1)}",
    },
    "give_coins": {
        "libelle": "Donner des pièces",
        "champs":  [("amount", "Montant", 0)],
        "resume":  lambda d: f"+{d.get('amount',0)} pièces",
    },

    # ── Mort scriptée (cinématique on_death) ─────────────────────────────
    "revive_player": {
        "libelle": "Réanimer le joueur (fin cinématique mort)",
        "champs":  [
            ("cible",
             "Spawn cible : 'map spawn' ou 'spawn' (vide = défaut)",
             ""),
        ],
        "resume":  lambda d: f"Réanime → '{d.get('cible','(défaut)')}'",
    },

    # ── Macro : débloquer la barre quick-use + donner des pommes ─────────
    "unlock_quickuse": {
        "libelle": "Débloquer croix directionnelle (+ pommes)",
        "champs":  [
            ("pommes", "Pommes données (défaut 10)", 10),
        ],
        "resume":  lambda d: f"Débloque quick-use + {d.get('pommes',10)} pommes",
    },

    # ── Story flags (déclencheurs d'événements futurs) ───────────────────
    "set_flag": {
        "libelle": "Poser un story flag (booléen)",
        "champs":  [
            ("key",   "Clé (ex: 'parchemins_lus')", ""),
            ("value", "Valeur (1=true, 0=false)",     1),
        ],
        "resume":  lambda d: f"Flag {d.get('key','?')}={'T' if d.get('value',1) else 'F'}",
    },
    "flag_increment": {
        "libelle": "Incrémenter un story flag (compteur)",
        "champs":  [
            ("key",      "Clé du flag (ex: 'tiroir_indices')", ""),
            ("delta",    "Incrément (+N ou -N)",                 1),
            ("required", "Required (vide = registre, sinon N)", ""),
        ],
        "resume":  lambda d: (f"Flag {d.get('key','?')} +="
                              f"{d.get('delta',1)}"
                              + (f" /req={d['required']}"
                                 if d.get('required') not in (None, "", 0) else "")),
    },

    # ── Audio ──────────────────────────────────────────────────────────
    "play_music": {
        "libelle": "Musique : transition",
        "champs":  [
            ("chemin",     "Chemin (vide = fadeout seul)", ""),
            ("volume",     "Volume (0.0-1.0)",           0.6),
            ("fadeout_ms", "Fadeout (ms)",              1000),
            ("fadein_ms",  "Fadein (ms)",               1500),
        ],
        "resume":  lambda d: f"Musique → {d.get('chemin','(silence)')}",
    },

    # ── Attendre une touche du joueur ───────────────────────────────────
    "wait_input": {
        "libelle": "Attendre une touche du joueur",
        "champs":  [
            ("touche",  "Touche (any / space / enter)", "any"),
            ("timeout", "Timeout (s, 0 = jamais)",        0),
        ],
        "resume":  lambda d: f"Attend touche '{d.get('touche','any')}'",
    },

    # ── Hybride cinématique/gameplay ────────────────────────────────────
    "wait_for_player_at": {
        "libelle": "Rendre la main au joueur jusqu'à un point",
        "champs":  [
            ("x",       "X monde",                  0),
            ("y",       "Y monde",                  0),
            ("radius",  "Rayon d'arrivée (px)",    32),
            ("timeout", "Timeout (s)",              60),
        ],
        "resume":  lambda d: f"Joueur libre → ({d.get('x',0)},{d.get('y',0)}) r={d.get('radius',32)}",
    },
}


# ═════════════════════════════════════════════════════════════════════════════
#  2. ÉDITEUR DE CINÉMATIQUES
# ═════════════════════════════════════════════════════════════════════════════

class CinematiqueEditor:
    """Mini-IDE pour les cinématiques (s'affiche par-dessus le jeu)."""

    # Hauteur en items visibles dans le popup [Inser] (choix du type).
    # Avec ~24 types et un popup limité, on en montre 16 et on scrolle
    # avec ↑↓ / PgUp / PgDn / Home / End.
    _TYPE_PICK_VISIBLES = 16

    def __init__(self):
        self.actif       = False
        self.nom_fichier = ""              # ex: "foret/intro" (sans .json)
        self.steps       = []              # liste de dicts {"type": ..., ...}
        self.selection   = 0               # index de l'étape sélectionnée

        # ── CONDITION D'ACTIVATION ──────────────────────────────────────
        # Optionnelle : si définie, la cinématique ne se lance que quand
        # cette condition (sur les story_flags) est vraie. Vérifiée par
        # game.py après chaque changement de flag, avec un délai (sec).
        # Format dict : cf. systems/story_flags.tester_condition.
        self._condition = None             # None | dict
        self._delay     = 1.0              # secondes d'attente avant déclenchement
        self._one_shot  = True             # ne se déclenche qu'une seule fois

        # ── JOUEUR LIBRE ────────────────────────────────────────────────
        # Si True, le joueur garde le contrôle pendant TOUTE la cinématique
        # (gravité, mouvement, anim). Utile pour : secousse à l'atterrissage
        # d'une chute, fade pendant que le perso marche, voix off ambiante.
        # Toggle avec [J] dans l'éditeur.
        self._player_libre = False

        # ── AUTO-DÉCLENCHEMENT (auto_fire) ──────────────────────────────
        # Par défaut, une cine avec condition s'auto-déclenche dès que
        # la condition est vraie. Toggle [F] désactive cet auto-fire pour
        # les rares cas (ex. cine on_death où la condition n'est qu'un
        # filtre, sinon elle fire avant même la mort).
        #   None / True → auto-fire (défaut)
        #   False       → jamais d'auto-fire, ne fire que via trigger zone
        self._auto_fire = None

        # Mode interne :
        #   None              = navigation dans la liste
        #   "browser"         = affichage de l'arbre des cinématiques (pour [O])
        #   "type_pick"       = popup du choix de type (pour [Inser])
        #   "field"           = saisie d'un champ (édition d'une étape)
        #   "filename"        = saisie du nom de fichier (sauvegarde / nouveau)
        #   "edit_condition"  = saisie de la condition d'activation
        self.mode = None

        # Référence à la caméra (posée par world.editor pour le picker [P]).
        # Sert à lire les coordonnées MONDE de la souris dans les champs x/y.
        self.camera = None

        # Callback appelée par [T] (Tester) — posée par game.py.
        # Reçoit la liste d'étapes et lance la cinématique en jeu.
        self.on_test_callback = None

        # Callback appelée par [Ctrl+R] (Reset compteur) — posée par game.py.
        # Reçoit le nom de la cinématique à "oublier" (rendue rejouable).
        # nom=None → reset TOUS les compteurs (Maj+Ctrl+R).
        self.on_reset_counter_callback = None

        # Callback appelée après chaque sauvegarde [Ctrl+S] — posée par game.py.
        # Permet de re-scanner les cinématiques conditionnelles (un fichier
        # vient peut-être d'acquérir une condition d'activation).
        self.on_save_callback = None

        # État de saisie de champ
        self._field_step_idx   = -1
        self._field_index      = 0    # index du champ en cours dans champs[]
        self._field_input      = ""
        self._field_pending    = {}   # dict en cours de remplissage (pour les ajouts)
        self._field_is_new     = False

        # Saisie de nom de fichier
        self._filename_input   = ""
        self._filename_purpose = ""  # "new" | "save_as"

        # Browser
        self._browser_files = []
        self._browser_index = 0

        # Pour [Inser] : liste des types possibles, et l'index sélectionné
        self._type_keys     = list(TYPES_ETAPES.keys())
        self._type_index    = 0
        self._type_scroll   = 0    # offset de scroll dans le popup type_pick

        # Saisie d'une condition (mode "edit_condition")
        self._cond_input    = ""

        # Police lazy
        self._font   = None
        self._fontsm = None

        # Message éphémère
        self._msg       = ""
        self._msg_timer = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    #  Cycle de vie
    # ─────────────────────────────────────────────────────────────────────────

    def ouvrir(self, nom=""):
        """Ouvre l'éditeur (depuis world.editor). nom = cinématique à charger,
        ou "" pour ouvrir le navigateur."""
        self.actif = True
        if nom:
            self._charger(nom)
        else:
            self._ouvrir_browser()

    def fermer(self):
        self.actif = False
        self.mode  = None

    def _msg_show(self, msg, duration=2.0):
        self._msg       = msg
        self._msg_timer = duration

    # ─────────────────────────────────────────────────────────────────────────
    #  Polices (lazy)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_fonts(self):
        if self._font is None:
            self._font   = pygame.font.SysFont("Consolas", 17)
            self._fontsm = pygame.font.SysFont("Consolas", 13)
        return self._font, self._fontsm

    # ─────────────────────────────────────────────────────────────────────────
    #  Persistence (charger / sauver)
    # ─────────────────────────────────────────────────────────────────────────

    def _charger(self, nom):
        """nom = chemin relatif sans .json (ex: 'foret/intro').

        Supporte deux formats JSON :
          - Liste pure (legacy) : [{...}, {...}]   → steps direct
          - Dict (enrichi)      : {"steps":[...], "condition":{...},
                                   "delay":1.0, "one_shot":true}
        """
        chemin = os.path.join(CINEMATIQUES_DIR, f"{nom}.json")
        if not os.path.exists(chemin):
            self._msg_show(f"Introuvable : {nom}")
            self.steps        = []
            self._condition   = None
            self._delay       = 1.0
            self._one_shot    = True
            self._player_libre = False
            self._auto_fire   = None
            self.nom_fichier  = nom
            return
        try:
            with open(chemin, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self._msg_show(f"Erreur lecture : {e}")
            data = []
        # Détection de format
        if isinstance(data, dict):
            self.steps         = list(data.get("steps", []))
            self._condition    = data.get("condition")
            self._delay        = float(data.get("delay", 1.0))
            self._one_shot     = bool(data.get("one_shot", True))
            self._player_libre = bool(data.get("player_libre", False))
            af = data.get("auto_fire", None)
            self._auto_fire    = (None if af is None else bool(af))
        else:
            self.steps         = list(data) if isinstance(data, list) else []
            self._condition    = None
            self._delay        = 1.0
            self._one_shot     = True
            self._player_libre = False
            self._auto_fire    = None
        self.nom_fichier = nom
        self.selection   = 0
        self.mode        = None

    def _sauver(self):
        """Sauvegarde dans cinematiques/<nom_fichier>.json.

        Si une condition d'activation est définie, on sauvegarde le format
        enrichi (dict). Sinon on garde le format simple (liste) pour
        rétrocompatibilité avec les cinématiques existantes.
        """
        if not self.nom_fichier:
            self._demander_nom("save_as")
            return
        chemin = os.path.join(CINEMATIQUES_DIR, f"{self.nom_fichier}.json")
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        # Choix du format : enrichi (dict) si on a une condition, joueur
        # libre, ou auto_fire explicite — sinon format simple (liste pure)
        # pour rester léger et rétrocompatible avec les cines existantes.
        if self._condition or self._player_libre or self._auto_fire is not None:
            data = {"steps": self.steps}
            if self._condition:
                data["condition"] = self._condition
                data["delay"]     = self._delay
                data["one_shot"]  = self._one_shot
            if self._player_libre:
                data["player_libre"] = True
            if self._auto_fire is not None:
                data["auto_fire"] = bool(self._auto_fire)
        else:
            data = self.steps
        try:
            with open(chemin, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._msg_show(f"Sauvegardé : {self.nom_fichier}.json")
            # Notifie game.py pour qu'il re-scanne les cinématiques avec
            # condition (au cas où on vient d'en ajouter une).
            if callable(self.on_save_callback):
                try:
                    self.on_save_callback()
                except Exception as e_cb:
                    print(f"[CineEditor] callback save : {e_cb}")
        except Exception as e:
            self._msg_show(f"Erreur écriture : {e}")

    # ─────────────────────────────────────────────────────────────────────────
    #  Navigateur de fichiers
    # ─────────────────────────────────────────────────────────────────────────

    def _ouvrir_browser(self):
        """Liste tous les fichiers .json sous cinematiques/ (récursivement)."""
        self.mode = "browser"
        self._browser_files = self._lister_cinematiques()
        # Place la sélection sur le fichier courant si possible
        try:
            self._browser_index = self._browser_files.index(self.nom_fichier)
        except ValueError:
            self._browser_index = 0

    def _lister_cinematiques(self):
        """Liste récursive (sous-dossiers inclus). Renvoie chemins relatifs
        sans extension, ex: ['exemple', 'foret/intro', 'final/boss']."""
        if not os.path.isdir(CINEMATIQUES_DIR):
            return []
        resultats = []
        for racine, _, fichiers in os.walk(CINEMATIQUES_DIR):
            for f in fichiers:
                if f.endswith(".json"):
                    chemin_complet = os.path.join(racine, f)
                    rel  = os.path.relpath(chemin_complet, CINEMATIQUES_DIR)
                    rel  = rel.replace("\\", "/")[:-5]   # vire .json
                    resultats.append(rel)
        return sorted(resultats)

    # ─────────────────────────────────────────────────────────────────────────
    #  Saisie : nom de fichier (popup)
    # ─────────────────────────────────────────────────────────────────────────

    def _demander_nom(self, purpose):
        """purpose = 'new' (nouveau fichier) ou 'save_as'."""
        self.mode              = "filename"
        self._filename_input   = self.nom_fichier
        self._filename_purpose = purpose

    def _confirmer_nom(self):
        nom = self._filename_input.strip()
        if not nom:
            self._msg_show("Nom vide annulé")
            self.mode = None
            return
        # Nettoyage : retire les .json à la fin si l'utilisateur l'a tapé
        if nom.endswith(".json"):
            nom = nom[:-5]
        self.nom_fichier = nom
        if self._filename_purpose == "new":
            self.steps     = []
            self.selection = 0
            self._msg_show(f"Nouvelle cinématique : {nom}")
        elif self._filename_purpose == "save_as":
            self._sauver()
        self.mode = None

    # ─────────────────────────────────────────────────────────────────────────
    #  Saisie : champs d'une étape
    # ─────────────────────────────────────────────────────────────────────────

    def _commencer_edition_etape(self, idx):
        """Édite l'étape `idx` champ par champ (popup successif)."""
        if not (0 <= idx < len(self.steps)):
            return
        step = self.steps[idx]
        meta = TYPES_ETAPES.get(step.get("type", ""))
        if meta is None or not meta["champs"]:
            self._msg_show("Aucun champ à éditer")
            return
        self.mode             = "field"
        self._field_step_idx  = idx
        self._field_index     = 0
        self._field_pending   = dict(step)   # copie pour rollback Esc
        self._field_is_new    = False
        self._init_field_input()

    def _commencer_ajout_etape(self, type_cle):
        """Crée une étape de type `type_cle` et lance la saisie des champs."""
        meta = TYPES_ETAPES.get(type_cle)
        if meta is None:
            return
        # Étape vierge (avec valeurs par défaut)
        nouvelle = {"type": type_cle}
        for nom, _libelle, defaut in meta["champs"]:
            nouvelle[nom] = defaut

        if not meta["champs"]:
            # Pas de champ : ajout direct (ex: camera_release)
            self._inserer_etape(nouvelle)
            return

        # On l'ajoute en fin de liste, on note l'index pour le retrouver
        self._inserer_etape(nouvelle)
        idx = len(self.steps) - 1

        self.mode             = "field"
        self._field_step_idx  = idx
        self._field_index     = 0
        self._field_pending   = dict(nouvelle)
        self._field_is_new    = True
        self._init_field_input()

    def _inserer_etape(self, etape):
        """Insère après la sélection actuelle (ou en fin si vide)."""
        if not self.steps:
            self.steps.append(etape)
            self.selection = 0
        else:
            insert_at = self.selection + 1
            self.steps.insert(insert_at, etape)
            self.selection = insert_at

    def _init_field_input(self):
        """Initialise self._field_input avec la valeur courante du champ."""
        meta   = TYPES_ETAPES[self._field_pending["type"]]
        champs = meta["champs"]
        if self._field_index >= len(champs):
            self._terminer_edition_etape()
            return
        nom, _libelle, defaut = champs[self._field_index]

        # Cas spécial : édition de "lignes_texte" → on linéarise
        if nom == "lignes_texte":
            lignes = self._field_pending.get("lignes", [])
            self._field_input = " // ".join(
                f"{l.get('texte', '')}|{l.get('auteur', '')}" for l in lignes
            )
        elif nom == "dialogues_texte":
            # Linéarise les conv : "; " entre conv, " // " entre lignes.
            convs = self._field_pending.get("dialogues", [])
            parts = []
            for conv in convs:
                lignes_str = []
                for ligne in conv:
                    if isinstance(ligne, (list, tuple)) and len(ligne) >= 2:
                        lignes_str.append(f"{ligne[0]}|{ligne[1]}")
                    else:
                        lignes_str.append(f"{ligne}|")
                parts.append(" // ".join(lignes_str))
            self._field_input = " ; ".join(parts)
        else:
            valeur = self._field_pending.get(nom, defaut)
            if valeur == "" or valeur is None:
                self._field_input = ""
            else:
                self._field_input = str(valeur)

    def _confirmer_champ(self):
        """Valide le champ courant et passe au suivant (ou termine)."""
        meta   = TYPES_ETAPES[self._field_pending["type"]]
        champs = meta["champs"]
        nom, _libelle, defaut = champs[self._field_index]
        brut = self._field_input.strip()

        if nom == "lignes_texte":
            # Format : "Bonjour|Marc // Ça va ?|Marc // Tres bien|Théa"
            lignes = []
            for tok in brut.split("//"):
                tok = tok.strip()
                if not tok:
                    continue
                if "|" in tok:
                    texte, auteur = tok.split("|", 1)
                    lignes.append({"texte": texte.strip(),
                                   "auteur": auteur.strip()})
                else:
                    lignes.append({"texte": tok, "auteur": ""})
            self._field_pending["lignes"] = lignes
            # On NE garde PAS "lignes_texte" dans le dict final
            self._field_pending.pop("lignes_texte", None)

        elif nom == "dialogues_texte":
            # Format : "Hello|Anna // Ça va ?|Anna ; Bye|Anna"
            #  • ";" sépare les conversations
            #  • "//" sépare les répliques d'une même conversation
            #  • "|" sépare texte et auteur
            # Produit : [[["Hello","Anna"],["Ça va ?","Anna"]], [["Bye","Anna"]]]
            conv_list = []
            for conv in brut.split(";"):
                conv = conv.strip()
                if not conv:
                    continue
                lignes = []
                for tok in conv.split("//"):
                    tok = tok.strip()
                    if not tok:
                        continue
                    if "|" in tok:
                        t, a = tok.split("|", 1)
                        lignes.append([t.strip(), a.strip()])
                    else:
                        lignes.append([tok, ""])
                if lignes:
                    conv_list.append(lignes)
            self._field_pending["dialogues"] = conv_list
            self._field_pending.pop("dialogues_texte", None)

        elif nom == "events_texte":
            # Events à appliquer en fin de dialogue. Format identique au
            # PNJ editor : "type1:val1; type2:val2 ; e3:v3 :: e3bis:v3bis"
            # où "::" sépare les conversations (rare car la plupart des
            # PNJ spawnés n'ont qu'une seule conversation).
            # Types supportés : skill, luciole, coins, hp, max_hp, item,
            # flag, flag_increment (via flag:k+=N), teleport (tp:cible).
            ev_list_par_conv = []
            for conv_block in brut.split("::"):
                conv_block = conv_block.strip()
                if not conv_block:
                    ev_list_par_conv.append([])
                    continue
                events_conv = []
                for seg in conv_block.split(";"):
                    seg = seg.strip()
                    if not seg or ":" not in seg:
                        continue
                    t, rest = seg.split(":", 1)
                    t    = t.strip()
                    rest = rest.strip()
                    if t == "tp":
                        # tp:cible OU tp:cible:X:Y OU tp::X:Y
                        ev = {"type": "teleport"}
                        segs = rest.split(":")
                        if segs:
                            ev["cible"] = segs[0].strip()
                        if len(segs) >= 3:
                            try:
                                ev["x"] = float(segs[1].strip()) if segs[1].strip() else None
                                ev["y"] = float(segs[2].strip()) if segs[2].strip() else None
                            except ValueError:
                                pass
                        events_conv.append(ev)
                    elif t == "skill":
                        events_conv.append({"type": "skill", "value": rest})
                    elif t == "luciole":
                        events_conv.append({"type": "luciole", "source": rest})
                    elif t in ("coins", "hp", "max_hp"):
                        try:
                            events_conv.append({"type": t, "value": int(rest)})
                        except ValueError:
                            pass
                    elif t == "item":
                        if ":" in rest:
                            name, cnt = rest.split(":", 1)
                            try:
                                events_conv.append({"type": "item",
                                                    "value": name.strip(),
                                                    "count": int(cnt)})
                            except ValueError:
                                events_conv.append({"type": "item", "value": name.strip()})
                        else:
                            events_conv.append({"type": "item", "value": rest})
                    elif t == "flag":
                        if "+=" in rest or "-=" in rest:
                            op = "+=" if "+=" in rest else "-="
                            kp, dp = rest.split(op, 1)
                            key = kp.strip()
                            req = None
                            if ":req=" in dp:
                                d2, rp = dp.split(":req=", 1)
                                try:
                                    delta = int(d2.strip()) if d2.strip() else 1
                                except ValueError:
                                    delta = 1
                                try:
                                    req = max(1, int(rp.strip()))
                                except ValueError:
                                    req = None
                            else:
                                try:
                                    delta = int(dp.strip()) if dp.strip() else 1
                                except ValueError:
                                    delta = 1
                            if op == "-=":
                                delta = -abs(delta)
                            ev = {"type": "flag_increment", "key": key, "delta": delta}
                            if req is not None:
                                ev["required"] = req
                            events_conv.append(ev)
                        elif "=" in rest:
                            k, v = rest.split("=", 1)
                            events_conv.append({
                                "type": "flag", "key": k.strip(),
                                "value": v.strip() not in ("0", "false", "False", ""),
                            })
                        else:
                            events_conv.append({"type": "flag", "key": rest, "value": True})
                ev_list_par_conv.append(events_conv)
            self._field_pending["events"] = ev_list_par_conv
            self._field_pending.pop("events_texte", None)

        else:
            # Conversion typée d'après le default
            if isinstance(defaut, float):
                if brut:
                    try:    self._field_pending[nom] = float(brut)
                    except: self._field_pending[nom] = defaut
                else:
                    self._field_pending[nom] = None
            elif isinstance(defaut, int):
                if brut:
                    try:    self._field_pending[nom] = int(brut)
                    except: self._field_pending[nom] = defaut
                else:
                    self._field_pending[nom] = None
            else:
                # Champs string : si vide, on stocke None pour signaler
                # "valeur non fournie" (utile pour les durées optionnelles
                # comme "vide=jusqu'à release"). Le chargeur JSON gère "" et None.
                self._field_pending[nom] = brut if brut else None

        self._field_index += 1
        # ── Cas spécial : pour teleport_player, si la cible est remplie,
        # on saute les fields x/y (qui ne sont qu'un fallback inutile).
        # Évite à l'utilisateur de devoir taper Entrée 2 fois pour valider.
        if (self._field_pending.get("type") == "teleport_player"
                and self._field_pending.get("cible")):
            # Skip vers la fin (ne pas demander x ni y)
            self._field_index = len(champs)
        if self._field_index >= len(champs):
            self._terminer_edition_etape()
        else:
            self._init_field_input()

    def _terminer_edition_etape(self):
        """Étape complète : on remplace l'étape dans self.steps."""
        idx = self._field_step_idx
        if 0 <= idx < len(self.steps):
            # Nettoie les clés temporaires (lignes_texte / dialogues_texte)
            self._field_pending.pop("lignes_texte", None)
            self._field_pending.pop("dialogues_texte", None)
            self.steps[idx] = self._field_pending
        self.mode             = None
        self._field_step_idx  = -1
        self._field_pending   = {}
        self._field_is_new    = False

    def _annuler_edition_etape(self):
        """Esc en cours d'édition : si c'était un ajout, on retire l'étape."""
        if self._field_is_new and 0 <= self._field_step_idx < len(self.steps):
            self.steps.pop(self._field_step_idx)
            if self.selection >= len(self.steps):
                self.selection = max(0, len(self.steps) - 1)
        self.mode             = None
        self._field_step_idx  = -1
        self._field_pending   = {}
        self._field_is_new    = False

    # ─────────────────────────────────────────────────────────────────────────
    #  Entrée clavier
    # ─────────────────────────────────────────────────────────────────────────

    def handle_key(self, key, mods=0):
        """Renvoie True si on a consommé l'événement (l'éditeur reste ouvert)."""
        if not self.actif:
            return False

        # Esc global : ferme le mode courant ou l'éditeur entier
        if key == pygame.K_ESCAPE:
            if self.mode == "field":
                self._annuler_edition_etape()
            elif self.mode in ("browser", "type_pick", "filename",
                               "edit_condition"):
                self.mode = None
            else:
                self.fermer()
            return True

        # Selon le mode
        if self.mode == "filename":
            return self._handle_key_filename(key)
        if self.mode == "browser":
            return self._handle_key_browser(key)
        if self.mode == "type_pick":
            return self._handle_key_type_pick(key)
        if self.mode == "field":
            return self._handle_key_field(key)
        if self.mode == "edit_condition":
            return self._handle_key_condition(key)

        # Mode navigation : la liste des étapes
        return self._handle_key_navigation(key, mods)

    def handle_textinput(self, text):
        """Caractères Unicode (saisie de texte avec accents)."""
        if not self.actif:
            return
        if self.mode == "filename":
            self._filename_input += text
        elif self.mode == "field":
            self._field_input += text
        elif self.mode == "edit_condition":
            self._cond_input += text

    def _handle_key_navigation(self, key, mods):
        shift = bool(mods & pygame.KMOD_SHIFT)
        ctrl  = bool(mods & pygame.KMOD_CTRL)

        # Réordonnage : Shift+↑/↓ (clavier portable friendly)
        if shift and key == pygame.K_UP and self.steps and self.selection > 0:
            self.steps[self.selection], self.steps[self.selection - 1] = \
                self.steps[self.selection - 1], self.steps[self.selection]
            self.selection -= 1
        elif shift and key == pygame.K_DOWN and self.steps \
                and self.selection < len(self.steps) - 1:
            self.steps[self.selection], self.steps[self.selection + 1] = \
                self.steps[self.selection + 1], self.steps[self.selection]
            self.selection += 1

        # Navigation simple
        elif key == pygame.K_UP and self.steps:
            self.selection = (self.selection - 1) % len(self.steps)
        elif key == pygame.K_DOWN and self.steps:
            self.selection = (self.selection + 1) % len(self.steps)

        # [A] = ajouter | [+] = ajouter aussi (touche du pavé num)
        elif key in (pygame.K_a, pygame.K_KP_PLUS, pygame.K_PLUS, pygame.K_EQUALS):
            self.mode        = "type_pick"
            self._type_index = 0

        # [D] = supprimer | [-] | [Suppr] (Delete) si dispo
        elif key in (pygame.K_d, pygame.K_KP_MINUS, pygame.K_MINUS,
                     pygame.K_DELETE) and self.steps:
            self.steps.pop(self.selection)
            if self.selection >= len(self.steps):
                self.selection = max(0, len(self.steps) - 1)

        elif key == pygame.K_RETURN:
            self._commencer_edition_etape(self.selection)

        elif key == pygame.K_s and ctrl:
            self._sauver()
        elif key == pygame.K_n and ctrl:
            self._demander_nom("new")
        elif key == pygame.K_o and ctrl:
            self._ouvrir_browser()
        elif key == pygame.K_c and not ctrl:
            # [C] = éditer la CONDITION D'ACTIVATION de la cinématique.
            # Si elle est définie, la cinématique se déclenchera UNIQUEMENT
            # quand cette condition (sur les story_flags) sera vraie. Le
            # joueur doit avoir fini un dialogue (~delay sec) pour qu'elle
            # soit vérifiée.
            self._commencer_edition_condition()
        elif key == pygame.K_j and not ctrl:
            # [J] = toggle "Joueur libre". La cinématique tourne mais le
            # joueur garde le contrôle de son perso (gravité, mouvement).
            # Idéal pour shake d'écran à l'atterrissage, fade en marchant,
            # voix off ambiante…
            self._player_libre = not self._player_libre
            etat = "ON" if self._player_libre else "OFF"
            self._msg_show(f"Joueur libre : {etat}")
        elif key == pygame.K_f and not ctrl:
            # [F] = toggle auto-déclenchement.
            # Par défaut (None ou True), la cine s'auto-déclenche quand sa
            # condition devient vraie. Le toggle bascule à False pour
            # désactiver. Re-toggle remet à True (= défaut explicite).
            if self._auto_fire is False:
                self._auto_fire = True
                self._msg_show("Auto-déclenchement : ACTIVÉ (défaut)")
            else:
                self._auto_fire = False
                self._msg_show("Auto-déclenchement : DÉSACTIVÉ "
                               "(la cine ne fire que via trigger zone)")
        elif key == pygame.K_t and self.steps and self.on_test_callback:
            # Tester la cinématique : on ferme l'éditeur et on lance le run
            # via le callback (game.py construit un Cutscene depuis self.steps).
            # On passe aussi les options pour que le test reflète exactement
            # ce qu'il se passera en jeu (joueur libre, etc.).
            try:
                self.on_test_callback(list(self.steps),
                                      player_libre=self._player_libre)
            except TypeError:
                # Rétrocompat : ancien callback à 1 seul argument.
                self.on_test_callback(list(self.steps))
            self.fermer()
        elif key == pygame.K_r and ctrl and self.on_reset_counter_callback:
            # Reset le compteur "cinematiques_jouees" pour la cinématique
            # courante. Avec Maj : reset TOUS les compteurs (debug global).
            shift = bool(mods & pygame.KMOD_SHIFT)
            cible = None if shift else self.nom_fichier
            self.on_reset_counter_callback(cible)
            if shift:
                self._msg_show("Tous les compteurs réinitialisés")
            elif self.nom_fichier:
                self._msg_show(f"Compteur '{self.nom_fichier}' réinitialisé")
            else:
                self._msg_show("Pas de cinématique chargée")
        return True

    def _handle_key_browser(self, key):
        n = len(self._browser_files)
        if key == pygame.K_UP and n:
            self._browser_index = (self._browser_index - 1) % n
        elif key == pygame.K_DOWN and n:
            self._browser_index = (self._browser_index + 1) % n
        elif key == pygame.K_RETURN and n:
            self._charger(self._browser_files[self._browser_index])
        elif key in (pygame.K_n, pygame.K_a, pygame.K_KP_PLUS,
                     pygame.K_PLUS, pygame.K_EQUALS):
            self._demander_nom("new")
        return True

    def _handle_key_type_pick(self, key):
        n = len(self._type_keys)
        # Nombre d'items visibles : doit correspondre à _draw_popup_type_pick.
        visibles = self._TYPE_PICK_VISIBLES
        if key == pygame.K_UP and n:
            self._type_index = (self._type_index - 1) % n
        elif key == pygame.K_DOWN and n:
            self._type_index = (self._type_index + 1) % n
        elif key == pygame.K_PAGEUP and n:
            self._type_index = max(0, self._type_index - visibles)
        elif key == pygame.K_PAGEDOWN and n:
            self._type_index = min(n - 1, self._type_index + visibles)
        elif key == pygame.K_HOME and n:
            self._type_index = 0
        elif key == pygame.K_END and n:
            self._type_index = n - 1
        elif key == pygame.K_RETURN and n:
            type_cle = self._type_keys[self._type_index]
            self.mode = None
            self._commencer_ajout_etape(type_cle)
        # Maintient l'item sélectionné dans la fenêtre visible.
        if self._type_index < self._type_scroll:
            self._type_scroll = self._type_index
        elif self._type_index >= self._type_scroll + visibles:
            self._type_scroll = self._type_index - visibles + 1
        return True

    # ── Édition de la condition d'activation ──────────────────────────────────

    def _commencer_edition_condition(self):
        """Ouvre le popup de saisie de la condition d'activation."""
        from systems.story_flags import formater_condition_texte
        self.mode        = "edit_condition"
        self._cond_input = formater_condition_texte(self._condition)

    def _handle_key_condition(self, key):
        from systems.story_flags import parser_condition_texte
        mods = pygame.key.get_mods()
        ctrl = bool(mods & pygame.KMOD_CTRL)
        if key == pygame.K_RETURN:
            self._condition = parser_condition_texte(self._cond_input)
            self.mode = None
            if self._condition:
                self._msg_show("Condition d'activation enregistrée ✓")
            else:
                self._msg_show("Condition retirée (déclenchement manuel)")
        elif key == pygame.K_BACKSPACE:
            self._cond_input = self._cond_input[:-1]
        elif ctrl and key == pygame.K_v:
            self._cond_input += _clipboard_get().replace("\n", "").replace("\r", "")
        elif ctrl and key == pygame.K_c:
            _clipboard_set(self._cond_input)
        return True

    def _handle_key_filename(self, key):
        mods = pygame.key.get_mods()
        ctrl = bool(mods & pygame.KMOD_CTRL)
        if key == pygame.K_RETURN:
            self._confirmer_nom()
        elif key == pygame.K_BACKSPACE:
            self._filename_input = self._filename_input[:-1]
        elif ctrl and key == pygame.K_v:
            # Ctrl+V : colle le presse-papiers (filtre le \n).
            self._filename_input += _clipboard_get().replace("\n", "").replace("\r", "")
        elif ctrl and key == pygame.K_c:
            _clipboard_set(self._filename_input)
        return True

    def _handle_key_field(self, key):
        mods = pygame.key.get_mods()
        ctrl = bool(mods & pygame.KMOD_CTRL)
        if key == pygame.K_RETURN:
            self._confirmer_champ()
        elif key == pygame.K_BACKSPACE:
            self._field_input = self._field_input[:-1]
        elif ctrl and key == pygame.K_v:
            # Ctrl+V : colle le presse-papiers. On normalise les retours
            # de ligne pour ne pas casser les saisies multi-conv (où "//"
            # et ";" sont les vrais séparateurs).
            txt = _clipboard_get().replace("\r\n", "\n").replace("\r", "\n")
            self._field_input += txt
        elif ctrl and key == pygame.K_c:
            _clipboard_set(self._field_input)
        elif key == pygame.K_p and self.camera is not None:
            # Picker : remplit le champ courant avec la coord monde de la souris
            # (X ou Y selon le nom du champ courant).
            meta   = TYPES_ETAPES[self._field_pending["type"]]
            champs = meta["champs"]
            if self._field_index < len(champs):
                nom_champ = champs[self._field_index][0]
                if nom_champ in ("x", "y"):
                    mx, my = pygame.mouse.get_pos()
                    wx = int(mx + self.camera.offset_x)
                    wy = int(my + self.camera.offset_y)
                    self._field_input = str(wx if nom_champ == "x" else wy)
                    self._confirmer_champ()
        return True

    # ─────────────────────────────────────────────────────────────────────────
    #  Rendu
    # ─────────────────────────────────────────────────────────────────────────

    def update(self, dt):
        if self._msg_timer > 0:
            self._msg_timer -= dt

    def draw(self, surf):
        if not self.actif:
            return
        font, fontsm = self._get_fonts()
        w, h = surf.get_size()

        # ── Mode "viser" : on est en saisie d'un champ x/y → on rend le voile
        # quasi transparent pour que l'utilisateur VOIE le monde et puisse
        # déplacer sa souris à la position voulue. Le popup mini en bas + les
        # coords MONDE en haut à droite suffisent.
        if self._is_picking_xy():
            self._draw_pick_mode(surf, font, fontsm)
            return

        # Voile noir semi-transparent (pour bien démarquer)
        voile = pygame.Surface((w, h), pygame.SRCALPHA)
        voile.fill((0, 0, 0, 200))
        surf.blit(voile, (0, 0))

        # Cadre principal
        marge = 60
        cadre = pygame.Rect(marge, marge, w - 2 * marge, h - 2 * marge)
        pygame.draw.rect(surf, (25, 25, 35), cadre)
        pygame.draw.rect(surf, (240, 200, 80), cadre, 2)

        # Titre
        titre = f"CINEMATIQUE  >  {self.nom_fichier or '(non nommée)'}"
        surf.blit(font.render(titre, True, (240, 200, 80)),
                  (cadre.x + 16, cadre.y + 12))

        # Aide
        aide = ("[↑↓] [A] +  [D] -  [Enter] éditer  [Maj+↑↓] reord  "
                "[C] cond  [J] joueur libre  [F] auto-fire  [T] Test  "
                "[Ctrl+R] reset  [Ctrl+S/N/O]  [Esc]")
        surf.blit(fontsm.render(aide, True, (140, 140, 140)),
                  (cadre.x + 16, cadre.y + 38))

        # ── Bandeau "Condition d'activation" / "Joueur libre" ────────────
        # Affichés en doré (condition) et vert (joueur libre) pour rappeler
        # les options actives sans avoir à fouiller dans le JSON.
        y = cadre.y + 70
        if self._condition:
            from systems.story_flags import formater_condition_texte
            cond_str = formater_condition_texte(self._condition)
            txt = (f"⏵ Condition : {cond_str}   "
                   f"(délai: {self._delay:.1f}s, "
                   f"{'one-shot' if self._one_shot else 'rejouable'})")
            surf.blit(fontsm.render(txt, True, (255, 215, 70)),
                      (cadre.x + 16, y - 10))
            y += 16
        if self._player_libre:
            txt = "⏵ Joueur libre : le perso garde le contrôle pendant la cinématique"
            surf.blit(fontsm.render(txt, True, (140, 220, 140)),
                      (cadre.x + 16, y - 10))
            y += 16
        if self._auto_fire is False:
            # Seul le cas "désactivé" mérite un bandeau (le défaut activé
            # n'a pas besoin d'être affiché — c'est… le défaut).
            txt = ("⏵ Auto-fire DÉSACTIVÉ : la cinématique ne se déclenche "
                   "que via sa trigger zone")
            surf.blit(fontsm.render(txt, True, (220, 140, 140)),
                      (cadre.x + 16, y - 10))
            y += 16

        # Liste des étapes
        for i, step in enumerate(self.steps):
            meta = TYPES_ETAPES.get(step.get("type", ""))
            if meta:
                txt = meta["resume"](step)
            else:
                txt = step.get("type", "?")

            if i == self.selection and self.mode is None:
                pygame.draw.rect(surf, (60, 60, 90),
                                 (cadre.x + 12, y - 2, cadre.width - 24, 22))
            prefix = f"{i+1:2d}. "
            color  = (255, 255, 255) if i == self.selection else (200, 200, 220)
            surf.blit(font.render(prefix + txt, True, color),
                      (cadre.x + 16, y))
            y += 22
            if y > cadre.bottom - 60:
                break

        if not self.steps:
            surf.blit(font.render("(cinématique vide — appuyer sur [Inser] pour ajouter une étape)",
                                  True, (140, 140, 140)),
                      (cadre.x + 16, y))

        # Message éphémère
        if self._msg_timer > 0 and self._msg:
            ms = font.render(self._msg, True, (255, 220, 120))
            surf.blit(ms, (cadre.centerx - ms.get_width() // 2, cadre.bottom - 30))

        # Popups par-dessus
        if self.mode == "filename":
            self._draw_popup_filename(surf, font)
        elif self.mode == "browser":
            self._draw_popup_browser(surf, font, fontsm)
        elif self.mode == "type_pick":
            self._draw_popup_type_pick(surf, font, fontsm)
        elif self.mode == "field":
            self._draw_popup_field(surf, font, fontsm)
        elif self.mode == "edit_condition":
            self._draw_popup_condition(surf, font, fontsm)

    def _is_picking_xy(self):
        """True si l'utilisateur est en train de saisir un champ x ou y."""
        if self.mode != "field":
            return False
        if not self._field_pending:
            return False
        meta = TYPES_ETAPES.get(self._field_pending.get("type", ""))
        if meta is None:
            return False
        champs = meta["champs"]
        if not (0 <= self._field_index < len(champs)):
            return False
        nom = champs[self._field_index][0]
        return nom in ("x", "y")

    def _draw_pick_mode(self, surf, font, fontsm):
        """Vue minimale : on garde le monde visible, on n'affiche qu'un voile
        très léger + un bandeau bas + les coords souris en haut à droite +
        une croix au centre de l'écran (le centre du cadre cinématique)."""
        w, h = surf.get_size()

        # Voile très léger pour rappeler qu'on est dans un mode spécial
        voile = pygame.Surface((w, h), pygame.SRCALPHA)
        voile.fill((0, 0, 0, 50))
        surf.blit(voile, (0, 0))

        # Réticule au centre de l'écran (= où la caméra cinématique cadrera)
        cx, cy = w // 2, h // 2
        col = (255, 240, 130)
        pygame.draw.line(surf, col, (cx - 14, cy), (cx - 4, cy), 2)
        pygame.draw.line(surf, col, (cx + 4,  cy), (cx + 14, cy), 2)
        pygame.draw.line(surf, col, (cx, cy - 14), (cx, cy - 4), 2)
        pygame.draw.line(surf, col, (cx, cy + 4),  (cx, cy + 14), 2)
        pygame.draw.circle(surf, col, (cx, cy), 18, 1)

        # Coordonnées MONDE de la souris en haut à droite
        self._draw_coords_overlay(surf, font)

        # Petit bandeau en bas avec les instructions
        meta = TYPES_ETAPES[self._field_pending["type"]]
        champs = meta["champs"]
        nom, libelle, _ = champs[self._field_index]
        bh = 80
        bg = pygame.Surface((w, bh), pygame.SRCALPHA)
        bg.fill((10, 10, 18, 230))
        surf.blit(bg, (0, h - bh))
        pygame.draw.line(surf, (240, 200, 80), (0, h - bh), (w, h - bh), 2)

        surf.blit(font.render(f"{meta['libelle']} — {libelle}", True, (240, 200, 80)),
                  (16, h - bh + 8))
        instr = ("Bouge la souris pour viser. [P] = utiliser cette position. "
                 "[Esc] annuler.  Ou tape la valeur :")
        surf.blit(fontsm.render(instr, True, (200, 200, 200)),
                  (16, h - bh + 32))
        surf.blit(font.render(self._field_input + "_", True, (255, 255, 255)),
                  (16, h - bh + 50))

    def _draw_popup_box(self, surf, w, h):
        sw, sh = surf.get_size()
        box = pygame.Rect(sw // 2 - w // 2, sh // 2 - h // 2, w, h)
        pygame.draw.rect(surf, (30, 30, 45), box)
        pygame.draw.rect(surf, (240, 200, 80), box, 2)
        return box

    def _draw_popup_filename(self, surf, font):
        box = self._draw_popup_box(surf, 600, 100)
        prompt = "Nom du fichier (ex: foret/intro) : " + self._filename_input + "_"
        surf.blit(font.render(prompt, True, (255, 255, 255)),
                  (box.x + 16, box.y + 36))

    def _draw_popup_browser(self, surf, font, fontsm):
        box = self._draw_popup_box(surf, 700, 500)
        surf.blit(font.render("Cinématiques disponibles  ([N] nouvelle)",
                              True, (240, 200, 80)),
                  (box.x + 16, box.y + 12))
        y = box.y + 50
        for i, nom in enumerate(self._browser_files):
            if i == self._browser_index:
                pygame.draw.rect(surf, (60, 60, 90),
                                 (box.x + 8, y - 2, box.width - 16, 22))
            color = (255, 255, 255) if i == self._browser_index else (200, 200, 220)
            surf.blit(font.render(nom, True, color), (box.x + 16, y))
            y += 22
            if y > box.bottom - 16:
                break
        if not self._browser_files:
            surf.blit(font.render("(aucune cinématique — [N] pour en créer une)",
                                  True, (140, 140, 140)),
                      (box.x + 16, box.y + 50))

    def _draw_popup_type_pick(self, surf, font, fontsm):
        # Box plus large pour accueillir des libellés longs sans déborder.
        box = self._draw_popup_box(surf, 620, 480)
        surf.blit(font.render("Type d'étape :  ([↑↓] / [PgUp/PgDn] / [Home/End])",
                              True, (240, 200, 80)),
                  (box.x + 16, box.y + 12))

        n        = len(self._type_keys)
        visibles = self._TYPE_PICK_VISIBLES
        # Ajuste le scroll au cas où l'index a bougé hors-fenêtre.
        if self._type_index < self._type_scroll:
            self._type_scroll = self._type_index
        elif self._type_index >= self._type_scroll + visibles:
            self._type_scroll = self._type_index - visibles + 1
        self._type_scroll = max(0, min(self._type_scroll, max(0, n - visibles)))

        y       = box.y + 50
        debut   = self._type_scroll
        fin     = min(n, debut + visibles)
        # Flèche "↑" si du contenu au-dessus
        if debut > 0:
            surf.blit(fontsm.render("▲ ...", True, (180, 180, 200)),
                      (box.x + 16, y - 14))

        for i in range(debut, fin):
            key  = self._type_keys[i]
            meta = TYPES_ETAPES[key]
            if i == self._type_index:
                pygame.draw.rect(surf, (60, 60, 90),
                                 (box.x + 8, y - 2, box.width - 16, 22))
            color = (255, 255, 255) if i == self._type_index else (200, 200, 220)
            # Tronque les libellés trop longs (sécurité)
            label = f"{key:20s}  {meta['libelle']}"
            if font.size(label)[0] > box.width - 30:
                while label and font.size(label + "…")[0] > box.width - 30:
                    label = label[:-1]
                label += "…"
            surf.blit(font.render(label, True, color),
                      (box.x + 16, y))
            y += 22

        # Flèche "↓" si du contenu en-dessous
        if fin < n:
            surf.blit(fontsm.render(f"▼ ... ({n - fin} de plus)",
                                    True, (180, 180, 200)),
                      (box.x + 16, y + 2))

        # Indicateur de position globale
        pos_str = f"{self._type_index + 1}/{n}"
        surf.blit(fontsm.render(pos_str, True, (160, 160, 180)),
                  (box.right - 60, box.bottom - 22))

    def _draw_popup_field(self, surf, font, fontsm):
        # Box élargie pour accueillir le wrap multi-lignes.
        box = self._draw_popup_box(surf, 900, 230)
        meta = TYPES_ETAPES[self._field_pending["type"]]
        champs = meta["champs"]
        nom, libelle, _ = champs[self._field_index]
        progression = f"({self._field_index + 1}/{len(champs)})"
        type_lib = meta["libelle"]
        surf.blit(font.render(f"{type_lib} {progression}",
                              True, (240, 200, 80)),
                  (box.x + 16, box.y + 12))
        surf.blit(font.render(libelle + " :", True, (200, 200, 200)),
                  (box.x + 16, box.y + 46))

        # Affichage avec wrap pour ne pas déborder de la box.
        largeur_max = box.width - 32
        lignes = self._wrap_texte(self._field_input + "_", font, largeur_max)
        max_lignes = 4
        lignes_visibles = lignes[-max_lignes:]
        y = box.y + 74
        for ligne in lignes_visibles:
            surf.blit(font.render(ligne, True, (255, 255, 255)),
                      (box.x + 16, y))
            y += 22

        # Indication du picker [P] si on est sur un champ x/y
        if nom in ("x", "y"):
            surf.blit(fontsm.render(
                "[P] = utiliser la position de la souris (monde)",
                True, (180, 180, 120)),
                (box.x + 16, box.bottom - 44))
            self._draw_coords_overlay(surf, font)
        surf.blit(fontsm.render("[Enter] valider | [Esc] annuler",
                                True, (140, 140, 140)),
                  (box.x + 16, box.bottom - 24))

    def _draw_popup_condition(self, surf, font, fontsm):
        """Popup pour saisir la condition d'activation de la cinématique."""
        box = self._draw_popup_box(surf, 800, 220)
        surf.blit(font.render("Condition d'activation de la cinématique :",
                              True, (255, 215, 70)),
                  (box.x + 16, box.y + 12))
        aide_lignes = [
            "(vide)            = pas de condition (cinématique sur trigger zone uniquement)",
            "flag:tiroirs      = activée quand le flag 'tiroirs' est COMPLÉTÉ (current >= required)",
            "flag:tiroirs=2    = activée quand current >= 2 (seuil)",
            "flag:tiroirs=0    = activée quand le flag est INCOMPLET ou absent",
            "any:k1,k2         = activée si AU MOINS un des flags est complet",
            "all:k1,k2         = activée si TOUS les flags sont complets",
        ]
        y = box.y + 44
        for li in aide_lignes:
            surf.blit(fontsm.render(li, True, (170, 170, 200)),
                      (box.x + 16, y))
            y += 16

        # Champ de saisie (wrap si très long)
        largeur_max = box.width - 32
        lignes = self._wrap_texte(self._cond_input + "_", font, largeur_max)
        for ligne in lignes[-2:]:
            surf.blit(font.render(ligne, True, (255, 255, 255)),
                      (box.x + 16, y + 6))
            y += 22

        surf.blit(fontsm.render("[Enter] valider | [Esc] annuler | [Ctrl+V] coller",
                                True, (140, 140, 140)),
                  (box.x + 16, box.bottom - 22))

    def _wrap_texte(self, texte, font, largeur_max):
        """Coupe `texte` en lignes pour rester dans `largeur_max` (px)."""
        if not texte:
            return [""]
        lignes = []
        for paragraphe in texte.split("\n"):
            mots  = paragraphe.split(" ")
            ligne = ""
            for mot in mots:
                test = (ligne + " " + mot).strip()
                if font.size(test)[0] <= largeur_max:
                    ligne = test
                else:
                    if ligne:
                        lignes.append(ligne)
                    if font.size(mot)[0] > largeur_max:
                        cur = ""
                        for c in mot:
                            if font.size(cur + c)[0] > largeur_max:
                                if cur:
                                    lignes.append(cur)
                                cur = c
                            else:
                                cur += c
                        ligne = cur
                    else:
                        ligne = mot
            lignes.append(ligne)
        return lignes or [""]

    def _draw_coords_overlay(self, surf, font):
        """Bandeau visible en haut à droite avec les coords MONDE de la souris.

        Sert pendant la saisie de x/y : la barre habituelle de l'éditeur est
        masquée par notre voile, donc on affiche les coords PAR-DESSUS le voile."""
        if self.camera is None:
            return
        mx, my = pygame.mouse.get_pos()
        wx = int(mx + self.camera.offset_x)
        wy = int(my + self.camera.offset_y)
        sw, sh = surf.get_size()
        txt = f"Souris monde :  X = {wx}    Y = {wy}"
        rendu = font.render(txt, True, (255, 240, 130))
        # Cadre semi-transparent par-dessus tout
        bg = pygame.Surface((rendu.get_width() + 24, rendu.get_height() + 12),
                            pygame.SRCALPHA)
        bg.fill((0, 0, 0, 220))
        pygame.draw.rect(bg, (240, 200, 80),
                         bg.get_rect(), 2)
        surf.blit(bg, (sw - bg.get_width() - 20, 20))
        surf.blit(rendu, (sw - bg.get_width() - 20 + 12, 26))
