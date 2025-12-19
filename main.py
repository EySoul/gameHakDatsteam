import pygame
import requests

# УБРАТЬ ЛИШНИЙ ПРОБЕЛ В КОНЦЕ!
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


# === НОВАЯ ФУНКЦИЯ: переключение юнита по цифре ===
def select_bomber_by_key(bombers, key):
    """
    Выбирает юнита по нажатой цифровой клавише (1–6).
    Возвращает его ID или None, если недоступен.
    """
    digit_map = {
        pygame.K_1: 0,
        pygame.K_2: 1,
        pygame.K_3: 2,
        pygame.K_4: 3,
        pygame.K_5: 4,
        pygame.K_6: 5,
    }
    if key not in digit_map:
        return None

    index = digit_map[key]
    if index < len(bombers):
        bomber = bombers[index]
        if bomber["alive"]:
            print(
                f"Selected bomber {index + 1}: ID={bomber['id']}, pos={bomber['pos']}"
            )
            return bomber["id"]
        else:
            print(f"Bomber {index + 1} is dead!")
    else:
        print(f"No bomber at index {index}")
    return None


if __name__ == "__main__":
    data = get_arena()
    map_size = data["map_size"]
    arena = data["arena"]
    bombers = data["bombers"]
    enemies = data.get("enemies", [])
    mobs = data.get("mobs", [])
    bomber_id = bombers[0]["id"] if bombers else None

    pygame.init()
    screen_width = 800
    screen_height = 800
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Bomber Game Visualization")

    renderer = GameRenderer(screen_width, screen_height)
    renderer.update_data(map_size, arena, bombers, bomber_id, enemies, mobs)

    zoom = 1.0
    offset_x = 0
    offset_y = 0
    dragging = False
    last_mouse = (0, 0)
    last_update = 0
    bombs = []
    bomber_id = None  # будет устанавливаться вручную

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                # === ПЕРЕКЛЮЧЕНИЕ ЮНИТОВ ПО 1-6 ===
                if event.key in [
                    pygame.K_1,
                    pygame.K_2,
                    pygame.K_3,
                    pygame.K_4,
                    pygame.K_5,
                    pygame.K_6,
                ]:
                    new_id = select_bomber_by_key(bombers, event.key)
                    if new_id is not None:
                        bomber_id = new_id
                        bombs = []  # сбросить бомбы текущего юнита

                elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    zoom = min(zoom * 1.1, 5.0)
                    renderer.set_zoom(zoom)
                elif event.key == pygame.K_MINUS:
                    zoom = max(zoom / 1.1, 0.1)
                    renderer.set_zoom(zoom)
                elif event.key == pygame.K_SPACE:
                    bomber = next(
                        (b for b in bombers if b["id"] == bomber_id and b["alive"]),
                        None,
                    )
                    if bomber:
                        pos = bomber["pos"]
                        bombs = [pos]
                        send_move(bomber_id, [], bombs)
                        print(f"Placing bomb at {pos}")
                    else:
                        print("No active bomber selected or bomber is dead")

                elif bomber_id and event.key in [
                    pygame.K_UP,
                    pygame.K_DOWN,
                    pygame.K_LEFT,
                    pygame.K_RIGHT,
                ]:
                    bomber = next(
                        (b for b in bombers if b["id"] == bomber_id and b["alive"]),
                        None,
                    )
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
                        ):
                            path = [pos, new_pos]
                            send_move(bomber_id, path, bombs)
                            print(f"Moving to {new_pos}")
                        else:
                            print("Move out of bounds")
                    else:
                        print("Controlled bomber not found or dead")

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
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

        # Обновление данных каждые 500 мс
        if pygame.time.get_ticks() - last_update > 500:
            new_data = get_arena()
            if "map_size" in new_data:
                data = new_data
                map_size = data["map_size"]
                arena = data["arena"]
                bombers = data["bombers"]
                enemies = data.get("enemies", [])
                mobs = data.get("mobs", [])
                # ⚠️ НЕ СБРАСЫВАЕМ bomber_id! Пользователь сам выбирает.
                print(
                    f"Updated bombers: {[f'{b["id"]}: {b["pos"]}' for b in bombers if b['alive']]}"
                )
                renderer.update_data(map_size, arena, bombers, bomber_id, enemies, mobs)
                last_update = pygame.time.get_ticks()
            else:
                print("Invalid data received")

        renderer.draw(screen)
        pygame.display.flip()

    pygame.quit()
