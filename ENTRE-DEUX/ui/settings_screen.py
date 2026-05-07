# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Écran Paramètres (depuis le menu Pause)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Une fenêtre "Paramètres" qui s'ouvre par-dessus le menu Pause quand
#  l'utilisateur choisit "Paramètres". Elle fait plusieurs sous-pages :
#
#     Page "main"       → liste des sections (Affichage, Compagnons, Aide...)
#     Page "affichage"  → bascule entre HUD permanent et HUD immersion
#     Page "compagnons" → règle le nombre de compagnons (Lueurs)
#     Page "aide_jeu"   → rappel des touches du jeu
#     Page "aide_edit"  → rappel détaillé des touches de l'éditeur
#
#  La gestion des entrées est totalement interne : game.py vérifie juste
#  `parametres.visible` et délègue les events. La méthode handle_key()
#  renvoie la chaîne "close" quand on a quitté définitivement (= il faut
#  revenir au menu Pause).
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  core/game.py crée l'instance :
#       self.parametres = SettingsScreen()
#       self.parametres.bind_compagnons(self.compagnons, self.player)
#       self.parametres.bind_editeur(self.editeur)   # ← après création éditeur
#  Puis dans la boucle :
#       if self.parametres.visible:
#           resultat = self.parametres.handle_key(event.key)
#           if resultat == "close": (revenir au menu Pause)
#       self.parametres.draw(screen)
#
#  RÈGLE PRODUIT IMPORTANTE :
#  --------------------------
#  La page "Compagnons" (couleur / taille / nombre des Lueurs) n'est
#  affichée QUE quand l'éditeur est ouvert (self._editeur.active = True).
#  En mode normal, le joueur n'a aucun contrôle direct là-dessus :
#  les Lueurs s'obtiennent au fil de l'aventure (récompenses de quêtes).
#  L'éditeur, lui, sert à tester librement les combinaisons.
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Ajouter une sous-page   → dans _options_courantes() + _activer()
#                                  + titres[] dans draw() + bloc if self.page
#     - Changer les contrôles   → constantes CONTROLES_JEU / CONTROLES_EDITEUR
#     - Changer les couleurs    → constantes C_* en haut
#     - Persister une option    → via systems.save_system (lire_config/ecrire_config)
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D1]  pygame.Surface       — panneau et voile semi-transparents
#     [D2]  SRCALPHA             — transparence du panneau
#     [D3]  blit                 — coller les éléments sur l'écran
#     [D22] Machine à états      — self.page ∈ {main, affichage, ...}
#     [D35] JSON                 — persistance via game_config.json
#
# ─────────────────────────────────────────────────────────────────────────────

import pygame
import settings
from systems.save_system import lire_config, ecrire_config


# ═════════════════════════════════════════════════════════════════════════════
#  1. CONTENU STATIQUE DES PAGES D'AIDE
# ═════════════════════════════════════════════════════════════════════════════
#
#  Listes de tuples (touche, description). Volontairement détaillées :
#  c'est le but du sous-menu d'aide (le panneau F1 reste léger pour le
#  jeu courant). Pour ajouter une touche, il suffit d'ajouter un tuple
#  dans la liste correspondante — le rendu s'adapte.

CONTROLES_JEU = [
    ("Q / D",            "Gauche / Droite"),
    ("Espace",           "Sauter (double-saut en l'air)"),
    ("Shift",            "Dash (cooldown ~0.5 s)"),
    ("F",                "Attaquer (S+F en l'air = attaque vers le bas)"),
    ("Contre un mur",    "Wall-slide → Espace = wall-jump"),
    ("Z / ↑",            "Regarder en haut (affiche les PV)"),
    ("E",                "Parler à un PNJ"),
    ("C",                "Rappeler / faire sortir les compagnons (cape)"),
    ("Tab",              "Inventaire"),
    ("F1",               "Panneau d'aide rapide"),
    ("Échap",            "Pause / Paramètres"),
]

