from datetime import time
import pygame
import requests
import json
from collections import defaultdict

from paint import GameRenderer

domen = "https://games-test.datsteam.dev"
token = "d4d94a5f-c6aa-49af-b547-13897fb0896a"
prefix = "/api"


def get_arena():
    response = requests.get(f"{domen}{prefix}/arena", headers={"X-Auth-Token": token})
    return response.json()


def send_moves(commands):
    """Отправка команд для ВСЕХ юнитов в правильном формате"""
    print(f"📤 Отправка команд для всех юнитов: {json.dumps(commands, indent=2)}")
    try:
        response = requests.post(
            f"{domen}{prefix}/move",
            headers={"X-Auth-Token": token, "Content-Type": "application/json"},
            json=commands,
        )
        print(f"✅ Ответ сервера: {response.status_code}")
        print(f"📄 Тело ответа: {response.text}")
        return response.json()
    except Exception as e:
        print(f"❌ Ошибка при отправке команд: {str(e)}")
        return None


class UnitController:
    """Контроллер для управления несколькими юнитами"""
    
    def __init__(self):
        self.selected_unit_index = 0
        self.auto_mode = True  # Автоматическое управление для остальных юнитов
        self.last_command_time = 0
        self.command_cooldown = 0.3  # 300ms между командами
    
    def get_controlled_unit(self, bombers):
        """Получение текущего управляемого юнита"""
        alive_bombers = [b for b in bombers if b["alive"]]
        
        if not alive_bombers:
            return None
        
        # Обеспечиваем корректный индекс
        self.selected_unit_index = self.selected_unit_index % len(alive_bombers)
        return alive_bombers[self.selected_unit_index]
    
    def cycle_selected_unit(self, bombers):
        """Переключение между юнитами"""
        alive_bombers = [b for b in bombers if b["alive"]]
        if alive_bombers:
            self.selected_unit_index = (self.selected_unit_index + 1) % len(alive_bombers)
            unit = alive_bombers[self.selected_unit_index]
            print(f"🎯 Выбран юнит {self.selected_unit_index + 1}/{len(alive_bombers)}: ID={unit['id']}, Позиция={unit['pos']}")
    
    def generate_auto_commands(self, bombers, map_size, arena):
        """Генерация автоматических команд для всех юнитов"""
        commands = {"bombers": []}
        current_time = time.time()
        
        # Если слишком часто отправляем команды - ждем
        if current_time - self.last_command_time < self.command_cooldown:
            return None
        
        for i, unit in enumerate(bombers):
            if not unit["alive"] or not unit["can_move"]:
                continue
            
            command = {
                "id": unit["id"],
                "path": [],
                "bombs": []
            }
            
            # Для выбранного юнита не генерируем автоматические команды
            if i == self.selected_unit_index and not self.auto_mode:
                continue
            
            current_pos = unit["pos"]
            obstacles = arena.get("obstacles", [])
            
            # Простая стратегия: ищем препятствия в радиусе 3 клеток
            nearby_obstacles = []
            for obs in obstacles:
                if abs(obs[0] - current_pos[0]) + abs(obs[1] - current_pos[1]) <= 3:
                    nearby_obstacles.append(obs)
            
            # Если есть препятствия рядом и есть доступные бомбы - двигаемся к ним
            if nearby_obstacles and unit["bombs_available"] > 0:
                # Выбираем ближайшее препятствие
                target_obs = min(nearby_obstacles, 
                               key=lambda obs: abs(obs[0] - current_pos[0]) + abs(obs[1] - current_pos[1]))
                
                # Генерируем путь к препятствию (максимум 2 шага)
                path = [current_pos.copy()]
                steps = min(2, max(abs(target_obs[0] - current_pos[0]), abs(target_obs[1] - current_pos[1])))
                
                for step in range(1, steps + 1):
                    new_x = current_pos[0] + (target_obs[0] - current_pos[0]) * step // steps
                    new_y = current_pos[1] + (target_obs[1] - current_pos[1]) * step // steps
                    path.append([new_x, new_y])
                
                command["path"] = path
            
            # Если находимся в безопасной зоне и есть препятствия вокруг - ставим бомбу
            if nearby_obstacles and unit["safe_time"] > 1000 and unit["bombs_available"] > 0:
                command["bombs"] = [current_pos.copy()]
            
            commands["bombers"].append(command)
        
        self.last_command_time = current_time
        return commands if commands["bombers"] else None


