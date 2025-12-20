#!/usr/bin/env python3
"""
Визуализатор для DatsJingleBang
Просто показывает состояние игры в реальном времени
"""
import asyncio
import pygame
import sys
import os
import time
from datetime import datetime

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Импортируем визуализацию
from paint import GameRenderer

# API функции (такие же как у бота)
import aiohttp

# Конфигурация
DOMAIN = "https://games-test.datsteam.dev"
API_PREFIX = "api"
API_KEY = "d4d94a5f-c6aa-49af-b547-13897fb0896a"

HEADERS = {"X-Auth-Token": API_KEY, "Content-Type": "application/json"}

async def get_arena_data():
    """Получает данные арены с сервера"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{DOMAIN}/{API_PREFIX}/arena", 
                headers=HEADERS
            ) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            print(f"❌ Ошибка получения данных: {e}")
            return None

class GameVisualizer:
    def __init__(self):
        """Инициализация визуализатора"""
        pygame.init()
        
        # Размеры окна
        self.screen_width = 900
        self.screen_height = 600
        
        # Создаем окно
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption(f"DatsJingleBang Visualizer | API Key: {API_KEY[:10]}...")
        
        # Создаем рендерер
        self.renderer = GameRenderer(self.screen_width, self.screen_height, cell_size=25)
        
        # Состояние
        self.running = True
        self.paused = False
        self.last_update = 0
        self.update_interval = 0.2  # 5 обновлений в секунду
        
        # Данные игры
        self.game_data = None
        self.stats = {
            "updates": 0,
            "last_updated": None,
            "errors": 0
        }
        
        # Шрифт для текста
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 20)
        
        print("="*60)
        print("🎮 Визуализатор DatsJingleBang")
        print("="*60)
        print("Управление:")
        print("  ESC - выход")
        print("  ПРОБЕЛ - пауза/продолжение")
        print("  +/- - масштаб")
        print("  СТРЕЛКИ - перемещение камеры")
        print("="*60)
    
    def process_events(self):
        """Обрабатывает события PyGame"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                
                elif event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                    print(f"⏸️  Пауза: {'ВКЛ' if self.paused else 'ВЫКЛ'}")
                
                elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    self.renderer.zoom = min(2.0, self.renderer.zoom + 0.1)
                    print(f"🔍 Масштаб: {self.renderer.zoom:.1f}x")
                
                elif event.key == pygame.K_MINUS:
                    self.renderer.zoom = max(0.5, self.renderer.zoom - 0.1)
                    print(f"🔍 Масштаб: {self.renderer.zoom:.1f}x")
                
                elif event.key == pygame.K_UP:
                    self.renderer.offset_y += 20
                elif event.key == pygame.K_DOWN:
                    self.renderer.offset_y -= 20
                elif event.key == pygame.K_LEFT:
                    self.renderer.offset_x += 20
                elif event.key == pygame.K_RIGHT:
                    self.renderer.offset_x -= 20
                
                elif event.key == pygame.K_r:
                    # Сброс камеры
                    self.renderer.offset_x = 0
                    self.renderer.offset_y = 0
                    self.renderer.zoom = 1.0
                    print("🔄 Камера сброшена")
    
    def draw_info_panel(self):
        """Рисует панель с информацией"""
        if not self.game_data:
            return
        
        # Фон панели
        panel_rect = pygame.Rect(0, 0, 300, self.screen_height)
        pygame.draw.rect(self.screen, (30, 30, 40), panel_rect)
        pygame.draw.line(self.screen, (100, 100, 120), (300, 0), (300, self.screen_height), 2)
        
        y_offset = 20
        line_height = 30
        
        # Заголовок
        title = self.font.render("СТАТУС ИГРЫ", True, (255, 255, 100))
        self.screen.blit(title, (20, y_offset))
        y_offset += 40
        
        # Общая информация
        info_lines = [
            f"Раунд: {self.game_data.get('round', 'N/A')}",
            f"Игрок: {self.game_data.get('player', 'N/A')}",
            f"Очки: {self.game_data.get('raw_score', 0)}",
            f"Карта: {self.game_data.get('map_size', [0, 0])}",
            f"Обновлений: {self.stats['updates']}",
            f"Последнее: {self.stats['last_updated']}",
            f"Ошибок: {self.stats['errors']}",
            "",
            "ЮНИТЫ:"
        ]
        
        for line in info_lines:
            if line:
                text = self.small_font.render(line, True, (220, 220, 220))
                self.screen.blit(text, (20, y_offset))
            y_offset += line_height
        
        # Информация о юнитах
        bombers = self.game_data.get('bombers', [])
        for i, bomber in enumerate(bombers):
            if i >= 6:  # Показываем только первые 6
                break
            
            status = "🟢" if bomber.get('alive', False) else "🔴"
            bombs = bomber.get('bombs_available', 0)
            pos = bomber.get('pos', [0, 0])
            
            unit_text = f"  {status} Юнит {i+1}: ({pos[0]}, {pos[1]}) | 💣{bombs}"
            text = self.small_font.render(unit_text, True, 
                (100, 255, 100) if bomber.get('alive') else (150, 150, 150))
            self.screen.blit(text, (20, y_offset))
            y_offset += 22
        
        y_offset += 10
        
        # Мобы
        mobs = self.game_data.get('mobs', [])
        mobs_text = f"Мобов на карте: {len(mobs)}"
        text = self.small_font.render(mobs_text, True, (255, 100, 255))
        self.screen.blit(text, (20, y_offset))
        y_offset += 25
        
        # Препятствия
        arena = self.game_data.get('arena', {})
        obstacles = len(arena.get('obstacles', []))
        walls = len(arena.get('walls', []))
        
        obs_text = f"Препятствия: {obstacles} разруш."
        text = self.small_font.render(obs_text, True, (255, 182, 193))
        self.screen.blit(text, (20, y_offset))
        y_offset += 22
        
        walls_text = f"Стены: {walls} неразруш."
        text = self.small_font.render(walls_text, True, (100, 100, 100))
        self.screen.blit(text, (20, y_offset))
        
        # Состояние паузы
        if self.paused:
            pause_text = self.font.render("⏸️  ПАУЗА", True, (255, 100, 100))
            pause_rect = pause_text.get_rect(center=(150, self.screen_height - 40))
            self.screen.blit(pause_text, pause_rect)
        
        # FPS
        fps_text = f"FPS: {int(clock.get_fps())}"
        text = self.small_font.render(fps_text, True, (100, 200, 255))
        self.screen.blit(text, (20, self.screen_height - 25))
    
    def update_game_data(self, new_data):
        """Обновляет данные игры для отображения"""
        if not new_data:
            self.stats['errors'] += 1
            return False
        
        self.game_data = new_data
        self.stats['updates'] += 1
        self.stats['last_updated'] = datetime.now().strftime("%H:%M:%S")
        
        # Конвертируем данные для рендерера
        map_size = new_data.get('map_size', [50, 50])
        arena = new_data.get('arena', {})
        bombers = new_data.get('bombers', [])
        enemies = new_data.get('enemies', [])
        mobs = new_data.get('mobs', [])
        
        # Для мобов нужно преобразовать формат
        mobs_positions = []
        for mob in mobs:
            if isinstance(mob, dict) and 'pos' in mob:
                mobs_positions.append(mob['pos'])
        print("BOMBERS: ", bombers)
        # Обновляем рендерер
        bombers_data = bombers[0]
        self.renderer.update_data(
            map_size=map_size,
            arena=arena,
            bombers=bombers,
            bomber_id=bombers_data["id"] if bombers else None,
            enemies=enemies,
            mobs=mobs_positions
        )
        
        return True
    
    async def fetch_data(self):
        """Получает данные с сервера"""
        try:
            data = await get_arena_data()
            if data and data.get('code') == 0:
                return data
            return None
        except Exception as e:
            print(f"❌ Ошибка при запросе: {e}")
            return None
    
    async def run(self):
        """Основной цикл визуализатора"""
        print("🔄 Подключаюсь к серверу...")
        
        # Первоначальное получение данных
        initial_data = await self.fetch_data()
        if not initial_data:
            print("❌ Не удалось подключиться к серверу")
            return
        
        self.update_game_data(initial_data)
        print("✅ Подключение успешно!")
        
        # Основной цикл
        while self.running:
            current_time = time.time()
            
            # Обработка событий
            self.process_events()
            
            # Обновляем данные если не на паузе
            if not self.paused and current_time - self.last_update > self.update_interval:
                data = await self.fetch_data()
                if data:
                    self.update_game_data(data)
                self.last_update = current_time
            
            # Очищаем экран
            self.screen.fill((0, 0, 0))  # Черный фон
            
            # Рисуем игру
            self.renderer.draw(self.screen)
            
            # Рисуем панель информации
            self.draw_info_panel()
            
            # Обновляем экран
            pygame.display.flip()
            
            # Ограничиваем FPS
            clock.tick(60)
        
        # Завершение
        pygame.quit()
        print("\n👋 Визуализатор завершен")

# Глобальные переменные для PyGame
clock = pygame.time.Clock()

async def main():
    """Основная функция"""
    visualizer = GameVisualizer()
    await visualizer.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Программа завершена пользователем")
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()