CONTROLES_EDITEUR = [
    ("E",                  "Ouvrir / fermer l'éditeur"),
    ("M",                  "Changer de mode (cycle)"),
    ("Mode 0",             "Plateformes : clic-clic = rectangle, clic D = supprimer"),
    ("Mode 1",             "Ennemis : clic = poser, T = changer sprite, P = patrouille, D = détection"),
    ("Mode 2",             "Lumières : clic = poser, T = type, F = flicker"),
    ("Mode 3",             "Spawn joueur : clic = repositionner"),
    ("Mode 4",             "Trous : clic-clic = zone trou (chute)"),
    ("Mode 5",             "Murs custom : double clic G = poser"),
    ("Mode 6",             "Hitboxes : T = sprite (joueur ou monstre), clic-clic = rectangle"),
    ("Mode 7",             "Restaurer : sélectionner un point de sauvegarde"),
    ("Mode 8",             "Copier-coller : C = copier sélection, V = coller"),
    ("Mode 9",             "Décor : clic = poser sprite, T = changer, +/- = échelle"),
    ("Mode 10",            "PNJs : clic = poser, T = sprite"),
    ("Mode 11",            "Blocs (terrain auto)"),
    ("H",                  "Gestionnaire d'histoire (cartes)"),
    ("Ctrl + S",           "Sauvegarder la carte"),
    ("Ctrl + Z / Y",       "Annuler / Refaire"),
    ("Molette",            "Zoom avant/arrière"),
    ("Clic molette",       "Caméra libre (drag)"),
    ("Échap",              "Pause / Paramètres"),
]


# ═════════════════════════════════════════════════════════════════════════════
#  2. COULEURS & STYLE
# ═════════════════════════════════════════════════════════════════════════════
#
#  Centralisées ici pour pouvoir retoucher l'ambiance en un seul endroit.
#  Les noms C_* commencent tous par C (pour Couleur) afin qu'elles se
#  groupent automatiquement dans l'auto-complétion.

C_FOND     = (14,  10,  28, 235)   # fond panneau violet sombre presque opaque
C_BORD     = (110,  90, 200)       # bordure violette principale
C_BORD_INT = (50,   40,  90)       # bordure interne (effet "gravé")
C_ACCENT   = (255, 215,  70)       # accent doré (coins, sélection, barre)
C_TITRE    = (210, 190, 255)       # titre violet pâle
C_OPT      = (150, 135, 200)       # option non sélectionnée
C_OPT_SEL  = (255, 215,  70)       # option sélectionnée (doré)
C_KEY      = (180, 220, 255)       # nom de touche dans l'aide
C_DESC     = (220, 220, 220)       # description dans l'aide
C_HINT     = (130, 120, 170)       # petit texte en bas de page


# ═════════════════════════════════════════════════════════════════════════════
#  3. CONSTRUCTION
# ═════════════════════════════════════════════════════════════════════════════

