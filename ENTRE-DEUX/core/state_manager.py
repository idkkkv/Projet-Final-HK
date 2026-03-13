# ─────────────────────────────────────────
#  ENTRE-DEUX — Gestionnaire d'états
#  (menu → jeu → pause → game over...)
# ─────────────────────────────────────────

class StateManager:
    def __init__(self):
        self.state = "game"  # état actuel

    def switch(self, new_state):
        self.state = new_state
