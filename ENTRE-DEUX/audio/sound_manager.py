# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Effets sonores (SFX)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  Tout ce qui fait "tac", "pof", "boum" dans le jeu passe par ici. À ne PAS
#  confondre avec audio/music_manager.py, qui gère la musique de fond
#  (longue, en boucle, fondue). Ici, c'est court et instantané :
#
#       - pas du joueur
#       - coup d'épée
#       - dégâts encaissés
#       - bips de menu
#       - etc.
#
#  EXEMPLE CONCRET
#  ---------------
#       # Au démarrage du jeu :
#       sound_manager.charger("epee", "assets/sounds/sword.wav")
#       sound_manager.charger_ou_synth("ui_nav", "ui.wav",
#                                       freq=520, duree=0.04)   # bip de secours
#
#       # Pendant la partie :
#       sound_manager.jouer("epee", volume=0.8)   # → "schlik"
#       sound_manager.jouer("ui_nav")             # → "bip" (vrai son OU bip généré)
#
#  Petit lexique :
#     - SFX            = "Sound Effects" — effets sonores courts (≠ musique).
#     - mixer          = sous-module pygame qui gère le son. pygame.mixer.Sound
#                        = un objet "son chargé en mémoire, prêt à être joué".
#     - sample         = une mesure d'amplitude du son. À 44 100 Hz, on a
#                        44 100 samples par seconde → c'est ça qui définit
#                        la finesse du son (qualité CD).
#     - stéréo 16-bit  = 2 canaux (gauche / droite), 16 bits par sample.
#                        → 4 octets (bites) par "instant" de son. C'est
#                        le format standard de pygame.mixer.
#     - synthèse       = générer un son MATHÉMATIQUEMENT (pas depuis un
#                        fichier). On calcule sin(2π·f·t) → bip pur. j'ai regardé
#                        sur internet car c'est impossible sinon.
#                        Ici c'est un PLAN B : si le fichier .wav manque,
#                        on bipe pour ne pas planter le jeu.
#     - enveloppe      = fonction qui module le volume au fil du son. Ici
#                        on fait un FADE-IN court (10 % du son) + FADE-OUT
#                        plus long (30 %), pour éviter le "clic" sec qu'on
#                        entend quand un son démarre/s'arrête brutalement.
#     - struct.pack    = "convertir un nombre Python en octets binaires".
#                        struct.pack("<h", 12345) → 2 octets = un int16
#                        en little-endian. C'est le format que pygame attend.
#                        De ce que j'ai compris.
#     - get_raw()      = lecture des octets bruts d'un Sound. Utilisé ici
#                        pour DÉTECTER et SUPPRIMER le silence en début de
#                        son (sons de pas trop "mous").
#     - registre _sons = dict {nom: Sound}. La variable est PRIVÉE (préfixe _)
#                        et globale au module. On l'alimente avec charger()
#                        et on lit avec jouer(). Pas besoin d'objet — c'est
#                        un fonctionnel.
#
#  POURQUOI charger_ou_synth() ?
#  -----------------------------
#  Quand on développe, on n'a PAS toujours tous les fichiers audio sous
#  la main. Avec charger_ou_synth(), si le .wav manque, on génère un bip
#  → le jeu reste jouable et silencieux-mais-pas-muet. Quand un son
#  pro arrive, on le dépose dans assets/sounds/ et il remplace le bip
#  automatiquement (même nom, même chemin).
#
#  POURQUOI BLOQUER LA SUPERPOSITION DES "PAS" ?
#  ---------------------------------------------
#  Si on jouait le son "pas" sans contrôle, le joueur qui court enchaîne
#  3-4 pas en moins d'une seconde → 3-4 sons qui se chevauchent → bouillie
#  audio. On vérifie son.get_num_channels() (= "ce son est-il déjà en
#  train d'être joué ?") et on saute si oui.
#
#  OÙ EST-CE UTILISÉ ?
#  -------------------
#  Partout où il y a un "événement instantané" : entities/player.py
#  (pas, attaque, dégât, mort), entities/enemy.py (impact), ui/menu.py
#  (bips de navigation), etc.
#
#  JE VEUX MODIFIER QUOI ?
#  -----------------------
#     - Ajouter un nouveau son                  → charger() au démarrage,
#                                                 jouer() au moment voulu
#     - Bipper plus aigu / plus grave           → freq dans charger_ou_synth()
#     - Bip plus long                           → duree dans charger_ou_synth()
#     - Forme d'onde "chip-tune" (8-bit feel)   → forme="saw" (dent de scie)
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D6]   pygame.mixer  — gestion audio
#     [D24]  module global — _sons est un état partagé du module
#
# ─────────────────────────────────────────────────────────────────────────────

