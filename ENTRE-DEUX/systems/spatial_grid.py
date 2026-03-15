# ─────────────────────────────────────────────────────
#  ENTRE-DEUX — Grille spatiale (collisions rapides)
# ─────────────────────────────────────────────────────
#
#  Au lieu de tester TOUS les objets à chaque frame,
#  on découpe le monde en cellules et on ne teste que
#  les objets dans les mêmes cellules que le joueur.
#
#  100 plateformes → on en teste 3 ou 4 au lieu de 100.
# ─────────────────────────────────────────────────────


class SpatialGrid:
    """
    Grille qui découpe le monde en carrés de cell_size pixels.
    Chaque objet est rangé dans les cellules qu'il touche.
    Pour chercher des voisins, on regarde seulement les cellules
    autour du point ou rectangle demandé.
    """

    def __init__(self, cell_size=128):
        self.cell_size = cell_size
        self.cells = {}   # {(cx, cy): [obj, obj, ...]}

    def clear(self):
        """Vide toute la grille."""
        self.cells.clear()

    def insert(self, obj):
        """
        Insère un objet dans la grille.
        L'objet doit avoir un attribut .rect (pygame.Rect).
        """
        for cell in self._cells_for(obj.rect):
            self.cells.setdefault(cell, []).append(obj)

    def query(self, rect):
        """
        Retourne tous les objets qui POURRAIENT toucher ce rect.
        (Ceux dans les mêmes cellules — il faut encore faire
        le vrai test de collision ensuite.)
        """
        found = set()
        for cell in self._cells_for(rect):
            for obj in self.cells.get(cell, []):
                found.add(obj)
        return found

    def rebuild(self, objects):
        """
        Reconstruit toute la grille à partir d'une liste d'objets.
        Appeler quand on ajoute/supprime des éléments (éditeur).
        """
        self.clear()
        for obj in objects:
            self.insert(obj)

    def _cells_for(self, rect):
        """Retourne les coordonnées de cellule que ce rect touche."""
        cs = self.cell_size
        x1 = rect.left   // cs
        y1 = rect.top    // cs
        x2 = rect.right  // cs
        y2 = rect.bottom // cs
        cells = []
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                cells.append((x, y))
        return cells