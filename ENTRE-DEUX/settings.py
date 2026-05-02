# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Constantes globales du jeu
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  C'est LE fichier de réglages du jeu. Toutes les valeurs « qu'on peut
#  avoir envie de changer » (vitesse du joueur, PV max, couleur du fond,
#  volume de la musique...) sont ici. Tous les autres fichiers font
#  `import settings` et lisent ces valeurs.
#
#  RÈGLE D'OR :
#  ------------
#  Si tu veux changer le comportement du jeu, REGARDE D'ABORD ICI.
#  Dans 90% des cas, la valeur que tu cherches est dans ce fichier.
#
#  POURQUOI REGROUPER ICI ?
#  ------------------------
#  - Pour éviter d'avoir à fouiller dans 20 fichiers.
#  - Pour éviter les imports circulaires (settings n'importe rien).
#  - Pour qu'un autre élève puisse ajuster un paramètre sans avoir à
#    comprendre tout le code qui l'utilise.
#
#  SOMMAIRE (utilise Ctrl+F sur "──" pour sauter de section en section) :
#       1. Fenêtre & affichage           (ligne ~45)
#       2. Couleurs                      (ligne ~60)
#       3. Monde (scène, sol, plafond)   (ligne ~75)
#       4. Physique du joueur            (ligne ~90)
#       5. Combat                        (ligne ~105)
#      5b. Capacités (dash, wall-jump)   (ligne ~135)
#      5c. Compagnons                    (ligne ~155)
#       6. Caméra                        (ligne ~175)
#       7. Éclairage / ambiance          (ligne ~185)
#       8. Audio                         (ligne ~195)
#       9. Manette PS5 (mapping)         (ligne ~210)
#      10. État runtime                  (ligne ~245)
#
#  POUR SAVOIR OÙ MODIFIER QUOI : voir docs/OU_EST_QUOI.md
#  POUR COMPRENDRE UN CONCEPT   : voir docs/DICTIONNAIRE.md
#
# ─────────────────────────────────────────────────────────────────────────────


# ═════════════════════════════════════════════════════════════════════════════
# 1. FENÊTRE & AFFICHAGE
# ═════════════════════════════════════════════════════════════════════════════
#
#  WIDTH × HEIGHT = taille de la fenêtre du jeu (en pixels).
#  FPS            = nombre d'images par seconde qu'on vise. Voir [D10] dans
#                   le dictionnaire pour comprendre le rôle de `dt`.

WIDTH       = 1520            # largeur de la fenêtre (px)
HEIGHT      = 745             # hauteur de la fenêtre (px)
FPS         = 80              # images par seconde visées
TITLE       = "LIMINAL"       # texte dans la barre de titre de la fenêtre


# ═════════════════════════════════════════════════════════════════════════════
# 1b. CHEMINS DES DOSSIERS (répertoires d'assets)
# ═════════════════════════════════════════════════════════════════════════════
#
#  On calcule les chemins depuis l'emplacement de CE fichier (settings.py
#  est à la racine du projet). Comme ça le jeu marche peu importe d'où on
#  le lance (depuis VS Code, depuis le terminal, depuis un .bat…).
#
#  Règle : tous les autres fichiers utilisent ces constantes. Pas de
#  chemin "assets/images/..." écrit en dur ailleurs → si on réorganise,
#  on change UNE ligne ici.

import os as _os
_BASE_DIR = _os.path.dirname(_os.path.abspath(__file__))

# Dossier unique pour tous les décors (sprites manuels comme
# buisson-1.png ET PNG générés par l'import Tiled comme tiled_*.png).
# Avant, il y avait 2 dossiers (decor/ et decors/) ce qui provoquait des
# "décors disparaissent au reload" à cause de la confusion.
DECORS_DIR  = _os.path.join(_BASE_DIR, "assets", "images", "decor")
MAPS_DIR    = _os.path.join(_BASE_DIR, "maps")
TILED_DIR   = _os.path.join(_BASE_DIR, "tiled")


# ═════════════════════════════════════════════════════════════════════════════
# 2. COULEURS
# ═════════════════════════════════════════════════════════════════════════════
#
#  Chaque couleur est un triplet (R, G, B) où chaque composante va de 0 à 255.
#  Règle : on définit les couleurs ICI et on les réutilise partout → si un
#  jour on veut changer la charte graphique, on modifie une seule ligne.

