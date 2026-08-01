import asyncio
import os
import sqlite3
import re
import tempfile
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ============================================================
# 🔧 КОНФИГУРАЦИЯ
# ============================================================
BOT_TOKEN = "8545058389:AAE8YobYpPTOKVlQPj8jxjqXbU1LJDOIIZA"

# ============================================================
# 🗄️ БАЗА ДАННЫХ (SQLite)
# ============================================================
DB_PATH = "users_stats.db"


def init_db():
    """Создаёт таблицу users, если её нет."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            user_name TEXT NOT NULL DEFAULT '',
            count INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def get_or_create_user(user_id: int, user_name: str):
    """Возвращает строку пользователя, создаёт если нет."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, user_name, count FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if row is None:
        cur.execute("INSERT INTO users (id, user_name, count) VALUES (?, ?, 0)",
                    (user_id, user_name))
        conn.commit()
        row = (user_id, user_name, 0)
    else:
        # Обновляем имя, если изменилось
        if row[1] != user_name:
            cur.execute("UPDATE users SET user_name = ? WHERE id = ?",
                        (user_name, user_id))
            conn.commit()
            row = (user_id, user_name, row[2])
    conn.close()
    return {"id": row[0], "user_name": row[1], "count": row[2]}


def increment_count(user_id: int):
    """Увеличивает счётчик скачиваний на 1."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET count = count + 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_stats(user_id: int) -> dict:
    """Возвращает статистику пользователя."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, user_name, count FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "user_name": row[1], "count": row[2]}
    return None


# ============================================================
# 🤖 ИНИЦИАЛИЗАЦИЯ БОТА
# ============================================================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ============================================================
# 🧰 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def detect_source(url: str) -> str | None:
    """Определяет источник ссылки: 'youtube', 'instagram' или None."""
    youtube_pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/'
    instagram_pattern = r'(?:https?://)?(?:www\.)?(?:instagram\.com)/'
    if re.search(youtube_pattern, url):
        return 'youtube'
    if re.search(instagram_pattern, url):
        return 'instagram'
    return None


async def download_youtube_video(url: str) -> str | None:
    """
    Скачивает видео с YouTube через yt-dlp.
    Возвращает путь к временному файлу или None.
    """
    # Создаём временную папку для файла
    tmp_dir = tempfile.mkdtemp()
    output_template = os.path.join(tmp_dir, '%(title)s.%(ext)s')

    try:
        # Запускаем yt-dlp как subprocess (чтобы не тащить библиотеку в Python)
        proc = await asyncio.create_subprocess_exec(
            'yt-dlp',
            '-f', 'best[ext=mp4]/best',  # лучшее mp4-видео
            '-o', output_template,
            '--no-playlist',
            '--print', 'filename',       # выводит имя файла после скачивания
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            print(f"[yt-dlp error] {stderr.decode()}")
            return None

        # Получаем путь к скачанному файлу
        file_path = stdout.decode().strip()
        if file_path and os.path.exists(file_path):
            return file_path

        # Если yt-dlp не вывел filename — ищем любой файл во временной папке
        files = os.listdir(tmp_dir)
        if files:
            return os.path.join(tmp_dir, files[0])

        return None

    except Exception as e:
        print(f"[YouTube download error] {e}")
        return None


async def download_instagram_video(url: str) -> str | None:
    """
    Скачивает видео/Reels из Instagram через gallery-dl или instaloader.
    Используем gallery-dl (умеет IG).
    Возвращает путь к временному файлу или None.
    """
    tmp_dir = tempfile.mkdtemp()
    output_template = os.path.join(tmp_dir, '%(title)s_%(id)s.%(ext)s')

    try:
        proc = await asyncio.create_subprocess_exec(
            'gallery-dl',
            '--output', output_template,
            '--print', 'filename',
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            print(f"[gallery-dl error] {stderr.decode()}")
            return None

        file_path = stdout.decode().strip().split('\n')[0]
        if file_path and os.path.exists(file_path):
            return file_path

        files = os.listdir(tmp_dir)
        if files:
            return os.path.join(tmp_dir, files[0])

        return None

    except Exception as e:
        print(f"[Instagram download error] {e}")
        return None


async def download_video(url: str, source: str) -> str | None:
    """Универсальная функция скачивания."""
    if source == 'youtube':
        return await download_youtube_video(url)
    elif source == 'instagram':
        return await download_instagram_video(url)
    return None


# ============================================================
# 🎛️ ХЕНДЛЕРЫ
# ============================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Команда /start — приветствие."""
    user = message.from_user
    get_or_create_user(user.id, user.username or user.full_name)
    await message.answer(
        "👋 Привет! Я бот для скачивания видео.\n\n"
        "📥 Просто отправь мне ссылку на видео из <b>Instagram</b> или <b>YouTube</b>, "
        "и я скачаю его для тебя!\n\n"
        "📊 <b>/stats</b> — твоя статистика",
        parse_mode="HTML"
    )


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Команда /stats — статистика пользователя."""
    user_id = message.from_user.id
    stats = get_stats(user_id)
    if stats:
        await message.answer(
            f"📊 <b>Твоя статистика</b>\n\n"
            f"🆔 ID: <code>{stats['id']}</code>\n"
            f"👤 Имя: {stats['user_name']}\n"
            f"⬇️ Скачано видео: <b>{stats['count']}</b>",
            parse_mode="HTML"
        )
    else:
        await message.answer("Статистика пока пуста. Отправь мне ссылку!")


@dp.message(lambda msg: detect_source(msg.text or ""))
async def handle_video_link(message: types.Message):
    """Обрабатывает ссылки на видео."""
    url = message.text.strip()
    source = detect_source(url)
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.full_name

    # Создаём / обновляем пользователя
    get_or_create_user(user_id, user_name)

    # Отправляем статус
    status_msg = await message.answer("⏳ Начинаю скачивание...")

    try:
        # Скачиваем видео
        file_path = await download_video(url, source)

        if not file_path:
            await status_msg.edit_text(
                "❌ Не удалось скачать видео.\n"
                "Возможные причины:\n"
                "• Ссылка недоступна\n"
                "• Видео слишком длинное\n"
                "• Аккаунт приватный\n"
                "Попробуй другую ссылку."
            )
            return

        # Отправляем видео пользователю
        video = FSInputFile(file_path)
        await message.answer_video(
            video=video,
            caption="✅ Вот твоё видео!",
            supports_streaming=True
        )

        # Увеличиваем счётчик
        increment_count(user_id)

        # Удаляем статус
        await status_msg.delete()

        # Чистим временный файл
        try:
            os.remove(file_path)
            os.rmdir(os.path.dirname(file_path))
        except Exception:
            pass

    except Exception as e:
        print(f"[handle_video_link error] {e}")
        await message.answer("❌ Произошла ошибка при обработке видео.")


@dp.message()
async def handle_unknown(message: types.Message):
    """Обработчик прочих сообщений."""
    await message.answer(
        "🤷 Я понимаю только ссылки на видео из Instagram или YouTube.\n"
        "Просто отправь мне ссылку!"
    )


# ============================================================
# 🚀 ЗАПУСК
# ============================================================

async def main():
    """Точка входа."""
    print("🤖 Бот запущен...")
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
