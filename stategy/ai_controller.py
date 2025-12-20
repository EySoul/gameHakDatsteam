import random
from typing import List, Optional
from models.models import Bomber, GameState, Position
from stategy.behaivour import PositionEvaluator, ThreatAnalyzer


class SimpleAIController:
    def __init__(self):
        self.state = None
        self.move_history = {}  # история движений юнитов
        
    def update_state(self, new_state: GameState):
        """Обновляет внутреннее состояние"""
        self.state = new_state
    
    def get_move_commands(self) -> dict:
        """Генерирует команды движения для всех юнитов"""
        if not self.state:
            return {"bombers": []}
        
        commands = []
        for bomber_id, bomber in self.state.bombers.items():
            if not bomber.alive or not bomber.can_move:
                continue
            
            # Простейшая логика: идем в случайную свободную клетку
            possible_moves = self._get_possible_moves(bomber)
            if possible_moves:
                target_pos = random.choice(possible_moves)
                path = self._find_path(bomber.pos, target_pos)
                
                if path:
                    command = {
                        "id": bomber_id,
                        "path": [[pos.x, pos.y] for pos in path],
                        "bombs": []  # пока не ставим бомбы
                    }
                    commands.append(command)
        
        return {"bombers": commands}
    
    def _get_possible_moves(self, bomber: Bomber) -> List[Position]:
        """Возвращает список доступных для перемещения клеток"""
        moves = []
        current = bomber.pos
        
        # Проверяем 4 направления
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            new_pos = Position(current.x + dx, current.y + dy)
            
            # Проверяем границы карты
            if (0 <= new_pos.x < self.state.map_size[0] and 
                0 <= new_pos.y < self.state.map_size[1]):
                
                # Проверяем, свободна ли клетка
                if self.state.is_position_free(new_pos):
                    moves.append(new_pos)
        
        return moves
    
    def _find_path(self, start: Position, target: Position) -> List[Position]:
        """Упрощенный поиск пути (позже заменим на A*)"""
        # Пока что просто возвращаем прямую линию если возможно
        # В будущем реализуем полноценный A*
        path = []
        current = start
        
        while current != target:
            # Простой greedy алгоритм
            if current.x < target.x and self.state.is_position_free(Position(current.x + 1, current.y)):
                current = Position(current.x + 1, current.y)
            elif current.x > target.x and self.state.is_position_free(Position(current.x - 1, current.y)):
                current = Position(current.x - 1, current.y)
            elif current.y < target.y and self.state.is_position_free(Position(current.x, current.y + 1)):
                current = Position(current.x, current.y + 1)
            elif current.y > target.y and self.state.is_position_free(Position(current.x, current.y - 1)):
                current = Position(current.x, current.y - 1)
            else:
                break  # не можем продвинуться
            
            path.append(current)
            if len(path) > 30:  # ограничение API
                break
        
        return path if path else []
    

