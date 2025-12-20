import json
import aiohttp
import asyncio
import logging
from datetime import datetime, time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from gameHakDatsteam.unit_logic.models import GameStateManager, RateLimiter
from gameHakDatsteam.unit_logic.stategy import UnitStrategyCoordinator



class GameOrchestrator:
    """
    Основной оркестратор игры с интеграцией RateLimiter
    """
    
    def __init__(self, api_base_url: str, auth_token: str):
        self.api_base_url = api_base_url.rstrip('/')
        self.auth_token = auth_token
        self.game_state_manager = GameStateManager()
        self.strategy_coordinator = UnitStrategyCoordinator(self.game_state_manager)
        self.session = None
        self.last_move_time = datetime.min
        # Внедрение RateLimiter для контроля запросов
        self.rate_limiter = RateLimiter(max_requests=3, period=1.0)  # 3 запроса в секунду
    
    async def get_arena_state(self) -> dict:
        """Получение состояния арены с API с применением rate limiting"""
        await self.rate_limiter.acquire()  # Ждем разрешения на запрос
        async with self.session.get(f"{self.api_base_url}/api/arena") as response:
            response.raise_for_status()
            return await response.json()
    
    async def send_move_commands(self, commands: dict) -> dict:
        """Отправка команд движения на API с применением rate limiting"""
        await self.rate_limiter.acquire()  # Ждем разрешения на запрос
        async with self.session.post(
            f"{self.api_base_url}/api/move",
            json=commands
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def _send_safe_commands(self, arena_: dict):
        """Отправка безопасных команд при ошибке"""
        safe_commands = {"bombers": []}
        
        for bomber in arena_['bombers']:
            if bomber['alive'] and bomber['can_move']:
                safe_commands["bombers"].append({
                    "id": bomber['id'],
                    "commands": [{
                        "command": "move",
                        "coordinates": [bomber['pos']]
                    }]
                })
        
        if safe_commands["bombers"]:
            try:
                await self.rate_limiter.acquire()
                async with self.session.post(
                    f"{self.api_base_url}/api/move",
                    json=safe_commands
                ) as response:
                    response.raise_for_status()
                logging.warning("Отправлены безопасные fallback-команды")
            except Exception as e:
                logging.error(f"Не удалось отправить безопасные команды: {str(e)}")

    async def game_loop(self):
        """ОСНОВНОЙ ИГРОВОЙ ЦИКЛ - СЮДА ВСЕ ДОБАВЛЯЕТСЯ"""
        try:
            logging.info("🚀 Игровой цикл запущен")
            
            while True:
                current_time = datetime.utcnow()
                
                # === ШАГ 1: Получение состояния арены ===
                try:
                    arena_data = await self.get_arena_state()
                    self.game_state_manager.update_from_api(arena_data)
                    logging.info(f"🎮 Состояние арены обновлено. Очки: {arena_data.get('raw_score', 0)}")
                except Exception as e:
                    logging.error(f"❌ Ошибка при получении состояния арены: {str(e)}")
                    await asyncio.sleep(0.1)
                    continue
                
                # === ШАГ 2: Генерация и отправка команд ===
                commands = self.strategy_coordinator.generate_commands()
                
                if commands["bombers"]:
                    try:
                        result = await self.send_move_commands(commands)
                        logging.info(f"✅ Команды отправлены успешно")
                    except Exception as e:
                        logging.error(f"❌ Ошибка при отправке команд: {str(e)}")
                        await self._send_safe_commands(arena_data)
                
                # === ШАГ 3: Адаптивная задержка ===
                next_request_time = self.rate_limiter.get_next_available_time()
                current_time = time.time()
                
                if next_request_time > current_time:
                    sleep_time = min(0.5, next_request_time - current_time)
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0.05)
                
        except asyncio.CancelledError:
            logging.info("🛑 Игровой цикл остановлен")
        except Exception as e:
            logging.critical(f"💥 Критическая ошибка в игровом цикле: {str(e)}", exc_info=True)
            raise

# Запуск игры
async def main():
    """Основная точка входа с полной интеграцией RateLimiter"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("game.log"),
            logging.StreamHandler()
        ]
    )
    
    API_BASE_URL = "https://games-test.datsteam.dev"
    AUTH_TOKEN = "d4d94a5f-c6aa-49af-b547-13897fb0896a"
    
    # Создаем оркестратор с автоматическим управлением ресурсами
    async with GameOrchestrator(API_BASE_URL, AUTH_TOKEN) as orchestrator:
        logging.info("🚀 Игровой цикл запущен. RateLimiter активен.")
        logging.info(f"⏱️  Лимит запросов: {orchestrator.rate_limiter.max_requests} в {orchestrator.rate_limiter.period} сек")
        
        try:
            await orchestrator.game_loop()
        except KeyboardInterrupt:
            logging.info("🛑 Игра остановлена пользователем")
        except Exception as e:
            logging.critical(f"💥 Необработанное исключение: {str(e)}", exc_info=True)
            # Пытаемся отправить безопасные команды даже при критической ошибке
            try:
                arena_state = await orchestrator.get_arena_state()
                await orchestrator._send_safe_commands(arena_state)
                logging.info("✅ Безопасные команды отправлены перед завершением")
            except:
                logging.warning("❌ Не удалось отправить безопасные команды при завершении")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Программа остановлена пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {str(e)}")
        logging.exception("Критическая ошибка на верхнем уровне")