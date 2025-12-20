import asyncio
import queue
import threading
import time
import logging
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any

import pygame

# ======================
# 1. RATE LIMITER
# ======================
class RateLimiter:
    """Контроллер частоты запросов к API (3 запроса в секунду)"""
    def __init__(self, max_requests=3, period=1.0):
        self.max_requests = max_requests
        self.period = period
        self.request_timestamps = deque()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Ожидание разрешения на отправку запроса"""
        async with self._lock:
            now = time.time()
            # Удаляем старые записи
            while self.request_timestamps and now - self.request_timestamps[0] > self.period:
                self.request_timestamps.popleft()
            
            # Если лимит исчерпан - ждем
            if len(self.request_timestamps) >= self.max_requests:
                sleep_time = self.period - (now - self.request_timestamps[0]) + 0.05
                logging.debug(f"лимит запросов достигнут. ожидание {sleep_time:.2f}с")
                await asyncio.sleep(sleep_time)
                # После ожидания очищаем старые записи снова
                now = time.time()
                while self.request_timestamps and now - self.request_timestamps[0] > self.period:
                    self.request_timestamps.popleft()
            
            self.request_timestamps.append(now)
    
    def get_next_available_time(self):
        """Время следующего доступного запроса"""
        now = time.time()
        while self.request_timestamps and now - self.request_timestamps[0] > self.period:
            self.request_timestamps.popleft()
        
        if len(self.request_timestamps) < self.max_requests:
            return now
        return self.request_timestamps[0] + self.period


# ======================
# 2. МОДЕЛИ ДАННЫХ
# ======================
@dataclass
class UnitSnapshot:
    """Снимок состояния юнита"""
    unit_id: str
    position: Tuple[int, int]
    alive: bool
    armor: int
    bombs_available: int
    can_move: bool
    safe_time: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_api(cls, api_: dict) -> 'UnitSnapshot':
        return cls(
            unit_id=api_['id'],
            position=(api_['pos'][0], api_['pos'][1]),
            alive=api_['alive'],
            armor=api_['armor'],
            bombs_available=api_['bombs_available'],
            can_move=api_['can_move'],
            safe_time=api_['safe_time']
        )

@dataclass
class ArenaSnapshot:
    """Снимок состояния арены"""
    map_size: Tuple[int, int]
    obstacles: List[Tuple[int, int]]
    walls: List[Tuple[int, int]]
    bombs: List[dict]
    enemies: List[dict]
    mobs: List[dict]
    raw_score: int
    round_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_api(cls, api_: dict) -> 'ArenaSnapshot':
        arena_data = api_['arena']
        return cls(
            map_size=(api_['map_size'][0], api_['map_size'][1]),
            obstacles=[(pos[0], pos[1]) for pos in arena_data['obstacles']],
            walls=[(pos[0], pos[1]) for pos in arena_data['walls']],
            bombs=arena_data['bombs'],
            enemies=api_['enemies'],
            mobs=api_['mobs'],
            raw_score=api_['raw_score'],
            round_id=api_['round'],
            timestamp=datetime.utcnow()
        )


# ======================
# 3. МЕНЕДЖЕР СОСТОЯНИЯ
# ======================
class GameStateManager:
    """Управление состоянием игры и историей за 1 секунду"""
    
    def __init__(self):
        self._unit_states: Dict[str, List[UnitSnapshot]] = {}
        self._arena_history: List[ArenaSnapshot] = []
        self._last_update_time: datetime = datetime.min
    
    def update_from_api(self, api_response: dict):
        """Обновление состояния из API"""
        current_time = datetime.utcnow()
        
        # Обновление арены
        arena_snapshot = ArenaSnapshot.from_api(api_response)
        self._arena_history.append(arena_snapshot)
        
        # Очистка старой истории арены
        self._arena_history = [
            snap for snap in self._arena_history
            if (current_time - snap.timestamp).total_seconds() <= 1.0
        ]
        
        # Обновление юнитов
        for bomber_data in api_response['bombers']:
            unit_id = bomber_data['id']
            unit_snapshot = UnitSnapshot.from_api(bomber_data)
            
            if unit_id not in self._unit_states:
                self._unit_states[unit_id] = []
            
            self._unit_states[unit_id].append(unit_snapshot)
            
            # Очистка старой истории юнита
            self._unit_states[unit_id] = [
                snap for snap in self._unit_states[unit_id]
                if (current_time - snap.timestamp).total_seconds() <= 1.0
            ]
        
        self._last_update_time = current_time
    
    def get_current_game_state(self) -> Optional[dict]:
        """Получение текущего состояния для принятия решений"""
        if not self._arena_history:
            return None
        
        current_time = datetime.utcnow()
        current_arena = self._arena_history[-1]
        current_units = {}
        
        for unit_id, history in self._unit_states.items():
            if history:
                current_units[unit_id] = history[-1]
        
        # Анализ перемещений юнитов
        unit_movements = self._analyze_unit_movements()
        
        # ВРЕМЕННОЕ РЕШЕНИЕ (вместо отсутствующего _analyze_bomb_changes)
        bomb_changes = []
        
        return {
            'arena': current_arena,
            'units': current_units,
            'unit_movements': unit_movements,
            'bomb_changes': bomb_changes,
            'time_elapsed': (current_time - self._last_update_time).total_seconds(),
            'is_starting_position': self._check_starting_position(current_units)
        }
    
    def _analyze_unit_movements(self) -> dict:
        """Анализ перемещений юнитов за последнюю секунду"""
        movements = {}
        current_time = datetime.utcnow()
        
        for unit_id, history in self._unit_states.items():
            if len(history) < 2:
                continue
            
            unit_movements = []
            for i in range(1, len(history)):
                prev = history[i-1]
                curr = history[i]
                
                if prev.position != curr.position:
                    unit_movements.append((
                        prev.position,
                        curr.position,
                        curr.timestamp
                    ))
            
            if unit_movements:
                movements[unit_id] = unit_movements
        
        return movements
    
    def _check_starting_position(self, current_units: dict) -> bool:
        """Проверка, находятся ли все юниты в стартовой позиции"""
        if not current_units:
            return False
        
        positions = [unit.position for unit in current_units.values()]
        return len(set(positions)) == 1 and len(positions) >= 5  # Почти все юниты в одной точке


# ======================
# 4. СТРАТЕГИИ
# ======================
class UnitStrategyCoordinator:
    """Координация стратегий для всех юнитов с правильным форматом команд"""
    
    def __init__(self, game_state_manager: GameStateManager):
        self.game_state_manager = game_state_manager
    
    def generate_commands(self) -> dict:
        """Генерация команд в правильном формате для /api/move"""
        game_state = self.game_state_manager.get_current_game_state()
        
        if not game_state:
            return {"bombers": []}
        
        # Стратегия для начальной позиции
        if game_state['is_starting_position']:
            return self._generate_starting_commands(game_state)
        
        # Обычная стратегия
        return self._generate_normal_commands(game_state)
    
    def _generate_starting_commands(self, game_state: dict) -> dict:
        """Специальная стратегия для начальной позиции в правильном формате"""
        units = list(game_state['units'].values())
        if not units:
            return {"bombers": []}
        
        starting_pos = units[0].position
        directions = [
            (1, 0),   # вправо
            (0, 1),   # вниз
            (0, -1),  # вверх
            (-1, 0),  # влево
            (1, 1),   # вправо-вниз
            (1, -1)   # вправо-вверх
        ]
        
        # Правильный формат для API
        commands = {"bombers": []}
        map_size = game_state['arena'].map_size
        
        for i, unit in enumerate(units[:len(directions)]):
            if not unit.alive or not unit.can_move:
                continue
            
            direction = directions[i]
            # Путь движения (максимум 30 точек)
            path = []
            current_pos = list(unit.position)
            
            # Генерируем путь из 2-3 точек в заданном направлении
            for step in range(1, 4):  # Максимум 3 шага
                next_pos = [
                    current_pos[0] + direction[0] * step,
                    current_pos[1] + direction[1] * step
                ]
                
                # Проверка границ карты
                next_pos[0] = max(0, min(map_size[0]-1, next_pos[0]))
                next_pos[1] = max(0, min(map_size[1]-1, next_pos[1]))
                
                path.append(next_pos)
            
            # Координаты для бомб (если нужно)
            bombs = []
            if unit.safe_time > 1000:
                # Ставим бомбу в текущей позиции
                bombs.append(list(unit.position))
            
            # Формируем команду в правильном формате
            bomber_command = {
                "id": unit.unit_id,
                "path": path[:30],  # Ограничение API - максимум 30 точек
                "bombs": bombs
            }
            
            commands["bombers"].append(bomber_command)
        
        return commands
    
    def _generate_normal_commands(self, game_state: dict) -> dict:
        """Обычная стратегия в правильном формате для API"""
        arena = game_state['arena']
        units = game_state['units']
        
        # Правильный формат для API
        commands = {"bombers": []}
        
        for unit_id, unit in units.items():
            if not unit.alive or not unit.can_move:
                continue
            
            # Простая стратегия: двигаемся вправо на 3 клетки
            current_x, current_y = unit.position
            path = [
                [current_x + 1, current_y],
                [current_x + 2, current_y],
                [current_x + 3, current_y]
            ]
            
            # Проверка границ карты
            map_size = arena.map_size
            path = [
                [
                    max(0, min(map_size[0]-1, pos[0])),
                    max(0, min(map_size[1]-1, pos[1]))
                ] for pos in path
            ]
            
            # Бомбы ставим только если есть доступные бомбы и безопасно
            bombs = []
            if unit.bombs_available > 0 and unit.safe_time > 1000:
                bombs.append([current_x, current_y])
            
            # Формируем команду в правильном формате
            bomber_command = {
                "id": unit_id,
                "path": path[:30],  # Ограничение API
                "bombs": bombs
            }
            
            commands["bombers"].append(bomber_command)
        
        return commands


# ======================
# 5. ГЛАВНЫЙ ОРКЕСТРАТОР (ЗДЕСЬ НАХОДИТСЯ game_loop)
# ======================
class GameOrchestrator:
    """Основной оркестратор игры"""
    
    def __init__(self, api_base_url: str, auth_token: str):
        self.api_base_url = api_base_url.rstrip('/')
        self.auth_token = auth_token
        self.game_state_manager = GameStateManager()
        self.strategy_coordinator = UnitStrategyCoordinator(self.game_state_manager)
        self.session = None
        self.rate_limiter = RateLimiter(max_requests=3, period=1.0)  # 3 запроса в секунду
    
    async def __aenter__(self):
        """Создание aiohttp сессии"""
        import aiohttp
        self.session = aiohttp.ClientSession(
            headers={
                "X-Auth-Token": self.auth_token,
                "Content-Type": "application/json"
            },
            timeout=aiohttp.ClientTimeout(total=5)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие сессии"""
        if self.session:
            await self.session.close()
    
    async def get_arena_state(self) -> dict:
        """Получение состояния арены с API"""
        await self.rate_limiter.acquire()
        async with self.session.get(f"{self.api_base_url}/api/arena") as response:
            response.raise_for_status()
            return await response.json()
    async def send_move_commands(self, commands: dict) -> dict:
        """Отправка команд движения на API с правильным форматом"""
        await self.rate_limiter.acquire()
        
        # Валидация формата перед отправкой
        if not self._validate_move_commands(commands):
            logging.error("❌ Неверный формат команд для /api/move")
            return {"error": "invalid_format"}
        
        async with self.session.post(
            f"{self.api_base_url}/api/move",
            json=commands  # aiohttp автоматически сериализует в JSON
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    def _validate_move_commands(self, commands: dict) -> bool:
        """Валидация формата команд перед отправкой"""
        if not isinstance(commands, dict):
            return False
        
        if "bombers" not in commands or not isinstance(commands["bombers"], list):
            return False
        
        for bomber in commands["bombers"]:
            # Проверка обязательных полей
            if "id" not in bomber or "path" not in bomber or "bombs" not in bomber:
                return False
            
            # Проверка типов
            if not isinstance(bomber["id"], str):
                return False
            
            if not isinstance(bomber["path"], list) or not all(
                isinstance(p, list) and len(p) == 2 and all(isinstance(x, int) for x in p)
                for p in bomber["path"]
            ):
                return False
            
            if not isinstance(bomber["bombs"], list) or not all(
                isinstance(b, list) and len(b) == 2 and all(isinstance(x, int) for x in b)
                for b in bomber["bombs"]
            ):
                return False
            
            # Проверка ограничения на 30 точек в пути
            if len(bomber["path"]) > 30:
                logging.warning(f"⚠️ Путь для юнита {bomber['id']} обрезан до 30 точек (было {len(bomber['path'])})")
                bomber["path"] = bomber["path"][:30]
        
        return True
    
    async def _send_safe_commands(self, arena_: dict):
        """Отправка безопасных команд в правильном формате"""
        safe_commands = {"bombers": []}
        
        for bomber in arena_['bombers']:
            if bomber['alive'] and bomber['can_move']:
                # Безопасная команда: остаться на месте (пустой путь)
                safe_command = {
                    "id": bomber['id'],
                    "path": [],  # Пустой путь = остаться на месте
                    "bombs": []  # Не ставить бомбы
                }
                safe_commands["bombers"].append(safe_command)
        
        if safe_commands["bombers"]:
            try:
                await self.rate_limiter.acquire()
                async with self.session.post(
                    f"{self.api_base_url}/api/move",
                    json=safe_commands
                ) as response:
                    response.raise_for_status()
                logging.warning("✅ Отправлены безопасные fallback-команды")
            except Exception as e:
                logging.error(f"❌ Не удалось отправить безопасные команды: {str(e)}")
    
    # ======================
    # ГЛАВНЫЙ ИГРОВОЙ ЦИКЛ (ВОТ ОН!)
    # ======================
    async def game_loop(self):
        """ОСНОВНОЙ ИГРОВОЙ ЦИКЛ - СЮДА ВСЕ ДОБАВЛЯЕТСЯ"""
        try:
            logging.info("🚀 Игровой цикл запущен")
            
            while True:
                current_time = datetime.utcnow()
                
                # === ШАГ 1: Получение состояния арены ===
                try:
                    arena_data = await self.get_arena_state()
                    self.game_state_manager.update_from_api(arena_data)
                    logging.info(f"🎮 Состояние арены обновлено. Очки: {arena_data.get('raw_score', 0)}")
                except Exception as e:
                    logging.error(f"❌ Ошибка при получении состояния арены: {str(e)}")
                    await asyncio.sleep(0.1)
                    continue
                
                # === ШАГ 2: Генерация и отправка команд ===
                commands = self.strategy_coordinator.generate_commands()
                
                if commands["bombers"]:
                    try:
                        result = await self.send_move_commands(commands)
                        logging.info(f"✅ Команды отправлены успешно")
                    except Exception as e:
                        logging.error(f"❌ Ошибка при отправке команд: {str(e)}")
                        await self._send_safe_commands(arena_data)
                
                # === ШАГ 3: Адаптивная задержка ===
                next_request_time = self.rate_limiter.get_next_available_time()
                current_time = time.time()
                
                if next_request_time > current_time:
                    sleep_time = min(0.5, next_request_time - current_time)
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0.05)
                
        except asyncio.CancelledError:
            logging.info("🛑 Игровой цикл остановлен")
        except Exception as e:
            logging.critical(f"💥 Критическая ошибка в игровом цикле: {str(e)}", exc_info=True)
            raise

