# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Mixin Audio (musique par map)
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  C'est un MIXIN : un petit bout de classe qui contient des méthodes
#  liées à un thème précis (ici : la musique de fond par map). La classe
#  Game (core/game.py) en hérite — comme ça les méthodes sont accessibles
#  via self.X, mais elles vivent dans ce fichier séparé pour ne pas
#  alourdir game.py qui faisait 4700+ lignes.
#
#  CONCEPT : un MIXIN n'est pas instanciable seul. Il est CONÇU pour être
#  hérité par une autre classe (Game) qui apporte les attributs (self.editeur,
#  self.screen, etc.) sur lesquels les méthodes du mixin opèrent.
#
#  CE QU'IL Y A DEDANS
#  -------------------
#       _appliquer_musique_carte()  — lance/coupe la musique selon le
#                                     champ "music" du JSON de la map
#                                     courante.
# ─────────────────────────────────────────────────────────────────────────────

import os

import settings
from audio import music_manager as music


class AudioMixin:
    """Méthodes liées à la musique de map (transition au chargement)."""

    def _appliquer_musique_carte(self):
        """Lit editeur.musique_carte et fait un fondu vers cette musique.

        Si la map n'a pas de musique configurée (champ vide), on coupe
        la musique courante avec un fondu sortant. Si la map a la même
        musique que celle déjà en cours, on ne fait rien (évite le hoquet
        de transition à chaque rechargement de map identique).

        Le fichier "music" du JSON map doit être un nom de fichier dans
        assets/music/ (ex: "fond.mp3"). On ne vérifie pas l'existence ici
        — music.transition log un warning et continue silencieusement.
        """
        nom_musique = (getattr(self.editeur, "musique_carte", "") or "").strip()
        # Mémoire de la dernière musique appliquée pour éviter de
        # re-déclencher un fondu sur le même morceau.
        derniere = getattr(self, "_derniere_musique_carte", None)
        if nom_musique == derniere:
            return
        self._derniere_musique_carte = nom_musique

        if not nom_musique:
            # Map sans musique → on coupe en douceur.
            try:
                music.arreter(fadeout_ms=1000)
            except Exception as e:
                print(f"[Musique] arreter : {e}")
            return

        # Chemin ABSOLU pour ne pas dépendre du dossier de lancement.
        # On remonte deux dossiers depuis ce fichier (core/_game_audio_mixin
        # → ENTRE-DEUX/) pour pointer sur assets/music.
        _base  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        chemin = os.path.join(_base, "assets", "music", nom_musique)
        if not os.path.isfile(chemin):
            print(f"[Musique] fichier introuvable : {chemin}")
            return
        # Volume centralisé dans settings.VOLUME_MUSIQUE_MAP — baisser
        # cette valeur dans settings.py pour rendre TOUTES les musiques
        # de map plus douces (sans toucher à la musique du menu).
        try:
            vol = float(getattr(settings, "VOLUME_MUSIQUE_MAP", 0.5))
        except Exception:
            vol = 0.5
        try:
            music.transition(chemin, volume=vol,
                             fadeout_ms=1000, fadein_ms=1500)
        except Exception as e:
            print(f"[Musique] transition '{nom_musique}' : {e}")