BLEU        = ( 98, 143, 217)  # bleu clair  — joueur, UI
BLEU_NUIT   = ( 30,  30,  40)  # bleu très sombre — fond
ROUGE       = (217, 108,  98)  # rouge doux  — dégâts, ennemis
GRIS        = (178, 171, 184)  # gris violacé — décor secondaire
VIOLET      = ( 0,  0,  0)  # violet foncé — ambiance
BLANC       = (255, 255, 255)  # blanc pur   — compagnons, texte
NOIR        = (  0,   0,   0)  # noir pur    — voile, contours


# ═════════════════════════════════════════════════════════════════════════════
# 3. MONDE (taille d'une scène, sol, plafond)
# ═════════════════════════════════════════════════════════════════════════════
#
#  Une « scène » est un écran de jeu. Elle peut être plus grande que la
#  fenêtre : la caméra suit alors le joueur à l'intérieur. Voir [D20].

SCENE_WIDTH  = 2400           # X du bord DROIT du monde (≈ 3 écrans de large)
SCENE_LEFT   = 0              # X du bord GAUCHE du monde (négatif = monde étendu à gauche)
SCENE_HEIGHT = 4000           # hauteur d'une scène (≈ 2 écrans de haut)

GROUND_Y     = 590            # Y du sol par défaut (plus Y est grand = plus bas)
CEILING_Y    = 0              # Y du plafond par défaut


# ═════════════════════════════════════════════════════════════════════════════
# 4. PHYSIQUE DU JOUEUR
# ═════════════════════════════════════════════════════════════════════════════
#
#  Toutes les valeurs sont « par seconde » ou « par seconde² » — elles sont
#  donc multipliées par dt dans le code ([D10]).
#
#  Exemple concret : `self.x += PLAYER_SPEED * dt` → avance de 300 px en 1 s.

GRAVITY       = 1500          # accélération verticale (px/s²)
JUMP_POWER    = 700           # impulsion de saut (px/s, vers le haut)
PLAYER_SPEED  = 220           # vitesse horizontale de course (px/s)
PLAYER_RUN_SPEED = 370        # vitesse horizontale courir (px/s)

PLAYER_W      = 90            # largeur de la hitbox du joueur (px)
PLAYER_H      = 104           # hauteur de la hitbox du joueur (px)
PLAYER_SPAWN  = (100, 400)    # position (x, y) de spawn par défaut
# Échelle du joueur (hitbox + sprite). 1.0 = taille de base ; 0.5 = deux
# fois plus petit ; 2.0 = deux fois plus grand. Modifiable par carte via
# [Ctrl+U] dans l'éditeur, et sauvegardé dans le JSON de la map.
PLAYER_SCALE  = 1.0
jump = 0

# ═════════════════════════════════════════════════════════════════════════════
# 5. COMBAT
# ═════════════════════════════════════════════════════════════════════════════
#
#  Combat au corps-à-corps type Hollow Knight : le joueur swingue vers
#  l'avant, le haut ou le bas. Les hitbox sont des rectangles ([D4])
#  créés pendant la durée de l'attaque.

# Attaque face (gauche ou droite)
ATTACK_DURATION       = 0.61   # durée d'une attaque (s)
ATTACK_RECT_W         = 120    # largeur de la hitbox d'attaque (px)
ATTACK_RECT_H         = 40    # hauteur de la hitbox d'attaque (px)

# Attaque vers le bas (en l'air → rebond si elle touche = "pogo")
ATTACK_DOWN_W         = 60
ATTACK_DOWN_H         = 50
POGO_BOUNCE_VY        = -550  # impulsion verticale après un pogo réussi

# Points de vie et invincibilité
PLAYER_MAX_HP         = 5     # PV max du joueur
INVINCIBLE_DURATION   = 1.0   # invincibilité après dégât (s)
HP_DISPLAY_DURATION   = 2.0   # durée d'affichage des cœurs au-dessus du joueur

# Knockback (recul quand on prend / donne un coup)
KNOCKBACK_PLAYER      = 300   # vitesse de recul du joueur
KNOCKBACK_ENEMY       = 200   # vitesse de recul de l'ennemi
KNOCKBACK_DECAY       = 0.85  # freinage appliqué chaque frame (× 0.85)

