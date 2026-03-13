# ─────────────────────────────────────────
#  ENTRE-DEUX — Jauge de Peur
# ─────────────────────────────────────────

class FearSystem:
    def __init__(self, max_fear=100):
        self.max_fear = max_fear
        self.current = max_fear  # Commence à fond

    def reduce(self, amount):
        self.current = max(0, self.current - amount)

    def increase(self, amount):
        self.current = min(self.max_fear, self.current + amount)

    def is_zero(self):
        return self.current <= 0

    def get_ratio(self):
        return self.current / self.max_fear  # 0.0 à 1.0
