import aiohttp
import asyncio
import logging
from typing import List, Tuple, Dict, Set, Optional
import heapq
from collections import defaultdict

# Константы
SPEED = 2  # клеток в секунду
BOMB_TIMER = 8  # секунд до взрыва
BOMB_RANGE = 1  # начальный радиус взрыва
SAFE_DISTANCE_FROM_BOMB = 2  # минимальное расстояние от бомбы для безопасности
MAX_PATH_LENGTH = 30  # максимальная длина пути
REQUEST_LIMIT = 3  # максимальное количество запросов в секунду

class GameStrategy:
    def __init__(self, domen: str, prefix: str, headers: dict):
        self.domen = domen
        self.prefix = prefix
        self.headers = headers
        self.limiter = asyncio.Semaphore(REQUEST_LIMIT)

    async def get_arena(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.domen}/{self.prefix}/arena", headers=self.headers) as resp:
                return await resp.json()

    async def move(self, move_data: dict):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.domen}/{self.prefix}/move", headers=self.headers, json=move_data) as resp:
                return await resp.json()

    def manhattan_distance(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def get_neighbors(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        x, y = pos
        return [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]

    def is_within_bounds(self, pos: Tuple[int, int], map_size: Tuple[int, int]) -> bool:
        return 0 <= pos[0] < map_size[0] and 0 <= pos[1] < map_size[1]

    def get_dangerous_cells(self, bombs: List[dict], obstacles: Set[Tuple[int, int]], walls: Set[Tuple[int, int]], map_size: Tuple[int, int], threshold: float = 2.0) -> Set[Tuple[int, int]]:
        dangerous = set()
        for bomb in bombs:
            if bomb['timer'] >= threshold:
                continue
            x, y = bomb['pos']
            r = bomb['range']
            # Проверяем четыре направления
            for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                for step in range(1, r+1):
                    nx, ny = x + dx*step, y + dy*step
                    if (nx, ny) in walls:
                        break
                    if not self.is_within_bounds((nx, ny), map_size):
                        break
                    dangerous.add((nx, ny))
                    if (nx, ny) in obstacles:
                        break
            dangerous.add((x, y))
        return dangerous

    def a_star(self, start: Tuple[int, int], goal: Tuple[int, int], passable: Set[Tuple[int, int]], max_steps: int = MAX_PATH_LENGTH) -> Optional[List[Tuple[int, int]]]:
        if start not in passable or goal not in passable:
            return None

        open_set = []
        heapq.heappush(open_set, (0, start))
        came_from = {}
        g_score = {start: 0}
        f_score = {start: self.manhattan_distance(start, goal)}

        while open_set:
            _, current = heapq.heappop(open_set)
            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.reverse()
                return path[:max_steps]

            for neighbor in self.get_neighbors(current):
                if neighbor not in passable:
                    continue
                tentative_g = g_score[current] + 1
                if tentative_g >= max_steps:
                    continue
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + self.manhattan_distance(neighbor, goal)
                    f_score[neighbor] = f
                    heapq.heappush(open_set, (f, neighbor))
        return None

    def find_best_target(self, bomber_pos: Tuple[int, int], targets: List[Tuple[int, int]], dangerous_cells: Set[Tuple[int, int]], passable_cells: Set[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        best_target = None
        min_dist = float('inf')
        for target in targets:
            dist = self.manhattan_distance(bomber_pos, target)
            if dist < min_dist and target in passable_cells and target not in dangerous_cells:
                min_dist = dist
                best_target = target
        return best_target

    def plan_bomber_path(self, bomber: dict, arena: dict, dangerous_cells: Set[Tuple[int, int]]) -> Dict:
        pos = tuple(bomber['pos'])
        map_size = tuple(arena['map_size'])
        obstacles = set(tuple(o) for o in arena['obstacles'])
        walls = set(tuple(w) for w in arena['walls'])
        enemies = [tuple(e['pos']) for e in arena['enemies']]
        bombs = arena['bombs']

        # Проходимые клетки
        passable_cells = set()
        for x in range(map_size[0]):
            for y in range(map_size[1]):
                cell = (x, y)
                if cell in walls:
                    continue
                if cell in obstacles and not bomber.get('can_pass_obstacles', False):
                    continue
                if any(cell == tuple(b['pos']) for b in bombs) and not bomber.get('can_pass_bombs', False):
                    continue
                passable_cells.add(cell)

        # Цели: препятствия и враги
        targets = list(obstacles) + enemies
        target = self.find_best_target(pos, targets, dangerous_cells, passable_cells)

        if target:
            # Пытаемся подойти к цели
            path = self.a_star(pos, target, passable_cells - dangerous_cells)
            if path:
                # Проверяем, можно ли поставить бомбу рядом с целью
                bomb_placement = None
                for neighbor in self.get_neighbors(target):
                    if neighbor in passable_cells and neighbor not in dangerous_cells:
                        bomb_placement = neighbor
                        break

                if bomb_placement and bomber['bombs_available'] > 0:
                    # Пытаемся уйти от бомбы после установки
                    safe_cells = passable_cells - dangerous_cells - {bomb_placement}
                    safe_path = self.a_star(bomb_placement, next(iter(safe_cells), None), safe_cells, max_steps=16)
                    if safe_path:
                        full_path = path + [bomb_placement] + safe_path
                        return {
                            'id': bomber['id'],
                            'path': full_path[:MAX_PATH_LENGTH],
                            'bombs': [list(bomb_placement)]
                        }

        # Если не нашли цель или нельзя поставить бомбу, идём в безопасное место
        safe_cells = passable_cells - dangerous_cells
        if safe_cells:
            safe_target = min(safe_cells, key=lambda c: self.manhattan_distance(pos, c))
            path = self.a_star(pos, safe_target, safe_cells)
            if path:
                return {
                    'id': bomber['id'],
                    'path': path[:MAX_PATH_LENGTH],
                    'bombs': []
                }

        # Если ничего не найдено, стоим на месте
        return {
            'id': bomber['id'],
            'path': [list(pos)],
            'bombs': []
        }

    async def make_strategic_move(self):
        arena_data = await self.get_arena()
        if not arena_data:
            return

        map_size = tuple(arena_data['map_size'])
        bombs = arena_data['arena']['bombs']
        obstacles = set(tuple(o) for o in arena_data['arena']['obstacles'])
        walls = set(tuple(w) for w in arena_data['arena']['walls'])

        # Опасные клетки от бомб с таймером < 2 секунды
        dangerous_cells = self.get_dangerous_cells(bombs, obstacles, walls, map_size, threshold=2.0)

        move_commands = []
        for bomber in arena_data['bombers']:
            if bomber['alive'] and bomber['can_move']:
                command = self.plan_bomber_path(bomber, arena_data, dangerous_cells)
                move_commands.append(command)

        move_data = {
            'bombers': move_commands
        }

        await self.move(move_data)


async def main():
    domen = "https://games.datsteam.dev"
    prefix = "api"
    token = "d4d94a5f-c6aa-49af-b547-13897fb0896a"
    HEADERS = {"X-Auth-Token": token, "Content-Type": "application/json"}

    strategy = GameStrategy(domen, prefix, HEADERS)
    await strategy.make_strategic_move()

if __name__ == "__main__":
    asyncio.run(main())