# Régénération passive : si le joueur reste immobile au sol, il récupère
# progressivement des PV. Le moindre mouvement remet les compteurs à zéro.
REGEN_DELAY           = 1.5   # temps immobile avant le 1er PV récupéré (s)
REGEN_INTERVAL        = 1.0   # intervalle entre deux PV récupérés (s)


# ═════════════════════════════════════════════════════════════════════════════
# 5b. CAPACITÉS "HOLLOW KNIGHT"
# ═════════════════════════════════════════════════════════════════════════════

# ── Dash (touche Shift / L1) ────────────────────────────────────────────────
#  Impulsion horizontale rapide, ignore la gravité pendant sa durée.
#  DASH_DURATION calé pour que les 17-20 frames de slide / back dodge aient
#  le temps de défiler entièrement (sinon la moitié n'est jamais visible).
DASH_SPEED            = 500   # vitesse pendant le dash (px/s)
DASH_DURATION         = 0.50  # durée du dash (s) - assez long pour voir l'anim
DASH_COOLDOWN         = 0.65  # délai avant de pouvoir re-dash (s)

# ── Back dodge ──────────────────────────────────────────────────────────────
#  Après un back dodge (Shift + direction opposée au regard), on verrouille
#  la direction face pendant BACK_DODGE_LOCK secondes : le perso continue
#  de regarder l'ennemi meme si le joueur maintient la touche opposée.
#  Le joueur doit RELACHER puis ré-appuyer pour vraiment se retourner.
#  IMPORTANT : pendant le dash lui-même, la direction ne change déjà jamais
#  (vx imposé). Donc le lock UTILE = BACK_DODGE_LOCK - DASH_DURATION.
#  Avec 0.55s on a juste ~50 ms de grâce après la fin du dash : le temps
#  de relâcher la touche, sans voir le perso "marcher en arrière".
BACK_DODGE_LOCK       = 0.55  # durée (s) pendant laquelle le regard reste figé

#  Fenêtre de TOLÉRANCE pour déclencher le back dodge :
#  pas besoin d'appuyer pile en même temps sur "direction opposée" + Shift.
#  Si tu as appuyé sur la direction opposée dans les BACK_DODGE_INPUT_WINDOW
#  secondes qui PRÉCÈDENT le Shift, c'est compté comme back dodge.
#  → augmente la valeur si tu trouves ça encore dur (max conseillé 0.4)
BACK_DODGE_INPUT_WINDOW = 0.25

#  Durée + vitesse PROPRE au back dodge (≠ dash avant).
#  L'anim de back dodge a 20 frames (recoil + touche la tête + se relève).
#  À DASH_DURATION=0.5s on ne voyait que la moitié de l'anim.
#  → On la rallonge à 1.25s pour 5 frames moteur par image (≈ aerial dash).
#  Le perso recule moins vite (BACK_DODGE_SPEED réduit) pour que la
#  distance totale parcourue reste comparable à un dash avant.
BACK_DODGE_DURATION   = 0.75  # durée totale (anim complète)
BACK_DODGE_SPEED      = 220   # vitesse pendant le recul (px/s)

#  Phase de mouvement vs phase de récupération.
#  Le sprite de back dodge a 20 frames :
#    - frames 1→13 : recoil (le perso recule réellement)
#    - frames 14→20 : recovery (la perso se relève / touche la tête, IMMOBILE)
#  Pendant la phase de récupération, on ANNULE la vitesse physique : le
#  rect ne bouge plus, seul le sprite continue à animer la pose finale.
#  → 13/20 = 0.65
BACK_DODGE_MOVE_FRACTION = 0.65

# ── Double-saut ─────────────────────────────────────────────────────────────
#  Un 2e saut autorisé en l'air. Légèrement plus faible que le 1er.
DOUBLE_JUMP_POWER     = 540   # impulsion du 2e saut (px/s)
COYOTE_TIME           = 0.10  # tolérance après avoir quitté le sol (s)  [D23]
JUMP_BUFFER           = 0.12  # tolérance avant l'atterrissage (s)       [D23]

# ── Wall-slide / wall-jump ──────────────────────────────────────────────────
#  Quand le joueur est collé à un mur en l'air : il glisse lentement.
#  Un saut à ce moment le propulse dans l'autre sens.
WALL_SLIDE_SPEED      = 120   # vitesse de chute max contre un mur (px/s)

