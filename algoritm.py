import random
from collections import deque
from typing import List, Tuple, Optional, Dict, Any




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


def find_bomb_targets(arena: dict, map_size: tuple, bomb_range: int = 1) -> list:
    """
    Находит все позиции для бомб, из которых можно уничтожить ≥1 препятствие.
    Учитывает, что луч взрыва останавливается на первом препятствии.
    Исключает дубликаты: если два положения уничтожают один и тот же набор препятствий — оставляет только одно.
    """
    obstacles = set(tuple(o) for o in arena["obstacles"])
    if not obstacles:
        return []

    width, height = map_size
    targets = []
    seen_destroyed_sets = set()

    for x in range(width):
        for y in range(height):
            destroyed = set()

            # Четыре направления: вверх, вниз, влево, вправо
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                # Идём по лучу до bomb_range
                for step in range(1, bomb_range + 1):
                    cell = (x + dx * step, y + dy * step)
                    if cell in obstacles:
                        destroyed.add(cell)
                        break  # ← луч останавливается на первом препятствии!

            if not destroyed:
                continue

            # Ограничиваем до 4 препятствий (максимум 10 очков)
            destroyed_frozen = frozenset(list(destroyed)[:4])

            # Пропускаем, если такой набор уже обрабатывался
            if destroyed_frozen in seen_destroyed_sets:
                continue
            seen_destroyed_sets.add(destroyed_frozen)

            # Считаем очки: 1 + 2 + 3 + 4 = 10 (но не больше, чем препятствий)
            n = len(destroyed_frozen)
            score = n * (n + 1) // 2  # сумма 1..n

            targets.append({
                "pos": (x, y),
                "score": score,
                "destroyed": destroyed_frozen
            })

    # Сортируем по убыванию полезности
    return sorted(targets, key=lambda t: t["score"], reverse=True)

def assign_tasks_to_bombers(bombers: list, targets: list, map_size: tuple) -> dict:
    """
    Возвращает: {bomber_id: {"type": "bomb"|"explore", "target": (x, y)}}
    """
    alive_bombers = [b for b in bombers if b["alive"]]
    if not alive_bombers:
        return {}

    assignments = {}
    target_positions = [t["pos"] for t in targets]
    used_targets = set()

    # 1. Назначаем цели юнитам (по одному на цель)
    for bomber in sorted(alive_bombers, key=lambda b: b["id"]):
        if not target_positions:
            break
        # Ближайшая свободная цель
        bomber_pos = tuple(bomber["pos"])
        best = min(
            [t for t in target_positions if t not in used_targets],
            key=lambda t: abs(t[0] - bomber_pos[0]) + abs(t[1] - bomber_pos[1]),
            default=None
        )
        if best:
            used_targets.add(best)
            assignments[bomber["id"]] = {"type": "bomb", "target": best}
            target_positions.remove(best)

    # 2. Остальные идут на разведку
    for bomber in alive_bombers:
        if bomber["id"] not in assignments:
            # Выбираем случайную точку в неизведанной зоне
            # (пока просто случайная точка на карте — можно улучшить)
            import random
            x = random.randint(0, map_size[0] - 1)
            y = random.randint(0, map_size[1] - 1)
            assignments[bomber["id"]] = {"type": "explore", "target": (x, y)}

    return assignments


def get_exploration_target(bomber_pos: tuple, map_size: tuple, obstacles: set) -> tuple:
    """
    Возвращает цель для разведки: угол или край карты с минимальной плотностью препятствий.
    """
    width, height = map_size
    corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]

    # Оцениваем каждый угол: чем дальше от препятствий — тем лучше
    best_corner = corners[0]
    best_score = -1

    for corner in corners:
        # Среднее расстояние до препятствий (или просто расстояние до ближайшего)
        if obstacles:
            min_dist = min(abs(corner[0] - ox) + abs(corner[1] - oy) for (ox, oy) in obstacles)
        else:
            min_dist = width + height
        # Плюс: расстояние от текущего юнита (чтобы не уходить слишком далеко)
        dist_from_bomber = abs(corner[0] - bomber_pos[0]) + abs(corner[1] - bomber_pos[1])
        score = min_dist - dist_from_bomber * 0.1  # чуть штрафуем за дальность
        if score > best_score:
            best_score = score
            best_corner = corner

    return best_corner