class SmartAIController:
    def __init__(self):
        self.state = None
        self.threat_analyzer = ThreatAnalyzer()
        self.position_evaluator = PositionEvaluator(self.threat_analyzer)
        self.bomber_targets = {}
        
    def update_state(self, new_state: GameState):
        self.state = new_state
        self.threat_analyzer.analyze_threats(new_state)
    
    def get_move_commands(self) -> dict:
        if not self.state:
            return {"bombers": []}
        
        commands = []
        
        for bomber_id, bomber in self.state.bombers.items():
            if not bomber.alive or not bomber.can_move:
                continue
            
            command = self._generate_command_for_bomber(bomber)
            if command:
                commands.append(command)
                if command["path"]:
                    last_pos = command["path"][-1]
                    self.position_evaluator.mark_visited(bomber_id, Position(last_pos[0], last_pos[1]))
        
        return {"bombers": commands}
    
    def _generate_command_for_bomber(self, bomber: Bomber) -> dict:
        current_pos = bomber.pos
        
        # 1. Проверяем безопасность текущей позиции
        current_danger = self.threat_analyzer.get_danger_level(current_pos)
        if current_danger > 50:
            safe_pos = self._find_safe_position(bomber)
            if safe_pos:
                path = self._find_path(current_pos, safe_pos, emergency=True)
                return self._create_command(bomber.id, path)
        
        # 2. Ищем выгодную цель
        target_pos = self._find_best_target(bomber)
        
        # 3. Планируем путь
        if target_pos and target_pos != current_pos:
            path = self._find_path(current_pos, target_pos)
            if path:
                bombs_to_place = self._plan_bombs_along_path(bomber, path)
                return self._create_command(bomber.id, path, bombs_to_place)
        
        # 4. Ищем безопасную клетку
        safe_pos = self._find_safe_position(bomber)
        if safe_pos and safe_pos != current_pos:
            path = self._find_path(current_pos, safe_pos)
            return self._create_command(bomber.id, path)
        
        return None
    
    def _find_safe_position(self, bomber: Bomber) -> Optional[Position]:
        current_pos = bomber.pos
        search_radius = 5
        best_score = -float('inf')
        best_pos = None
        
        for dx in range(-search_radius, search_radius + 1):
            for dy in range(-search_radius, search_radius + 1):
                if abs(dx) + abs(dy) > search_radius:
                    continue
                
                candidate = Position(current_pos.x + dx, current_pos.y + dy)
                
                if not self._is_position_accessible(candidate):
                    continue
                
                danger = self.threat_analyzer.get_danger_level(candidate)
                if danger < 30:
                    distance = abs(dx) + abs(dy)
                    score = 100 - danger - distance * 5
                    
                    if score > best_score:
                        best_score = score
                        best_pos = candidate
        
        return best_pos
    
    def _find_best_target(self, bomber: Bomber) -> Optional[Position]:
        current_pos = bomber.pos
        
        # Стратегия: ищем препятствия для разрушения
        return self._find_best_obstacle_target(bomber)
    
    def _find_best_obstacle_target(self, bomber: Bomber) -> Optional[Position]:
        if not self.state.obstacles:
            return None
        
        best_score = -float('inf')
        best_pos = None
        
        for obstacle in self.state.obstacles:
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if abs(dx) + abs(dy) == 0 or abs(dx) + abs(dy) > 2:
                        continue
                    
                    candidate = Position(obstacle.x + dx, obstacle.y + dy)
                    
                    if not self._is_position_accessible(candidate):
                        continue
                    
                    score = self.position_evaluator.evaluate_position(candidate, self.state, bomber.id)
                    
                    distance = abs(dx) + abs(dy)
                    score += (3 - distance) * 25
                    
                    nearby_obstacles = self._count_nearby_obstacles(candidate, radius=2)
                    score += nearby_obstacles * 15
                    
                    if score > best_score:
                        best_score = score
                        best_pos = candidate
        
        return best_pos
    
    def _count_nearby_obstacles(self, pos: Position, radius: int) -> int:
        count = 0
        for obstacle in self.state.obstacles:
            if abs(obstacle.x - pos.x) + abs(obstacle.y - pos.y) <= radius:
                count += 1
        return count
    
    def _is_position_accessible(self, pos: Position) -> bool:
        if not (0 <= pos.x < self.state.map_size[0] and 
                0 <= pos.y < self.state.map_size[1]):
            return False
        
        if pos in self.state.walls:
            return False
        if pos in self.state.obstacles:
            return False
        
        return True
    
    def _find_path(self, start: Position, target: Position, emergency: bool = False) -> List[List[int]]:
        """Упрощенный A* поиск пути"""
        # Ограничиваем длину пути
        max_steps = 30
        
        # Если цель рядом - простой путь
        if start.manhattan_distance(target) <= 3:
            return self._simple_path(start, target, max_steps)
        
        # Или прямой путь если возможно
        path = []
        current = start
        
        # Простой жадный алгоритм с избеганием препятствий
        while current != target and len(path) < max_steps:
            # Определяем направление
            dx = target.x - current.x
            dy = target.y - current.y
            
            # Пробуем двигаться по X
            if dx != 0:
                step_x = Position(current.x + (1 if dx > 0 else -1), current.y)
                if self._is_position_accessible(step_x):
                    current = step_x
                    path.append([current.x, current.y])
                    continue
            
            # Пробуем двигаться по Y
            if dy != 0:
                step_y = Position(current.x, current.y + (1 if dy > 0 else -1))
                if self._is_position_accessible(step_y):
                    current = step_y
                    path.append([current.x, current.y])
                    continue
            
            # Если нельзя двигаться ни по X, ни по Y, ищем обход
            break
        
        return path
    
    def _simple_path(self, start: Position, target: Position, max_steps: int) -> List[List[int]]:
        """Прямой путь с учетом препятствий"""
        path = []
        current = start
        
        while current != target and len(path) < max_steps:
            # Определяем направление
            dx = target.x - current.x
            dy = target.y - current.y
            
            # Пробуем двигаться по X
            if dx != 0:
                step_x = Position(current.x + (1 if dx > 0 else -1), current.y)
                if self._is_position_accessible(step_x):
                    current = step_x
                    path.append([current.x, current.y])
                    continue
            
            # Пробуем двигаться по Y
            if dy != 0:
                step_y = Position(current.x, current.y + (1 if dy > 0 else -1))
                if self._is_position_accessible(step_y):
                    current = step_y
                    path.append([current.x, current.y])
                    continue
            
            # Не можем двигаться
            break
        
        return path
    
    def _plan_bombs_along_path(self, bomber: Bomber, path: List[List[int]]) -> List[List[int]]:
        bombs = []
        
        if bomber.bombs_available == 0:
            return bombs
        
        # Проверяем каждую точку пути
        for i, pos_data in enumerate(path):
            pos = Position(pos_data[0], pos_data[1])
            
            # Простая логика: ставим бомбу рядом с препятствиями
            if self._should_place_bomb_at(pos, bomber):
                bombs.append([pos.x, pos.y])
                if len(bombs) >= min(bomber.bombs_available, 1):  # Не больше 1 бомбы за ход
                    break
        
        return bombs
    
    def _should_place_bomb_at(self, pos: Position, bomber: Bomber) -> bool:
        # Проверяем, есть ли рядом разрушаемые препятствия
        nearby_obstacles = 0
        for obstacle in self.state.obstacles:
            if obstacle.manhattan_distance(pos) <= 1:
                nearby_obstacles += 1
        
        if nearby_obstacles == 0:
            return False
        
        # Проверяем безопасность (есть ли путь отхода)
        escape_routes = self.position_evaluator._count_escape_routes(pos, self.state)
        if escape_routes == 0:
            return False
        
        return True
    
    def _create_command(self, bomber_id: str, path: List[List[int]], bombs: List[List[int]] = None) -> dict:
        return {
            "id": bomber_id,
            "path": path,
            "bombs": bombs or []
        }