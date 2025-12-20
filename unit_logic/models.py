import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
import logging
from typing import Dict, List, Tuple, Optional
import json

@dataclass
class UnitSnapshot:
    """Снимок состояния юнита в момент времени"""
    unit_id: str
    position: Tuple[int, int]  # [x, y] из API
    alive: bool
    armor: int
    bombs_available: int
    can_move: bool
    safe_time: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_api(cls, api_data: dict) -> 'UnitSnapshot':
        """Создание снимка из данных API"""
        return cls(
            unit_id=api_data['id'],
            position=(api_data['pos'][0], api_data['pos'][1]),
            alive=api_data['alive'],
            armor=api_data['armor'],
            bombs_available=api_data['bombs_available'],
            can_move=api_data['can_move'],
            safe_time=api_data['safe_time']
        )

@dataclass
class ArenaSnapshot:
    """Снимок состояния арены в момент времени"""
    map_size: Tuple[int, int]
    obstacles: List[Tuple[int, int]]  # Список [x, y]
    walls: List[Tuple[int, int]]
    bombs: List[dict]  # Более сложная структура для бомб
    enemies: List[dict]
    mobs: List[dict]
    raw_score: int
    round_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_api(cls, api_data: dict) -> 'ArenaSnapshot':
        """Создание снимка арены из данных API"""
        arena_data = api_data['arena']
        return cls(
            map_size=(api_data['map_size'][0], api_data['map_size'][1]),
            obstacles=[(pos[0], pos[1]) for pos in arena_data['obstacles']],
            walls=[(pos[0], pos[1]) for pos in arena_data['walls']],
            bombs=arena_data['bombs'],  # Требует дополнительной обработки
            enemies=api_data['enemies'],
            mobs=api_data['mobs'],
            raw_score=api_data['raw_score'],
            round_id=api_data['round'],
            timestamp=datetime.utcnow()
        )

