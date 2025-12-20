# game_client.py
import asyncio
import logging
import time
from typing import Optional, Dict, Any
from controller.rate_limiter import RateLimiter
from models.parser import GameStateParser
from stategy.ai_controller import SmartAIController

class GameClient:
    def __init__(self, visualize: bool = False):
        self.rate_limiter = RateLimiter(max_calls=3, period=1.0)
        self.parser = GameStateParser()
        self.ai_controller = SmartAIController()
        self.running = False
        self.stats = {
            "cycles": 0,
            "errors": 0,
            "last_update": time.time()
        }
        
        # Визуализация
        self.visualize = visualize
        if visualize:
            self._init_visualization()
    
    def _init_visualization(self):
        """Инициализация визуализации (ленивый импорт)"""
        try:
            import pygame
            from paint import GameRenderer
            
            pygame.init()
            self.screen = pygame.display.set_mode((800, 600))
            pygame.display.set_caption("DatsJingleBang Bot Visualizer")
            self.renderer = GameRenderer(800, 600, cell_size=20)
            
            # Импортируем функции конвертации
            from models.converter import (
                convert_game_state_to_renderer,
                convert_threat_analyzer_to_renderer,
                create_debug_info
            )
            self.convert_game_state = convert_game_state_to_renderer
            self.convert_threat = convert_threat_analyzer_to_renderer
            self.create_debug_info = create_debug_info
            
            logging.info("✅ Визуализация инициализирована")
            
        except ImportError as e:
            logging.error(f"❌ Не удалось инициализировать визуализацию: {e}")
            logging.error("Установите pygame: pip install pygame")
            self.visualize = False
    
    async def run_game_cycle(self, get_arena_func, move_func):
        """Выполняет один игровой цикл"""
        try:
            # 1. Получаем состояние арены
            arena_data = await get_arena_func()
            if not arena_data:
                logging.warning("Не удалось получить состояние арены")
                self.stats["errors"] += 1
                return
            
            # 2. Парсим состояние
            game_state = self.parser.parse_arena_response(arena_data)
            
            # 3. Обновляем контроллер
            self.ai_controller.update_state(game_state)
            
            # 4. Генерируем команды
            move_commands = self.ai_controller.get_move_commands()
            
            # 5. Визуализация (если включена)
            if self.visualize:
                should_continue = self._update_visualization(game_state)
                if not should_continue:
                    self.running = False
            
            # 6. Отправляем команды
            if move_commands and move_commands.get("bombers"):
                logging.info(f"Отправляем команды для {len(move_commands['bombers'])} юнитов")
                await move_func(move_commands)
            
            # 7. Статистика
            self.stats["cycles"] += 1
            if self.stats["cycles"] % 10 == 0:
                self._print_stats()
                
        except Exception as e:
            logging.error(f"Ошибка в игровом цикле: {e}")
            self.stats["errors"] += 1
    
    def _update_visualization(self, game_state) -> bool:
        """Обновляет визуализацию, возвращает False если нужно остановиться"""
        if not self.visualize or not hasattr(self, 'renderer'):
            return True
        
        try:
            import pygame
            
            # Конвертируем данные для визуализации
            render_data = self.convert_game_state(game_state)
            danger_zones = self.convert_threat(self.ai_controller.threat_analyzer)
            
            # Создаем отладочную информацию
            debug_info = []
            if game_state.bombers:
                # Берем первого живого юнита для примера
                first_bomber = next((b for b in game_state.bombers.values() if b.alive), None)
                if first_bomber:
                    debug_info = self.create_debug_info(
                        game_state, 
                        self.ai_controller.threat_analyzer,
                        first_bomber.id
                    )
            
            # Обновляем рендерер
            self.renderer.update_data(
                render_data["map_size"],
                render_data["arena"],
                render_data["bombers"],
                render_data["enemies"],
                render_data["mobs"],
                danger_zones
            )
            
            # Отрисовываем
            self.renderer.draw(self.screen, debug_info)
            pygame.display.flip()
            
            # Обрабатываем события
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return False
                    elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                        self.renderer.zoom = min(2.0, self.renderer.zoom + 0.1)
                    elif event.key == pygame.K_MINUS:
                        self.renderer.zoom = max(0.5, self.renderer.zoom - 0.1)
                    elif event.key == pygame.K_SPACE:
                        # Пауза
                        self._handle_pause()
            
            return True
            
        except Exception as e:
            logging.error(f"Ошибка визуализации: {e}")
            return True
    
    def _handle_pause(self):
        """Обработка паузы"""
        import pygame
        logging.info("Пауза. Нажмите SPACE для продолжения, ESC для выхода")
        
        paused = True
        while paused:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    paused = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        paused = False
                    elif event.key == pygame.K_ESCAPE:
                        self.running = False
                        paused = False
            
            pygame.time.wait(100)
    
    def _print_stats(self):
        current_time = time.time()
        elapsed = current_time - self.stats["last_update"]
        rate = 10 / elapsed if elapsed > 0 else 0
        
        logging.info(f"📊 Статистика: {self.stats['cycles']} циклов, {self.stats['errors']} ошибок, {rate:.1f} циклов/сек")
        self.stats["last_update"] = current_time
    
    async def run(self, get_arena_func, move_func, duration_seconds: int = None):
        """Основной цикл игры"""
        logging.info(f"🚀 Запуск игры на {duration_seconds if duration_seconds else '∞'} секунд")
        self.running = True
        start_time = time.time()
        
        while self.running:
            try:
                # Проверяем время
                if duration_seconds and time.time() - start_time > duration_seconds:
                    logging.info(f"⏰ Время вышло ({duration_seconds} секунд)")
                    break
                
                # Выполняем цикл
                await self.run_game_cycle(get_arena_func, move_func)
                
                # Ждем следующий тик (~50мс)
                await asyncio.sleep(0.05)
                
            except KeyboardInterrupt:
                logging.info("👋 Получен сигнал прерывания")
                self.running = False
            except Exception as e:
                logging.error(f"💥 Критическая ошибка: {e}")
                await asyncio.sleep(1)
        
        # Завершаем визуализацию
        if self.visualize:
            try:
                import pygame
                pygame.quit()
            except:
                pass
        
        logging.info("🛑 Игра остановлена")