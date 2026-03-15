# ─────────────────────────────────────────
#  ENTRE-DEUX — Détection des collisions
# ─────────────────────────────────────────

def check_attack_collisions(player, enemies):
    if player.attacking:
        for enemy in enemies:
            if enemy.alive and enemy.rect.colliderect(player.attack_rect):
                enemy.alive = False

def check_platform_collisions(player, platforms_or_grid):
    if hasattr(platforms_or_grid, 'query'):
        nearby = platforms_or_grid.query(player.rect)
    else:
        nearby = platforms_or_grid
    for platform in nearby:
        platform.verifier_collision(player)

def check_wall_collisions(player, walls):
    for wall in walls:
        wall.verifier_collision(player)

def check_player_enemy_collisions(player, enemies):
    """
    Joueur touché → poussé + invincible.
    Ennemi → recul aussi (via enemy.hit_player).
    """
    if player.invincible:
        return

    for enemy in enemies:
        if not enemy.alive:
            continue
        if enemy.attack_cooldown > 0:
            continue
        if player.rect.colliderect(enemy.rect):
            # L'ennemi frappe → recul des DEUX côtés
            if enemy.hit_player(player.rect):
                player.hit_by_enemy(enemy.rect)
            return