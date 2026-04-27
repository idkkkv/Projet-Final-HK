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
        "libelle": "Téléporter le joueur",
        "champs":  [
            ("x", "X monde", 0),
            ("y", "Y monde", 0),
        ],
        "resume":  lambda d: f"Téléport joueur ({d.get('x', 0)}, {d.get('y', 0)})",
    },
}


# ═════════════════════════════════════════════════════════════════════════════
#  2. ÉDITEUR DE CINÉMATIQUES
# ═════════════════════════════════════════════════════════════════════════════

class CinematiqueEditor:
    """Mini-IDE pour les cinématiques (s'affiche par-dessus le jeu)."""

    def __init__(self):
        self.actif       = False
        self.nom_fichier = ""              # ex: "foret/intro" (sans .json)
        self.steps       = []              # liste de dicts {"type": ..., ...}
        self.selection   = 0               # index de l'étape sélectionnée

        # Mode interne :
        #   None         = navigation dans la liste
        #   "browser"    = affichage de l'arbre des cinématiques (pour [O])
        #   "type_pick"  = popup du choix de type (pour [Inser])
        #   "field"      = saisie d'un champ (édition d'une étape)
        #   "filename"   = saisie du nom de fichier (sauvegarde / nouveau)
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
        """nom = chemin relatif sans .json (ex: 'foret/intro')."""
        chemin = os.path.join(CINEMATIQUES_DIR, f"{nom}.json")
        if not os.path.exists(chemin):
            self._msg_show(f"Introuvable : {nom}")
            self.steps = []
            self.nom_fichier = nom
            return
        try:
            with open(chemin, encoding="utf-8") as f:
                self.steps = json.load(f)
        except Exception as e:
            self._msg_show(f"Erreur lecture : {e}")
            self.steps = []
        self.nom_fichier = nom
        self.selection   = 0
        self.mode        = None

    def _sauver(self):
        """Sauvegarde dans cinematiques/<nom_fichier>.json."""
        if not self.nom_fichier:
            self._demander_nom("save_as")
            return
        chemin = os.path.join(CINEMATIQUES_DIR, f"{self.nom_fichier}.json")
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        try:
            with open(chemin, "w", encoding="utf-8") as f:
                json.dump(self.steps, f, indent=2, ensure_ascii=False)
            self._msg_show(f"Sauvegardé : {self.nom_fichier}.json")
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
        if self._field_index >= len(champs):
            self._terminer_edition_etape()
        else:
            self._init_field_input()

    def _terminer_edition_etape(self):
        """Étape complète : on remplace l'étape dans self.steps."""
        idx = self._field_step_idx
        if 0 <= idx < len(self.steps):
            # Nettoie les clés temporaires (lignes_texte)
            self._field_pending.pop("lignes_texte", None)
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
            elif self.mode in ("browser", "type_pick", "filename"):
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
        elif key == pygame.K_t and self.steps and self.on_test_callback:
            # Tester la cinématique : on ferme l'éditeur et on lance le run
            # via le callback (game.py construit un Cutscene depuis self.steps).
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
        if key == pygame.K_UP and n:
            self._type_index = (self._type_index - 1) % n
        elif key == pygame.K_DOWN and n:
            self._type_index = (self._type_index + 1) % n
        elif key == pygame.K_RETURN and n:
            type_cle = self._type_keys[self._type_index]
            self.mode = None
            self._commencer_ajout_etape(type_cle)
        return True

    def _handle_key_filename(self, key):
        if key == pygame.K_RETURN:
            self._confirmer_nom()
        elif key == pygame.K_BACKSPACE:
            self._filename_input = self._filename_input[:-1]
        return True

    def _handle_key_field(self, key):
        if key == pygame.K_RETURN:
            self._confirmer_champ()
        elif key == pygame.K_BACKSPACE:
            self._field_input = self._field_input[:-1]
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
                "[T] Tester  [Ctrl+R] reset compteur  [Ctrl+S/N/O] sauv/new/open  [Esc]")
        surf.blit(fontsm.render(aide, True, (140, 140, 140)),
                  (cadre.x + 16, cadre.y + 38))

        # Liste des étapes
        y = cadre.y + 70
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
        box = self._draw_popup_box(surf, 500, 480)
        surf.blit(font.render("Type d'étape :", True, (240, 200, 80)),
                  (box.x + 16, box.y + 12))
        y = box.y + 50
        for i, key in enumerate(self._type_keys):
            meta = TYPES_ETAPES[key]
            if i == self._type_index:
                pygame.draw.rect(surf, (60, 60, 90),
                                 (box.x + 8, y - 2, box.width - 16, 22))
            color = (255, 255, 255) if i == self._type_index else (200, 200, 220)
            surf.blit(font.render(f"{key:20s}  {meta['libelle']}", True, color),
                      (box.x + 16, y))
            y += 22

    def _draw_popup_field(self, surf, font, fontsm):
        box = self._draw_popup_box(surf, 700, 160)
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
        surf.blit(font.render(self._field_input + "_", True, (255, 255, 255)),
                  (box.x + 16, box.y + 74))
        # Indication du picker [P] si on est sur un champ x/y
        if nom in ("x", "y"):
            surf.blit(fontsm.render(
                "[P] = utiliser la position de la souris (monde)",
                True, (180, 180, 120)),
                (box.x + 16, box.y + 108))
            # Affiche les coordonnées MONDE en temps réel pour aider à viser.
            self._draw_coords_overlay(surf, font)
        surf.blit(fontsm.render("[Enter] valider | [Esc] annuler",
                                True, (140, 140, 140)),
                  (box.x + 16, box.y + 130))

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
