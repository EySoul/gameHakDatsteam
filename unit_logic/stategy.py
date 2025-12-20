from datetime import datetime
from typing import Tuple
from gameHakDatsteam.unit_logic.models import GameStateManager


class UnitStrategyCoordinator:
    """
    Координация стратегий для всех юнитов
    Зависит только от интерфейса GameStateManager, а не от конкретной реализации
    """
    
    def __init__(self, game_state_manager: GameStateManager):
        self.game_state_manager = game_state_manager
        self.unit_assignments = {}  # unit_id -> зона ответственности
        self.last_assignment_time = datetime.min
    
    def generate_commands(self) -> dict:
        """
        Генерация команд для всех юнитов на основе текущего состояния
        Возвращает данные в формате API /move
        """
        game_state = self.game_state_manager.get_current_game_state()
        
        if not game_state:
            return {"bombers": []}
        
        # Специальная обработка начальной позиции
        if game_state['is_starting_position']:
            return self._generate_starting_commands(game_state)
        
        # Обычная стратегия
        return self._generate_normal_commands(game_state)
    
    def _generate_starting_commands(self, game_state: dict) -> dict:
        """
        Специальная стратегия для начальной позиции, где все юниты в одной точке
        """
        units = list(game_state['units'].values())
        starting_pos = units[0].position if units else (1, 106)
        
        # Направления для разделения юнитов (вокруг стартовой позиции)
        directions = [
            (1, 0),   # вправо
            (0, 1),   # вниз
            (0, -1),  # вверх
            (-1, 0),  # влево
            (1, 1),   # вправо-вниз
            (1, -1)   # вправо-вверх
        ]
        
        commands = {"bombers": []}
        
        for i, unit in enumerate(units[:len(directions)]):
            if not unit.alive or not unit.can_move:
                continue
            
            direction = directions[i]
            # Двигаемся на 2 клетки в заданном направлении
            target_pos = (
                starting_pos[0] + direction[0] * 2,
                starting_pos[1] + direction[1] * 2
            )
            
            # Проверяем, что позиция в пределах карты
            map_size = game_state['arena'].map_size
            target_pos = (
                max(0, min(map_size[0]-1, target_pos[0])),
                max(0, min(map_size[1]-1, target_pos[1]))
            )
            
            # Формируем команду движения
            command = {
                "id": unit.unit_id,
                "commands": [{
                    "command": "move",
                    "coordinates": [target_pos]
                }]
            }
            
            # Если рядом есть препятствия и есть время неуязвимости - ставим бомбу
            if unit.safe_time > 1000 and self._has_nearby_obstacles(unit.position, game_state):
                command["commands"].append({
                    "command": "bomb",
                    "coordinates": [unit.position]
                })
            
            commands["bombers"].append(command)
        
        return commands
    
    def _has_nearby_obstacles(self, position: Tuple[int, int], game_state: dict) -> bool:
        """Проверка наличия препятствий в радиусе 2 клеток"""
        obstacles = game_state['arena'].obstacles
        for obs in obstacles:
            if abs(obs[0] - position[0]) + abs(obs[1] - position[1]) <= 2:
                return True
        return False
    
    def _generate_normal_commands(self, game_state: dict) -> dict:
        """Обычная стратегия для распределенных юнитов"""
        commands = {"bombers": []}
        arena = game_state['arena']
        units = game_state['units']
        
        # Для каждого юнита генерируем индивидуальную команду
        for unit_id, unit in units.items():
            if not unit.alive or not unit.can_move:
                continue
            
            # Выбор стратегии на основе состояния юнита
            if unit.safe_time > 1000:
                # Агрессивная стратегия при неуязвимости
                target = self._find_aggressive_target(unit, arena, units)
            else:
                # Безопасная стратегия
                target = self._find_safe_target(unit, arena, units)
            
            if target:
                command = {
                    "id": unit_id,
                    "commands": [{
                        "command": "move",
                        "coordinates": [target]
                    }]
                }
                
                # Решение об установке бомбы
                if self._should_place_bomb(unit, target, arena):
                    command["commands"].append({
                        "command": "bomb",
                        "coordinates": [unit.position]
                    })
                
                commands["bombers"].append(command)
        
        return commands
    
    def _find_aggressive_target(self, unit, arena, all_units):
        """Поиск агрессивной цели (максимизация очков)"""
        # Находим скопления препятствий
        obstacle_clusters = self._find_obstacle_clusters(arena.obstacles)
        
        # Исключаем позиции, где уже есть юниты
        occupied_positions = {u.position for u in all_units.values() if u.alive}
        
        best_target = None
        best_score = -1
        
        for cluster in obstacle_clusters:
            if len(cluster) < 2:  # Игнорируем одиночные препятствия
                continue
            
            # Центр кластера как потенциальная цель
            center_x = sum(p[0] for p in cluster) // len(cluster)
            center_y = sum(p[1] for p in cluster) // len(cluster)
            target_pos = (center_x, center_y)
            
            if target_pos in occupied_positions:
                continue
            
            # Оценка потенциальных очков
            score = len(cluster) * 2  # Бонус за количество препятствий
            
            if score > best_score:
                best_score = score
                best_target = target_pos
        
        return best_target or self._find_random_safe_position(unit, arena)