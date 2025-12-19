import pygame

from models import Bomb, Bomber, GameState, Mob, Position


class GameRenderer:
    def __init__(self, screen_width, screen_height, cell_size=20):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.cell_size = cell_size
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.map_size = None
        self.game_state = None
        self.bomber_id = None
        # Colors
        self.BLACK = (0, 0, 0)
        self.WHITE = (255, 255, 255)
        self.RED = (255, 0, 0)
        self.BLUE = (0, 0, 255)
        self.GREEN = (0, 255, 0)
        self.GRAY = (128, 128, 128)
        self.LIGHT_GRAY = (200, 200, 200)
        self.DARK_GRAY = (100, 100, 100)
        self.PINK = (255, 192, 203)
        self.PURPLE = (255, 0, 255)

    def set_map_size(self, map_size):
        self.map_size = map_size

    def set_game_state(self, game_state):
        self.game_state = game_state

    def set_bomber_id(self, bomber_id):
        self.bomber_id = bomber_id

    def update_data(self, map_size, game_state, bomber_id):
        self.map_size = map_size
        self.game_state = game_state
        self.bomber_id = bomber_id

    def set_zoom(self, zoom):
        self.zoom = zoom

    def set_offset(self, offset_x, offset_y):
        self.offset_x = offset_x
        self.offset_y = offset_y

    def draw(self, screen):
        if not self.map_size or not self.game_state:
            return

        screen.fill(self.BLACK)
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

        # Get alive bombers for rendering
        alive_bombers = [
            bomber for bomber in self.game_state.bombers.values() if bomber.alive
        ]

        for i, bomber in enumerate(alive_bombers):
            if not bomber.alive:
                continue

            bx, by = bomber.pos.x, bomber.pos.y
            min_x = max(0, bx - 3)
            max_x = min(self.map_size[0] - 1, bx + 3)
            min_y = max(0, by - 3)
            max_y = min(self.map_size[1] - 1, by + 3)

            # Filter visible obstacles
            visible_obs = [
                pos
                for pos in self.game_state.obstacles
                if min_x <= pos.x <= max_x and min_y <= pos.y <= max_y
            ]

            # Filter visible walls
            visible_walls = [
                pos
                for pos in self.game_state.walls
                if min_x <= pos.x <= max_x and min_y <= pos.y <= max_y
            ]

            # Filter visible bombs
            visible_bombs = [
                bomb
                for bomb in self.game_state.bombs
                if min_x <= bomb.pos.x <= max_x and min_y <= bomb.pos.y <= max_y
            ]

            # Filter visible bombers
            visible_bombers = [
                b
                for b in self.game_state.bombers.values()
                if b.alive and min_x <= b.pos.x <= max_x and min_y <= b.pos.y <= max_y
            ]
            visible_enemies = [
                e
                for e in self.game_state.enemies
                if min_x <= e.pos.x <= max_x and min_y <= e.pos.y <= max_y
            ]

            # Filter visible mobs
            visible_mobs = [
                m
                for m in self.game_state.mobs
                if min_x <= m.pos.x <= max_x and min_y <= m.pos.y <= max_y
            ]

            mini_surface = pygame.Surface((7 * self.cell_size, 7 * self.cell_size))
            mini_surface.fill(self.WHITE)

            # Draw grid
            for x in range(8):
                pygame.draw.line(
                    mini_surface,
                    self.DARK_GRAY,
                    (x * self.cell_size, 0),
                    (x * self.cell_size, 7 * self.cell_size),
                    1,
                )
            for y in range(8):
                pygame.draw.line(
                    mini_surface,
                    self.DARK_GRAY,
                    (0, y * self.cell_size),
                    (7 * self.cell_size, y * self.cell_size),
                    1,
                )

            # Draw obstacles
            for obs in visible_obs:
                rx = obs.x - min_x
                ry = obs.y - min_y
                pygame.draw.rect(
                    mini_surface,
                    self.PINK,
                    (
                        rx * self.cell_size,
                        ry * self.cell_size,
                        self.cell_size,
                        self.cell_size,
                    ),
                )

            # Draw walls
            for wall in visible_walls:
                rx = wall.x - min_x
                ry = wall.y - min_y
                pygame.draw.rect(
                    mini_surface,
                    self.BLACK,
                    (
                        rx * self.cell_size,
                        ry * self.cell_size,
                        self.cell_size,
                        self.cell_size,
                    ),
                )

            # Draw bombs
            for bomb in visible_bombs:
                rx = bomb.pos.x - min_x
                ry = bomb.pos.y - min_y
                pygame.draw.circle(
                    mini_surface,
                    self.RED,
                    (
                        rx * self.cell_size + self.cell_size // 2,
                        ry * self.cell_size + self.cell_size // 2,
                    ),
                    self.cell_size // 4,
                )

            # Draw entities
            size = self.cell_size - 2
            offset = (self.cell_size - size) // 2

            # Draw bombers
            for b in visible_bombers:
                rx = b.pos.x - min_x
                ry = b.pos.y - min_y
                color = self.GREEN if b.id == self.bomber_id else self.BLUE
                pygame.draw.rect(
                    mini_surface,
                    color,
                    (
                        rx * self.cell_size + offset,
                        ry * self.cell_size + offset,
                        size,
                        size,
                    ),
                )
            # Draw enemies
            for e in visible_enemies:
                rx = e["pos"][0] - min_x
                ry = e["pos"][1] - min_y
                pygame.draw.rect(
                    mini_surface,
                    self.RED,
                    (
                        rx * self.cell_size + offset,
                        ry * self.cell_size + offset,
                        size,
                        size,
                    ),
                )
            # Draw mobs
            for m in visible_mobs:
                rx = m["pos"][0] - min_x
                ry = m["pos"][1] - min_y
                pygame.draw.rect(
                    mini_surface,
                    self.PURPLE,
                    (
                        rx * self.cell_size + offset,
                        ry * self.cell_size + offset,
                        size,
                        size,
                    ),
                )

            if i < len(positions):
                scaled_mini = pygame.transform.scale(
                    mini_surface,
                    (
                        int(7 * self.cell_size * self.zoom),
                        int(7 * self.cell_size * self.zoom),
                    ),
                )
                screen.blit(
                    scaled_mini,
                    (positions[i][0] + self.offset_x, positions[i][1] + self.offset_y),
                )
