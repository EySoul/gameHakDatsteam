from models.models import Bomber, GameState, Mob, Position


class GameStateParser:
    @staticmethod
    def parse_arena_response(data: dict) -> GameState:
        """Парсит ответ от /api/arena в структурированный GameState"""
        
        # Парсим юнитов
        bombers = {}
        for bomber_data in data.get("bombers", []):
            pos = Position(bomber_data["pos"][0], bomber_data["pos"][1])
            bomber = Bomber(
                id=bomber_data["id"],
                alive=bomber_data["alive"],
                pos=pos,
                armor=bomber_data["armor"],
                bombs_available=bomber_data["bombs_available"],
                can_move=bomber_data["can_move"],
                safe_time=bomber_data.get("safe_time", 0)
            )
            bombers[bomber.id] = bomber
        
        # Парсим препятствия и стены
        arena = data.get("arena", {})
        obstacles = [Position(x, y) for x, y in arena.get("obstacles", [])]
        walls = [Position(x, y) for x, y in arena.get("walls", [])]
        
        # Парсим мобов
        mobs = []
        for mob_data in data.get("mobs", []):
            pos = Position(mob_data["pos"][0], mob_data["pos"][1])
            mob = Mob(
                id=mob_data["id"],
                type=mob_data["type"],
                pos=pos,
                safe_time=mob_data.get("safe_time", 0)
            )
            mobs.append(mob)
        
        # Создаем состояние игры
        return GameState(
            player_name=data.get("player", ""),
            round_id=data.get("round", ""),
            map_size=tuple(data.get("map_size", [50, 50])),
            raw_score=data.get("raw_score", 0),
            bombers=bombers,
            obstacles=obstacles,
            walls=walls,
            bombs=[],  # пока нет информации о бомбах в ответе
            mobs=mobs,
            enemies=data.get("enemies", [])
        )