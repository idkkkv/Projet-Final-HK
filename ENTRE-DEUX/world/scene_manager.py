# ─────────────────────────────────────────
#  ENTRE-DEUX — Gestionnaire de scènes
# ─────────────────────────────────────────

class SceneManager:
    def __init__(self):
        self.scenes = {}
        self.current = None

    def add_scene(self, name, scene):
        self.scenes[name] = scene

    def load(self, name):
        if name in self.scenes:
            self.current = self.scenes[name]

    def update(self, dt, player):
        if self.current:
            self.current.update(dt, player)

    def draw(self, surf):
        if self.current:
            self.current.draw(surf)
