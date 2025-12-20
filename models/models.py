from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import math

@dataclass
class Position:
    x: int
    y: int
    
    def distance_to(self, other: 'Position') -> float:
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
    
    def manhattan_distance(self, other: 'Position') -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    
    def __hash__(self):
        return hash((self.x, self.y))

@dataclass
class Bomber:
    id: str
    alive: bool
    pos: Position
    armor: int
    bombs_available: int
    can_move: bool
    safe_time: int  # время неуязвимости после возрождения
    
@dataclass  
class Mob:
    id: str
    type: str  # "patrol" или "ghost"
    pos: Position
    safe_time: int

@dataclass
class Bomb:
    pos: Position
    timer: float  # время до взрыва
    radius: int
    owner: str  # ID юнита или команды

@dataclass
class GameState:
    # Основная информация
    player_name: str
    round_id: str
    map_size: Tuple[int, int]
    raw_score: int
    
    # Игровые объекты
    bombers: Dict[str, Bomber]  # ключ - ID юнита
    obstacles: List[Position]  # разрушаемые препятствия
    walls: List[Position]  # неразрушаемые стены
    bombs: List[Bomb]
    mobs: List[Mob]
    enemies: List[dict]  # пока пусто, но может появиться
    
    # Состояние улучшений (из /api/booster)
    upgrades: Optional[dict] = None
    
    def get_bomber_by_id(self, bomber_id: str) -> Optional[Bomber]:
        return self.bombers.get(bomber_id)
    
    def is_position_free(self, pos: Position) -> bool:
        """Проверяет, свободна ли клетка для перемещения"""
        # Проверяем стены
        if pos in self.walls:
            return False
        # Проверяем препятствия
        if pos in self.obstacles:
            return False
        # Проверяем бомбы (позже учтем улучшение акробатики)
        for bomb in self.bombs:
            if bomb.pos == pos:
                return False
        return True