class GameStateManager:
    """
    Управление полным состоянием игры с хранением истории за 1 секунду
    Инкапсулирует всю сложность работы с состоянием
    """
    def __init__(self):
        self._unit_states: Dict[str, List[UnitSnapshot]] = {}  # unit_id -> история
        self._arena_history: List[ArenaSnapshot] = []
        self._last_update_time: datetime = datetime.min
    
    def update_from_api(self, api_response: dict):
        """Обновление состояния из API ответа"""
        current_time = datetime.utcnow()
        
        # Обновление данных об арене
        arena_snapshot = ArenaSnapshot.from_api(api_response)
        self._arena_history.append(arena_snapshot)
        
        # Очистка старой истории арены (>1 секунды)
        self._arena_history = [
            snap for snap in self._arena_history
            if (current_time - snap.timestamp).total_seconds() <= 1.0
        ]
        
        # Обновление данных о юнитах
        for bomber_data in api_response['bombers']:
            unit_id = bomber_data['id']
            unit_snapshot = UnitSnapshot.from_api(bomber_data)
            
            if unit_id not in self._unit_states:
                self._unit_states[unit_id] = []
            
            self._unit_states[unit_id].append(unit_snapshot)
            
            # Очистка старой истории юнита (>1 секунды)
            self._unit_states[unit_id] = [
                snap for snap in self._unit_states[unit_id]
                if (current_time - snap.timestamp).total_seconds() <= 1.0
            ]
        
        self._last_update_time = current_time
    
    def get_current_game_state(self) -> dict:
        """Получение текущего состояния для принятия решений"""
        current_time = datetime.utcnow()
        
        if not self._arena_history:
            return None
        
        # Текущее состояние арены
        current_arena = self._arena_history[-1]
        
        # Текущие состояния юнитов
        current_units = {}
        for unit_id, history in self._unit_states.items():
            if history:
                current_units[unit_id] = history[-1]
        
        # Анализ изменений за последнюю секунду
        unit_movements = self._analyze_unit_movements()
        bomb_changes = self._analyze_bomb_changes()
        
        return {
            'arena': current_arena,
            'units': current_units,
            'unit_movements': unit_movements,  # {unit_id: [(old_pos, new_pos, timestamp), ...]}
            'bomb_changes': bomb_changes,      # [(position, appeared/disappeared, timestamp)]
            'time_elapsed': (current_time - self._last_update_time).total_seconds(),
            'is_starting_position': self._check_starting_position(current_units)
        }
    
    def _analyze_unit_movements(self) -> dict:
        """Анализ перемещений юнитов за последнюю секунду"""
        movements = {}
        
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
        
        # Проверяем, все ли юниты на одинаковой позиции
        positions = [unit.position for unit in current_units.values()]
        return len(set(positions)) == 1
    def _analyze_bomb_changes(self) -> List[Tuple[Tuple[int, int], str, datetime]]:
        """Анализ появления и исчезания бомб за последнюю секунду"""
        if len(self._arena_history) < 2:
            return []
        
        bomb_changes = []
        current_time = datetime.utcnow()
        
        # Сравниваем последний снимок с предыдущими для выявления изменений
        current_bombs = {(bomb['pos'][0], bomb['pos'][1]): bomb for bomb in self._arena_history[-1].bombs}
        
        for i in range(len(self._arena_history)-2, -1, -1):
            prev_snapshot = self._arena_history[i]
            prev_bombs = {(bomb['pos'][0], bomb['pos'][1]): bomb for bomb in prev_snapshot.bombs}
            
            # Новые бомбы
            for pos, bomb in current_bombs.items():
                if pos not in prev_bombs:
                    bomb_changes.append((pos, "appeared", current_time))
            
            # Исчезнувшие бомбы
            for pos, bomb in prev_bombs.items():
                if pos not in current_bombs:
                    bomb_changes.append((pos, "disappeared", current_time))
        
        # Фильтрация только изменений за последнюю секунду
        recent_changes = [
            change for change in bomb_changes
            if (current_time - change[2]).total_seconds() <= 1.0
        ]
        
        return recent_changes

    def _check_starting_position(self, current_units: Dict[str, UnitSnapshot]) -> bool:
        """Проверка, находятся ли все юниты в стартовой позиции"""
        if not current_units:
            return False
        
        # Проверяем, все ли юниты на одинаковой позиции
        positions = [unit.position for unit in current_units.values()]
        return len(set(positions)) == 1 and len(positions) == 6  # Все 6 юнитов в одной точке
    

class RateLimiter:
    """
    Усовершенствованный RateLimiter с поддержкой асинхронного ожидания
    и методом для получения времени следующего доступного запроса
    """
    def __init__(self, max_requests=3, period=1.0):
        self.max_requests = max_requests
        self.period = period
        self.request_timestamps = deque()  # Храним временные метки запросов
        self._lock = asyncio.Lock()  # Для потокобезопасности в асинхронной среде
    
    async def acquire(self):
        """Асинхронное ожидание разрешения на запрос"""
        async with self._lock:
            now = time.time()
            
            # Удаляем старые временные метки
            while self.request_timestamps and now - self.request_timestamps[0] > self.period:
                self.request_timestamps.popleft()
            
            # Если достигнут лимит - ждем
            if len(self.request_timestamps) >= self.max_requests:
                # Вычисляем время ожидания
                wait_time = self.period - (now - self.request_timestamps[0]) + 0.05  # 50мс буфер
                logging.debug(f"Достигнут лимит запросов. Ожидание {wait_time:.2f} сек")
                await asyncio.sleep(wait_time)
                # После ожидания повторно очищаем старые метки
                now = time.time()
                while self.request_timestamps and now - self.request_timestamps[0] > self.period:
                    self.request_timestamps.popleft()
            
            # Добавляем новую временную метку
            self.request_timestamps.append(now)
    
    def get_next_available_time(self):
        """Получение времени следующего доступного запроса (для адаптивной задержки)"""
        now = time.time()
        
        # Очищаем старые метки
        while self.request_timestamps and now - self.request_timestamps[0] > self.period:
            self.request_timestamps.popleft()
        
        if len(self.request_timestamps) < self.max_requests:
            return now  # Запрос можно сделать немедленно
        
        # Иначе возвращаем время, когда освободится первый слот
        return self.request_timestamps[0] + self.period