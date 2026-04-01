# ─────────────────────────────────────────
#  ENTRE-DEUX — Constantes globales
# ─────────────────────────────────────────
import pygame
# Résolution

SCENE_WIDTH  = 2400   # largeur d'une scène (3x l'écran)
SCENE_HEIGHT = 4000   # hauteur d'une scène (2x l'écran)

WIDTH, HEIGHT = 1520, 745
FPS = 80
TITLE = "LIMINAL"

# Couleurs
BLEU   = (98,  143, 217)
BLEU_NUIT = (30, 30, 40)
ROUGE  = (217, 108, 98)
GRIS   = (178, 171, 184)
VIOLET = (38,  19,  46)
BLANC  = (255, 255, 255)
NOIR   = (0,   0,   0)

# Physique joueur
GRAVITY        = 1500
JUMP_POWER     = 600
PLAYER_SPEED   = 300
ATTACK_DURATION = 0.2
CEILING_Y = 0

# Sol (temporaire, sera remplacé par les collisions de tilemap)
GROUND_Y = 590

# cd
wx = 0
wy = 0

# joy
manette = None
axis_y = 0
axis_x = 0
DEAD_ZONE = 0.15

# MANETTE PS5 — mapping pygame
# Axes
AXIS_GAUCHE_X  = 0   # joystick gauche horizontal
AXIS_GAUCHE_Y  = 1   # joystick gauche vertical
AXIS_DROITE_X  = 2
AXIS_DROITE_Y  = 3
AXIS_L2        = 4   # -1.0 à 1.0
AXIS_R2        = 5

# Boutons
BTN_CROIX      = 0
BTN_ROND       = 1
BTN_CARRE      = 2
BTN_TRIANGLE   = 3
BTN_L1         = 4
BTN_R1         = 5
BTN_L2         = 6
BTN_R2         = 7
BTN_OPTIONS    = 9
BTN_L3         = 11  # appui joystick gauche
BTN_R3         = 12


mod = 0

# lumière

FOND_ALPHA   = 40  # luminosité ambiante (0=noir total, 100=sombre, 255=jour)
RAYON_JOUEUR = 140  # taille du halo du joueur