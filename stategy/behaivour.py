import math
from models.models import Bomb, GameState, Mob, Position


class ThreatAnalyzer:
    def __init__(self):
        self.danger_zones = {}  # клетка -> уровень опасности (0-100)
    
    def analyze_threats(self, game_state: GameState):
        """Анализирует все угрозы на карте"""
        self.danger_zones = {}
        
        # 1. Бомбы (самая большая угроза)
        for bomb in game_state.bombs:
            self._mark_bomb_danger(bomb)
        
        # 2. Мобы (особенно призраки)
        for mob in game_state.mobs:
            self._mark_mob_danger(mob, game_state)
        
        # 3. Противники
        for enemy in game_state.enemies:
            self._mark_enemy_danger(enemy)
    
    def _mark_bomb_danger(self, bomb: Bomb):
        """Помечает зону поражения бомбы"""
        radius = bomb.radius
        center = bomb.pos
        
        # Помечаем центр - максимальная опасность
        self._set_danger(center.x, center.y, 100)
        
        # Помечаем взрыв по кресту
        for dx in range(1, radius + 1):
            self._set_danger(center.x + dx, center.y, 80)
            self._set_danger(center.x - dx, center.y, 80)
        
        for dy in range(1, radius + 1):
            self._set_danger(center.x, center.y + dy, 80)
            self._set_danger(center.x, center.y - dy, 80)
    
    def _mark_mob_danger(self, mob: Mob, game_state: GameState):
        """Помечает опасную зону вокруг моба"""
        pos = mob.pos
        
        # Для патрульного - только текущая клетка
        if mob.type == "patrol":
            self._set_danger(pos.x, pos.y, 60)
        
        # Для призрака - зона видимости (рядность обзора 10)
        elif mob.type == "ghost":
            for dx in range(-10, 11):
                for dy in range(-10, 11):
                    # Проверяем расстояние
                    distance = math.sqrt(dx**2 + dy**2)
                    if distance <= 10:
                        danger = 70 - distance * 3  # Ближе = опаснее
                        self._set_danger(pos.x + dx, pos.y + dy, max(10, danger))
    
    def _mark_enemy_danger(self, enemy: dict):
        """Помечает опасную зону вокруг противника"""
        # Пока просто отмечаем клетку противника
        # Позже добавим анализ направления движения
        pass
    
    def _set_danger(self, x: int, y: int, value: int):
        """Устанавливает уровень опасности для клетки"""
        key = (x, y)
        if key in self.danger_zones:
            self.danger_zones[key] = max(self.danger_zones[key], value)
        else:
            self.danger_zones[key] = value
    
    def get_danger_level(self, pos: Position) -> int:
        """Возвращает уровень опасности клетки (0-100)"""
        return self.danger_zones.get((pos.x, pos.y), 0)
    
class PositionEvaluator:
    def __init__(self, threat_analyzer: ThreatAnalyzer):
        self.threat_analyzer = threat_analyzer
        self.visited_positions = set()
    
    def evaluate_position(self, pos: Position, game_state: GameState, bomber_id: str) -> float:
        score = 0.0
        
        # 1. Безопасность
        danger = self.threat_analyzer.get_danger_level(pos)
        score -= danger * 2.0
        
        # 2. Расстояние до препятствий
        nearest_obstacle = self._distance_to_nearest_obstacle(pos, game_state)
        if nearest_obstacle <= 2:
            score += (3 - nearest_obstacle) * 15
        
        # 3. Центральность
        centrality = self._calculate_centrality(pos, game_state)
        score += centrality * 5
        
        # 4. Избегаем повторных посещений
        if (pos.x, pos.y) in self.visited_positions:
            score -= 20
        
        # 5. Выходы из клетки
        escape_routes = self._count_escape_routes(pos, game_state)
        score += escape_routes * 8
        
        return score
    
    def _distance_to_nearest_obstacle(self, pos: Position, game_state: GameState) -> float:
        if not game_state.obstacles:
            return float('inf')
        
        min_dist = float('inf')
        for obstacle in game_state.obstacles:
            dist = pos.manhattan_distance(obstacle)
            if dist < min_dist:
                min_dist = dist
        
        return min_dist
    
    def _calculate_centrality(self, pos: Position, game_state: GameState) -> float:
        center_x = game_state.map_size[0] / 2
        center_y = game_state.map_size[1] / 2
        
        dist_to_center = math.sqrt((pos.x - center_x)**2 + (pos.y - center_y)**2)
        max_dist = math.sqrt((center_x)**2 + (center_y)**2)
        
        return 1.0 - (dist_to_center / max_dist) if max_dist > 0 else 0
    
    def _count_escape_routes(self, pos: Position, game_state: GameState) -> int:
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        free_directions = 0
        
        for dx, dy in directions:
            new_pos = Position(pos.x + dx, pos.y + dy)
            if (0 <= new_pos.x < game_state.map_size[0] and 
                0 <= new_pos.y < game_state.map_size[1] and
                game_state.is_position_free(new_pos)):
                free_directions += 1
        
        return free_directions
    
    def mark_visited(self, bomber_id: str, pos: Position):
        self.visited_positions.add((pos.x, pos.y))