import math
import struct
import pygame


# ═════════════════════════════════════════════════════════════════════════════
#  REGISTRE GLOBAL (tous les sons chargés sont là)
# ═════════════════════════════════════════════════════════════════════════════
#
# {nom: pygame.mixer.Sound}. Préfixe _ = "privé au module" (les autres
# fichiers passent par les fonctions ci-dessous, pas par _sons direct).

_sons = {}


# ═════════════════════════════════════════════════════════════════════════════
#  1. NETTOYAGE DU SILENCE INITIAL (pour les sons de pas)
# ═════════════════════════════════════════════════════════════════════════════

def _trim_silence(son, seuil=400, max_duree=0.25):
    """Supprime le blanc au début d'un son ET le tronque à `max_duree`.

    DEUX nettoyages :
      1) DÉBUT : certains .wav ont 50-100 ms de silence avant le son utile.
         Pour un son de pas joué à la cadence de la marche, ce délai se
         voit (pied qui touche le sol AVANT qu'on entende le bruit). On
         scanne le buffer brut et on coupe au 1er sample > seuil.
      2) FIN : on tronque à `max_duree` secondes (par défaut 250 ms).
         CRUCIAL pour les sons de pas : si le fichier source contient
         plusieurs pas en boucle (ex : pas.mp3 = 10 s), la cadence des
         pas est dictée par le FICHIER (et non par STEP_INTERVAL_WALK
         qu'on règle dans settings.py). En tronquant à 1 seul pas, le
         contrôle de cadence repasse à STEP_INTERVAL_*.

    Format pygame standard : stéréo 16-bit → 4 octets par sample stéréo
    (2 octets gauche + 2 octets droite). On ne lit que le canal gauche,
    largement suffisant pour détecter "le son a commencé".
    """
    raw = son.get_raw()

    # 1) Trim début (silence)
    start = 0
    for i in range(0, len(raw) - 4, 4):
        left = struct.unpack_from("<h", raw, i)[0]
        if abs(left) > seuil:
            start = i
            break

    # 2) Trim fin (max_duree secondes)
    # Récupère les paramètres du mixer (Hz + bits + channels)
    freq, bits, channels = pygame.mixer.get_init()
    bytes_per_sample = abs(bits) // 8 * channels  # ex: 16-bit stereo = 4
    max_bytes = int(max_duree * freq * bytes_per_sample)

    end = min(start + max_bytes, len(raw))
    trimmed = raw[start:end]

    if len(trimmed) < 4:
        return son                             # rien d'utile → on garde l'original
    return pygame.mixer.Sound(buffer=bytes(trimmed))


# ═════════════════════════════════════════════════════════════════════════════
#  2. CHARGEMENT (à appeler au démarrage du jeu)
# ═════════════════════════════════════════════════════════════════════════════

def charger(nom, chemin, trim=False):
    """Charge un son depuis `chemin` et le range sous `nom` dans le registre.

    `trim=True` → on coupe le silence initial (pour les sons de pas).
    En cas d'erreur (fichier absent / corrompu), on ABSORBE silencieusement :
    pas de crash, juste pas de son. Le jeu continue de tourner."""
    try:
        son = pygame.mixer.Sound(chemin)
        if trim:
            son = _trim_silence(son)
        _sons[nom] = son
    except Exception:
        pass                                   # tant pis, pas de son


def charger_ou_synth(nom, chemin, freq, duree, volume=0.3, forme="sin"):
    """Comme charger(), mais avec un PLAN B : si le fichier manque,
    on génère un bip de remplacement pour ne pas avoir un jeu muet.

    Idéal pour les sons de menu (ui_nav, ui_select…) qu'on veut entendre
    même sans avoir préparé tous les fichiers .wav.
    """
    try:
        _sons[nom] = pygame.mixer.Sound(chemin)
    except Exception:
        _sons[nom] = _generer_son(freq, duree, volume, forme)