#  WALL JUMP — physique type Hollow Knight
#  Le perso bondit du mur avec la PUISSANCE d'un saut normal (VY=-700 =
#  JUMP_POWER) et un push horizontal qui donne un angle de ~34° depuis la
#  verticale (atan(480/700) ≈ 34°). Ça l'éloigne franchement du mur tout
#  en lui faisant gagner de la hauteur.
WALL_JUMP_VX          = 480   # impulsion horizontale au wall-jump (push)
WALL_JUMP_VY          = -780  # impulsion verticale au wall-jump (légèrement
                              # > JUMP_POWER pour un peu plus de hauteur :
                              # peak ~0.52s, max height 203px vs 163 saut normal)
WALL_JUMP_LOCK        = 0.18  # durée pendant laquelle l'input vers le mur est ignoré

#  WALL_JUMP_PUSH : durée pendant laquelle on PRÉSERVE le vx du wall jump
#  (sinon l'étape 4 le remplace immédiatement par ax*speed et la poussée
#  est perdue → le perso reste collé au mur). Pendant cette fenêtre, vx
#  est forcé à WALL_JUMP_VX dans la direction opposée au mur, peu importe
#  l'input du joueur.
WALL_JUMP_PUSH        = 0.25  # durée (s) de la phase de push horizontal

#  WALL_JUMP_WINDUP : phase de "préparation" avant le décollage.
#  L'anim wall jump (3 frames) montre le perso qui se ramasse / s'appuie
#  contre le mur AVANT de bondir. Pendant cette durée, la physique du
#  saut N'EST PAS encore appliquée — le perso reste collé au mur, immobile.
#  À la fin du wind-up, on applique vx + vy + on entre en phase WALL_JUMP_PUSH.
#  → calé sur la durée de l'anim (3 frames × img_dur=6 / 80 fps = 0.225s)
WALL_JUMP_WINDUP      = 0.225


# ═════════════════════════════════════════════════════════════════════════════
# 5c. COMPAGNONS (blobs blancs qui suivent le joueur)
# ═════════════════════════════════════════════════════════════════════════════
#
#  Règles du jeu :
#    - Touche C → tous dans la cape → la peur baisse VITE.
#    - Compagnon proche du joueur → la peur baisse DOUCEMENT.
#    - Compagnon trop loin → la peur MONTE.
#
#  Code associé :
#    - Le « corps » d'un compagnon       : entities/compagnon.py
#    - La gestion du groupe entier       : systems/compagnons.py
#    - Le déclenchement de la touche C   : core/event_handler.py

COMPAGNON_NB_MAX           = 5      # nombre maximum (menu Paramètres)
COMPAGNON_VITESSE_MARCHE   = 140    # px/s en mode "follow"
COMPAGNON_VITESSE_COURSE   = 280    # px/s quand il est trop loin
COMPAGNON_DIST_RAPPROCHE   = 60     # < cette distance → freine (évite de coller)
COMPAGNON_DIST_COURSE      = 200    # > cette distance → passe en mode course
COMPAGNON_DIST_RASSURANT   = 260    # zone "rassurante" autour du joueur

PEUR_VITESSE_BAISSE_CAPE   = 14     # peur baisse / s quand tous dans la cape
PEUR_VITESSE_BAISSE_PROCHE = 6      # peur baisse / s par compagnon proche
PEUR_VITESSE_HAUSSE_LOIN   = 8      # peur monte  / s par compagnon trop loin


