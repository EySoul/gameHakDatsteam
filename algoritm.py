import random
from collections import deque
from typing import List, Tuple, Optional, Dict, Any


def generate_all_commands(bombers, arena, map_size, dt_seconds=0.5):
    """
    Генерирует список команд для всех живых юнитов, распределяя цели.
    Возвращает список команд в формате:
    [{"id": ..., "path": [...], "bombs": [...]}, ...]
    """
    if not bombers:
        return []

    # Получаем все препятствия
    obstacles = [tuple(o) for o in arena["obstacles"]]
    if not obstacles:
        # Если нет препятствий — все исследуют
        return [
            _explore_randomly(b, _get_blocked(arena, b), map_size, b.get("speed", 2), dt_seconds)
            for b in bombers if b["alive"]
        ]

    # Назначаем зоны
    zones = assign_zones([b for b in bombers if b["alive"]], map_size)
    alive_bombers = [b for b in bombers if b["alive"]]
    commands = []

    # Для каждого юнита — своя зона
    for i, bomber in enumerate(alive_bombers):
        x_min, x_max = zones[i] if i < len(zones) else (0, map_size[0])

        # Фильтруем препятствия только в зоне
        zone_obstacles = [obs for obs in obstacles if x_min <= obs[0] < x_max]

        if not zone_obstacles:
            # Если в зоне пусто — идём в ближайшую непустую зону или исследуем
            cmd = _explore_randomly(bomber, _get_blocked(arena, bomber), map_size, bomber.get("speed", 2), dt_seconds)
        else:
            # Создаём временный arena только с зоной
            zone_arena = arena.copy()
            zone_arena["obstacles"] = zone_obstacles
            cmd = move_to_chain_bombs(bomber, zone_arena, map_size, dt_seconds)

        if cmd:
            commands.append(cmd)

    return commands

def move_toward_obstacle_or_explore_with_speed(
    bomber: dict,
    arena: dict,
    map_size: tuple,
    dt_seconds: float = 0.5
) -> dict:
    """
    Генерирует команду для юнита на основе его текущих атрибутов (взятых из /arena).
    """
    if not bomber["alive"]:
        return None

    pos = tuple(bomber["pos"])
    speed = bomber.get("speed", 2)  # уже есть в bomber!
    max_steps = max(1, int(speed * dt_seconds))

    # Непроходимые клетки
    walls = set(tuple(w) for w in arena["walls"])
    bombs_set = set()
    for b in arena["bombs"]:
        if isinstance(b, dict):
            bombs_set.add(tuple(b["pos"]))
        else:
            bombs_set.add(tuple(b))

    blocked = set(walls)
    if not bomber.get("can_pass_bombs", False):
        blocked.update(bombs_set)

    # Препятствия в радиусе 5
    obstacles = [tuple(o) for o in arena["obstacles"]]
    nearby_obstacles = []
    for obs in obstacles:
        dx = obs[0] - pos[0]
        dy = obs[1] - pos[1]
        if dx*dx + dy*dy <= 25:
            nearby_obstacles.append(obs)

    from collections import deque

    if nearby_obstacles:
        # Ищем клетку рядом с препятствием
        candidates = []
        for obs in nearby_obstacles:
            for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
                cell = (obs[0] + dx, obs[1] + dy)
                if 0 <= cell[0] < map_size[0] and 0 <= cell[1] < map_size[1]:
                    if cell not in blocked:
                        candidates.append(cell)
        if candidates:
            target = min(candidates, key=lambda c: abs(c[0]-pos[0]) + abs(c[1]-pos[1]))
            # BFS
            queue = deque([(pos, [pos])])
            visited = {pos}
            while queue:
                cur, path = queue.popleft()
                if cur == target:
                    final_path = [list(p) for p in path[:30]]
                    return {
                        "id": bomber["id"],
                        "path": final_path,
                        "bombs": [final_path[-1]]
                    }
                if len(path) >= 30:
                    continue
                x, y = cur
                for nx, ny in [(x+1,y), (x-1,y), (x,y+1), (x,y-1)]:
                    nxt = (nx, ny)
                    if 0 <= nx < map_size[0] and 0 <= ny < map_size[1] and nxt not in visited and nxt not in blocked:
                        visited.add(nxt)
                        queue.append((nxt, path + [nxt]))

    # Исследование
    directions = [(1,0), (-1,0), (0,1), (0,-1)]
    random.shuffle(directions)
    for dx, dy in directions:
        path = [list(pos)]
        cur = pos
        for _ in range(max_steps):
            nx, ny = cur[0] + dx, cur[1] + dy
            if not (0 <= nx < map_size[0] and 0 <= ny < map_size[1]):
                break
            if (nx, ny) in blocked:
                break
            path.append([nx, ny])
            cur = (nx, ny)
        if len(path) > 1:
            return {
                "id": bomber["id"],
                "path": path[:30],
                "bombs": []
            }

    return {
        "id": bomber["id"],
        "path": [list(pos)],
        "bombs": []
    }

def assign_zones(bombers, map_size):
    """Возвращает список зон (границы по X) для каждого юнита."""
    width = map_size[0]
    zone_width = width // len(bombers) if bombers else 1
    zones = []
    for i in range(len(bombers)):
        x_min = i * zone_width
        x_max = (i + 1) * zone_width if i < len(bombers) - 1 else width
        zones.append((x_min, x_max))
    return zones