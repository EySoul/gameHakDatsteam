from models.models import Position


class PerformanceTracker:
    def __init__(self):
        self.metrics = {
            'obstacles_destroyed': 0,
            'deaths_by_bomb': 0,
            'deaths_by_mob': 0,
            'safe_movements': 0,
            'dangerous_movements': 0
        }
    
    def log_movement(self, from_pos: Position, to_pos: Position, danger_level: int):
        if danger_level > 50:
            self.metrics['dangerous_movements'] += 1
        else:
            self.metrics['safe_movements'] += 1