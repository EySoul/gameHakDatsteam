import time
import json
import logging
import asyncio
import aiohttp
import heapq
from typing import List, Tuple, Dict, Set, Optional
from collections import defaultdict
from rate_limiter import RateLimiter

domen = "https://games.datsteam.dev"
token = "d4d94a5f-c6aa-49af-b547-13897fb0896a"
prefix = "api"

BOOSTER_ENDPOINT = "booster"
ARENA_ENDPOINT = "arena"
LOGS_ENDPOINT = "logs"
MOVE_ENDPOINT = "move"
ROUNDS_ENDPOINT = "rounds"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

HEADERS = {"X-Auth-Token": token, "Content-Type": "application/json"}
limiter = RateLimiter(max_calls=3, period=1.0)

class GameStrategy:
    def __init__(self):
        self.max_path_length = 30
        self.bomb_timer_threshold = 2.0
        self.view_radius = 5
        
    def manhattan_distance(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
    
    def get_neighbors(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        x, y = pos
        return [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
    
    def is_within_bounds(self, pos: Tuple[int, int], map_size: Tuple[int, int]) -> bool:
        return 0 <= pos[0] < map_size[0] and 0 <= pos[1] < map_size[1]
    
    def get_dangerous_cells(self, bombs: List[dict], obstacles: Set[Tuple[int, int]], 
                           walls: Set[Tuple[int, int]], map_size: Tuple[int, int]) -> Set[Tuple[int, int]]:
        """Возвращает опасные клетки от бомб с малым таймером"""
        dangerous = set()
        
        for bomb in bombs:
            # Считаем опасными только бомбы с малым таймером
            if bomb.get('timer', 10) > self.bomb_timer_threshold:
                continue
                
            x, y = bomb['pos']
            r = bomb.get('range', 1)
            
            # Добавляем клетку самой бомбы
            dangerous.add((x, y))
            
            # Проверяем четыре направления взрыва
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                for step in range(1, r + 1):
                    nx, ny = x + dx * step, y + dy * step
                    
                    if not self.is_within_bounds((nx, ny), map_size):
                        break
                    
                    dangerous.add((nx, ny))
                    
                    # Если на пути стена или препятствие - луч останавливается
                    if (nx, ny) in walls or (nx, ny) in obstacles:
                        break
                        
        return dangerous
    
    def get_passable_cells(self, bomber: dict, map_size: Tuple[int, int], 
                          obstacles: Set[Tuple[int, int]], walls: Set[Tuple[int, int]],
                          bombs: List[dict]) -> Set[Tuple[int, int]]:
        """Определяет проходимые клетки для данного юнита"""
        passable = set()
        
        for x in range(map_size[0]):
            for y in range(map_size[1]):
                cell = (x, y)
                
                # Стены всегда непроходимы
                if cell in walls:
                    continue
                
                # Проверяем препятствия (если нет улучшения)
                if cell in obstacles and not bomber.get('can_pass_obstacles', False):
                    continue
                
                # Проверяем бомбы (если нет улучшения)
                bomb_on_cell = any(tuple(b['pos']) == cell for b in bombs)
                if bomb_on_cell and not bomber.get('can_pass_bombs', False):
                    continue
                
                passable.add(cell)
                
        return passable
    
    def a_star(self, start: Tuple[int, int], goal: Tuple[int, int], 
               passable: Set[Tuple[int, int]], max_steps: int = None) -> Optional[List[Tuple[int, int]]]:
        """Алгоритм A* для поиска пути"""
        if start not in passable or goal not in passable:
            return None
            
        if max_steps is None:
            max_steps = self.max_path_length
            
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
    
    def find_best_target(self, bomber_pos: Tuple[int, int], targets: List[Tuple[int, int]], 
                        dangerous_cells: Set[Tuple[int, int]], passable_cells: Set[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        """Находит лучшую цель для атаки"""
        best_target = None
        min_dist = float('inf')
        
        for target in targets:
            dist = self.manhattan_distance(bomber_pos, target)
            if dist < min_dist and target in passable_cells and target not in dangerous_cells:
                min_dist = dist
                best_target = target
                
        return best_target
    
    def plan_bomber_action(self, bomber: dict, arena_data: dict) -> dict:
        """Планирует действие для одного юнита"""
        pos = tuple(bomber['pos'])
        map_size = tuple(arena_data['map_size'])
        
        # Преобразуем объекты в множества
        obstacles = set(tuple(o) for o in arena_data['arena']['obstacles'])
        walls = set(tuple(w) for w in arena_data['arena']['walls'])
        bombs = arena_data['arena']['bombs']
        enemies = [tuple(e['pos']) for e in arena_data['enemies']]
        mobs = [tuple(m['pos']) for m in arena_data.get('mobs', [])]
        
        # Определяем опасные клетки
        dangerous_cells = self.get_dangerous_cells(bombs, obstacles, walls, map_size)
        
        # Добавляем клетки с мобами как опасные
        for mob_pos in mobs:
            dangerous_cells.add(mob_pos)
        
        # Определяем проходимые клетки
        passable_cells = self.get_passable_cells(bomber, map_size, obstacles, walls, bombs)
        
        # Если текущая клетка опасна - срочно уходим
        if pos in dangerous_cells:
            safe_cells = passable_cells - dangerous_cells
            if safe_cells:
                nearest_safe = min(safe_cells, key=lambda c: self.manhattan_distance(pos, c))
                path = self.a_star(pos, nearest_safe, passable_cells, max_steps=10)
                if path:
                    return {
                        'id': bomber['id'],
                        'path': [list(p) for p in path],
                        'bombs': []
                    }
        
        # Ищем цели для атаки
        targets = list(obstacles) + enemies
        target = self.find_best_target(pos, targets, dangerous_cells, passable_cells)
        
        if target and bomber.get('bombs_available', 0) > 0:
            # Пытаемся подойти к цели и поставить бомбу
            safe_passable = passable_cells - dangerous_cells
            path_to_target = self.a_star(pos, target, safe_passable)
            
            if path_to_target:
                # Ищем клетку для установки бомбы рядом с целью
                bomb_cell = None
                for neighbor in self.get_neighbors(target):
                    if neighbor in safe_passable:
                        bomb_cell = neighbor
                        break
                
                if bomb_cell:
                    # Пытаемся уйти от бомбы после установки
                    safe_after_bomb = safe_passable - {bomb_cell}
                    if safe_after_bomb:
                        safe_target = min(safe_after_bomb, key=lambda c: self.manhattan_distance(bomb_cell, c))
                        escape_path = self.a_star(bomb_cell, safe_target, safe_after_bomb, max_steps=15)
                        
                        if escape_path:
                            full_path = path_to_target + [bomb_cell] + escape_path
                            return {
                                'id': bomber['id'],
                                'path': [list(p) for p in full_path[:self.max_path_length]],
                                'bombs': [list(bomb_cell)]
                            }
        
        # Если не нашли цель или нельзя поставить бомбу, идем в безопасное место
        safe_cells = passable_cells - dangerous_cells
        if safe_cells:
            # Ищем ближайшую безопасную клетку с препятствием для атаки
            best_safe = None
            min_dist = float('inf')
            
            for cell in safe_cells:
                dist = self.manhattan_distance(pos, cell)
                # Предпочитаем клетки рядом с препятствиями
                for neighbor in self.get_neighbors(cell):
                    if neighbor in obstacles:
                        if dist < min_dist:
                            min_dist = dist
                            best_safe = cell
                        break
            
            if not best_safe:
                best_safe = min(safe_cells, key=lambda c: self.manhattan_distance(pos, c))
            
            path = self.a_star(pos, best_safe, safe_cells)
            if path:
                return {
                    'id': bomber['id'],
                    'path': [list(p) for p in path[:self.max_path_length]],
                    'bombs': []
                }
        
        # Если ничего не найдено, стоим на месте
        return {
            'id': bomber['id'],
            'path': [list(pos)],
            'bombs': []
        }
    
    def generate_commands(self, arena_data: dict) -> dict:
        """Генерирует команды для всех юнитов"""
        commands = []
        
        for bomber in arena_data.get('bombers', []):
            if bomber.get('alive', False) and bomber.get('can_move', False):
                command = self.plan_bomber_action(bomber, arena_data)
                commands.append(command)
        
        return {'bombers': commands}

# Создаем экземпляр стратегии
strategy = GameStrategy()

# Заменяем функцию generate_bomber_commands на нашу стратегию
def generate_bomber_commands(arena_data: dict) -> dict:
    return strategy.generate_commands(arena_data)

# Существующие асинхронные функции API остаются без изменений
async def get_arena_async():
    await limiter.wait()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{domen}/{prefix}/{ARENA_ENDPOINT}", headers=HEADERS) as response:
                response.raise_for_status()
                data = await response.json()
                logging.info(f"Я из {ARENA_ENDPOINT}")
                return data
        except aiohttp.ClientError as e:
            logging.error(f"Асинхронная ошибка {ARENA_ENDPOINT}: {e}")
            return None

async def get_booster_async():
    await limiter.wait()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{domen}/{prefix}/{BOOSTER_ENDPOINT}", headers=HEADERS) as response:
                response.raise_for_status()
                data = await response.json()
                logging.info(f"Я из {BOOSTER_ENDPOINT}")
                return data
        except aiohttp.ClientError as e:
            logging.error(f"Асинхронная ошибка {BOOSTER_ENDPOINT}: {e}")
            return None

async def improve_booster_async(booster: str):
    payload = {"booster": booster}
    await limiter.wait()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{domen}/{prefix}/{BOOSTER_ENDPOINT}", 
                headers=HEADERS,
                json=payload
            ) as response:
                response_data = await response.json()
                logging.info(f"Я из {BOOSTER_ENDPOINT} Ответ: {response_data}")
        except aiohttp.ClientError as e:
            logging.error(f"Ошибка в {BOOSTER_ENDPOINT} при '{booster}': {str(e)}")
            return None

async def get_logs_async():
    await limiter.wait()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{domen}/{prefix}/{LOGS_ENDPOINT}", headers=HEADERS) as response:
                response.raise_for_status()
                data = await response.json()
                logging.info(f"Я из {LOGS_ENDPOINT}")
                return data
        except aiohttp.ClientError as e:
            logging.error(f"Асинхронная ошибка {LOGS_ENDPOINT}: {e}")
            return None

async def move_async(move_data: dict):
    '''
        Передаваемый формат \n
        {
            "bombers": [
                {
                    "bombs": [
                        [
                            0
                        ]
                    ],
                    "id": "string",
                    "path": [
                        [
                            0
                        ]
                    ]
                }
            ]
        }
    '''
    await limiter.wait()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{domen}/{prefix}/{MOVE_ENDPOINT}", 
                headers=HEADERS,
                json=move_data
            ) as response:
                response_data = await response.json()
                logging.info(f"Я из {MOVE_ENDPOINT} Ответ: {response_data}")    
        except aiohttp.ClientError as e:
            logging.error(f"Ошибка в {MOVE_ENDPOINT} при '{move_data}': {str(e)}")
            return None

async def get_rounds_async():
    await limiter.wait()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{domen}/{prefix}/{ROUNDS_ENDPOINT}", headers=HEADERS) as response:
                response.raise_for_status()
                data = await response.json()
                logging.info(f"Я из {ROUNDS_ENDPOINT}")
                return data
        except aiohttp.ClientError as e:
            logging.error(f"Асинхронная ошибка {ROUNDS_ENDPOINT}: {e}")
            return None

if __name__ == "__main__":
    async def main():
        logger = logging.getLogger(__name__)
        logger.info("🚀 Запуск игрового цикла с улучшенной стратегией")
        last_booster_time = 0
        booster_interval = 90  # секунды между применением бустеров
        
        # Приоритеты бустеров
        booster_priority = [
            "bomb_range",    # Увеличение радиуса бомбы
            "bomb_count",    # Увеличение количества бомб
            "speed",         # Увеличение скорости
            "armor",         # Броня
            "vision",        # Увеличение обзора
        ]
        
        try:
            while True:
                try:
                    # 1. Получаем все необходимые данные параллельно
                    logger.info("📡 Запрос данных об арене и бустерах")
                    arena_data, booster_data = await asyncio.gather(
                        get_arena_async(),
                        get_booster_async()
                    )
                    
                    if not arena_data:
                        logger.warning("❌ Не удалось получить данные арены")
                        await asyncio.sleep(1.0)
                        continue
                    
                    # 2. Решение о применении бустера
                    current_time = time.time()
                    if current_time - last_booster_time > booster_interval and booster_data:
                        logger.info("🎁 Принятие решения об улучшении")
                        if booster_data.get("available_boosters"):
                            # Выбираем бустер по приоритету
                            for booster in booster_priority:
                                if booster in booster_data["available_boosters"]:
                                    logger.info(f"🌟 Применение бустера: {booster}")
                                    await improve_booster_async(booster)
                                    last_booster_time = current_time
                                    break
                    
                    # 3. Генерация и отправка стратегических команд
                    logger.info("🤖 Генерация стратегических команд")
                    move_commands = generate_bomber_commands(arena_data)
                    
                    if move_commands and move_commands.get("bombers"):
                        alive_count = len(move_commands['bombers'])
                        logger.info(f"🎯 Отправка команд для {alive_count} юнитов")
                        await move_async(move_commands)
                    
                    # 4. Информационное логирование
                    raw_score = arena_data.get("raw_score", 0)
                    alive_bombers = sum(1 for b in arena_data.get("bombers", []) if b.get("alive"))
                    enemies_count = len(arena_data.get("enemies", []))
                    obstacles_count = len(arena_data.get("arena", {}).get("obstacles", []))
                    
                    logger.info(f"📊 Статистика: Очки={raw_score}, Юниты={alive_bombers}/6, "
                               f"Враги={enemies_count}, Препятствия={obstacles_count}")
                    
                    # 5. Небольшая задержка перед следующим циклом
                    await asyncio.sleep(0.1)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.exception(f"💥 Ошибка в цикле: {str(e)}")
                    await asyncio.sleep(1.0)
        
        except KeyboardInterrupt:
            logger.info("👋 Игра остановлена пользователем")
        finally:
            logger.info("✅ Игровой цикл завершен")

    asyncio.run(main())