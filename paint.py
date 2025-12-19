import pygame


class GameRenderer:
    def __init__(self, screen_width, screen_height, cell_size=20):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.cell_size = cell_size
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.map_size = None
        self.arena = None
        self.bombers = None
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

    def set_map_size(self, map_size):
        self.map_size = map_size

    def set_arena(self, arena):
        self.arena = arena

    def set_bombers(self, bombers):
        self.bombers = bombers

    def set_bomber_id(self, bomber_id):
        self.bomber_id = bomber_id

    def update_data(self, map_size, arena, bombers, bomber_id):
        self.map_size = map_size
        self.arena = arena
        self.bombers = bombers
        self.bomber_id = bomber_id

    def set_zoom(self, zoom):
        self.zoom = zoom

    def set_offset(self, offset_x, offset_y):
        self.offset_x = offset_x
        self.offset_y = offset_y

    def draw(self, screen):
        if not self.map_size or not self.arena or not self.bombers:
            return
        # Create surface for drawing
        surface = pygame.Surface(
            (self.map_size[0] * self.cell_size, self.map_size[1] * self.cell_size)
        )
        surface.fill(self.BLACK)

        # Draw grid
        for x in range(0, self.map_size[0] * self.cell_size + 1, self.cell_size):
            pygame.draw.line(
                surface,
                self.DARK_GRAY,
                (x, 0),
                (x, self.map_size[1] * self.cell_size),
                1,
            )
        for y in range(0, self.map_size[1] * self.cell_size + 1, self.cell_size):
            pygame.draw.line(
                surface,
                self.DARK_GRAY,
                (0, y),
                (self.map_size[0] * self.cell_size, y),
                1,
            )

        # Draw obstacles
        for obs in self.arena["obstacles"]:
            x, y = obs
            pygame.draw.rect(
                surface,
                self.PINK,
                (
                    x * self.cell_size,
                    y * self.cell_size,
                    self.cell_size,
                    self.cell_size,
                ),
            )

        # Draw walls
        for wall in self.arena["walls"]:
            x, y = wall
            pygame.draw.rect(
                surface,
                self.WHITE,
                (
                    x * self.cell_size,
                    y * self.cell_size,
                    self.cell_size,
                    self.cell_size,
                ),
            )

        # Draw bombs
        for bomb in self.arena["bombs"]:
            if isinstance(bomb, dict) and "pos" in bomb:
                x, y = bomb["pos"]
                pygame.draw.circle(
                    surface,
                    self.RED,
                    (
                        x * self.cell_size + self.cell_size // 2,
                        y * self.cell_size + self.cell_size // 2,
                    ),
                    self.cell_size // 4,
                )

        # Draw bombers
        for bomber in self.bombers:
            if bomber["alive"]:
                x, y = bomber["pos"]
                color = self.GREEN if bomber["id"] == self.bomber_id else self.BLUE
                size = self.cell_size - 2
                offset = (self.cell_size - size) // 2
                pygame.draw.rect(
                    surface,
                    color,
                    (
                        x * self.cell_size + offset,
                        y * self.cell_size + offset,
                        size,
                        size,
                    ),
                )

        # Scale the surface
        scaled_width = int(self.map_size[0] * self.cell_size * self.zoom)
        scaled_height = int(self.map_size[1] * self.cell_size * self.zoom)
        scaled_surface = pygame.transform.scale(surface, (scaled_width, scaled_height))

        # Blit to screen
        screen.fill(self.BLACK)
        screen.blit(scaled_surface, (self.offset_x, self.offset_y))