if __name__ == "__main__":
    data = get_arena()
    map_size = data["map_size"]
    arena = data["arena"]
    bombers = data["bombers"]
    enemies = data.get("enemies", [])
    mobs = data.get("mobs", [])
    
    # Initialize Pygame
    pygame.init()
    screen_width = 800
    screen_height = 800
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Bomber Game Visualization")

    renderer = GameRenderer(screen_width, screen_height)
    renderer.update_data(map_size, arena, bombers, bombers[0]["id"] if bombers else None, enemies, mobs)

    zoom = 1.0
    offset_x = 0
    offset_y = 0
    dragging = False
    last_mouse = (0, 0)
    last_update = 0
    last_auto_command = 0
    
    # Инициализация контроллера юнитов
    unit_controller = UnitController()
    selected_bomber_id = bombers[0]["id"] if bombers else None
    auto_mode = True  # По умолчанию включено автоматическое управление

    running = True
    while running:
        current_time = pygame.time.get_ticks()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    zoom = min(zoom * 1.1, 5.0)
                    renderer.set_zoom(zoom)
                elif event.key == pygame.K_MINUS:
                    zoom = max(zoom / 1.1, 0.1)
                    renderer.set_zoom(zoom)
                elif event.key == pygame.K_TAB:
                    # Переключение между юнитами
                    unit_controller.cycle_selected_unit(bombers)
                    selected_bomber = unit_controller.get_controlled_unit(bombers)
                    selected_bomber_id = selected_bomber["id"] if selected_bomber else None
                elif event.key == pygame.K_a:
                    # Переключение режима (авто/ручной)
                    auto_mode = not auto_mode
                    unit_controller.auto_mode = auto_mode
                    print(f"🔄 Режим управления: {'АВТОМАТИЧЕСКИЙ' if auto_mode else 'РУЧНОЙ'}")
                elif event.key == pygame.K_SPACE:
                    # Установка бомбы для выбранного юнита
                    selected_bomber = next((b for b in bombers if b["id"] == selected_bomber_id), None)
                    if selected_bomber and selected_bomber["alive"] and selected_bomber["can_move"]:
                        # Отправляем команду только для этого юнита
                        command = {
                            "bombers": [{
                                "id": selected_bomber["id"],
                                "path": [],
                                "bombs": [selected_bomber["pos"].copy()]
                            }]
                        }
                        send_moves(command)
                        print(f"💣 Бомба установлена юнитом {selected_bomber_id} на позиции {selected_bomber['pos']}")
                elif selected_bomber_id and event.key in [
                    pygame.K_UP,
                    pygame.K_DOWN,
                    pygame.K_LEFT,
                    pygame.K_RIGHT,
                ] and not auto_mode:
                    # Ручное управление только в ручном режиме
                    selected_bomber = next((b for b in bombers if b["id"] == selected_bomber_id), None)
                    if selected_bomber and selected_bomber["alive"] and selected_bomber["can_move"]:
                        current_pos = selected_bomber["pos"]
                        new_pos = current_pos.copy()
                        
                        if event.key == pygame.K_UP:
                            new_pos[1] -= 1
                        elif event.key == pygame.K_DOWN:
                            new_pos[1] += 1
                        elif event.key == pygame.K_LEFT:
                            new_pos[0] -= 1
                        elif event.key == pygame.K_RIGHT:
                            new_pos[0] += 1
                        
                        # Проверка границ
                        if (0 <= new_pos[0] < map_size[0] and 
                            0 <= new_pos[1] < map_size[1] and 
                            new_pos != current_pos):
                            
                            # Отправляем команду движения для выбранного юнита
                            command = {
                                "bombers": [{
                                    "id": selected_bomber["id"],
                                    "path": [current_pos, new_pos],
                                    "bombs": []
                                }]
                            }
                            send_moves(command)
                            print(f"➡️ Юнит {selected_bomber_id} движется с {current_pos} на {new_pos}")
                elif event.key == pygame.K_s:
                    # Отправка автоматических команд для всех юнитов
                    commands = unit_controller.generate_auto_commands(bombers, map_size, arena)
                    if commands:
                        send_moves(commands)
                        print("🤖 Отправлены автоматические команды для всех юнитов")
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left mouse button
                    dragging = True
                    last_mouse = event.pos
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                dx = event.pos[0] - last_mouse[0]
                dy = event.pos[1] - last_mouse[1]
                offset_x += dx
                offset_y += dy
                renderer.set_offset(offset_x, offset_y)
                last_mouse = event.pos

        # Автоматическое обновление данных каждые 0.5 секунд
        if current_time - last_update > 500:
            new_data = get_arena()
            if new_data and "map_size" in new_data:
                data = new_data
                map_size = data["map_size"]
                arena = data["arena"]
                bombers = data["bombers"]
                enemies = data.get("enemies", [])
                mobs = data.get("mobs", [])
                
                # Обновление выбранного юнита (на случай смерти)
                if selected_bomber_id not in [b["id"] for b in bombers if b["alive"]]:
                    unit_controller.cycle_selected_unit(bombers)
                    selected_bomber = unit_controller.get_controlled_unit(bombers)
                    selected_bomber_id = selected_bomber["id"] if selected_bomber else None
                
                renderer.update_data(map_size, arena, bombers, selected_bomber_id, enemies, mobs)
                last_update = current_time
            else:
                print("❌ Получены некорректные данные, пропуск обновления")
        
        # Автоматическая отправка команд каждые 2 секунды (если включен авто-режим)
        if auto_mode and current_time - last_auto_command > 2000:
            commands = unit_controller.generate_auto_commands(bombers, map_size, arena)
            if commands:
                send_moves(commands)
                last_auto_command = current_time

        # Отображение информации о текущем режиме и выбранном юните
        info_text = f"Режим: {'АВТО' if auto_mode else 'РУЧНОЙ'} | Юнит: {unit_controller.selected_unit_index + 1 if bombers else 0}/{len([b for b in bombers if b['alive']]) if bombers else 0}"
        if selected_bomber_id:
            selected_bomber = next((b for b in bombers if b["id"] == selected_bomber_id), None)
            if selected_bomber:
                info_text += f" | Поз: {selected_bomber['pos']} | Бомбы: {selected_bomber['bombs_available']} | Безопасность: {selected_bomber['safe_time']}"
        
        pygame.display.set_caption(f"Bomber Game Visualization | {info_text}")

        renderer.draw(screen)
        pygame.display.flip()

    pygame.quit()