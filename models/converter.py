from typing import Dict, Any, List

def convert_game_state_to_renderer(game_state) -> Dict[str, Any]:
    """
    Конвертирует объект GameState в формат для визуализации
    
    Args:
        game_state: Объект GameState с полями:
            - bombers: Dict[str, Bomber]
            - obstacles: List[Position]
            - walls: List[Position]
            - mobs: List[Mob]
            - map_size: Tuple[int, int]
    
    Returns:
        Словарь в формате для GameRenderer
    """
    # Юниты
    bombers_list = []
    for bomber in game_state.bombers.values():
        bombers_list.append({
            "id": bomber.id,
            "alive": bomber.alive,
            "pos": [bomber.pos.x, bomber.pos.y],
            "bombs_available": bomber.bombs_available,
            "armor": bomber.armor,
            "can_move": bomber.can_move
        })
    
    # Препятствия и стены
    obstacles = [[pos.x, pos.y] for pos in game_state.obstacles]
    walls = [[pos.x, pos.y] for pos in game_state.walls]
    
    # Мобы
    mobs = []
    for mob in game_state.mobs:
        mobs.append([mob.pos.x, mob.pos.y])
    
    # Враги (пока пусто)
    enemies = []
    
    return {
        "map_size": list(game_state.map_size),
        "arena": {
            "obstacles": obstacles,
            "walls": walls,
            "bombs": []  # пока нет информации о бомбах в ответе
        },
        "bombers": bombers_list,
        "enemies": enemies,
        "mobs": mobs
    }


def convert_threat_analyzer_to_renderer(threat_analyzer) -> Dict[tuple, int]:
    """
    Конвертирует опасные зоны ThreatAnalyzer в формат для визуализации
    
    Args:
        threat_analyzer: Объект ThreatAnalyzer с полем danger_zones
    
    Returns:
        Словарь {(x, y): уровень_опасности}
    """
    if not threat_analyzer or not hasattr(threat_analyzer, 'danger_zones'):
        return {}
    return threat_analyzer.danger_zones


def create_debug_info(game_state, threat_analyzer=None, bomber_id=None) -> List[str]:
    """
    Создает отладочную информацию для отображения
    
    Args:
        game_state: Объект GameState
        threat_analyzer: Объект ThreatAnalyzer (опционально)
        bomber_id: ID конкретного юнита для детальной информации
    
    Returns:
        Список строк с отладочной информацией
    """
    debug_lines = []
    
    # Общая статистика
    alive_count = sum(1 for b in game_state.bombers.values() if b.alive)
    debug_lines.append(f"Активные юниты: {alive_count}/6")
    debug_lines.append(f"Очки: {game_state.raw_score}")
    debug_lines.append(f"Препятствия: {len(game_state.obstacles)}")
    debug_lines.append(f"Мобы: {len(game_state.mobs)}")
    
    # Информация об опасности для конкретного юнита
    if bomber_id and bomber_id in game_state.bombers and threat_analyzer:
        bomber = game_state.bombers[bomber_id]
        if bomber.alive:
            danger = threat_analyzer.get_danger_level(bomber.pos)
            debug_lines.append(f"Юнит {bomber_id[:8]}:")
            debug_lines.append(f"  Позиция: ({bomber.pos.x}, {bomber.pos.y})")
            debug_lines.append(f"  Опасность: {danger}/100")
            debug_lines.append(f"  Бомб: {bomber.bombs_available}")
            debug_lines.append(f"  Броня: {bomber.armor}")
    
    # Информация об опасных зонах
    if threat_analyzer and hasattr(threat_analyzer, 'danger_zones'):
        danger_count = len(threat_analyzer.danger_zones)
        if danger_count > 0:
            max_danger = max(threat_analyzer.danger_zones.values()) if threat_analyzer.danger_zones else 0
            debug_lines.append(f"Опасные зоны: {danger_count} (макс: {max_danger})")
    
    return debug_lines