# ─────────────────────────────────────────────────────────────────────────────
#  ZONES DE PEUR (FearZoneTrigger) — règles de ralentissement
# ─────────────────────────────────────────────────────────────────────────────
#
#  Quand le joueur entre dans une zone de peur ET que son stade > peur_max
#  exigée par la zone, on RALENTIT sa vitesse. Règle :
#
#       multiplicateur = max(MIN, 1.0 - REDUCTION_PAR_STADE × (stade - peur_max))
#
#  Exemples avec les défauts (MIN = 0.08 et REDUCTION = 0.22) :
#     - +1 stade au-dessus → 1.0 - 0.22 = 0.78 (sensiblement plus lent)
#     - +2 stades          → 0.56
#     - +3 stades          → 0.34
#     - +4 stades          → 0.12
#     - +5 stades          → 0.08  (plancher atteint, on rampe)
#
#  POURQUOI UN PLANCHER (et pas zéro) ?
#  ------------------------------------
#  À 8 % de vitesse on bouge encore d'environ 16 px/s — assez pour
#  pouvoir reculer si on s'est trop avancé. Combiné au RALENTISSEMENT
#  PROGRESSIF (cf. world/triggers.py facteur_vitesse_progressif), dès
#  qu'on s'éloigne du mur on récupère de la vitesse, donc le demi-tour
#  reste toujours possible. Mais collé au mur, c'est un calvaire — c'est
#  exactement ce qu'on veut pour faire comprendre "tu ne dois pas être là".
#
#  POURQUOI 0.08 ET 0.22 ?
#  -----------------------
#  Réglages calibrés pour que :
#     - Stade 5 vs peur_max 0 : on rampe vraiment près du mur (8%).
#     - Stade 2 vs peur_max 0 : ralentissement marqué (56%) mais jouable.
#     - Stade 1 vs peur_max 0 : léger handicap (78%) — la zone se
#       remarque sans être pénible.
#  Tu peux ajuster MIN plus bas (0.05 = vraiment immobile) ou plus haut
#  (0.20 = encore "praticable") selon ton goût.

FEAR_ZONE_VITESSE_MIN          = 0.08   # plancher : 8 % au pire (presque sur place)
FEAR_ZONE_REDUCTION_PAR_STADE  = 0.22   # 22 % de vitesse en moins par stade en trop

# ─────────────────────────────────────────────────────────────────────────────
#  Vitesse de RECUL (quand on s'éloigne du mur de peur)
# ─────────────────────────────────────────────────────────────────────────────
#  Si le joueur va DANS LE SENS OPPOSÉ au mur (= il essaie de sortir de
#  la zone), on lui rend une vitesse "presque normale" (75 % par défaut),
#  même s'il est physiquement contre le mur. Sans ça, le joueur croit
#  qu'il est bloqué — il appuie pour reculer mais bouge à peine.
#
#  Avec ce système, dès qu'il change de direction, il se sent capable
#  de fuir → message clair : "je peux sortir si je le veux".
#
#  On garde le ralentissement progressif quand il VA VERS le mur
#  (la zone reste dissuasive dans le bon sens).
#
#  Mettre 1.0 → vitesse pleine en recul (très permissif).
#  Mettre 0.5 → recul ralenti aussi (déconseillé : risque blocage perçu).

FEAR_ZONE_VITESSE_RECUL        = 0.75   # 75 % quand on s'éloigne du mur


# ── PALETTE DES LUCIOLES (couleur + taille personnalisables par slot) ───────
#
#  Le joueur peut, via le menu Paramètres → Compagnons, choisir une couleur
#  et une taille pour CHAQUE luciole individuellement (la 1ʳᵉ peut être
#  jaune normale, la 2ᵉ violette grande, etc.).
#
#  - LUCIOLE_PALETTE = liste de (nom_affiché, (R, G, B)). Pour ajouter une
#    couleur disponible dans le menu, il suffit d'ajouter une entrée ici.
#  - LUCIOLE_TAILLES = liste de (nom_affiché, multiplicateur_du_rayon).
#    1.0 = taille par défaut. 0.5 = moitié, 2.0 = double.
#
#  Lu par : entities/luciole.py (à chaque draw())
#  Modifié par : ui/settings_screen.py (le joueur change ses préférences)

LUCIOLE_PALETTE = [
    ("Jaune chaud",   (255, 225, 170)),    # défaut — ambiance feu de camp
    ("Vert marais",   (180, 255, 180)),    # un peu blafard, bestioles des bois
    ("Bleu glacé",    (170, 220, 255)),    # froid, mystique
    ("Rose blessé",   (255, 170, 190)),    # tendre, poétique
    ("Violet rêve",   (210, 175, 255)),    # onirique
    ("Blanc fantôme", (255, 245, 220)),    # presque blanc pur
    ("Orange braise", (255, 180, 100)),    # plus orangée que la jaune chaud
]

LUCIOLE_TAILLES = [
    ("Minuscule", 0.5),
    ("Petite",    0.75),
    ("Normale",   1.0),
    ("Grande",    1.4),
    ("Énorme",    2.0),
]

