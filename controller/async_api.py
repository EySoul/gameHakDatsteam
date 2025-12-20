import requests
import json
import logging
import asyncio
import aiohttp
from .rate_limiter import RateLimiter
domen = "https://games-test.datsteam.dev"
token = "d4d94a5f-c6aa-49af-b547-13897fb0896a"
prefix = "api"

BOOSTER_ENDPOINT = "booster"
ARENA_ENDPOINT = "arena"
LOGS_ENDPOINT = "logs"
MOVE_ENDPOINT = "move"
ROUNDS_ENDPOINT = "rounds"


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

HEADERS = {"X-Auth-Token": token, "Content-Type": "application/json"}

limiter = RateLimiter(max_calls=3, period=1.0)

async def get_arena_async():
    await limiter.wait()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{domen}/{prefix}/{ARENA_ENDPOINT}", headers=HEADERS) as response:
                response.raise_for_status()
                data = await response.json()
                logging.info(f"Я из {ARENA_ENDPOINT}")
                return data
        except aiohttp.ClientError as e:
            logging.error(f"Асинхронная ошибка {ARENA_ENDPOINT}: {e}")
            return None


async def get_booster_async():
    await limiter.wait()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{domen}/{prefix}/{BOOSTER_ENDPOINT}", headers=HEADERS) as response:
                response.raise_for_status()
                data = await response.json()
                logging.info(f"Я из {BOOSTER_ENDPOINT}")
                return data
        except aiohttp.ClientError as e:
            logging.error(f"Асинхронная ошибка {BOOSTER_ENDPOINT}: {e}")
            return None


async def improve_booster_async(booster: str):
    payload = {"booster": booster}

    await limiter.wait()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{domen}/{prefix}/{BOOSTER_ENDPOINT}", 
                headers=HEADERS,
                json=payload
            ) as response:
                response_data = await response.json()
                logging.info(f"Я из {BOOSTER_ENDPOINT} Ответ: {response_data}")
        except aiohttp.ClientError as e:
            logging.error(f"Ошибка в {BOOSTER_ENDPOINT} при '{booster}': {str(e)}")
            return None


async def get_logs_async():
    await limiter.wait()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{domen}/{prefix}/{LOGS_ENDPOINT}", headers=HEADERS) as response:
                response.raise_for_status()
                data = await response.json()
                logging.info(f"Я из {LOGS_ENDPOINT}")
                return data
        except aiohttp.ClientError as e:
            logging.error(f"Асинхронная ошибка {LOGS_ENDPOINT}: {e}")
            return None


async def move_async(move_data: dict):
    '''
        Передаваемый формат \n
        {
            "bombers": [
                {
                    "bombs": [
                        [
                            0
                        ]
                    ],
                    "id": "string",
                    "path": [
                        [
                            0
                        ]
                    ]
                }
            ]
        }
    '''
    await limiter.wait()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{domen}/{prefix}/{MOVE_ENDPOINT}", 
                headers=HEADERS,
                json=move_data
            ) as response:
                response_data = await response.json()
                logging.info(
                    f"""
                        Я из {MOVE_ENDPOINT}
                        Запрос: {move_data}
                        Ответ: {response_data}
                    """
                ) 
        except aiohttp.ClientError as e:
            logging.error(f"Ошибка в {MOVE_ENDPOINT} при '{move_data}': {str(e)}")
            return None


async def get_rounds_async():
    await limiter.wait()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{domen}/{prefix}/{ROUNDS_ENDPOINT}", headers=HEADERS) as response:
                response.raise_for_status()
                data = await response.json()
                logging.info(f"Я из {ROUNDS_ENDPOINT}")
                return data
        except aiohttp.ClientError as e:
            logging.error(f"Асинхронная ошибка {ROUNDS_ENDPOINT}: {e}")
            return None