@dataclass
class UnitState:
    unit_id: str
    position: Tuple[int, int]
    alive: bool
    armor: int
    bombs_available: int
    can_move: bool
    safe_time: int

@dataclass
class GameState:
    map_size: Tuple[int, int]
    obstacles: List[Tuple[int, int]]
    walls: List[Tuple[int, int]]
    bombs: List[Dict]
    enemies: List[Tuple[int, int]]
    mobs: List[Tuple[int, int]]
    bombers: List[UnitState]
    current_time: float

class GameVisualizer:
    """Асинхронная визуализация игрового состояния с помощью pygame"""
    
    def __init__(self, window_width: int = 1200, window_height: int = 800):
        self.window_width = window_width
        self.window_height = window_height
        self.cell_size = 40  # Размер клетки в пикселях
        self.running = False
        self.data_queue = queue.Queue(maxsize=1)  # Ограниченная очередь для передачи состояний
        self.clock = None
        self.screen = None
        self.font = None
        self.selected_unit_index = 0
        
        # Цветовая схема
        self.COLORS = {
            'background': (30, 30, 40),      # Темно-синий фон
            'grid': (60, 60, 80),            # Сетка
            'wall': (80, 80, 90),            # Стены - темно-серые
            'obstacle': (255, 165, 0),       # Препятствия - оранжевые (более контрастные)
            'bomb': (255, 50, 50),           # Бомбы - ярко-красные
            'friendly': (50, 200, 100),      # Дружественные юниты - зеленые
            'enemy': (220, 80, 80),          # Враги - красные с оттенком
            'mob': (150, 50, 220),           # Мобы - фиолетовые
            'visibility': (30, 100, 200, 80), # Область видимости - полупрозрачный синий
            'path': (100, 200, 255, 120),    # Путь движения - полупрозрачный голубой
            'text': (220, 220, 240),         # Текст - светлый
            'highlight': (255, 255, 100),    # Подсветка
            'ui_background': (40, 40, 60, 200), # Фон UI
            'ui_border': (100, 150, 220)     # Граница UI
        }
    
    def start_visualization(self):
        """Запуск визуализации в отдельном потоке"""
        self.running = True
        visualization_thread = threading.Thread(target=self._visualization_loop, daemon=True)
        visualization_thread.start()
        return visualization_thread
    
    def update_game_state(self, game_state: GameState):
        """Обновление состояния игры для визуализации"""
        try:
            # Удаляем старое состояние, если очередь заполнена
            if not self.data_queue.empty():
                self.data_queue.get_nowait()
            self.data_queue.put_nowait(game_state)
        except queue.Full:
            pass  # Игнорируем, если очередь заполнена
    
    def stop_visualization(self):
        """Остановка визуализации"""
        self.running = False
    
    def _init_pygame(self):
        """Инициализация pygame"""
        pygame.init()
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption("DatsJingleBang Visualization")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('arial', 16)
        self.small_font = pygame.font.SysFont('arial', 12)
    
    def _draw_mini_map(self, surface, game_state: GameState, unit: UnitState, position: Tuple[int, int]):
        """Отрисовка мини-карты для одного юнита"""
        if not unit.alive:
            return
        
        # Размер мини-карты (радиус видимости 5 клеток = 11x11 клеток)
        mini_map_size = 11
        mini_width = mini_map_size * self.cell_size
        mini_height = mini_map_size * self.cell_size
        
        # Создание поверхности для мини-карты
        mini_surface = pygame.Surface((mini_width, mini_height))
        mini_surface.fill(self.COLORS['background'])
        
        # Центр мини-карты - позиция юнита
        center_x, center_y = unit.position
        min_x = max(0, center_x - 5)
        max_x = min(game_state.map_size[0] - 1, center_x + 5)
        min_y = max(0, center_y - 5)
        max_y = min(game_state.map_size[1] - 1, center_y + 5)
        
        # Отрисовка сетки
        for x in range(mini_map_size + 1):
            pygame.draw.line(mini_surface, self.COLORS['grid'],
                           (x * self.cell_size, 0),
                           (x * self.cell_size, mini_height), 1)
        for y in range(mini_map_size + 1):
            pygame.draw.line(mini_surface, self.COLORS['grid'],
                           (0, y * self.cell_size),
                           (mini_width, y * self.cell_size), 1)
        
        # Функция для преобразования глобальных координат в локальные для мини-карты
        def to_local_coord(global_pos: Tuple[int, int]) -> Tuple[int, int]:
            local_x = global_pos[0] - min_x
            local_y = global_pos[1] - min_y
            return (local_x, local_y)
        
        # Отрисовка стен
        for wall in game_state.walls:
            if min_x <= wall[0] <= max_x and min_y <= wall[1] <= max_y:
                lx, ly = to_local_coord(wall)
                pygame.draw.rect(mini_surface, self.COLORS['wall'],
                               (lx * self.cell_size, ly * self.cell_size,
                                self.cell_size, self.cell_size))
        
        # Отрисовка препятствий
        for obs in game_state.obstacles:
            if min_x <= obs[0] <= max_x and min_y <= obs[1] <= max_y:
                lx, ly = to_local_coord(obs)
                pygame.draw.rect(mini_surface, self.COLORS['obstacle'],
                               (lx * self.cell_size, ly * self.cell_size,
                                self.cell_size, self.cell_size))
        
        # Отрисовка бомб
        for bomb in game_state.bombs:
            bomb_pos = bomb['pos']
            if min_x <= bomb_pos[0] <= max_x and min_y <= bomb_pos[1] <= max_y:
                lx, ly = to_local_coord(bomb_pos)
                # Красный круг для бомбы
                pygame.draw.circle(mini_surface, self.COLORS['bomb'],
                                 (lx * self.cell_size + self.cell_size // 2,
                                  ly * self.cell_size + self.cell_size // 2),
                                 self.cell_size // 3)
                # Таймер бомбы
                if 'timer' in bomb:
                    timer_text = self.small_font.render(str(bomb['timer']), True, (255, 255, 255))
                    text_rect = timer_text.get_rect(center=(
                        lx * self.cell_size + self.cell_size // 2,
                        ly * self.cell_size + self.cell_size // 2
                    ))
                    mini_surface.blit(timer_text, text_rect)
        
        # Отрисовка врагов
        for enemy in game_state.enemies:
            if min_x <= enemy[0] <= max_x and min_y <= enemy[1] <= max_y:
                lx, ly = to_local_coord(enemy)
                # Красный квадрат для врага
                pygame.draw.rect(mini_surface, self.COLORS['enemy'],
                               (lx * self.cell_size + 2, ly * self.cell_size + 2,
                                self.cell_size - 4, self.cell_size - 4))
        
        # Отрисовка мобов
        for mob in game_state.mobs:
            if min_x <= mob[0] <= max_x and min_y <= mob[1] <= max_y:
                lx, ly = to_local_coord(mob)
                # Фиолетовый круг для моба
                pygame.draw.circle(mini_surface, self.COLORS['mob'],
                                 (lx * self.cell_size + self.cell_size // 2,
                                  ly * self.cell_size + self.cell_size // 2),
                                 self.cell_size // 3)
        
        # Отрисовка юнитов (включая текущего)
        for bomber in game_state.bombers:
            if not bomber.alive:
                continue
            if min_x <= bomber.position[0] <= max_x and min_y <= bomber.position[1] <= max_y:
                lx, ly = to_local_coord(bomber.position)
                
                # Выбор цвета в зависимости от того, текущий это юнит или нет
                color = self.COLORS['friendly'] if bomber.unit_id == unit.unit_id else (100, 180, 100)
                
                # Зеленый квадрат для юнита
                pygame.draw.rect(mini_surface, color,
                               (lx * self.cell_size + 2, ly * self.cell_size + 2,
                                self.cell_size - 4, self.cell_size - 4))
                
                # Отображение ID юнита
                id_text = self.small_font.render(bomber.unit_id[:4], True, (255, 255, 255))
                text_rect = id_text.get_rect(
                    center=(lx * self.cell_size + self.cell_size // 2,
                            ly * self.cell_size + self.cell_size // 2)
                )
                mini_surface.blit(id_text, text_rect)
        
        # Отображение границы видимости
        visibility_rect = pygame.Rect(5 * self.cell_size, 5 * self.cell_size, self.cell_size, self.cell_size)
        pygame.draw.rect(mini_surface, self.COLORS['highlight'], visibility_rect, 2)
        
        # Отображение заголовка мини-карты
        title = f"Unit {unit.unit_id[:4]}"
        if unit.unit_id == game_state.bombers[self.selected_unit_index].unit_id if game_state.bombers else False:
            title += " (SELECTED)"
        title_surface = self.font.render(title, True, self.COLORS['text'])
        
        # Отображение мини-карты на основном экране
        surface.blit(title_surface, (position[0], position[1] - 30))
        surface.blit(mini_surface, position)
        
        # Отображение информации о юните
        info_lines = [
            f"Pos: {unit.position}",
            f"Bombs: {unit.bombs_available}",
            f"Safe: {unit.safe_time}ms",
            f"Armor: {unit.armor}"
        ]
        
        for i, line in enumerate(info_lines):
            info_surface = self.small_font.render(line, True, self.COLORS['text'])
            surface.blit(info_surface, (position[0], position[1] + mini_height + 5 + i * 15))
    
    def _draw_main_map(self, surface, game_state: GameState):
        """Отрисовка основной карты для обзора всей ситуации"""
        if not game_state.map_size:
            return
        
        # Размеры для основной карты
        map_width = min(game_state.map_size[0] * self.cell_size, self.window_width // 2)
        map_height = min(game_state.map_size[1] * self.cell_size, self.window_height // 2)
        
        # Создание поверхности для основной карты
        map_surface = pygame.Surface((map_width, map_height))
        map_surface.fill(self.COLORS['background'])
        
        # Отрисовка сетки
        for x in range(game_state.map_size[0] + 1):
            if x * self.cell_size < map_width:
                pygame.draw.line(map_surface, self.COLORS['grid'],
                               (x * self.cell_size, 0),
                               (x * self.cell_size, map_height), 1)
        
        for y in range(game_state.map_size[1] + 1):
            if y * self.cell_size < map_height:
                pygame.draw.line(map_surface, self.COLORS['grid'],
                               (0, y * self.cell_size),
                               (map_width, y * self.cell_size), 1)
        
        # Отрисовка объектов
        for wall in game_state.walls:
            if wall[0] * self.cell_size < map_width and wall[1] * self.cell_size < map_height:
                pygame.draw.rect(map_surface, self.COLORS['wall'],
                               (wall[0] * self.cell_size, wall[1] * self.cell_size,
                                self.cell_size, self.cell_size))
        
        for obs in game_state.obstacles:
            if obs[0] * self.cell_size < map_width and obs[1] * self.cell_size < map_height:
                pygame.draw.rect(map_surface, self.COLORS['obstacle'],
                               (obs[0] * self.cell_size, obs[1] * self.cell_size,
                                self.cell_size, self.cell_size))
        
        for bomb in game_state.bombs:
            bomb_pos = bomb['pos']
            if bomb_pos[0] * self.cell_size < map_width and bomb_pos[1] * self.cell_size < map_height:
                pygame.draw.circle(map_surface, self.COLORS['bomb'],
                                 (bomb_pos[0] * self.cell_size + self.cell_size // 2,
                                  bomb_pos[1] * self.cell_size + self.cell_size // 2),
                                 self.cell_size // 3)
        
        for enemy in game_state.enemies:
            if enemy[0] * self.cell_size < map_width and enemy[1] * self.cell_size < map_height:
                pygame.draw.rect(map_surface, self.COLORS['enemy'],
                               (enemy[0] * self.cell_size + 2, enemy[1] * self.cell_size + 2,
                                self.cell_size - 4, self.cell_size - 4))
        
        for mob in game_state.mobs:
            if mob[0] * self.cell_size < map_width and mob[1] * self.cell_size < map_height:
                pygame.draw.circle(map_surface, self.COLORS['mob'],
                                 (mob[0] * self.cell_size + self.cell_size // 2,
                                  mob[1] * self.cell_size + self.cell_size // 2),
                                 self.cell_size // 3)
        
        for bomber in game_state.bombers:
            if not bomber.alive:
                continue
            if bomber.position[0] * self.cell_size < map_width and bomber.position[1] * self.cell_size < map_height:
                color = self.COLORS['friendly'] if bomber.unit_id == game_state.bombers[self.selected_unit_index].unit_id else (100, 180, 100)
                pygame.draw.rect(map_surface, color,
                               (bomber.position[0] * self.cell_size + 2, bomber.position[1] * self.cell_size + 2,
                                self.cell_size - 4, self.cell_size - 4))
        
        # Отображение основной карты
        surface.blit(map_surface, (self.window_width // 2 - map_width // 2, 20))
        
        # Заголовок
        title = self.font.render("Global Map View", True, self.COLORS['text'])
        surface.blit(title, (self.window_width // 2 - title.get_width() // 2, 0))
    
    def _draw_ui_panel(self, surface, game_state: GameState):
        """Отрисовка информационной панели"""
        panel_width = 300
        panel_height = 200
        panel_x = self.window_width - panel_width - 10
        panel_y = 10
        
        # Фон панели
        panel_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel_surface.fill(self.COLORS['ui_background'])
        pygame.draw.rect(panel_surface, self.COLORS['ui_border'], panel_surface.get_rect(), 2)
        surface.blit(panel_surface, (panel_x, panel_y))
        
        # Заголовок
        title = self.font.render("Game Status", True, self.COLORS['highlight'])
        surface.blit(title, (panel_x + 10, panel_y + 10))
        
        # Статистика
        stats = [
            f"Time: {game_state.current_time:.1f}s",
            f"Units: {len([u for u in game_state.bombers if u.alive])}/{len(game_state.bombers)} alive",
            f"Bombs: {len(game_state.bombs)} active",
            f"Obstacles: {len(game_state.obstacles)}",
            f"Enemies: {len(game_state.enemies)}",
            f"Mobs: {len(game_state.mobs)}"
        ]
        
        for i, stat in enumerate(stats):
            stat_surface = self.small_font.render(stat, True, self.COLORS['text'])
            surface.blit(stat_surface, (panel_x + 10, panel_y + 40 + i * 20))
        
        # Управление
        controls = [
            "Controls:",
            "← →: Switch units",
            "SPACE: Place bomb",
            "Q: Quit visualization"
        ]
        
        for i, control in enumerate(controls):
            control_surface = self.small_font.render(control, True, self.COLORS['highlight'])
            surface.blit(control_surface, (panel_x + 10, panel_y + 120 + i * 18))
    
    def _visualization_loop(self):
        """Основной цикл визуализации"""
        self._init_pygame()
        
        last_update = 0
        update_interval = 0.1  # Обновление 10 раз в секунду
        
        while self.running:
            current_time = time.time()
            
            # Обработка событий pygame
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        self.running = False
                    elif event.key == pygame.K_LEFT:
                        if hasattr(self, 'current_game_state') and self.current_game_state:
                            self.selected_unit_index = (self.selected_unit_index - 1) % len(self.current_game_state.bombers)
                    elif event.key == pygame.K_RIGHT:
                        if hasattr(self, 'current_game_state') and self.current_game_state:
                            self.selected_unit_index = (self.selected_unit_index + 1) % len(self.current_game_state.bombers)
                    elif event.key == pygame.K_SPACE:
                        # Здесь можно добавить логику для установки бомбы
                        pass
            
            # Получение последнего состояния игры
            try:
                game_state = self.data_queue.get_nowait()
                self.current_game_state = game_state
            except queue.Empty:
                if not hasattr(self, 'current_game_state'):
                    continue
            
            # Ограничение частоты обновления
            if current_time - last_update < update_interval:
                self.clock.tick(60)
                continue
            
            last_update = current_time
            
            # Очистка экрана
            self.screen.fill(self.COLORS['background'])
            
            if hasattr(self, 'current_game_state') and self.current_game_state:
                # Отрисовка мини-карт для юнитов
                unit_spacing = 250
                max_units_per_row = 3
                for i, unit in enumerate(self.current_game_state.bombers):
                    if not unit.alive:
                        continue
                    
                    row = i // max_units_per_row
                    col = i % max_units_per_row
                    x = 10 + col * unit_spacing
                    y = 300 + row * 300
                    
                    if y + 300 < self.window_height:
                        self._draw_mini_map(self.screen, self.current_game_state, unit, (x, y))
                
                # Отрисовка основной карты
                self._draw_main_map(self.screen, self.current_game_state)
                
                # Отрисовка информационной панели
                self._draw_ui_panel(self.screen, self.current_game_state)
            
            # Обновление экрана
            pygame.display.flip()
            self.clock.tick(60)
        
        pygame.quit()

# Модифицированный GameOrchestrator для интеграции с визуализацией
class GameOrchestratorWithVisualization(GameOrchestrator):
    """Расширенный оркестратор с поддержкой визуализации"""
    
    def __init__(self, api_base_url: str, auth_token: str):
        super().__init__(api_base_url, auth_token)
        self.visualizer = None
    
    async def __aenter__(self):
        """Инициализация с визуализацией"""
        await super().__aenter__()
        self.visualizer = GameVisualizer()
        self.visualization_thread = self.visualizer.start_visualization()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Завершение работы с визуализацией"""
        if self.visualizer:
            self.visualizer.stop_visualization()
            self.visualization_thread.join(timeout=1.0)
        await super().__aexit__(exc_type, exc_val, exc_tb)
    
    async def game_loop(self):
        """Игровой цикл с визуализацией"""
        try:
            logging.info("🚀 Игровой цикл запущен с визуализацией")
            
            while True:
                current_time = datetime.utcnow()
                
                # === ШАГ 1: Получение состояния арены ===
                try:
                    arena_data = await self.get_arena_state()
                    self.game_state_manager.update_from_api(arena_data)
                    
                    # Преобразование данных для визуализатора
                    game_state = self._convert_to_visualization_state(arena_data)
                    if self.visualizer:
                        self.visualizer.update_game_state(game_state)
                    logging.info(f"🎮 Состояние арены обновлено. Очки: {arena_data.get('raw_score', 0)}")
                except Exception as e:
                    logging.error(f"❌ Ошибка при получении состояния арены: {str(e)}")
                    await asyncio.sleep(0.1)
                    continue
                
                # === ШАГ 2: Генерация и отправка команд ===
                commands = self.strategy_coordinator.generate_commands()
                
                if commands and commands["bombers"]:
                    try:
                        result = await self.send_move_commands(commands)
                        logging.info(f"✅ Команды отправлены успешно")
                    except Exception as e:
                        logging.error(f"❌ Ошибка при отправке команд: {str(e)}")
                        await self._send_safe_commands(arena_data)
                
                # === ШАГ 3: Адаптивная задержка ===
                next_request_time = self.rate_limiter.get_next_available_time()
                current_time = time.time()
                
                if next_request_time > current_time:
                    sleep_time = min(0.5, next_request_time - current_time)
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0.05)
                
        except asyncio.CancelledError:
            logging.info("🛑 Игровой цикл остановлен")
        except Exception as e:
            logging.critical(f"💥 Критическая ошибка в игровом цикле: {str(e)}", exc_info=True)
            raise
    
    def _convert_to_visualization_state(self, arena_data: dict) -> GameState:
        """Преобразование данных API в формат для визуализатора"""
        current_time = time.time()
        
        # Преобразование юнитов
        bombers = []
        for bomber_data in arena_data['bombers']:
            bombers.append(UnitState(
                unit_id=bomber_data['id'],
                position=(bomber_data['pos'][0], bomber_data['pos'][1]),
                alive=bomber_data['alive'],
                armor=bomber_data['armor'],
                bombs_available=bomber_data['bombs_available'],
                can_move=bomber_data['can_move'],
                safe_time=bomber_data['safe_time']
            ))
        
        # Преобразование остальных данных
        arena = arena_data['arena']
        obstacles = [(pos[0], pos[1]) for pos in arena['obstacles']]
        walls = [(pos[0], pos[1]) for pos in arena['walls']]
        
        # Преобразование бомб (если есть данные о таймерах)
        bombs = []
        for bomb in arena.get('bombs', []):
            if isinstance(bomb, dict):
                bombs.append(bomb)
            else:
                # Если бомба представлена в другом формате
                bombs.append({'pos': bomb, 'timer': 8})
        
        enemies = [(pos[0], pos[1]) for pos in arena_data.get('enemies', [])]
        mobs = [(pos[0], pos[1]) for pos in arena_data.get('mobs', [])]
        
        return GameState(
            map_size=(arena_data['map_size'][0], arena_data['map_size'][1]),
            obstacles=obstacles,
            walls=walls,
            bombs=bombs,
            enemies=enemies,
            mobs=mobs,
            bombers=bombers,
            current_time=current_time
        )

# Модифицированная функция main для запуска с визуализацией
async def main():
    """Основная функция запуска с визуализацией"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    API_BASE_URL = "https://games-test.datsteam.dev"
    AUTH_TOKEN = "d4d94a5f-c6aa-49af-b547-13897fb0896a"
    
    async with GameOrchestratorWithVisualization(API_BASE_URL, AUTH_TOKEN) as orchestrator:
        await orchestrator.game_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("👋 Программа остановлена пользователем")
    except Exception as e:
        logging.critical(f"🔥 Фатальная ошибка: {str(e)}", exc_info=True)