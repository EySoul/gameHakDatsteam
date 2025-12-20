import asyncio
import time
from collections import deque

class RateLimiter:
    def __init__(self, max_calls: int, period: float = 1.0):
        self.max_calls = max_calls  # 3 запроса
        self.period = period  # 1 секунда
        self.calls = deque()
        self.lock = asyncio.Lock()
    
    async def wait(self):
        async with self.lock:
            now = time.time()
            
            # Удаляем старые вызовы
            while self.calls and now - self.calls[0] > self.period:
                self.calls.popleft()
            
            # Если достигли лимита - ждем
            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    now = time.time()  # обновляем время после сна
                    # Снова удаляем старые вызовы
                    while self.calls and now - self.calls[0] > self.period:
                        self.calls.popleft()
            
            self.calls.append(now)


