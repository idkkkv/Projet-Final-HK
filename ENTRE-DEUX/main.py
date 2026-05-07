# ─────────────────────────────────────────────────────────────────────────────
#  LIMINAL (ENTRE-DEUX) — Point d'entrée du jeu
# ─────────────────────────────────────────────────────────────────────────────
#
#  À QUOI SERT CE FICHIER ?
#  ------------------------
#  C'est LE fichier qu'on lance pour démarrer le jeu :
# 
#  ----------------------------------
#  Convention universelle Python : main.py = un point d'entrée minimal
#  qui DÉLÈGUE tout à un module / une classe métier. Avantages :
#       - lecture immédiate "qu'est-ce qui démarre ?"
#       - facile à remplacer par un autre point d'entrée (ex : tests)
#       - pas de logique cachée dans un fichier qu'on ne lit jamais
#
#  Petit lexique :
#     - point d'entrée   = LE fichier qu'on lance pour démarrer un programme.
#     - __name__         = variable spéciale Python remplie automatiquement.
#                          "__main__" si lancé directement, sinon le nom du module.
#     - if __name__ ...  = formule idiomatique de protection.
#
#  CONCEPTS (voir docs/DICTIONNAIRE.md) :
#  --------------------------------------
#     [D1]  point d'entrée — convention Python pour démarrer une appli
#
# ─────────────────────────────────────────────────────────────────────────────

import os
import sys
import atexit

from core.game import Game


# ─── Désactive les "touches rémanentes" Windows pendant le jeu ─────────────
# Sur Windows, appuyer 5× rapidement sur Maj ouvre une popup système
# (Sticky Keys). Comme on spamme Shift pour le dash, ça flingue le jeu.
# On désactive l'activation auto au lancement et on restaure à la fermeture.
def _desactiver_touches_remanentes():
    if not sys.platform.startswith("win"):
        return  # Linux/Mac : rien à faire
    try:
        import ctypes
        from ctypes import wintypes

        class STICKYKEYS(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('dwFlags', wintypes.DWORD)]

        class FILTERKEYS(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                        ('iWaitMSec', wintypes.DWORD), ('iDelayMSec', wintypes.DWORD),
                        ('iRepeatMSec', wintypes.DWORD), ('iBounceMSec', wintypes.DWORD)]

        class TOGGLEKEYS(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('dwFlags', wintypes.DWORD)]

        SPI_GETSTICKYKEYS = 0x003A; SPI_SETSTICKYKEYS = 0x003B
        SPI_GETFILTERKEYS = 0x0032; SPI_SETFILTERKEYS = 0x0033
        SPI_GETTOGGLEKEYS = 0x0034; SPI_SETTOGGLEKEYS = 0x0035
        SKF_HOTKEYACTIVE = 0x4; SKF_CONFIRMHOTKEY = 0x8
        SKF_STICKYKEYSON = 0x1; FKF_FILTERKEYSON = 0x1; TKF_TOGGLEKEYSON = 0x1

        spi = ctypes.windll.user32.SystemParametersInfoW

        # Sticky Keys (popup Maj 5×)
        sk = STICKYKEYS(); sk.cbSize = ctypes.sizeof(STICKYKEYS)
        spi(SPI_GETSTICKYKEYS, sk.cbSize, ctypes.byref(sk), 0)
        sk_saved = sk.dwFlags
        if not (sk_saved & SKF_STICKYKEYSON):
            sk.dwFlags &= ~(SKF_HOTKEYACTIVE | SKF_CONFIRMHOTKEY)
            spi(SPI_SETSTICKYKEYS, sk.cbSize, ctypes.byref(sk), 0)

        # Filter Keys (popup Maj 8s)
        fk = FILTERKEYS(); fk.cbSize = ctypes.sizeof(FILTERKEYS)
        spi(SPI_GETFILTERKEYS, fk.cbSize, ctypes.byref(fk), 0)
        fk_saved = fk.dwFlags
        if not (fk_saved & FKF_FILTERKEYSON):
            fk.dwFlags &= ~(SKF_HOTKEYACTIVE | SKF_CONFIRMHOTKEY)
            spi(SPI_SETFILTERKEYS, fk.cbSize, ctypes.byref(fk), 0)

        # Toggle Keys (popup Verr Num 5s)
        tk = TOGGLEKEYS(); tk.cbSize = ctypes.sizeof(TOGGLEKEYS)
        spi(SPI_GETTOGGLEKEYS, tk.cbSize, ctypes.byref(tk), 0)
        tk_saved = tk.dwFlags
        if not (tk_saved & TKF_TOGGLEKEYSON):
            tk.dwFlags &= ~(SKF_HOTKEYACTIVE | SKF_CONFIRMHOTKEY)
            spi(SPI_SETTOGGLEKEYS, tk.cbSize, ctypes.byref(tk), 0)

        # Restaure les paramètres d'origine à la sortie du jeu
        def _restaurer():
            sk2 = STICKYKEYS(cbSize=ctypes.sizeof(STICKYKEYS), dwFlags=sk_saved)
            spi(SPI_SETSTICKYKEYS, sk2.cbSize, ctypes.byref(sk2), 0)
            fk2 = FILTERKEYS(cbSize=ctypes.sizeof(FILTERKEYS), dwFlags=fk_saved)
            spi(SPI_SETFILTERKEYS, fk2.cbSize, ctypes.byref(fk2), 0)
            tk2 = TOGGLEKEYS(cbSize=ctypes.sizeof(TOGGLEKEYS), dwFlags=tk_saved)
            spi(SPI_SETTOGGLEKEYS, tk2.cbSize, ctypes.byref(tk2), 0)
        atexit.register(_restaurer)

    except Exception as e:
        # Si pour une raison X la désactivation échoue (droits, etc.),
        # on continue : le jeu marchera, juste avec la popup possible.
        print(f"[main] Touches rémanentes : désactivation impossible ({e})")


if __name__ == "__main__":
    _desactiver_touches_remanentes()

    game = Game()
    game.run()