# Intensité = "puissance" d'éclairage. C'est juste un multiplicateur appliqué
# à l'opacité du halo (cf. luciole.OPACITE_MAX). 1.0 = défaut. >1 = plus
# brillant, plus présent. <1 = plus discret. On va plus haut que pour la
# taille parce que l'opacité de base est volontairement basse (pour ne pas
# faire "lampe LED") — les valeurs > 2.0 servent à éclairer vraiment la scène.
LUCIOLE_INTENSITES = [
    ("Très faible", 0.4),
    ("Faible",      0.7),
    ("Normale",     1.0),
    ("Forte",       1.6),
    ("Très forte",  2.4),
    ("Maximale",    3.5),
]

# ── État runtime : choix du joueur, slot par slot ───────────────────────────
#
#  Listes de longueur COMPAGNON_NB_MAX. L'élément i est l'index choisi pour
#  la luciole numéro i.
#  - lucioles_couleurs_idx[i]   = index dans LUCIOLE_PALETTE
#  - lucioles_tailles_idx[i]    = index dans LUCIOLE_TAILLES
#  - lucioles_intensites_idx[i] = index dans LUCIOLE_INTENSITES
#
#  Valeurs par défaut : chaque luciole prend une couleur différente dans la
#  palette (si on en a 5, on couvre les 5 premières), toutes en taille
#  "Normale" (index 2) et en intensité "Forte" (index 3) — la "Normale"
#  était trop discrète sur la scène d'après les tests utilisateur.
#
#  Hydratés au démarrage dans core/game.py depuis game_config.json,
#  et réécrits dans ce fichier quand le joueur modifie le menu.

lucioles_couleurs_idx   = [0, 1, 2, 3, 4]   # une couleur par défaut par slot
lucioles_tailles_idx    = [2, 2, 2, 2, 2]   # toutes "Normale" par défaut
lucioles_intensites_idx = [3, 3, 3, 3, 3]   # toutes "Forte" par défaut


# ═════════════════════════════════════════════════════════════════════════════
# 6. CAMÉRA
# ═════════════════════════════════════════════════════════════════════════════
#
#  La caméra suit le joueur avec un léger retard (c'est plus agréable
#  visuellement). Voir [D13] pour l'interpolation linéaire.

CAMERA_FOLLOW_SPEED   = 0.1   # facteur de lissage (0=fixe, 1=instant)
CAMERA_Y_OFFSET       = 150   # décalage vertical (caméra un peu au-dessus)
CAMERA_PAN_STEP       = 60    # pas de la molette en mode caméra libre (éditeur)


# ═════════════════════════════════════════════════════════════════════════════
# 7. ÉCLAIRAGE / AMBIANCE
# ═════════════════════════════════════════════════════════════════════════════
#
#  Le jeu est globalement sombre (ambiance oppressante). On pose un voile
#  noir semi-transparent sur tout l'écran, puis on « troue » ce voile
#  autour du joueur pour créer un halo de lumière.

FOND_ALPHA            = 40    # opacité du voile (0=aucun, 255=noir total)

# Rayon du halo de lumière autour du joueur (en pixels).
# → plus petit = halo plus serré autour du perso (plus sombre, plus stressant)
# → plus grand = halo plus généreux (plus visible, moins oppressant)
# Valeur typique : 80-180. Règle-la à l'œil selon la taille du joueur.
RAYON_JOUEUR          = 90


# ═════════════════════════════════════════════════════════════════════════════
# 8. AUDIO
# ═════════════════════════════════════════════════════════════════════════════
#
#  Les volumes vont de 0.0 (silence) à 1.0 (max).
#  Les fondus (fade-in / fade-out) sont en millisecondes.

VOLUME_MUSIQUE        = 0.7
VOLUME_PAS            = 0.3
VOLUME_ATK = 0.4 #joueur atk basiques en l'air en sur le sol
VOLUME_KILL_ENEMY = 0.15 #joueur atk et tue une enemyd

#  Cadence des bruits de pas — temps entre 2 sons (en secondes).
#  Plus PETIT = pas plus rapprochés (plus fréquents).
#  Doit COLLER au rythme visuel de l'animation correspondante :
#    - STEP_INTERVAL_WALK : marche (anim shewalks à img_dur=4 → cycle ~1.2s
#      pour 24 frames → 1 pas tous les ~0.6s grossièrement)
#    - STEP_INTERVAL_RUN  : course (anim sherun à img_dur=2 → ~2× plus
#      rapide → cadence des pas ~2× plus rapide aussi)
#  Si tu trouves que les pas sonnent en décalage avec les pieds qui touchent
#  le sol dans l'animation, ajuste ces 2 valeurs.
STEP_INTERVAL_WALK    = 0.60  # marche normale
STEP_INTERVAL_RUN     = 0.22  # course (plus rapide)

