import asyncio
import logging
import sys
from datetime import datetime
import sys
from pathlib import Path

from controller.async_api import get_arena_async, get_booster_async, get_logs_async, get_rounds_async, move_async
from controller.rate_limiter import RateLimiter
from game_logic.game_client import GameClient
from models.models import GameState
from models.parser import GameStateParser
from stategy.ai_controller import SimpleAIController, SmartAIController
from stategy.behaivour import ThreatAnalyzer

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


async def test_connection():
    """Тест подключения к серверу"""
    logging.info("Тестируем подключение к серверу...")
    
    # 1. Проверяем получение данных арены
    arena_data = await get_arena_async()
    if arena_data:
        logging.info(f"✅ Успешно подключились к серверу")
        logging.info(f"   Раунд: {arena_data.get('round')}")
        logging.info(f"   Карта: {arena_data.get('map_size')}")
        logging.info(f"   Юнитов: {len(arena_data.get('bombers', []))}")
        return True
    else:
        logging.error("❌ Не удалось подключиться к серверу")
        return False

async def test_rate_limiter():
    """Тест ограничителя запросов"""
    logging.info("Тестируем RateLimiter...")
    
    rate_limiter = RateLimiter(max_calls=3, period=1.0)
    
    start_time = datetime.now()
    
    # Делаем 5 запросов подряд
    for i in range(5):
        await rate_limiter.wait()
        logging.info(f"  Запрос {i+1} в {datetime.now().strftime('%H:%M:%S.%f')}")
    
    elapsed = (datetime.now() - start_time).total_seconds()
    logging.info(f"✅ 5 запросов заняли {elapsed:.2f} секунд")
    return elapsed >= 1.0  # Должно быть больше 1 секунды из-за лимита

async def test_game_state():
    """Тест парсера состояния игры"""
    logging.info("Тестируем парсер GameState...")
    
    arena_data = await get_arena_async()
    if not arena_data:
        return False
    
    parser = GameStateParser()
    game_state = parser.parse_arena_response(arena_data)
    
    logging.info(f"✅ Спарсили состояние игры:")
    logging.info(f"   Игрок: {game_state.player_name}")
    logging.info(f"   Очки: {game_state.raw_score}")
    logging.info(f"   Живых юнитов: {sum(1 for b in game_state.bombers.values() if b.alive)}")
    logging.info(f"   Препятствий: {len(game_state.obstacles)}")
    logging.info(f"   Мобов: {len(game_state.mobs)}")
    
    return True

async def test_simple_movement():
    """Тест простого движения юнитов"""
    logging.info("Тестируем простое движение...")
    
    # Создаем контроллер
    controller = SimpleAIController()
    
    # Получаем состояние
    arena_data = await get_arena_async()
    if not arena_data:
        return False
    
    parser = GameStateParser()
    game_state = parser.parse_arena_response(arena_data)
    
    # Обновляем контроллер
    controller.update_state(game_state)
    
    # Генерируем команды
    commands = controller.get_move_commands()
    
    logging.info(f"✅ Сгенерировали команды для {len(commands['bombers'])} юнитов")
    
    # Показываем пример команд
    if commands['bombers']:
        sample_cmd = commands['bombers'][0]
        logging.info(f"   Пример команды:")
        logging.info(f"     ID юнита: {sample_cmd['id']}")
        logging.info(f"     Путь: {len(sample_cmd['path'])} точек")
    
    return True

async def test_full_cycle():
    """Полный тест одного цикла игры"""
    logging.info("\n" + "="*50)
    logging.info("Запускаем полный тест цикла игры")
    logging.info("="*50)
    
    # 1. Тест подключения
    if not await test_connection():
        return False
    
    # 2. Тест RateLimiter
    if not await test_rate_limiter():
        return False
    
    # 3. Тест парсера
    if not await test_game_state():
        return False
    
    # 4. Тест движения
    if not await test_simple_movement():
        return False
    
    logging.info("\n" + "="*50)
    logging.info("✅ Все тесты пройдены успешно!")
    logging.info("="*50)
    return True

async def run_single_game_cycle():
    """Запуск одного игрового цикла (для отладки)"""
    logging.info("Запускаем один игровой цикл...")
    
    client = GameClient()
    
    try:
        # Получаем состояние
        arena_data = await get_arena_async()
        if not arena_data:
            return
        
        # Парсим
        parser = GameStateParser()
        game_state = parser.parse_arena_response(arena_data)
        client.ai_controller.update_state(game_state)
        
        # Генерируем ход
        move_commands = client.ai_controller.get_move_commands()
        
        # Отправляем (если есть что отправлять)
        if move_commands["bombers"]:
            logging.info(f"Отправляем команды для {len(move_commands['bombers'])} юнитов")
            await move_async(move_commands)
            logging.info("✅ Команды отправлены")
        else:
            logging.info("⚠️ Нет команд для отправки")
            
    except Exception as e:
        logging.error(f"Ошибка в игровом цикле: {e}")

async def run_game_for_time(seconds: int = 30):
    """Запуск игры на указанное время"""
    logging.info(f"Запускаем игру на {seconds} секунд...")
    
    client = GameClient()
    client.running = True
    
    start_time = asyncio.get_event_loop().time()
    
    while client.running:
        try:
            # Проверяем время
            current_time = asyncio.get_event_loop().time()
            if current_time - start_time > seconds:
                logging.info(f"Время вышло ({seconds} секунд)")
                client.running = False
                break
            
            # Выполняем цикл
            await client.run_game_loop()
            
        except KeyboardInterrupt:
            logging.info("Получен сигнал прерывания")
            client.running = False
            break
        except Exception as e:
            logging.error(f"Ошибка: {e}")
            await asyncio.sleep(1)
    
    logging.info("Игра остановлена")

async def main():
    """Запуск с визуализацией"""
    print("🤖 Запуск бота с визуализацией")
    print("="*50)
    print("Управление:")
    print("  ESC - выход")
    print("  +/- - масштаб")
    print("  SPACE - пауза")
    print("="*50)
    
    # Создаем компоненты
    parser = GameStateParser()
    ai_controller = SmartAIController()
    
    # Создаем клиент с визуализацией
    client = GameClient(visualize=True)
    client.parser = parser
    client.ai_controller = ai_controller
    
    # Запускаем на 5 минут
    await client.run(get_arena_async, move_async, duration_seconds=300)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Визуализация завершена")
    except Exception as e:
        print(f"💥 Ошибка: {e}")
        import traceback
        traceback.print_exc()