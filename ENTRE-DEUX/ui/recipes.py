class Recipe:
    def __init__(self, name, ingredients, instructions):
        self.name = name
        self.ingredients = ingredients
        self.instructions = instructions

    def __str__(self):
        return f"{self.name}\nIngredients: {', '.join(self.ingredients)}\nInstructions: {self.instructions}"