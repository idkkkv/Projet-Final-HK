# ─────────────────────────────────────────
#  ENTRE-DEUX — Détection des collisions
# ─────────────────────────────────────────

def check_attack_collisions(player, enemies):
    """Vérifie si l'attaque du joueur touche un ennemi."""
    if player.attacking:
        for enemy in enemies:
            if enemy.alive and enemy.rect.colliderect(player.attack_rect):
                enemy.alive = False

def check_platform_collisions(player, platforms_or_grid):
    """
    Vérifie les collisions avec les plateformes.
    Accepte une liste OU une SpatialGrid.
    """
    if hasattr(platforms_or_grid, 'query'):
        nearby = platforms_or_grid.query(player.rect)
    else:
        nearby = platforms_or_grid

    for platform in nearby:
        platform.verifier_collision(player)

def check_wall_collisions(player, walls):
    for wall in walls:
        wall.verifier_collision(player)

def check_player_enemy_collisions(player, enemies, dt):
    """
    Si le joueur touche un ennemi vivant, il est POUSSÉ horizontalement.
    Pas de saut, pas de grimpage — juste une poussée latérale.
    """
    for enemy in enemies:
        if not enemy.alive:
            continue
        if player.rect.colliderect(enemy.rect):
            # Direction de la poussée : le joueur est repoussé
            # dans la direction opposée à l'ennemi
            push_speed = 400
            if player.rect.centerx < enemy.rect.centerx:
                # Ennemi à droite → pousse le joueur à gauche
                player.rect.x -= int(push_speed * dt)
            else:
                # Ennemi à gauche → pousse le joueur à droite
                player.rect.x += int(push_speed * dt)
            return True
    return False