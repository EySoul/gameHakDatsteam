import pygame
from typing import List, Dict, Any

class GameRenderer:
    def __init__(self, screen_width=800, screen_height=600, cell_size=20):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.cell_size = cell_size
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.map_size = None
        self.arena = None
        self.bombers = None
        self.enemies = []
        self.mobs = []
        
        # Colors
        self.BLACK = (0, 0, 0)
        self.WHITE = (255, 255, 255)
        self.RED = (255, 0, 0)
        self.BLUE = (0, 0, 255)
        self.GREEN = (0, 255, 0)
        self.YELLOW = (255, 255, 0)  # Для опасных зон
        self.GRAY = (128, 128, 128)
        self.LIGHT_GRAY = (200, 200, 200)
        self.DARK_GRAY = (100, 100, 100)
        self.PINK = (255, 192, 203)  # Препятствия
        self.PURPLE = (255, 0, 255)  # Мобы
        self.ORANGE = (255, 165, 0)  # Пути движения
        self.CYAN = (0, 255, 255)    # Цели
        
        # Danger zones (новое)
        self.danger_zones = {}
        
    def set_danger_zones(self, danger_zones: dict):
        """Устанавливает опасные зоны для отрисовки"""
        self.danger_zones = danger_zones
    
    def update_data(self, map_size, arena, bombers, enemies=None, mobs=None, danger_zones=None):
        self.map_size = map_size
        self.arena = arena
        self.bombers = bombers
        self.enemies = enemies or []
        self.mobs = mobs or []
        if danger_zones:
            self.danger_zones = danger_zones
    
    def draw_mini_map(self, screen, bomber_index, bomber_data, visible_area):
        """Отрисовывает одну мини-карту"""
        bx, by = bomber_data["pos"]
        min_x = max(0, bx - 3)
        max_x = min(self.map_size[0] - 1, bx + 3)
        min_y = max(0, by - 3)
        max_y = min(self.map_size[1] - 1, by + 3)
        
        # Фильтруем объекты в области видимости
        visible_obs = [
            obs for obs in self.arena["obstacles"]
            if min_x <= obs[0] <= max_x and min_y <= obs[1] <= max_y
        ]
        visible_walls = [
            wall for wall in self.arena["walls"]
            if min_x <= wall[0] <= max_x and min_y <= wall[1] <= max_y
        ]
        visible_bombs = [
            bomb for bomb in self.arena["bombs"]
            if isinstance(bomb, dict) and "pos" in bomb
            and min_x <= bomb["pos"][0] <= max_x and min_y <= bomb["pos"][1] <= max_y
        ]
        visible_bombers = [
            b for b in self.bombers
            if b["alive"] and min_x <= b["pos"][0] <= max_x and min_y <= b["pos"][1] <= max_y
        ]
        visible_enemies = [
            e for e in self.enemies
            if min_x <= e[0] <= max_x and min_y <= e[1] <= max_y
        ]
        visible_mobs = [
            m for m in self.mobs
            if min_x <= m[0] <= max_x and min_y <= m[1] <= max_y
        ]
        
        # Создаем поверхность для мини-карты
        mini_width = 7 * self.cell_size
        mini_height = 7 * self.cell_size
        mini_surface = pygame.Surface((mini_width, mini_height))
        mini_surface.fill(self.WHITE)
        
        # Сетка
        for x in range(8):
            pygame.draw.line(mini_surface, self.DARK_GRAY,
                           (x * self.cell_size, 0),
                           (x * self.cell_size, mini_height), 1)
        for y in range(8):
            pygame.draw.line(mini_surface, self.DARK_GRAY,
                           (0, y * self.cell_size),
                           (mini_width, y * self.cell_size), 1)
        
        # Опасные зоны (полупрозрачные)
        for (dx, dy), danger in self.danger_zones.items():
            if min_x <= dx <= max_x and min_y <= dy <= max_y:
                rx = dx - min_x
                ry = dy - min_y
                danger_color = (255, 0, 0, min(200, danger * 2))  # Красный с прозрачностью
                danger_surface = pygame.Surface((self.cell_size, self.cell_size), pygame.SRCALPHA)
                danger_surface.fill(danger_color)
                mini_surface.blit(danger_surface,
                                (rx * self.cell_size, ry * self.cell_size))
        
        # Препятствия
        for obs in visible_obs:
            rx = obs[0] - min_x
            ry = obs[1] - min_y
            pygame.draw.rect(mini_surface, self.PINK,
                           (rx * self.cell_size, ry * self.cell_size,
                            self.cell_size, self.cell_size))
        
        # Стены
        for wall in visible_walls:
            rx = wall[0] - min_x
            ry = wall[1] - min_y
            pygame.draw.rect(mini_surface, self.BLACK,
                           (rx * self.cell_size, ry * self.cell_size,
                            self.cell_size, self.cell_size))
        
        # Бомбы
        for bomb in visible_bombs:
            rx = bomb["pos"][0] - min_x
            ry = bomb["pos"][1] - min_y
            pygame.draw.circle(mini_surface, self.RED,
                             (rx * self.cell_size + self.cell_size // 2,
                              ry * self.cell_size + self.cell_size // 2),
                             self.cell_size // 4)
        
        # Юниты
        entity_size = self.cell_size - 2
        offset = (self.cell_size - entity_size) // 2
        
        for b in visible_bombers:
            rx = b["pos"][0] - min_x
            ry = b["pos"][1] - min_y
            # Текущий юнит - зеленый, другие - синие
            color = self.GREEN if b["id"] == bomber_data["id"] else self.BLUE
            pygame.draw.rect(mini_surface, color,
                           (rx * self.cell_size + offset,
                            ry * self.cell_size + offset,
                            entity_size, entity_size))
        
        # Враги
        for e in visible_enemies:
            rx = e[0] - min_x
            ry = e[1] - min_y
            pygame.draw.rect(mini_surface, self.RED,
                           (rx * self.cell_size + offset,
                            ry * self.cell_size + offset,
                            entity_size, entity_size))
        
        # Мобы
        for m in visible_mobs:
            rx = m[0] - min_x
            ry = m[1] - min_y
            pygame.draw.rect(mini_surface, self.PURPLE,
                           (rx * self.cell_size + offset,
                            ry * self.cell_size + offset,
                            entity_size, entity_size))
        
        return mini_surface
    
    def draw_debug_info(self, screen, bomber_data, decisions):
        """Отрисовывает отладочную информацию"""
        font = pygame.font.Font(None, 24)
        
        # Позиция юнита
        pos_text = f"Pos: {bomber_data['pos']}"
        text_surface = font.render(pos_text, True, self.WHITE)
        screen.blit(text_surface, (10, 10))
        
        # Состояние
        state_text = f"Alive: {bomber_data['alive']} | Bombs: {bomber_data['bombs_available']}"
        text_surface = font.render(state_text, True, self.WHITE)
        screen.blit(text_surface, (10, 40))
        
        # Решения AI
        if decisions:
            for i, decision in enumerate(decisions[:5]):  # Показываем 5 решений
                dec_text = f"{decision}"
                text_surface = font.render(dec_text, True, self.YELLOW)
                screen.blit(text_surface, (10, 70 + i * 30))
    
    def draw(self, screen, decisions: List[Dict] = None):
        """Основной метод отрисовки"""
        if not self.map_size or not self.arena or not self.bombers:
            return
        
        screen.fill(self.BLACK)
        
        # Параметры мини-карт
        mini_size = 7 * self.cell_size
        gap = 20
        positions = [
            (0, 0),
            (mini_size + gap, 0),
            (2 * (mini_size + gap), 0),
            (0, mini_size + gap),
            (mini_size + gap, mini_size + gap),
            (2 * (mini_size + gap), mini_size + gap),
        ]
        
        # Отрисовываем каждую мини-карту
        for i, bomber in enumerate(self.bombers):
            if not bomber["alive"]:
                continue
            
            if i < len(positions):
                # Отрисовываем мини-карту
                mini_map = self.draw_mini_map(screen, i, bomber, visible_area=None)
                
                # Масштабируем
                scaled_mini = pygame.transform.scale(
                    mini_map,
                    (int(mini_size * self.zoom), int(mini_size * self.zoom))
                )
                
                # Позиционируем
                pos_x = positions[i][0] + self.offset_x
                pos_y = positions[i][1] + self.offset_y
                screen.blit(scaled_mini, (pos_x, pos_y))
                
                # Добавляем номер юнита
                font = pygame.font.Font(None, 20)
                text = font.render(f"Unit {i+1}", True, self.WHITE)
                screen.blit(text, (pos_x, pos_y - 20))
        
        # Отладочная информация для первого юнита
        if self.bombers and decisions:
            first_bomber = next((b for b in self.bombers if b["alive"]), None)
            if first_bomber:
                self.draw_debug_info(screen, first_bomber, decisions)
        
        # Общая статистика
        font = pygame.font.Font(None, 24)
        alive_count = sum(1 for b in self.bombers if b["alive"])
        stats_text = f"Alive: {alive_count}/6 | Obstacles: {len(self.arena['obstacles'])} | Mobs: {len(self.mobs)}"
        text_surface = font.render(stats_text, True, self.CYAN)
        screen.blit(text_surface, (screen.get_width() - text_surface.get_width() - 10, 10))