def find_path(start: tuple, goal: tuple, blocked: set, map_size: tuple, max_len: int = 30) -> list:
    """Возвращает путь как список координат или пустой список, если путь невозможен."""
    from collections import deque
    if start == goal:
        return [start]

    queue = deque([(start, [start])])
    visited = {start}
    width, height = map_size

    while queue:
        cur, path = queue.popleft()
        if cur == goal:
            return path[:max_len]
        if len(path) >= max_len:
            continue

        x, y = cur
        for nx, ny in [(x+1,y), (x-1,y), (x,y+1), (x,y-1)]:
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            nxt = (nx, ny)
            if nxt in visited or nxt in blocked:
                continue
            visited.add(nxt)
            queue.append((nxt, path + [nxt]))
    return []

def generate_command(bomber: dict, task: dict, arena: dict, map_size: tuple, dt_seconds: float = 0.5) -> dict:
    pos = tuple(bomber["pos"])
    target = task["target"]

    # Определяем непроходимые клетки
    walls = set(tuple(w) for w in arena["walls"])
    bombs_set = set()
    for b in arena["bombs"]:
        p = tuple(b["pos"]) if isinstance(b, dict) else tuple(b)
        bombs_set.add(p)
    blocked = set(walls)
    if not bomber.get("can_pass_bombs", False):
        blocked.update(bombs_set)

    if task["type"] == "bomb":
        path = find_path(pos, target, blocked, map_size)
        if not path:
            path = [pos]  # остаться на месте
        return {
            "id": bomber["id"],
            "path": [list(p) for p in path[:30]],
            "bombs": [list(target)] if target in path else []
        }

    else:  # explore
        # Идём в сторону цели, но не обязательно до конца
        max_steps = max(1, int(bomber.get("speed", 2) * dt_seconds))
        path = [pos]
        cur = pos
        dx = 1 if target[0] > cur[0] else -1 if target[0] < cur[0] else 0
        dy = 1 if target[1] > cur[1] else -1 if target[1] < cur[1] else 0

        for _ in range(max_steps):
            # Сначала по X, потом по Y (или наоборот — не критично)
            if dx != 0:
                nxt = (cur[0] + dx, cur[1])
                if 0 <= nxt[0] < map_size[0] and nxt not in blocked:
                    path.append(nxt)
                    cur = nxt
                    continue
            if dy != 0:
                nxt = (cur[0], cur[1] + dy)
                if 0 <= nxt[1] < map_size[1] and nxt not in blocked:
                    path.append(nxt)
                    cur = nxt
        return {
            "id": bomber["id"],
            "path": [list(p) for p in path[:30]],
            "bombs": []
        }

def generate_all_bomber_commands(bombers: list, arena: dict, map_size: tuple, dt_seconds: float = 0.5) -> list:
    # 1. Найти все цели (используем средний bomb_range, или можно для каждого отдельно)
    avg_bomb_range = max(b.get("bomb_range", 1) for b in bombers if b["alive"]) if bombers else 1
    targets = find_bomb_targets(arena, map_size, bomb_range=avg_bomb_range)

    # 2. Назначить задачи
    tasks = assign_tasks_to_bombers(bombers, targets, map_size)

    # 3. Сгенерировать команды
    commands = []
    for bomber in bombers:
        if not bomber["alive"]:
            continue
        task = tasks.get(bomber["id"])
        if task:
            cmd = generate_command(bomber, task, arena, map_size, dt_seconds)
            commands.append(cmd)
    return commands