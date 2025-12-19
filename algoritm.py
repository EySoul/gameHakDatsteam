import random
from collections import deque
from typing import List, Tuple, Optional, Dict, Any

def move_toward_obstacle_or_explore_with_speed(
    bomber: Dict[str, Any],
    arena: Dict[str, List],
    upgrades: Dict[str, Any],
    map_size: Tuple[int, int],
    dt_seconds: float = 0.5
) -> Optional[Dict[str, Any]]:
    """
    Учитывает скорость юнита при планировании пути.
    dt_seconds — интервал между запросами (в секундах).
    """
    if not bomber["alive"]:
        return None

    pos = tuple(bomber["pos"])
    speed = upgrades.get("speed", 2)  # стартовая скорость = 2
    max_steps_this_turn = max(1, int(speed * dt_seconds))  # минимум 1 шаг

    obstacles = [tuple(obs) for obs in arena["obstacles"]]
    walls = set(tuple(w) for w in arena["walls"])
    bombs = set(
        tuple(b["pos"]) for b in arena["bombs"]
    ) if arena["bombs"] and isinstance(arena["bombs"][0], dict) else set(
        tuple(b) for b in arena["bombs"]
    )

    blocked = set(walls)
    if not upgrades.get("can_pass_bombs", False):
        blocked.update(bombs)

    # === Проверка: есть ли препятствия в радиусе обзора (r^2 <= 25) ===
    nearby_obstacles = []
    for obs in obstacles:
        dx = obs[0] - pos[0]
        dy = obs[1] - pos[1]
        if dx * dx + dy * dy <= 25:
            nearby_obstacles.append(obs)

    if nearby_obstacles:
        # === Идём к ближайшему препятствию ===
        candidate_cells = []
        for obs in nearby_obstacles:
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                cell = (obs[0] + dx, obs[1] + dy)
                if not (0 <= cell[0] < map_size[0] and 0 <= cell[1] < map_size[1]):
                    continue
                if cell in blocked:
                    continue
                dist = abs(cell[0] - pos[0]) + abs(cell[1] - pos[1])
                candidate_cells.append((dist, cell))

        if candidate_cells:
            _, target_cell = min(candidate_cells, key=lambda x: x[0])

            # BFS с ограничением по длине (но не более max_steps_this_turn для первого шага)
            queue = deque([(pos, [pos])])
            visited = {pos}

            while queue:
                cur, path = queue.popleft()
                if cur == target_cell:
                    final_path = [list(p) for p in path[:30]]
                    return {
                        "id": bomber["id"],
                        "path": final_path,
                        "bombs": [final_path[-1]]
                    }

                if len(path) >= max_steps_this_turn + 5:  # небольшой запас
                    continue

                x, y = cur
                for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
                    nxt = (nx, ny)
                    if not (0 <= nx < map_size[0] and 0 <= ny < map_size[1]):
                        continue
                    if nxt in visited or nxt in blocked:
                        continue
                    visited.add(nxt)
                    queue.append((nxt, path + [nxt]))

    # === Исследование: движение в случайном направлении на max_steps_this_turn шагов ===
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    random.shuffle(directions)

    for dx, dy in directions:
        path = [list(pos)]
        current = pos
        steps_made = 0

        while steps_made < max_steps_this_turn:
            nx, ny = current[0] + dx, current[1] + dy
            if not (0 <= nx < map_size[0] and 0 <= ny < map_size[1]):
                break
            if (nx, ny) in blocked:
                break
            path.append([nx, ny])
            current = (nx, ny)
            steps_made += 1

        if len(path) > 1:
            return {
                "id": bomber["id"],
                "path": path[:30],
                "bombs": []
            }

    # Остаёмся на месте
    return {
        "id": bomber["id"],
        "path": [list(pos)],
        "bombs": []
    }