# ═════════════════════════════════════════════════════════════════════════════
#  3. JOUER / ARRÊTER (à appeler n'importe quand)
# ═════════════════════════════════════════════════════════════════════════════

def jouer(nom, volume=1.0):
    """Joue le son `nom` à `volume` (entre 0.0 et 1.0).

    Le volume EFFECTIF est multiplié par settings.volume_sfx (master des
    effets sonores, configurable depuis l'écran Paramètres). Si vide ou
    invalide, on retombe sur 1.0 (= pas d'atténuation).

    CAS SPÉCIAL : "pas" — si une instance est déjà en train de jouer, on
    la COUPE avant de lancer la nouvelle. Comme ça la cadence des pas
    est pilotée 100% par STEP_INTERVAL_WALK / STEP_INTERVAL_RUN dans
    settings.py (au lieu d'être bloquée par la durée du fichier audio).
    """
    son = _sons.get(nom)
    if son:
        if nom == "pas" and son.get_num_channels() > 0:
            son.stop()                         # coupe le précédent
        # Master SFX (paramètres). Lookup paresseux pour ne pas créer
        # de dépendance circulaire au chargement du module.
        try:
            import settings
            master = float(getattr(settings, "volume_sfx", 1.0))
        except Exception:
            master = 1.0
        son.set_volume(max(0.0, min(1.0, volume * master)))
        son.play()


def arreter(nom):
    """Coupe immédiatement le son `nom` (toutes ses instances)."""
    son = _sons.get(nom)
    if son:
        son.stop()


# ═════════════════════════════════════════════════════════════════════════════
#  4. SYNTHÈSE (pour les bips de remplacement)
# ═════════════════════════════════════════════════════════════════════════════

def _generer_son(freq, duree, volume=0.3, forme="sin"):
    """Crée un Sound depuis zéro (pas de fichier) à la fréquence `freq` Hz.

    Comment ça marche en 4 étapes :
        1) Pour chaque sample (44100 par seconde),
        2) on calcule sin(2π·freq·t)        → forme d'onde [-1, +1]
        3) on multiplie par une enveloppe   → fade in/out doux
        4) on convertit en int16 → octets binaires (struct.pack).
    Ensuite pygame.mixer.Sound emballe le tout en Sound jouable.
    """
    sample_rate = 44100
    n = int(sample_rate * duree)
    buf = bytearray()
    for i in range(n):
        t = i / sample_rate

        # Enveloppe = volume modulé pour éviter les clics aux bords du son :
        #   - fade-IN  pendant les 10 % premiers samples  (i / (n*0.1))
        #   - fade-OUT pendant les 30 % derniers samples  ((n-i) / (n*0.3))
        # min(1.0, ...) plafonne à 1.0 au milieu du son.
        env = min(1.0, i / (n * 0.1)) * min(1.0, (n - i) / (n * 0.3))

        if forme == "sin":
            val = math.sin(2 * math.pi * freq * t)         # sinusoïde douce
        else:
            val = (2 * (freq * t % 1) - 1)                 # dent de scie (chip-tune)

        # Conversion float [-1, +1] → int16 [-32768, +32767].
        sample = int(val * env * volume * 32767)
        sample = max(-32768, min(32767, sample))           # clamp de sécurité
        packed = struct.pack("<h", sample)                 # 2 octets little-endian
        buf += packed + packed                             # stéréo (gauche = droite)

    return pygame.mixer.Sound(buffer=bytes(buf))


# ═════════════════════════════════════════════════════════════════════════════
#  5. SONS UI PRÉ-CONFIGURÉS (appelée par le menu au démarrage)
# ═════════════════════════════════════════════════════════════════════════════

def init_sons_ui():
    """Crée les 3 bips de menu (s'ils n'existent pas déjà). Volontairement
    SYNTHÉTISÉS : pas de fichiers à fournir, ça marche sur toute installation."""
    if "ui_nav" not in _sons:
        _sons["ui_nav"]    = _generer_son(520, 0.04, 0.15)
        _sons["ui_select"] = _generer_son(680, 0.08, 0.20)
        _sons["ui_back"]   = _generer_son(320, 0.06, 0.15)