class SettingsScreen:
    """Écran Paramètres avec sous-pages.

    Convention :
      - visible=False → on ne rend rien, on ignore les events.
      - handle_key() retourne "close" quand l'utilisateur a quitté le menu
        (et donc qu'on doit revenir au menu Pause)."""

    def __init__(self):
        # État général
        self.visible    = False
        self.page       = "main"     # page courante (voir [D22])
        self.selection  = 0          # index de l'option surlignée

        # Références injectées par bind_compagnons() ci-dessous.
        # On ne peut pas les passer au constructeur parce que le groupe
        # de compagnons n'existe pas encore à ce moment-là (ordre de
        # création dans Game.__init__).
        self._compagnons = None
        self._joueur     = None

        # Référence à l'éditeur (injectée par bind_editeur). Sert UNIQUEMENT
        # à savoir si on est en mode éditeur, pour afficher (ou non) la
        # page "Compagnons". Si None → on considère qu'on est en jeu normal.
        self._editeur    = None

        # Polices initialisées paresseusement (la première fois qu'on dessine)
        # — on ne peut pas charger une SysFont avant pygame.font.init().
        self._font_titre = None
        self._font_opt   = None
        self._font_key   = None
        self._font_hint  = None

    # ═════════════════════════════════════════════════════════════════════════
    #  4. BRANCHEMENT (injection des dépendances)
    # ═════════════════════════════════════════════════════════════════════════

    def bind_compagnons(self, group, joueur):
        """Donne accès au groupe de compagnons et au joueur.

        Nécessaire pour que la page "compagnons" puisse modifier le nombre
        en direct (et repositionner les compagnons autour du joueur)."""
        self._compagnons = group
        self._joueur     = joueur

    def bind_editeur(self, editeur):
        """Donne accès à l'éditeur (pour gating de la page Compagnons).

        On lit `editeur.active` à chaque rendu : pas besoin d'événement,
        l'utilisateur ne peut pas ouvrir l'éditeur ET le menu Paramètres
        en même temps en pratique, mais on reste robuste."""
        self._editeur = editeur

    def _en_mode_editeur(self):
        """True si l'éditeur est actuellement ouvert.

        Utilisé pour décider si la page "Compagnons" est accessible :
        en jeu normal, l'utilisateur n'a aucun contrôle direct là-dessus
        (les Lueurs s'obtiennent via la progression / les quêtes)."""
        return self._editeur is not None and getattr(self._editeur, "active", False)

    # ═════════════════════════════════════════════════════════════════════════
    #  5. OUVERTURE / FERMETURE
    # ═════════════════════════════════════════════════════════════════════════

    def open(self):
        """Ouvre l'écran Paramètres sur la page racine."""
        self.visible   = True
        self.page      = "main"
        self.selection = 0

    def close(self):
        """Ferme l'écran Paramètres (le retour au menu Pause est géré par game.py)."""
        self.visible = False

    # ═════════════════════════════════════════════════════════════════════════
    #  6. ENTRÉES CLAVIER
    # ═════════════════════════════════════════════════════════════════════════

    def handle_key(self, key):
        """Gère une touche. Renvoie "close" quand on a totalement quitté."""

        if not self.visible:
            return None

        # ── Échap : revenir d'une page, ou fermer si on est déjà sur main ────
        if key == pygame.K_ESCAPE:
            if self.page != "main":
                self.page      = "main"
                self.selection = 0
                return None
            self.close()
            return "close"

        options = self._options_courantes()
        nb      = len(options)

        # ── Navigation / validation ──────────────────────────────────────────
        if key == pygame.K_UP:
            # Modulo pour boucler de la première à la dernière option.
            self.selection = (self.selection - 1) % nb
        elif key == pygame.K_DOWN:
            self.selection = (self.selection + 1) % nb
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._activer(options[self.selection])
        elif key in (pygame.K_LEFT, pygame.K_RIGHT):
            # ←/→ : ajustement direct sur certaines pages.
            if self.page == "compagnons":
                delta = 1 if key == pygame.K_RIGHT else -1
                self._ajuster_option_compagnons(options[self.selection], delta)
            elif self.page == "av":
                delta = +0.05 if key == pygame.K_RIGHT else -0.05
                self._ajuster_slider(options[self.selection], delta)
        return None

    # ═════════════════════════════════════════════════════════════════════════
    #  7. OPTIONS DE LA PAGE COURANTE
    # ═════════════════════════════════════════════════════════════════════════
    #
    #  Pour ajouter une page : ajouter un `if self.page == "ma_page":` qui
    #  renvoie la liste de chaînes à afficher. Les pages d'aide n'ont qu'une
    #  option "Retour" — c'est le cas par défaut en bas.

    def _options_courantes(self):
        """Liste des options (= chaînes à afficher) pour la page courante."""

        if self.page == "main":
            # "Compagnons" n'apparaît qu'en mode éditeur — voir docstring
            # de la classe (RÈGLE PRODUIT). En jeu normal, le joueur ne
            # règle pas ses Lueurs : il les gagne au fil de l'aventure.
            entrees = ["Affichage", "Son & Image"]
            if self._en_mode_editeur():
                entrees.append("Compagnons")
            entrees += ["Aide — Jeu", "Aide — Mode éditeur", "Retour"]
            return entrees

        if self.page == "affichage":
            # On construit dynamiquement le libellé en fonction du mode actuel,
            # pour que la chaîne affichée reflète l'état courant.
            mode_actuel = settings.hud_mode
            if mode_actuel == "permanent":
                label_hud = "HUD : Permanent"
            else:
                label_hud = "HUD : Immersion"
            return [label_hud, "Retour"]

        if self.page == "av":
            # Page Son & Image : 3 sliders. Les chaînes sont affichées
            # avec un slider à droite par _dessiner_options (cf. SLIDER_*).
            return [
                f"SLIDER:Volume musique:{settings.volume_musique}:0.0:1.0",
                f"SLIDER:Volume effets:{settings.volume_sfx}:0.0:1.0",
                f"SLIDER:Luminosité:{settings.luminosite}:0.5:1.5",
                "Retour",
            ]

        if self.page == "compagnons":
            return self._options_compagnons()

        # Pages d'aide : une seule option pour revenir
        return ["Retour"]

    # ═════════════════════════════════════════════════════════════════════════
    #  8. ACTIVATION D'UNE OPTION (Entrée/Espace)
    # ═════════════════════════════════════════════════════════════════════════

    def _activer(self, option):
        """Exécute l'action associée à une option."""

        # ── "Retour" : toujours géré en premier (commun à toutes les pages) ──
        if option == "Retour":
            if self.page == "main":
                self.close()
            else:
                self.page      = "main"
                self.selection = 0
            return

        # ── Depuis la page principale : on change de page ────────────────────
        if self.page == "main":
            if option == "Affichage":
                self.page      = "affichage"
                self.selection = 0
            elif option == "Son & Image":
                self.page      = "av"
                self.selection = 0
            elif option == "Compagnons":
                self.page      = "compagnons"
                self.selection = 0
            elif option == "Aide — Jeu":
                self.page      = "aide_jeu"
                self.selection = 0
            elif option == "Aide — Mode éditeur":
                self.page      = "aide_edit"
                self.selection = 0
            return

        # ── Page Affichage : basculer HUD permanent / immersion ──────────────
        if self.page == "affichage" and option.startswith("HUD"):
            self._toggler_hud_mode()
            return

        # ── Page Compagnons : Entrée = avance d'un cran sur l'option ─────────
        # Pour "Nombre" → +1 (avec bouclage à 0 quand on dépasse le max).
        # Pour les options Luciole → cycle vers la valeur suivante (Entrée
        # se comporte comme la flèche droite — utile sur clavier sans flèches).
        if self.page == "compagnons":
            if option.startswith("Nombre"):
                self._ajuster_nb_compagnons(+1, wrap=True)
            else:
                self._ajuster_option_compagnons(option, +1)

    # ═════════════════════════════════════════════════════════════════════════
    #  9. ACTIONS (bascule HUD, ajustement nombre de compagnons)
    # ═════════════════════════════════════════════════════════════════════════

    def _toggler_hud_mode(self):
        """Bascule entre "permanent" et "immersion", puis sauvegarde."""

        if settings.hud_mode == "permanent":
            nouveau = "immersion"
        else:
            nouveau = "permanent"
        settings.hud_mode = nouveau

        # Persistance dans game_config.json [D35] : on lit la config,
        # on modifie la clé, on réécrit. save_system gère le chemin
        # et les erreurs (fichier manquant, JSON invalide…).
        cfg = lire_config()
        cfg["hud_mode"] = nouveau
        ecrire_config(cfg)

    # ── Page Compagnons : génération dynamique des options ──────────────────
    #
    #  La liste affichée est :
    #      "Nombre : N / Max"
    #      pour chaque luciole active i :
    #          "Luciole i+1 — Couleur : NomCouleur"
    #          "Luciole i+1 — Taille  : NomTaille"
    #      "Retour"
    #
    #  ←/→ fait défiler la valeur sous le curseur (couleur ou taille ou nb).
    #  Entrée fait défiler aussi (alternative pour les ergonomies sans flèches).
    #  Voir _activer() et handle_key() pour le cycling.

    def _options_compagnons(self):
        """Construit la liste d'options de la page Compagnons."""
        if self._compagnons:
            nb = len(self._compagnons.compagnons)
        else:
            nb = 0
        nb_max = settings.COMPAGNON_NB_MAX

        options = [f"Nombre : {nb} / {nb_max}   (← / →)"]

        # Pour chaque luciole active, on ajoute 3 lignes éditables :
        # couleur, taille et intensité (puissance d'éclairage).
        for i in range(nb):
            nom_couleur   = self._libelle_couleur(i)
            nom_taille    = self._libelle_taille(i)
            nom_intensite = self._libelle_intensite(i)
            options.append(f"Luciole {i + 1}  —  Couleur   : {nom_couleur}")
            options.append(f"Luciole {i + 1}  —  Taille    : {nom_taille}")
            options.append(f"Luciole {i + 1}  —  Intensité : {nom_intensite}")

        options.append("Retour")
        return options

    def _libelle_couleur(self, idx_luciole):
        """Nom affichable de la couleur actuellement choisie pour la luciole idx."""
        try:
            i_choix = settings.lucioles_couleurs_idx[idx_luciole]
            nom, _ = settings.LUCIOLE_PALETTE[i_choix]
            return nom
        except (AttributeError, IndexError, TypeError):
            return "?"

    def _libelle_taille(self, idx_luciole):
        """Nom affichable de la taille actuellement choisie pour la luciole idx."""
        try:
            i_choix = settings.lucioles_tailles_idx[idx_luciole]
            nom, _ = settings.LUCIOLE_TAILLES[i_choix]
            return nom
        except (AttributeError, IndexError, TypeError):
            return "?"

    def _libelle_intensite(self, idx_luciole):
        """Nom affichable de l'intensité actuellement choisie pour la luciole idx."""
        try:
            i_choix = settings.lucioles_intensites_idx[idx_luciole]
            nom, _ = settings.LUCIOLE_INTENSITES[i_choix]
            return nom
        except (AttributeError, IndexError, TypeError):
            return "?"

    def _cycler_couleur_luciole(self, idx_luciole, delta):
        """Avance/recule l'index de couleur de la luciole idx, et persiste."""
        n_couleurs = len(settings.LUCIOLE_PALETTE)
        if n_couleurs == 0:
            return
        # Modulo Python gère bien les négatifs (-1 % 7 = 6) → cycling propre.
        ancien = settings.lucioles_couleurs_idx[idx_luciole]
        nouveau = (ancien + delta) % n_couleurs
        settings.lucioles_couleurs_idx[idx_luciole] = nouveau

        # Persistance dans game_config.json [D35].
        cfg = lire_config()
        cfg["lucioles_couleurs_idx"] = list(settings.lucioles_couleurs_idx)
        ecrire_config(cfg)

    def _cycler_taille_luciole(self, idx_luciole, delta):
        """Avance/recule l'index de taille de la luciole idx, et persiste."""
        n_tailles = len(settings.LUCIOLE_TAILLES)
        if n_tailles == 0:
            return
        ancien = settings.lucioles_tailles_idx[idx_luciole]
        nouveau = (ancien + delta) % n_tailles
        settings.lucioles_tailles_idx[idx_luciole] = nouveau

        cfg = lire_config()
        cfg["lucioles_tailles_idx"] = list(settings.lucioles_tailles_idx)
        ecrire_config(cfg)

    def _cycler_intensite_luciole(self, idx_luciole, delta):
        """Avance/recule l'index d'intensité de la luciole idx, et persiste.

        Même schéma que pour couleur/taille : modulo pour cycler proprement,
        écriture immédiate dans game_config.json [D35] pour que le réglage
        survive au redémarrage du jeu."""
        n_intens = len(settings.LUCIOLE_INTENSITES)
        if n_intens == 0:
            return
        ancien = settings.lucioles_intensites_idx[idx_luciole]
        nouveau = (ancien + delta) % n_intens
        settings.lucioles_intensites_idx[idx_luciole] = nouveau

        cfg = lire_config()
        cfg["lucioles_intensites_idx"] = list(settings.lucioles_intensites_idx)
        ecrire_config(cfg)

    # ─── Sliders Son & Image ───────────────────────────────────────────────

    def _ajuster_slider(self, option_str, delta):
        """Ajuste un slider de la page Son & Image.

        L'option_str a la forme "SLIDER:nom:valeur:min:max". On parse, on
        clamp, on applique en runtime (settings module + pygame.mixer),
        et on persiste dans game_config.json pour que le réglage survive
        à un redémarrage.
        """
        if not option_str.startswith("SLIDER:"):
            return
        parts = option_str.split(":")
        if len(parts) < 5:
            return
        nom    = parts[1]
        try:
            valeur = float(parts[2])
            vmin   = float(parts[3])
            vmax   = float(parts[4])
        except ValueError:
            return

        valeur = max(vmin, min(vmax, valeur + delta))
        # Snap au pas de 0.05 pour éviter les valeurs floues type 0.34999
        valeur = round(valeur * 20) / 20

        # ── Application + persistance ──────────────────────────────────
        cfg = lire_config()
        if nom == "Volume musique":
            settings.volume_musique = valeur
            cfg["volume_musique"]   = valeur
            try:
                pygame.mixer.music.set_volume(valeur)
            except Exception:
                pass
        elif nom == "Volume effets":
            settings.volume_sfx     = valeur
            cfg["volume_sfx"]       = valeur
        elif nom == "Luminosité":
            settings.luminosite     = valeur
            cfg["luminosite"]       = valeur
        ecrire_config(cfg)

    def _ajuster_option_compagnons(self, option, delta):
        """Aiguillage : selon l'intitulé de l'option, on cycle la bonne valeur.

        delta = +1 (suivant) ou -1 (précédent).

        On reconnaît l'option à partir de son texte affiché. C'est moins
        élégant qu'un identifiant abstrait, mais ça suit la convention déjà
        utilisée pour "Nombre" / "Retour" / "HUD" dans cette classe."""

        if option.startswith("Nombre"):
            self._ajuster_nb_compagnons(delta)
            return

        # Format attendu : "Luciole N  —  Couleur : ..." ou "... Taille : ..."
        if not option.startswith("Luciole"):
            return

        # On extrait N (numéro 1-based) entre "Luciole " et le double espace.
        # Exemple : "Luciole 3  —  Couleur : Bleu glacé" → idx_luciole = 2
        try:
            apres_mot = option.split("Luciole", 1)[1].strip()
            num_str   = apres_mot.split()[0]    # premier mot = "3"
            idx_luciole = int(num_str) - 1
        except (IndexError, ValueError):
            return

        if "Couleur" in option:
            self._cycler_couleur_luciole(idx_luciole, delta)
        elif "Taille" in option:
            self._cycler_taille_luciole(idx_luciole, delta)
        elif "Intensité" in option:
            self._cycler_intensite_luciole(idx_luciole, delta)

    def _ajuster_nb_compagnons(self, delta, wrap=False):
        """Ajoute/retire un compagnon, met à jour le groupe et persiste.

        delta = +1 ou -1 (flèches) ; wrap=True fait boucler à 0 au max
        (quand on appuie sur Entrée)."""

        if self._compagnons is None:
            return

        actuel  = len(self._compagnons.compagnons)
        nb_max  = settings.COMPAGNON_NB_MAX
        nouveau = actuel + delta

        # Si on appuie sur Entrée au max → on revient à 0 (bouclage)
        if wrap and nouveau > nb_max:
            nouveau = 0
        # Sinon on clampe simplement dans [0, nb_max]
        nouveau = max(0, min(nouveau, nb_max))

        # Si rien ne change, inutile de re-persister ni de respawn.
        if nouveau == actuel:
            return

        self._compagnons.set_nb(nouveau)
        # Recolle les nouveaux à côté du joueur (sinon ils apparaissent
        # à la position 0,0 créée par le constructeur par défaut).
        if self._joueur is not None:
            self._compagnons.respawn(self._joueur)

        cfg = lire_config()
        cfg["nb_compagnons"] = nouveau
        ecrire_config(cfg)

    # ═════════════════════════════════════════════════════════════════════════
    #  10. RENDU — aiguillage principal
    # ═════════════════════════════════════════════════════════════════════════

    def draw(self, screen):
        """Dessine tout l'écran Paramètres si visible."""

        if not self.visible:
            return
        self._init_polices()

        # ── Dimensions du panneau (adaptatif à la taille d'écran) ────────────
        w, h = screen.get_size()
        panel_w = min(720, w - 60)
        panel_h = min(560, h - 60)
        px      = (w - panel_w) // 2
        py      = (h - panel_h) // 2

        # ── Voile assombrissant légèrement violacé ───────────────────────────
        voile = pygame.Surface((w, h), pygame.SRCALPHA)
        voile.fill((10, 6, 22, 140))
        screen.blit(voile, (0, 0))

        # ── Fond du panneau + double bordure violette + coins dorés ──────────
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill(C_FOND)
        screen.blit(panel, (px, py))

        # Double bordure (style "gravé")
        pygame.draw.rect(screen, C_BORD, (px, py, panel_w, panel_h), 1)
        pygame.draw.rect(screen, C_BORD_INT,
                         (px + 3, py + 3, panel_w - 6, panel_h - 6), 1)
        # Coins dorés (4 angles, équerres en L)
        c = 14
        for (ax, ay, dx, dy) in (
                (px,           py,            +1, +1),
                (px + panel_w, py,            -1, +1),
                (px,           py + panel_h,  +1, -1),
                (px + panel_w, py + panel_h,  -1, -1)):
            pygame.draw.line(screen, C_ACCENT,
                             (ax, ay), (ax + dx * c, ay), 2)
            pygame.draw.line(screen, C_ACCENT,
                             (ax, ay), (ax, ay + dy * c), 2)

        # ── Titre selon la page (dictionnaire page → titre) ──────────────────
        titres = {
            "main":       "PARAMÈTRES",
            "affichage":  "AFFICHAGE",
            "av":         "SON & IMAGE",
            "compagnons": "COMPAGNONS",
            "aide_jeu":   "AIDE — COMMANDES DU JEU",
            "aide_edit":  "AIDE — MODE ÉDITEUR",
        }
        titre_surf = self._font_titre.render(titres.get(self.page, "?"), True, C_TITRE)
        tx = px + (panel_w - titre_surf.get_width()) // 2
        ty = py + 18
        screen.blit(titre_surf, (tx, ty))

        # Séparateur dégradé sous le titre (cohérent avec menu pause)
        import math
        sep_y = ty + titre_surf.get_height() + 8
        for i in range(60):
            t1 = i / 60
            ox = int(px + 25 + (panel_w - 50) * t1)
            w_seg = max(1, int((panel_w - 50) / 60))
            opacite = int(180 * math.sin(t1 * math.pi))
            tmp = pygame.Surface((w_seg, 1), pygame.SRCALPHA)
            tmp.fill((130, 100, 220, opacite))
            screen.blit(tmp, (ox, sep_y))

        # ── Contenu : aiguillage selon la page ───────────────────────────────
        zone_y = py + 80
        if self.page in ("main", "affichage", "av"):
            self._dessiner_options(screen, px, zone_y, panel_w)
        elif self.page == "compagnons":
            self._dessiner_compagnons(screen, px, zone_y, panel_w)
        else:
            # Pages d'aide : on liste les contrôles, puis le bouton "Retour"
            # tout en bas du panneau.
            if self.page == "aide_jeu":
                controles = CONTROLES_JEU
            else:
                controles = CONTROLES_EDITEUR
            self._dessiner_aide(screen, px, zone_y, panel_w, panel_h, controles)
            self._dessiner_options(screen, px, py + panel_h - 60, panel_w)

        # ── Hint de navigation en bas du panneau ─────────────────────────────
        hint = self._font_hint.render(
            "↑↓ Naviguer    ←→ Ajuster    Entrée Valider    Échap Retour",
            True, C_HINT)
        screen.blit(hint, (px + (panel_w - hint.get_width()) // 2, py + panel_h - 28))

    # ═════════════════════════════════════════════════════════════════════════
    #  11. RENDU — pièces détachées
    # ═════════════════════════════════════════════════════════════════════════

    def _dessiner_options(self, screen, px, y, panel_w, line_height=34):
        """Dessine la liste des options centrées dans le panneau.

        L'option sélectionnée est en doré et précédée de ">".
        Les options qui commencent par "SLIDER:" sont rendues comme un
        slider horizontal (cf. _dessiner_slider) au lieu d'un simple texte.
        """

        options = self._options_courantes()
        for i, opt in enumerate(options):
            couleur = C_OPT_SEL if i == self.selection else C_OPT
            ligne_y = y + i * line_height

            # Slider ?
            if opt.startswith("SLIDER:"):
                self._dessiner_slider(screen, px, ligne_y, panel_w, opt, couleur,
                                      selectionne=(i == self.selection))
                continue

            # Option texte normale
            surf = self._font_opt.render(opt, True, couleur)
            ox   = px + (panel_w - surf.get_width()) // 2
            screen.blit(surf, (ox, ligne_y))
            if i == self.selection:
                ind = self._font_opt.render(">", True, couleur)
                screen.blit(ind, (ox - ind.get_width() - 8, ligne_y))

    def _dessiner_slider(self, screen, px, y, panel_w, option_str,
                          couleur, selectionne):
        """Dessine un slider horizontal pour une option "SLIDER:nom:val:min:max".

        Layout (centré dans le panneau) :
            [Nom : XX%]            [────●────]

        - Le nom + pourcentage est à gauche
        - Une barre de 220 px à droite avec une "boule" à la position courante
        """
        parts  = option_str.split(":")
        nom    = parts[1]
        try:
            valeur = float(parts[2]); vmin = float(parts[3]); vmax = float(parts[4])
        except (ValueError, IndexError):
            return

        # Texte (nom + pourcentage)
        pct = int(round((valeur - vmin) / (vmax - vmin) * 100))
        label = self._font_opt.render(f"{nom} : {pct}%", True, couleur)

        bar_w  = 220
        bar_h  = 6
        gap    = 24
        bloc_w = label.get_width() + gap + bar_w
        ox     = px + (panel_w - bloc_w) // 2

        screen.blit(label, (ox, y))

        # Barre de fond
        bar_x = ox + label.get_width() + gap
        bar_y = y + (label.get_height() - bar_h) // 2
        pygame.draw.rect(screen, (60, 50, 90), (bar_x, bar_y, bar_w, bar_h),
                         border_radius=3)

        # Barre remplie (jusqu'à la position courante)
        ratio    = max(0.0, min(1.0, (valeur - vmin) / max(1e-6, (vmax - vmin))))
        fill_w   = int(bar_w * ratio)
        fill_col = C_OPT_SEL if selectionne else C_OPT
        pygame.draw.rect(screen, fill_col, (bar_x, bar_y, fill_w, bar_h),
                         border_radius=3)

        # Boule (knob)
        knob_x = bar_x + fill_w
        knob_y = bar_y + bar_h // 2
        pygame.draw.circle(screen, fill_col, (knob_x, knob_y), 8)

        # Indicateur ">" si sélectionné
        if selectionne:
            ind = self._font_opt.render(">", True, couleur)
            screen.blit(ind, (ox - ind.get_width() - 8, y))

    def _dessiner_compagnons(self, screen, px, y, panel_w):
        """Petit texte d'explication + options de la page compagnons.

        Avec jusqu'à 5 lucioles, on a 1 + 2×5 + 1 = 12 options. Pour que ça
        tienne dans le panneau standard (560 px), on rétrécit l'explication
        à 1 ligne et on serre la hauteur de ligne à 28 px (au lieu de 34)."""

        # Une seule ligne d'explication pour gagner de la place — les
        # détails (touche C, peur) sont rappelés dans la page d'aide F1.
        explication = "Tes Lueurs apaisent la peur. Personnalise leur couleur et leur taille ci-dessous."
        s = self._font_hint.render(explication, True, C_DESC)
        screen.blit(s, (px + (panel_w - s.get_width()) // 2, y))
        y += s.get_height() + 12

        # Espacement réduit à 28 px pour que les 12 options tiennent.
        self._dessiner_options(screen, px, y, panel_w, line_height=28)

    def _dessiner_aide(self, screen, px, y, panel_w, panel_h, controles):
        """Dessine la liste "touche → description" pour les pages d'aide.

        Deux colonnes : le nom de la touche à gauche (bleuté), la description
        à droite (blanc cassé). L'espacement est calé pour tenir dans le
        panneau standard."""

        for touche, desc in controles:
            t = self._font_key.render(touche, True, C_KEY)
            d = self._font_hint.render(desc, True, C_DESC)
            screen.blit(t, (px + 30, y))
            screen.blit(d, (px + 220, y))
            y += t.get_height() + 4

    # ═════════════════════════════════════════════════════════════════════════
    #  12. INITIALISATION PARESSEUSE DES POLICES
    # ═════════════════════════════════════════════════════════════════════════

    def _init_polices(self):
        """Charge les polices la première fois qu'on dessine le menu.

        On ne peut pas charger une SysFont tant que pygame.font.init()
        n'est pas passé, d'où l'initialisation différée."""

        if self._font_titre is None:
            self._font_titre = pygame.font.SysFont("Georgia",  32, bold=True)
            self._font_opt   = pygame.font.SysFont("Consolas", 22)
            self._font_key   = pygame.font.SysFont("Consolas", 14, bold=True)
            self._font_hint  = pygame.font.SysFont("Consolas", 14)
