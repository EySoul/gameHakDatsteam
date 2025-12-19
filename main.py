import pygame
import requests

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
    # No JSON parsing to avoid decode errors


if __name__ == "__main__":
    data = get_arena()
    map_size = data["map_size"]
    arena = data["arena"]
    bombers = data["bombers"]

    # Initialize Pygame
    pygame.init()
    screen_width = 800
    screen_height = 800
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Bomber Game Visualization")

    # Colors
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    RED = (255, 0, 0)
    BLUE = (0, 0, 255)
    GREEN = (0, 255, 0)
    GRAY = (128, 128, 128)
    LIGHT_GRAY = (200, 200, 200)
    PINK = (255, 192, 203)
    # Cell size
    cell_size = 5  # 215 * 3 = 645, fits in 800
    zoom = 1.0
    offset_x = 0
    offset_y = 0
    dragging = False
    last_mouse = (0, 0)
    last_update = 0
    bombs = []
    bomber_id = None

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    zoom = min(zoom * 1.1, 5.0)
                elif event.key == pygame.K_MINUS:
                    zoom = max(zoom / 1.1, 0.1)
                elif event.key == pygame.K_SPACE:
                    bomber = next((b for b in bombers if b["id"] == bomber_id), None)
                    if bomber:
                        pos = bomber["pos"]
                        bombs = [pos]
                        send_move(bomber_id, [], bombs)
                        print(f"Placing bomb at {pos}")
                elif bomber_id and event.key in [
                    pygame.K_UP,
                    pygame.K_DOWN,
                    pygame.K_LEFT,
                    pygame.K_RIGHT,
                ]:
                    bomber = next((b for b in bombers if b["id"] == bomber_id), None)
                    if bomber:
                        pos = bomber["pos"]
                        new_pos = list(pos)
                        if event.key == pygame.K_UP:
                            new_pos[1] -= 1
                        elif event.key == pygame.K_DOWN:
                            new_pos[1] += 1
                        elif event.key == pygame.K_LEFT:
                            new_pos[0] -= 1
                        elif event.key == pygame.K_RIGHT:
                            new_pos[0] += 1
                        if (
                            0 <= new_pos[0] < map_size[0]
                            and 0 <= new_pos[1] < map_size[1]
                            and new_pos != pos
                        ):
                            path = [pos, new_pos]
                            send_move(bomber_id, path, bombs)
                        else:
                            print(
                                f"Controlled bomber {bomber_id} not found or not alive"
                            )
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
                last_mouse = event.pos

        # Update data every 0.5 seconds
        if pygame.time.get_ticks() - last_update > 500:
            new_data = get_arena()
            if "map_size" in new_data:
                data = new_data
                map_size = data["map_size"]
                arena = data["arena"]
                bombers = data["bombers"]
                bomber_id = bombers[0]["id"] if bombers else None
                print(
                    f"Updated bombers: {[f'{b['id']}: {b['pos']}' for b in bombers if b['alive']]}"
                )
                print(f"Controlled bomber ID: {bomber_id}")
                last_update = pygame.time.get_ticks()
            else:
                print("Invalid data received, skipping update")

        # Create surface for drawing
        surface = pygame.Surface((map_size[0] * cell_size, map_size[1] * cell_size))
        surface.fill(BLACK)

        # Draw grid
        for x in range(0, map_size[0] * cell_size + 1, cell_size):
            pygame.draw.line(surface, LIGHT_GRAY, (x, 0), (x, map_size[1] * cell_size))
        for y in range(0, map_size[1] * cell_size + 1, cell_size):
            pygame.draw.line(surface, LIGHT_GRAY, (0, y), (map_size[0] * cell_size, y))

        # Draw obstacles
        for obs in arena["obstacles"]:
            x, y = obs
            pygame.draw.rect(
                surface, PINK, (x * cell_size, y * cell_size, cell_size, cell_size)
            )

        # Draw walls
        for wall in arena["walls"]:
            x, y = wall
            pygame.draw.rect(
                surface, WHITE, (x * cell_size, y * cell_size, cell_size, cell_size)
            )

        # Draw bombs
        print(f"Bombs: {arena['bombs']}")
        for bomb in arena["bombs"]:
            if isinstance(bomb, dict) and "pos" in bomb:
                x, y = bomb["pos"]
                pygame.draw.circle(
                    surface,
                    RED,
                    (x * cell_size + cell_size // 2, y * cell_size + cell_size // 2),
                    cell_size // 2,
                )

        # Draw bombers
        for bomber in bombers:
            if bomber["id"] == bomber_id and bomber["alive"]:
                x, y = bomber["pos"]
                pygame.draw.circle(
                    surface,
                    RED,
                    (x * cell_size + cell_size // 2, y * cell_size + cell_size // 2),
                    cell_size // 2,
                )

        # Scale the surface
        scaled_width = int(map_size[0] * cell_size * zoom)
        scaled_height = int(map_size[1] * cell_size * zoom)
        scaled_surface = pygame.transform.scale(surface, (scaled_width, scaled_height))

        # Blit to screen
        screen.fill(BLACK)
        screen.blit(scaled_surface, (offset_x, offset_y))

        pygame.display.flip()

    pygame.quit()