FADEIN_MUSIQUE_MS     = 2000  # fondu entrant au démarrage d'une musique
FADEOUT_MENU_MS       = 600   # fondu sortant à la sortie d'un menu


# ═════════════════════════════════════════════════════════════════════════════
# 9. MANETTE PS5 (mapping pygame)
# ═════════════════════════════════════════════════════════════════════════════
#
#  pygame numérote les boutons et les axes par un entier. Ces numéros
#  changent selon la manette — ici, c'est testé sur une DualSense PS5.
#
#  DEAD_ZONE : les joysticks analogiques ne reviennent jamais pile à 0.
#  On ignore donc toute valeur inférieure à 0.15 pour éviter les
#  micro-dérives (le perso qui avance tout seul).

DEAD_ZONE             = 0.15

# ── Axes (valeurs continues entre -1.0 et 1.0) ─────────────────────────────
AXIS_GAUCHE_X  = 0   # joystick gauche horizontal
AXIS_GAUCHE_Y  = 1   # joystick gauche vertical
AXIS_DROITE_X  = 2
AXIS_DROITE_Y  = 3
AXIS_L2        = 4   # gâchette gauche  (-1.0 → 1.0)
AXIS_R2        = 5   # gâchette droite

# ── Boutons (pressé / relâché) ─────────────────────────────────────────────
BTN_CROIX      = 0   # Croix      ×
BTN_ROND       = 1   # Rond       ○
BTN_CARRE      = 2   # Carré      □
BTN_TRIANGLE   = 3   # Triangle   △
BTN_L1         = 4   # gâchette haute gauche
BTN_R1         = 5   # gâchette haute droite
BTN_L2         = 6   # gâchette basse gauche (en plus de l'axe)
BTN_R2         = 7   # gâchette basse droite
BTN_OPTIONS    = 9   # bouton "Options" (pause)
BTN_L3         = 11  # appui sur le joystick gauche
BTN_R3         = 12  # appui sur le joystick droit


# ═════════════════════════════════════════════════════════════════════════════
# 10. ÉTAT RUNTIME (variables modifiées en direct par le jeu)
# ═════════════════════════════════════════════════════════════════════════════
#
#  ATTENTION : ce ne sont PAS des constantes. Ces variables sont mises à
#  jour CHAQUE FRAME par le code, et servent de « presse-papier » partagé
#  entre les modules.
#
#  On les place ici parce que settings.py est importé par tout le monde :
#  chaque module peut faire `settings.wx` pour lire la coordonnée souris
#  sans créer d'import circulaire.
#
#  Si tu ajoutes une nouvelle variable runtime, pense à la commenter
#  pour dire QUI l'écrit et QUI la lit.

# Manette : `None` si aucune manette n'est branchée, sinon instance pygame.
#   Écrit par : core/event_handler.py (détection en temps réel)
#   Lu par    : entities/player.py, ui/menu.py (pour lire les axes)
manette = None

# Valeur courante du joystick gauche (-1.0 à 1.0, 0 = repos).
#   Écrit par : core/event_handler.py
#   Lu par    : entities/player.py (déplacement horizontal/vertical)
axis_x  = 0.0
axis_y  = 0.0

# Coordonnées monde de la souris (en pixels absolus, pas relatifs à l'écran).
#   Écrit par : world/editor.py (chaque frame, en mode édition)
#   Lu par    : world/editor.py (pour savoir où poser une plateforme)
wx      = 0
wy      = 0

# Mode d'affichage du HUD en jeu.
#   Valeurs possibles :
#     "permanent" → cœurs + jauge de peur toujours affichés en haut à gauche
#     "immersion" → masqués tant que tout va bien, n'apparaissent que lors
#                   d'un dégât, d'une régénération, ou quand on regarde en
#                   l'air (style Hollow Knight)
#   Écrit par : ui/settings_screen.py (choix du joueur dans le menu)
#   Lu par    : ui/hud.py (décide s'il dessine ou pas)
hud_mode = "permanent"
