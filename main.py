import pygame
import requests

from models import Bomb, Bomber, GameState, Mob, Position
from paint import GameRenderer

domen = "https://games-test.datsteam.dev"
token = "d4d94a5f-c6aa-49af-b547-13897fb0896a"
prefix = "/api"


def get_arena():
    response = requests.get(f"{domen}{prefix}/arena", headers={"X-Auth-Token": token})
    return response.json()


def send_move(bomber_id, path, bombs):
    data = {"bombers": [{"id": bomber_id, "path": path, "bombs": bombs}]}
    print(f"Sending move for {bomber_id}: {data}")
    response = requests.post(
        f"{domen}{prefix}/move",
        headers={"X-Auth-Token": token, "Content-Type": "application/json"},
        json=data,
    )
    print(f"Response status: {response.status_code}, text: {response.text}")


def create_game_state_from_data(data):
    """Convert raw API data to GameState object with proper model instances."""
    # Create positions
    obstacles = [Position(obs[0], obs[1]) for obs in data["arena"]["obstacles"]]
    walls = [Position(wall[0], wall[1]) for wall in data["arena"]["walls"]]

    # Create bombs
    bombs = []
    for bomb_data in data["arena"]["bombs"]:
        if isinstance(bomb_data, dict) and "pos" in bomb_data:
            pos = Position(bomb_data["pos"][0], bomb_data["pos"][1])
            bomb = Bomb(
                pos=pos,
                timer=bomb_data.get("timer", 0),
                radius=bomb_data.get("radius", 1),
                owner=bomb_data.get("owner", ""),
            )
            bombs.append(bomb)

    # Create bombers
    bombers = {}
    for bomber_data in data["bombers"]:
        pos = Position(bomber_data["pos"][0], bomber_data["pos"][1])
        bomber = Bomber(
            id=bomber_data["id"],
            alive=bomber_data["alive"],
            pos=pos,
            armor=bomber_data["armor"],
            bombs_available=bomber_data["bombs_available"],
            can_move=bomber_data["can_move"],
            safe_time=bomber_data.get("safe_time", 0),
        )
        bombers[bomber.id] = bomber

    # Create mobs
    mobs = []
    for mob_data in data.get("mobs", []):
        pos = Position(mob_data[0], mob_data[1])
        mob = Mob(
            id="",  # API doesn't provide IDs for mobs
            type="patrol",  # Default type
            pos=pos,
            safe_time=0,
        )
        mobs.append(mob)

    # Handle enemies (if any)
    enemies = data.get("enemies", [])

    # Create game state
    game_state = GameState(
        player_name=data.get("player_name", ""),
        round_id=data.get("round_id", ""),
        map_size=data["map_size"],
        raw_score=data.get("raw_score", 0),
        bombers=bombers,
        obstacles=obstacles,
        walls=walls,
        bombs=bombs,
        mobs=mobs,
        enemies=enemies,
    )

    return game_state


if __name__ == "__main__":
    data = get_arena()
    map_size = data["map_size"]
    game_state = create_game_state_from_data(data)

    # Get first bomber ID
    bomber_id = next(iter(game_state.bombers)) if game_state.bombers else None

    # Initialize Pygame
    pygame.init()
    screen_width = 800
    screen_height = 800
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Bomber Game Visualization")

    renderer = GameRenderer(screen_width, screen_height)
    renderer.update_data(map_size, game_state, bomber_id)

    zoom = 1.0
    offset_x = 0
    offset_y = 0
    dragging = False
    last_mouse = (0, 0)
    last_update = 0
    bombs = []

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    zoom = min(zoom * 1.1, 5.0)
                    renderer.set_zoom(zoom)
                elif event.key == pygame.K_MINUS:
                    zoom = max(zoom / 1.1, 0.1)
                    renderer.set_zoom(zoom)
                elif event.key == pygame.K_SPACE:
                    bomber = (
                        game_state.get_bomber_by_id(bomber_id) if game_state else None
                    )
                    if bomber and bomber.alive:
                        pos = bomber.pos
                        bombs = [(pos.x, pos.y)]
                        send_move(bomber_id, [], bombs)
                        print(f"Placing bomb at ({pos.x}, {pos.y})")
                elif bomber_id and event.key in [
                    pygame.K_UP,
                    pygame.K_DOWN,
                    pygame.K_LEFT,
                    pygame.K_RIGHT,
                ]:
                    bomber = (
                        game_state.get_bomber_by_id(bomber_id) if game_state else None
                    )
                    if bomber and bomber.alive:
                        pos = bomber.pos
                        new_pos = Position(pos.x, pos.y)
                        if event.key == pygame.K_UP:
                            new_pos.y -= 1
                        elif event.key == pygame.K_DOWN:
                            new_pos.y += 1
                        elif event.key == pygame.K_LEFT:
                            new_pos.x -= 1
                        elif event.key == pygame.K_RIGHT:
                            new_pos.x += 1

                        # Check bounds
                        if (
                            0 <= new_pos.x < map_size[0]
                            and 0 <= new_pos.y < map_size[1]
                            and (new_pos.x != pos.x or new_pos.y != pos.y)
                        ):
                            path = [(pos.x, pos.y), (new_pos.x, new_pos.y)]
                            send_move(bomber_id, path, bombs)
                        else:
                            print(f"Invalid move for bomber {bomber_id}")
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left mouse button
                    dragging = True
                    last_mouse = event.pos
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                dx = event.pos[0] - last_mouse[0]
                dy = event.pos[1] - last_mouse[1]
                offset_x += dx
                offset_y += dy
                renderer.set_offset(offset_x, offset_y)
                last_mouse = event.pos

        # Update data every 0.5 seconds
        if pygame.time.get_ticks() - last_update > 500:
            new_data = get_arena()
            if "map_size" in new_data:
                data = new_data
                map_size = data["map_size"]
                game_state = create_game_state_from_data(data)
                bomber_id = (
                    next(iter(game_state.bombers)) if game_state.bombers else None
                )

                print(
                    f"Updated bombers: {[f'{b.id}: ({b.pos.x}, {b.pos.y})' for b in game_state.bombers.values() if b.alive]}"
                )
                print(f"Controlled bomber ID: {bomber_id}")

                renderer.update_data(map_size, game_state, bomber_id)
                last_update = pygame.time.get_ticks()
            else:
                print("Invalid data received, skipping update")

        renderer.draw(screen)

        pygame.display.flip()

    pygame.quit()
