import re
import os
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import telebot
import openbot_api
import sqlite3
import random
import time
import traceback
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import html
from telebot import apihelper
from datetime import datetime
from zoneinfo import ZoneInfo
import threading
from telebot import types
import newyear_random_db as winter_db
from telebot.handler_backends import BaseMiddleware, CancelUpdate
from openbot_api import ROLE # отдельная база события Random Bot (файл newyear_random_db.py): все её изменения идут только через этот модуль


# ======= Настройка ======
DB_NAME = str(Path(__file__).resolve().parent / "Random_bot.1.6.db")
WINTER_DB_NAME = "Newyear_random.db"
DEVELOPER_CHAT_ID = 6265920670
# test
KB_TYPE = False # Замените на свой ID
# ========================
TOKEN = "8493714047:AAGAVFDc_nvDR2S6LLpgDBhx85dikxJVMMY"
bot = telebot.TeleBot(TOKEN, use_class_middlewares=True)

OPENBOT_KEY = "openbot_staff_live_x7TDlXzrayMYFUhltO8VQJVLTuW_t8894leIPW087XA"
openbot = openbot_api.OpenbotAPI(api_key="openbot_staff_live_x7TDlXzrayMYFUhltO8VQJVLTuW_t8894leIPW087XA", bot=bot)

@bot.message_handler(commands=['test_error'])
def test_error(message):
    # Команда доступна только разработчику
    if message.from_user.id != DEVELOPER_CHAT_ID:
        return

    bot.reply_to(message, "🧪 Проверяю обработчик ошибок...")

    # Специально вызываем ошибку
    raise RuntimeError("Тестовая ошибка! Проверка GlobalExceptionHandler.")


@bot.message_handler(commands=['logs'])
def show_error_logs(message):
    if message.chat.type != 'private' or message.from_user.id != DEVELOPER_CHAT_ID:
        return

    try:
        if not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0:
            bot.reply_to(message, "✅ Ошибок пока нет.")
            return

        with LOG_FILE.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Последние 15 строк, максимум 1500 символов
        logs = "".join(lines[-15:])[-1500:]

        safe_logs = html.escape(logs)

        bot.reply_to(
            message,
            "📋 <b>Последние ошибки:</b>\n\n"
            f'<pre><code class="language-python">{safe_logs}</code></pre>',
            parse_mode="HTML"
        )

    except Exception:
        error_logger.exception("Ошибка чтения логов")
        bot.reply_to(message, "❌ Не удалось прочитать логи.")

def _ensure_maintenance_row():
    conn.execute("CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('maintenance', '0')")
    conn.commit()
 
 
def is_maintenance() -> bool:
    """Читает из БД: maintenance = 1 -> True, 0 -> False."""
    try:
        row = conn.execute("SELECT value FROM system_settings WHERE key = 'maintenance'").fetchone()
        return bool(row) and str(row[0]).strip() == "1"
    except Exception as e:
        print(f"[Maintenance] Не удалось прочитать флаг: {e}")
        return False  # если БД сбоит — не блокируем всех
 
 
def set_maintenance(enabled: bool) -> None:
    """Пишет в БД: True -> maintenance = 1, False -> maintenance = 0."""
    _ensure_maintenance_row()
    conn.execute("UPDATE system_settings SET value = ? WHERE key = 'maintenance'", ("1" if enabled else "0",))
    conn.commit()

MAINTENANCE_TEXT = "🟠 Ведутся технические работы. Зайдите позже!"
MAINTENANCE_ALLOWED = ("developer", "tester", "admin", "owner")
 
 
class MaintenanceMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self.update_types = ["message", "callback_query"]
 
    def pre_process(self, message, data):
        # При обратном отсчёте приоритет у праздничного экрана.
        if '_launch_pending' in globals() and _launch_pending():
            return None
        if not is_maintenance():
            return None
 
        user = getattr(message, "from_user", None)
        # Свои (developer / tester / admin / owner по openbot) проходят как обычно
        if user is not None and openbot.check_access(user.id, MAINTENANCE_ALLOWED, level=1):
            return None
 
        # Остальным — сообщение «тех. работы», обработчики НЕ вызываются
        try:
            if hasattr(message, "data"):          # нажатие inline-кнопки
                bot.answer_callback_query(message.id, MAINTENANCE_TEXT, show_alert=True)
            else:                                 # обычное сообщение / команда
                bot.send_message(message.chat.id, MAINTENANCE_TEXT)
        except Exception as e:
            print(f"[Maintenance] Не удалось ответить: {e}")
        return CancelUpdate()
 
    def post_process(self, message, data, exception):
        pass
 
 
bot.setup_middleware(MaintenanceMiddleware())

# -================================
# ======= Переменные ======
ALLOWED_ROLES = ["developer", "tester", "admin"]
STATUS = {
    "developer": "🌐💠 Openbot.Ai",
    "tester": "🌐 Тестер",
    "coder": "🌐 Кодер",
    "admin": "⭐ Администратор",
    "user": "👤 Игрок",
    "banned": "🚫 Забаненный",
}

PROFILE_TITLES = {
    "none": "Без титула", "veteran": "🎖 Ветеран", "king": "👑 Король", "legend_50": "🌟 Легенда",
    "pro": "🔥 Профи", "legend": "👑 Легенда",
    "winter_pioneer": "🏅 Первопроходец зимы",
}

# ========== База ========
conn = sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    """Инициализация базы Random Bot 1.6 без удаления существующих данных.

    Random Bot может иметь users.id вместо users.user_id. Мы добавляем
    совместимые поля и синхронизируем их, а не переименовываем/удаляем таблицы.
    """
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO system_settings (key, value)
        VALUES ('maintenance', '0')
    """)

    # USERS: создаём только если таблицы нет.
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [row[1] for row in cursor.fetchall()]
    if not user_cols:
        cursor.execute("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                first_name TEXT,
                status TEXT DEFAULT 'user',
                profile_title TEXT DEFAULT NULL,
                coins INTEGER DEFAULT 0,
                key_coleso INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                XP INTEGER DEFAULT 100,
                profile_emoji TEXT DEFAULT NULL,
                total_games INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                difficulty TEXT DEFAULT 'normal',
                tic_wins INTEGER DEFAULT 0,
                rps_wins INTEGER DEFAULT 0,
                role_level INTEGER DEFAULT 1,
                ban_reason TEXT DEFAULT NULL,
                global_ban_kind TEXT DEFAULT NULL,
                equipped_item TEXT DEFAULT '',
                kb_type TEXT DEFAULT 'inline',
                notifications INTEGER DEFAULT 1,
                show_id_to_others INTEGER DEFAULT 1,
                badge TEXT DEFAULT '',
                spooky_keys INTEGER DEFAULT 0,
                candies INTEGER DEFAULT 0,
                id INTEGER UNIQUE
            )
        """)
    else:
        # Random Bot 1.6 обычно использует id. Добавляем user_id как совместимый сугроб.
        if 'user_id' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN user_id INTEGER")
            if 'id' in user_cols:
                cursor.execute("UPDATE users SET user_id = id WHERE user_id IS NULL")

        additions = {
            'profile_title': "TEXT DEFAULT NULL",
            'coins': "INTEGER DEFAULT 0",
            'key_coleso': "INTEGER DEFAULT 0",
            'level': "INTEGER DEFAULT 1",
            'XP': "INTEGER DEFAULT 100",
            'profile_emoji': "TEXT DEFAULT NULL",
            'total_games': "INTEGER DEFAULT 0",
            'wins': "INTEGER DEFAULT 0",
            'difficulty': "TEXT DEFAULT 'normal'",
            'tic_wins': "INTEGER DEFAULT 0",
            'rps_wins': "INTEGER DEFAULT 0",
            'role_level': "INTEGER DEFAULT 1",
            'ban_reason': "TEXT DEFAULT NULL",
            'global_ban_kind': "TEXT DEFAULT NULL",
            'equipped_item': "TEXT DEFAULT ''",
            'kb_type': "TEXT DEFAULT 'inline'",
            'notifications': "INTEGER DEFAULT 1",
            'show_id_to_others': "INTEGER DEFAULT 1",
            'badge': "TEXT DEFAULT ''",
            'spooky_keys': "INTEGER DEFAULT 0",
            'snowflakes': "INTEGER DEFAULT 0",
            'id': "INTEGER",
        }
        candies_is_new = 'snowflakes' not in user_cols
        for name, definition in additions.items():
            if name not in user_cols:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
                except sqlite3.OperationalError:
                    pass
        # Один раз переносим старые Снежные сугроби в снежинки
        if candies_is_new and 'spooky_keys' in user_cols:
            cursor.execute("UPDATE users SET candies = COALESCE(spooky_keys, 0)")
        cursor.execute("PRAGMA table_info(users)")
        user_cols = [row[1] for row in cursor.fetchall()]
        if 'id' in user_cols:
            cursor.execute("UPDATE users SET id = user_id WHERE id IS NULL AND user_id IS NOT NULL")
        if 'user_id' in user_cols and 'id' in user_cols:
            cursor.execute("UPDATE users SET user_id = id WHERE user_id IS NULL AND id IS NOT NULL")

    # ACTIVE GAMES: сохраняем старые поля Random Bot и добавляем совместимые.
    cursor.execute("PRAGMA table_info(active_games)")
    game_cols = [row[1] for row in cursor.fetchall()]
    if not game_cols:
        cursor.execute("""
            CREATE TABLE active_games (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                game_type TEXT,
                secret_number INTEGER DEFAULT 0,
                attempts INTEGER DEFAULT 5,
                secret_code TEXT DEFAULT NULL,
                game_name TEXT,
                game_key TEXT,
                started_at TEXT,
                state_json TEXT DEFAULT '{}'
            )
        """)
    else:
        game_additions = {
            'user_id': 'INTEGER',
            'chat_id': 'INTEGER',
            'game_type': 'TEXT',
            'secret_number': 'INTEGER DEFAULT 0',
            'attempts': 'INTEGER DEFAULT 5',
            'secret_code': 'TEXT DEFAULT NULL',
            'game_name': 'TEXT',
            'game_key': 'TEXT',
            'started_at': 'TEXT',
            'state_json': "TEXT DEFAULT '{}'",
        }
        for name, definition in game_additions.items():
            if name not in game_cols:
                try:
                    cursor.execute(f"ALTER TABLE active_games ADD COLUMN {name} {definition}")
                except sqlite3.OperationalError:
                    pass
        # Переносим идентификатор игры из старых Random Bot полей.
        cursor.execute("UPDATE active_games SET game_type = COALESCE(game_type, game_key, game_name) WHERE game_type IS NULL")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_type TEXT,
            item_value TEXT,
            is_active INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS case_inventory (
            user_id INTEGER NOT NULL,
            case_key TEXT NOT NULL,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, case_key)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auction (
            lot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER,
            item_type TEXT,
            item_value TEXT,
            price INTEGER
        )
    """)

    conn.commit()

init_db()

# ======= База события «Новый год» (снежинки, кейсы, титулы) =======
# Снежинки и кейсы больше НЕ хранятся в основной базе (users.candies, case_inventory):
# они живут в Winter_random.db. В основной базе остаются как резервная копия.
# Внутри модуля снежинки хранятся как «сугроби» (один счётчик события).
winter_db.init(WINTER_DB_NAME)

# ======= Вспомогательные функции =======
# /reply_off временно переводит только role=user на Inline.
# /reply_on возвращает сохранённые предпочтения; роли выше user не меняются.
def _reply_staff(user_id):
    try:
        user = openbot.get_user(user_id)
        return (isinstance(user, dict) and user.get('exists') and
                str(user.get('status', '')).lower() in {'owner', 'developer'})
    except Exception:
        return False


def _reply_regular_user(user_id):
    # Не считаем сотрудника обычным пользователем при сбое Openbot API.
    try:
        info = openbot.get_user(user_id)
        return (isinstance(info, dict) and info.get('exists') and
                str(info.get('status', '')).lower() == 'user')
    except Exception:
        return False


def _reply_off_enabled():
    with sqlite3.connect(DB_NAME, timeout=10) as db:
        row = db.execute("SELECT value FROM system_settings WHERE key='reply_emergency_off'").fetchone()
    return bool(row and row[0] == '1')


def _reply_prepare_db():
    with sqlite3.connect(DB_NAME, timeout=10) as db:
        db.execute('CREATE TABLE IF NOT EXISTS reply_restore ('
                   'user_id INTEGER PRIMARY KEY, kb_type TEXT NOT NULL)')


_reply_prepare_db()


def get_user_settings(user_id):
    with sqlite3.connect(DB_NAME, timeout=10) as db:
        res = db.execute(
            'SELECT kb_type, notifications, show_id_to_others FROM users WHERE user_id=?',
            (user_id,)
        ).fetchone()
    kb_type = (res[0] or 'inline') if res else 'inline'
    if _reply_off_enabled() and _reply_regular_user(user_id):
        kb_type = 'inline'
    notifications = (res[1] if res[1] is not None else 1) if res else 1
    show_id = (res[2] if res[2] is not None else 1) if res else 1
    return kb_type, notifications, show_id


def mark_reply_mode(user_id):
    if _reply_off_enabled() and _reply_regular_user(user_id):
        return
    if get_user_settings(user_id)[0] != 'reply':
        with sqlite3.connect(DB_NAME, timeout=10) as db:
            db.execute("UPDATE users SET kb_type='reply' WHERE user_id=?", (user_id,))


_REPLY_EMERGENCY_MESSAGE = (
    "🚨 <b>ВРЕМЕННОЕ ОГРАНИЧЕНИЕ REPLY</b>\n\n"
    "При проверке Reply-клавиатуры обнаружена критическая ошибка. "
    "Чтобы избежать сбоев, её работа временно приостановлена.\n\n"
    "Пожалуйста, перейди на Inline-кнопки — они доступны под сообщениями бота.\n\n"
    "<b>P.S.</b> Рекомендуем использовать Inline-клавиатуру до завершения технических работ.\n\n"
    "С уважением, команда Openbot.Ai 🌐💠"
)


def _reply_emergency_markup():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton('➡️ Перейти на Inline', callback_data='reply:to_inline'))
    return kb


def _reply_reject_message(message):
    if not (_reply_off_enabled() and _reply_regular_user(message.from_user.id)):
        return False
    bot.send_message(message.chat.id, _REPLY_EMERGENCY_MESSAGE,
                     reply_markup=_reply_emergency_markup(), parse_mode='HTML')
    return True


def _reply_old_keyboard_button(text):
    value = (text or '').strip()
    exact = {
        '🎲 Рандом-мир', '❄️ Зимние игры', '👤 Профиль', '🎁 Зимняя лавка',
        '🎒 Инвентарь', '🏪 Рынок', '⚙️ Настройки', '⚙ Настройки',
        '⬅ Главное меню', '⬅ В главное меню', '⬅ Игры', '⬅ Магазин',
        '⬅ Зимняя лавка', '⬅ Инвентарь', '⬅ Рынок',
        '🎁 Кейсы', '🏆 Титулы', '⭐ Магазин Stars', '🏆 Мои титулы',
        '📊 Лидеры', '📅 Календарь декабря', '📅 Календарь ноября',
        '🎁 Код от подарка', '❄️ Зимние сугробы', '⛄ Поиск снеговика',
        '🎄 Ёлочная игрушка', '🎁 Выбор подарка', '❌⭕ Крестики-нолики',
        '🛑 Выйти из игры', '⬅ Предыдущие кейсы', 'Следующие кейсы ➡',
        '📦 Мои лоты', '◀️ Предыдущая страница', 'Следующая страница ▶️',
        '◀️ Предыдущая страница рынка', 'Следующая страница рынка ▶️',
    }
    prefixes = ('⌨ Переключить вид кнопок:', '🔔 Уведомления:',
                '🔕 Уведомления:', '👁 ID для других:', '🙈 ID для других:',
                '🛒 ', '🔓 Открыть ', '👕 ', '💰 Продать ', '🏪 Выставить ',
                '❌ Снять лот #', '❄️ Сугроб ', '🚪 Комната ',
                '🧪 Шар ', '🎁 Подарок ', '❌⭕ ', '🏆 ', '🔒 ')
    return value in exact or value.startswith(prefixes)


@bot.message_handler(func=lambda m: _reply_old_keyboard_button(m.text)
                     and _reply_off_enabled() and _reply_regular_user(m.from_user.id))
def _reply_off_regular_text(message):
    """Старые Reply-кнопки не обходят режим ограничения; есть путь на Inline."""
    _reply_reject_message(message)


@bot.callback_query_handler(func=lambda c: (c.data or '') == 'reply:to_inline')
def _reply_switch_inline(call):
    uid = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    with sqlite3.connect(DB_NAME, timeout=15) as db:
        row = db.execute('SELECT kb_type FROM users WHERE user_id=?', (uid,)).fetchone()
        already_inline = bool(row and row[0] == 'inline')
        if not already_inline:
            db.execute("UPDATE users SET kb_type='inline' WHERE user_id=?", (uid,))

    # Если Inline уже активна, не трогаем клавиатуру и не шлём лишних сообщений.
    # Просто превращаем сообщение с заглушкой в главное меню.
    if already_inline:
        bot.answer_callback_query(call.id, '🏠 Главное меню')
        return bot.edit_message_text(
            '🏠 <b>Главное меню Random Bot</b>',
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=main_mune(),
            parse_mode='HTML',
        )

    # Реально активную Reply-клавиатуру Telegram можно скрыть только
    # отдельным сообщением с ReplyKeyboardRemove.
    bot.answer_callback_query(call.id, '✅ Переключено на Inline')
    bot.send_message(chat_id, '✅ Теперь используется Inline-клавиатура.',
                     reply_markup=types.ReplyKeyboardRemove())
    bot.edit_message_text(
        '🏠 <b>Главное меню Random Bot</b>',
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=main_mune(),
        parse_mode='HTML',
    )


@bot.message_handler(commands=['reply_off'])
def reply_off_everyone(message):
    """Временно отключить Reply только для Openbot ID role=user."""
    if message.chat.type != 'private' or not _reply_staff(message.from_user.id):
        return bot.reply_to(message, '⛔ Команда доступна только developer и owner.')
    changed = []
    with sqlite3.connect(DB_NAME, timeout=15) as db:
        people = db.execute('SELECT user_id,kb_type FROM users WHERE user_id IS NOT NULL').fetchall()
    for user_id, old_mode in people:
        if not _reply_regular_user(user_id):
            continue
        if old_mode == 'reply':
            changed.append(user_id)
        with sqlite3.connect(DB_NAME, timeout=15) as db:
            db.execute('INSERT OR IGNORE INTO reply_restore(user_id,kb_type) VALUES(?,?)',
                       (user_id, old_mode if old_mode in ('inline','reply') else 'inline'))
            db.execute("UPDATE users SET kb_type='inline' WHERE user_id=?", (user_id,))
    with sqlite3.connect(DB_NAME, timeout=15) as db:
        db.execute("INSERT INTO system_settings(key,value) VALUES('reply_emergency_off','1') "
                   "ON CONFLICT(key) DO UPDATE SET value='1'")
    # Не удаляем Reply сразу: при нажатии старой кнопки игрок увидит заглушку
    # и сам выберет «Перейти на Inline».
    bot.reply_to(message, f'✅ Reply ограничена для обычных игроков. '
                          f'Сохранено режимов Reply: {len(changed)}. '
                          'Старые кнопки покажут уведомление с переходом на Inline. '
                          'Сотрудники не затронуты; /reply_on восстановит предпочтения.')

@bot.message_handler(commands=['reply_on'])
def reply_on_everyone(message):
    """Восстановить прежние режимы игроков, сохранённые при /reply_off."""
    if message.chat.type != 'private' or not _reply_staff(message.from_user.id):
        return bot.reply_to(message, '⛔ Команда доступна только developer и owner.')
    restored = []
    with sqlite3.connect(DB_NAME, timeout=15) as db:
        saved = db.execute('SELECT user_id,kb_type FROM reply_restore').fetchall()
    for uid, mode in saved:
        if not _reply_regular_user(uid):
            continue
        with sqlite3.connect(DB_NAME, timeout=15) as db:
            db.execute('UPDATE users SET kb_type=? WHERE user_id=?', (mode, uid))
            db.execute('DELETE FROM reply_restore WHERE user_id=?', (uid,))
        restored.append((uid,mode))
    with sqlite3.connect(DB_NAME, timeout=15) as db:
        db.execute("INSERT INTO system_settings(key,value) VALUES('reply_emergency_off','0') "
                   "ON CONFLICT(key) DO UPDATE SET value='0'")
    delivered = 0
    for uid, mode in restored:
        try:
            if mode == 'reply':
                bot.send_message(uid, '⌨️ Твой прежний режим Reply восстановлен.',
                                 reply_markup=main_mune_reply())
            else:
                bot.send_message(uid, '⌨️ Inline-клавиатура доступна.',
                                 reply_markup=types.ReplyKeyboardRemove())
                bot.send_message(uid, '🏠 Главное меню', reply_markup=main_mune())
            delivered += 1
        except Exception:
            logging.getLogger('random_bot.reply').warning('Нельзя восстановить клавиатуру %s', uid)
    bot.reply_to(message, f'✅ Режимы восстановлены у {len(restored)} пользователей. '
                          f'Уведомлено: {delivered}. Теперь переключение снова доступно всем.')


def toggle_user_setting(user_id, setting_name):
    kb_type, notifications, show_id = get_user_settings(user_id)

    cursor = conn.cursor()

    if setting_name == 'kb_type':
        if kb_type == 'inline' and _reply_off_enabled() and _reply_regular_user(user_id):
            return 'inline'
        if kb_type == 'inline':
            new_val = 'reply'
        else:
            new_val = 'inline'

        cursor.execute(
            "UPDATE users SET kb_type = ? WHERE user_id = ?",
            (new_val, user_id)
        )

        conn.commit()
        return new_val

    elif setting_name == 'notifications':
        new_val = 0 if notifications == 1 else 1

        cursor.execute(
            "UPDATE users SET notifications = ? WHERE user_id = ?",
            (new_val, user_id)
        )

        conn.commit()
        return new_val

    elif setting_name == 'show_id':
        new_val = 0 if show_id == 1 else 1

        cursor.execute(
            "UPDATE users SET show_id_to_others = ? WHERE user_id = ?",
            (new_val, user_id)
        )

        conn.commit()
        return new_val
    
def get_openbot_user(user_id):
    """Глобальные данные игрока из openbot (локально, без HTTP): {'status', 'level'} или None."""
    try:
        data = openbot.get_id(user_id)
        if not data:
            return None
        return {
            "status": str(data[6] or "user").strip().lower(),
            "level": int(data[10] or 1),
        }
    except Exception as e:
        print(f"[OpenBot ID] Ошибка чтения данных {user_id}: {e}")
        return None
    

def sync_global_status(user_id, *, global_ban=None):
    """Синхронизирует отображаемый статус без изменения роли в Openbot ID.

    Исходная роль берётся из центрального Openbot ID. Локальные и глобальные
    наказания не изменяют её, а только временно показывают «Забаненный».
    Если все наказания сняты, сразу возвращается исходная роль (developer и т.д.).
    """
    try:
        global_user = get_openbot_user(user_id)
        if not global_user:
            return False

        if global_ban is None:
            global_ban = openbot.get_global_ban(user_id)
        if not isinstance(global_ban, dict) or not isinstance(
            global_ban.get('banned'), bool
        ):
            raise ValueError('Openbot API не вернул статус глобального бана')

        local_ban = _punishment_get(user_id)
        global_kind = (
            global_ban.get('kind') if global_ban['banned'] else None
        )
        role = str(global_user.get('status') or 'user').lower()
        level = int(global_user.get('level') or 1)
        status = 'banned' if local_ban or global_kind else role
        reason = (
            local_ban.get('reason') if local_ban
            else global_ban.get('reason') if global_kind else None
        )

        with conn:
            row = conn.execute(
                'SELECT status, role_level, ban_reason, global_ban_kind '
                'FROM users WHERE user_id=?', (user_id,),
            ).fetchone()
            if not row:
                return False
            values = (status, level, reason, global_kind)
            if tuple(row) == values:
                return False
            conn.execute(
                'UPDATE users SET status=?, role_level=?, '
                'ban_reason=?, global_ban_kind=? WHERE user_id=?',
                (*values, user_id),
            )
        return True
    except Exception as exc:
        logging.getLogger('random_bot.status').warning(
            'Не удалось синхронизировать статус user_id=%s: %s',
            user_id, exc,
        )
        return False


def get_user(user_id):
    sync_global_status(user_id)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, first_name, status, profile_title, coins, level, XP
        FROM users WHERE user_id = ?
    """, (user_id,))
    return cursor.fetchone()

def get_equipped_emoji(user_id):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT equipped_item FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    return row[0] if row and row[0] else ""

def create_user(user_id, username, first_name):
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, first_name, status, role_level) VALUES (?, ?, ?, 'user', 1)",
            (user_id, username.lower() if username else None, first_name))
        conn.commit()

def add_coins(user_id, amount):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def count_matched_digits(secret, guess):
    return sum(1 for s, g in zip(secret, guess) if s == g)

def has_access(user_id):
    """Доступ для команды (developer / tester / admin / owner) — через openbot."""
    return openbot.check_access(user_id, ("developer", "tester", "admin", "owner"))

def check_ban(user_id):
    """Проверка только старых локальных банов без записи в punishments.

    Глобальные баны и новые локальные блокировки контролируют middleware.
    Нельзя блокировать профиль при обычном GLOBAL BAN только из-за того, что
    статус локально отображается как «Забаненный».
    """
    row = conn.execute(
        'SELECT status, ban_reason, global_ban_kind '
        'FROM users WHERE user_id=?', (user_id,),
    ).fetchone()
    if not row or row[0] != 'banned' or row[2]:
        return None
    if _punishment_get(user_id) is not None:
        return None
    return row[1] or None


# ========= спомогательные функции ==========
def add_xp(user_id, amount):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET XP = XP + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def set_active_game(user_id, chat_id, game_type, secret_number=0, attempts=5, secret_code=None):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO active_games (user_id, chat_id, game_type, secret_number, attempts, secret_code) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, chat_id, game_type, secret_number, attempts, secret_code))
    conn.commit()

def get_active_game(user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT game_type, secret_number, attempts, secret_code FROM active_games WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def update_game_state(user_id, secret_number=0, attempts=5, secret_code=None):
    cursor = conn.cursor()
    cursor.execute("UPDATE active_games SET secret_number = ?, attempts = ?, secret_code = ? WHERE user_id = ?", 
                   (secret_number, attempts, secret_code, user_id))
    conn.commit()

def update_game_attempts(user_id, attempts):
    cursor = conn.cursor()
    cursor.execute("UPDATE active_games SET attempts = ? WHERE user_id = ?", (attempts, user_id))
    conn.commit()

def delete_active_game(user_id):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_games WHERE user_id = ?", (user_id,))
    conn.commit()

# ===== Крестики-нолики: три уровня ИИ (0=пусто, 1=игрок, 2=бот) =====
from functools import lru_cache

_TTT_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8),
              (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))
_TTT_LEVELS = {'easy': '🟢 Лёгкий', 'normal': '🟡 Средний', 'hard': '🔴 Сложный'}
_TTT_REWARDS = {'easy': (20, 10), 'normal': (40, 25), 'hard': (80, 50)}


def ttt_winner(board):
    for a, b, c in _TTT_LINES:
        if board[a] != '0' and board[a] == board[b] == board[c]:
            return board[a]
    return 'draw' if '0' not in board else None


@lru_cache(maxsize=10000)
def _ttt_minimax(board_str, player):
    result = ttt_winner(board_str)
    if result == '2':
        return 1
    if result == '1':
        return -1
    if result == 'draw':
        return 0
    possible = []
    for i, char in enumerate(board_str):
        if char == '0':
            next_board = board_str[:i] + player + board_str[i + 1:]
            possible.append(_ttt_minimax(next_board, '1' if player == '2' else '2'))
    return max(possible) if player == '2' else min(possible)


def ttt_ai_move(board, difficulty='hard'):
    """Три сложности. Сложный ИИ иногда рискует, но не пропускает мгновенную угрозу."""
    options = [i for i, v in enumerate(board) if v == '0']
    if not options or ttt_winner(board):
        return None

    # Простой уровень почти всегда выбирает случайную клетку.
    if difficulty == 'easy':
        return random.choice(options)

    def after_move(pos, symbol):
        candidate = board.copy()
        candidate[pos] = symbol
        return candidate

    # Выигрыш за один ход приоритетнее любого случайного решения.
    wins = [p for p in options if ttt_winner(after_move(p, '2')) == '2']
    if wins:
        return random.choice(wins)

    # На сложном уровне защита от немедленного проигрыша обязательна.
    blocks = [p for p in options if ttt_winner(after_move(p, '1')) == '1']
    if blocks and difficulty == 'hard':
        return random.choice(blocks)

    # Промежуточный уровень иногда не замечает опасный ход.
    if difficulty == 'normal' and random.random() < 0.35:
        return random.choice(options)

    board_str = ''.join(board)
    priority = (4, 0, 2, 6, 8, 1, 3, 5, 7)
    moves = []
    for pos in options:
        candidate = board_str[:pos] + '2' + board_str[pos + 1:]
        value = _ttt_minimax(candidate, '1')
        # При равном результате используем не только центр, но и разные ходы.
        moves.append((pos, value))

    best_score = max(score for _, score in moves)
    best_moves = [pos for pos, score in moves if score == best_score]
    alternatives = [pos for pos, score in moves if score < best_score]

    # 18%: сложный ИИ выбирает рискованный ход только при отсутствии
    # прямой угрозы и возможности немедленно победить. Поэтому ничьих меньше.
    if difficulty == 'hard' and alternatives and random.random() < 0.18:
        # Отсеиваем совсем грубые ошибки: не даём игроку выиграть одним ходом.
        tolerable = []
        for pos in alternatives:
            next_board = after_move(pos, '2')
            available = [i for i, v in enumerate(next_board) if v == '0']
            if not any(ttt_winner(next_board[:i] + ['1'] + next_board[i+1:]) == '1'
                       for i in available):
                tolerable.append(pos)
        if tolerable:
            return random.choice(tolerable)

    # По возможности делаем игру разнообразной среди одинаково сильных ходов.
    if difficulty == 'hard':
        return random.choice(best_moves)
    return min(best_moves, key=lambda pos: priority.index(pos))


def ttt_get_level(user_id):
    row = conn.execute('SELECT state_json FROM active_games WHERE user_id=? AND game_type=?',
                       (user_id, 'ttt')).fetchone()
    if row and row[0]:
        try:
            level = json.loads(row[0]).get('difficulty', 'normal')
            if level in _TTT_LEVELS:
                return level
        except (ValueError, TypeError, AttributeError):
            pass
    return 'normal'


def ttt_start(user_id, chat_id, level):
    if level not in _TTT_LEVELS:
        raise ValueError('Неверная сложность')
    set_active_game(user_id, chat_id, 'ttt', secret_code='0' * 9)
    conn.execute('UPDATE active_games SET state_json=? WHERE user_id=?',
                 (json.dumps({'difficulty': level}), user_id))
    conn.commit()


def ttt_level_markup(reply=False):
    if reply:
        kb = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        for key, title in _TTT_LEVELS.items():
            kb.add(types.KeyboardButton(f'❌⭕ {title}'))
        kb.add(types.KeyboardButton('⬅ Игры'))
        return kb
    kb = types.InlineKeyboardMarkup(row_width=1)
    for key, title in _TTT_LEVELS.items():
        kb.add(types.InlineKeyboardButton(title, callback_data=f'ttt_level_{key}'))
    kb.add(types.InlineKeyboardButton('⬅ Игры', callback_data='game'))
    return kb


def ttt_play(user_id, pos):
    """Применить ход и выдать финальную награду; возвращает (результат, доска, текст)."""
    game = get_active_game(user_id)
    if not game or game[0] != 'ttt':
        return 'invalid', None, 'Игра не активна. Выбери сложность заново.'
    board_text = game[3]
    if not isinstance(board_text, str) or len(board_text) != 9 or any(x not in '012' for x in board_text):
        return 'invalid', None, 'Некорректная доска. Начни игру заново.'
    board = list(board_text)
    if not isinstance(pos, int) or pos not in range(9) or board[pos] != '0' or ttt_winner(board):
        return 'invalid', board_text, 'Эта клетка занята или игра уже завершена.'
    level = ttt_get_level(user_id)
    board[pos] = '1'
    result = ttt_winner(board)
    if result is None:
        ai = ttt_ai_move(board, level)
        if ai is not None:
            board[ai] = '2'
        result = ttt_winner(board)
    board_str = ''.join(board)
    if result:
        delete_active_game(user_id)
        if result == '1':
            coins, xp = _TTT_REWARDS[level]
            add_coins(user_id, coins)
            add_xp(user_id, xp)
            return 'done', board_str, f'🎉 <b>Победа!</b>\n💰 +{coins} монет · ⭐ +{xp} XP'
        if result == '2':
            return 'done', board_str, '🤖 <b>ИИ победил!</b> Попробуй ещё раз.'
        return 'done', board_str, '🤝 <b>Ничья!</b> Хорошая партия.'
    update_game_state(user_id, secret_code=board_str)
    return 'playing', board_str, f'❌⭕ <b>Крестики-нолики</b>\nСложность: {_TTT_LEVELS[level]}\n\nТвой ход: ❌'


def ttt_board_text(board):
    # Пробел вместо значка в незанятой клетке.
    icons = {'0': '　', '1': '❌', '2': '⭕'}
    return '\n'.join(' '.join(icons[ch] for ch in board[i:i+3]) for i in (0, 3, 6))


def build_ttt_keyboard(board_str, finished=False):
    """Поле 3×3: незанятые кнопки без видимого символа.

    Telegram сам управляет фоном кнопок, сделать его прозрачным через Bot API нельзя.
    Невидимый U+200B оставляет место для нажатия, не рисуя квадрат/эмодзи.
    """
    markup = types.InlineKeyboardMarkup(row_width=3)
    symbols = {'0': '\u200b', '1': '❌', '2': '⭕'}
    for start in range(0, 9, 3):
        row = []
        for i in range(start, start + 3):
            row.append(types.InlineKeyboardButton(
                symbols[board_str[i]],
                callback_data='ttt_done' if finished else f'ttt_pos_{i}'
            ))
        markup.row(*row)
    if not finished:
        markup.add(types.InlineKeyboardButton('🛑 Выход из игры', callback_data='back_to_games'))
    return markup

# ============= Снежинки ❄️ =============
CHEST_COST = 5            # цена праздничных кейсов в снежинках (без событий)

def add_candies(user_id, amount, source=None):
    """source: 'game' / 'lock' / 'drop' / 'house' / 'gift' — считаются в достижениях."""
    winter_db.add_keys(user_id, amount, source or "snowflakes")
    # Счётчик снежинок — в новогодней БД. Рандом-мир больше не используется.

def get_candies(user_id):
    return winter_db.get_keys(user_id)


# ============= КЕЙСЫ =============
# Количество кейсов хранится отдельно в case_inventory.
# Награды используют уже существующие в боте: монеты, XP, эмодзи и снежинки.
CASES = {

    "wood": {
        "name": "📦 Деревянный кейс",
        "description": "Первый кейс. Небольшие награды и обычные эмодзи.",
        "price": 500,
        "currency": "coins",
        "rewards": [
            {"type": "coins", "amount": 300, "chance": 35},
            {"type": "coins", "amount": 750, "chance": 25},
            {"type": "xp", "amount": 100, "chance": 20},
            {"type": "emoji", "value": "🙂", "chance": 10},
            {"type": "emoji", "value": "😎", "chance": 7},
            {"type": "emoji", "value": "🤩", "chance": 3},
        ],
    },

    "silver": {
        "name": "🥈 Серебряный кейс",
        "description": "Больше монет, опыта и необычные эмодзи.",
        "price": 2_000,
        "currency": "coins",
        "rewards": [
            {"type": "coins", "amount": 1_000, "chance": 30},
            {"type": "coins", "amount": 3_000, "chance": 25},
            {"type": "xp", "amount": 300, "chance": 20},
            {"type": "emoji", "value": "😱", "chance": 10},
            {"type": "emoji", "value": "🤖", "chance": 8},
            {"type": "emoji", "value": "🦊", "chance": 5},
            {"type": "candy", "amount": 3, "chance": 2},
        ],
    },

    "gold": {
        "name": "🥇 Золотой кейс",
        "description": "Ценные награды и редкие эмодзи.",
        "price": 7_500,
        "currency": "coins",
        "rewards": [
            {"type": "coins", "amount": 3_000, "chance": 30},
            {"type": "coins", "amount": 10_000, "chance": 25},
            {"type": "xp", "amount": 750, "chance": 18},
            {"type": "emoji", "value": "👑", "chance": 10},
            {"type": "emoji", "value": "🔥", "chance": 8},
            {"type": "emoji", "value": "❄️", "chance": 6},
            {"type": "candy", "amount": 3, "chance": 3},
        ],
    },

    "diamond": {
        "name": "💎 Алмазный кейс",
        "description": "Высокая стоимость, крупные награды и очень редкие эмодзи.",
        "price": 25_000,
        "currency": "coins",
        "rewards": [
            {"type": "coins", "amount": 10_000, "chance": 28},
            {"type": "coins", "amount": 40_000, "chance": 24},
            {"type": "xp", "amount": 2_000, "chance": 18},
            {"type": "emoji", "value": "💎", "chance": 10},
            {"type": "emoji", "value": "⚡", "chance": 8},
            {"type": "emoji", "value": "🐉", "chance": 7},
            {"type": "candy", "amount": 3, "chance": 5},
        ],
    },

    "fire": {
        "name": "🔥 Огненный кейс",
        "description": "Большие суммы и легендарные эмодзи.",
        "price": 75_000,
        "currency": "coins",
        "rewards": [
            {"type": "coins", "amount": 30_000, "chance": 30},
            {"type": "coins", "amount": 120_000, "chance": 22},
            {"type": "xp", "amount": 5_000, "chance": 18},
            {"type": "emoji", "value": "🔥", "chance": 10},
            {"type": "emoji", "value": "😈", "chance": 8},
            {"type": "emoji", "value": "👹", "chance": 7},
            {"type": "candy", "amount": 3, "chance": 5},
        ],
    },

    "cosmic": {
        "name": "🌌 Космический кейс",
        "description": "Очень дорогой кейс с эпическими и легендарными наградами.",
        "price": 250_000,
        "currency": "coins",
        "rewards": [
            {"type": "coins", "amount": 100_000, "chance": 28},
            {"type": "coins", "amount": 400_000, "chance": 22},
            {"type": "xp", "amount": 10_000, "chance": 17},
            {"type": "emoji", "value": "🌌", "chance": 10},
            {"type": "emoji", "value": "🚀", "chance": 9},
            {"type": "emoji", "value": "🌠", "chance": 8},
            {"type": "candy", "amount": 3, "chance": 6},
        ],
    },

    "royal": {
        "name": "👑 Королевский кейс",
        "description": "Почти максимальный уровень. Эпические и легендарные эмодзи.",
        "price": 1_000_000,
        "currency": "coins",
        "rewards": [
            {"type": "coins", "amount": 500_000, "chance": 30},
            {"type": "coins", "amount": 2_000_000, "chance": 20},
            {"type": "xp", "amount": 25_000, "chance": 15},
            {"type": "emoji", "value": "👑", "chance": 12},
            {"type": "emoji", "value": "💰", "chance": 10},
            {"type": "emoji", "value": "🦄", "chance": 8},
            {"type": "candy", "amount": 3, "chance": 5},
        ],
    },

    "void": {
        "name": "🕳️ Кейс Пустоты",
        "description": "Абсолютно эндгейм-кейс. Только мифические эмодзи и огромные награды.",
        "price": 5_000_000,
        "currency": "coins",
        "rewards": [
            {"type": "coins", "amount": 2_000_000, "chance": 30},
            {"type": "coins", "amount": 10_000_000, "chance": 18},
            {"type": "xp", "amount": 100_000, "chance": 15},

            # 🔴 МИФИЧЕСКИЕ ЭМОДЗИ
            {"type": "emoji", "value": "❤️", "chance": 7},
            {"type": "emoji", "value": "💜", "chance": 6},
            {"type": "emoji", "value": "💖", "chance": 5},
            {"type": "emoji", "value": "💕", "chance": 4},

            {"type": "candy", "amount": 3, "chance": 15},
        ],
    },
}


def _case_currency_info(case_info):
    if case_info["currency"] == "snowflakes":
        return "❄️", "snowflakes"
    return "💰", "coins"


def get_case_count(user_id, case_key):
    return winter_db.get_case_count(user_id, case_key)


CASES_PER_PAGE = 3


def get_cases_page(page=0):
    case_items = list(CASES.items())
    total_pages = max(1, (len(case_items) + CASES_PER_PAGE - 1) // CASES_PER_PAGE)
    page = max(0, min(int(page), total_pages - 1))
    start = page * CASES_PER_PAGE
    return case_items[start:start + CASES_PER_PAGE], page, total_pages


def build_cases_keyboard(user_id, page=0):
    case_items, page, total_pages = get_cases_page(page)
    kb = types.InlineKeyboardMarkup(row_width=2)

    for case_key, c_info in case_items:
        count = get_case_count(user_id, case_key)
        currency_icon, _ = _case_currency_info(c_info)
        kb.add(
            types.InlineKeyboardButton(
                f"🛒 Купить ({c_info['price']:,} {currency_icon})".replace(",", " "),
                callback_data=f"buy_case_{case_key}_{page}",
            ),
            types.InlineKeyboardButton(
                f"🔓 Открыть ({count} шт)",
                callback_data=f"open_case_{case_key}_{page}",
            ),
        )

    # Листание кейсов
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"casepage_{page - 1}"))
    nav.append(types.InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="ignore_click"))
    if page < total_pages - 1:
        nav.append(types.InlineKeyboardButton("➡️", callback_data=f"casepage_{page + 1}"))
    kb.row(*nav)

    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb


def balance_line(user_id):
    """Строка с балансом: монеты (основная база) и снежинки (база события)."""
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(coins, 0) FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    coins = int(row[0]) if row else 0
    candies = winter_db.get_keys(user_id)
    return f"💼 Твой баланс: <b>{_fmt(coins)}</b> 💰 · <b>{_fmt(candies)}</b> ❄️"

def cases_text(user_id, page=0):
    case_items, page, total_pages = get_cases_page(page)
    lines = [
        "🎁 <b>КЕЙСЫ</b>",
        "",
        balance_line(user_id),
        "",
        "Открывай кейсы и получай 💰 монеты, ⭐ XP, ❄️ снежинки и 🎒 эмодзи.",
        f"📄 Страница <b>{page + 1}/{total_pages}</b>",
        "",
    ]
    for case_key, c_info in case_items:
        count = get_case_count(user_id, case_key)
        icon, _ = _case_currency_info(c_info)
        lines.append(
            f"{c_info['name']} — <b>{c_info['price']:,} {icon}</b> · у тебя: <b>{count}</b>".replace(",", " ")
        )
    return "\n".join(lines)


def buy_case(user_id, case_key):
    if _tech_disabled('cases') or _tech_disabled('shop'):
        return False, '🛠 Кейсы временно недоступны.'
    c_info = CASES.get(case_key)
    if not c_info:
        return False, "❌ Кейс не найден!"

    currency = c_info["currency"]
    price = int(c_info["price"])
    icon = "❄️" if currency == "snowflakes" else "💰"
    not_enough = f"❌ Недостаточно валюты! Нужно {price:,} {icon}.".replace(",", " ")

    if currency == "snowflakes":
        # Снежинки лежат в базе события
        if not winter_db.spend_keys(user_id, price, f"buy_case:{case_key}"):
            return False, not_enough
        try:
            winter_db.add_case(user_id, case_key, 1, "buy")
        except Exception as e:
            winter_db.add_keys(user_id, price, "buy_case_refund")
            print(f"[Winter] Ошибка покупки кейса: {e}")
            return False, "❌ Не удалось купить кейс, снежинки возвращены."
    else:
        # Монеты лежат в основной базе
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET coins = coins - ? WHERE user_id = ? AND coins >= ?",
            (price, user_id, price),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return False, not_enough
        conn.commit()
        try:
            winter_db.add_case(user_id, case_key, 1, "buy")
        except Exception as e:
            add_coins(user_id, price)
            print(f"[Winter] Ошибка покупки кейса: {e}")
            return False, "❌ Не удалось купить кейс, монеты возвращены."

    return True, f"🛒 Куплен {c_info['name']} за {price:,} {icon}!".replace(",", " ")


def open_case(user_id, case_key):
    if _tech_disabled('cases') or _tech_disabled('shop'):
        return None, '🛠 Открытие кейсов временно недоступно.'
    c_info = CASES.get(case_key)
    if not c_info:
        return None, "❌ Кейс не найден!"
    if winter_db.get_case_count(user_id, case_key) <= 0:
        return None, "❌ У тебя нет такого кейса!"

    reward = random.choices(
        c_info["rewards"],
        weights=[r["chance"] for r in c_info["rewards"]],
        k=1,
    )[0]

    # Кейс забирается из базы события
    if not winter_db.take_case(user_id, case_key, "open"):
        return None, "❌ Не удалось открыть кейс."

    rtype = reward["type"]
    candy_amount = 0
    try:
        cursor = conn.cursor()
        if rtype == "coins":
            amount = int(reward["amount"])
            cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
            text = f"💰 +{amount:,} монет".replace(",", " ")
        elif rtype == "xp":
            amount = int(reward["amount"])
            cursor.execute("UPDATE users SET XP = XP + ? WHERE user_id = ?", (amount, user_id))
            text = f"⭐ +{amount:,} XP".replace(",", " ")
        elif rtype == "candy":
            # Снежинки выдаются в базе события — ниже, после основной базы
            candy_amount = int(reward.get("amount", 1))
            text = f"❄️ +{candy_amount} снежинк"
        elif rtype == "emoji":
            emoji = reward["value"]
            cursor.execute(
                "SELECT id FROM inventory WHERE user_id = ? AND item_type = 'emoji' AND item_value = ? LIMIT 1",
                (user_id, emoji),
            )
            duplicate = cursor.fetchone()
            if duplicate:
                compensation = {"Обычная": 50, "Необычная": 100, "Редкая": 250, "Очень редкая": 500, "Эпическая": 1000, "Мифическая": 2500, "Легендарная": 5000}.get(get_emoji_rarity(emoji), 100)
                cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (compensation, user_id))
                text = f"{emoji} Дубликат → 💰 +{compensation} монет"
            else:
                cursor.execute(
                    "INSERT INTO inventory (user_id, item_type, item_value, is_active) VALUES (?, 'emoji', ?, 0)",
                    (user_id, emoji),
                )
                text = f"{emoji} Новое эмодзи добавлено в инвентарь"
        else:
            raise ValueError(f"неизвестный тип награды: {rtype}")

        conn.commit()
        if candy_amount:
            winter_db.add_keys(user_id, candy_amount, f"case_reward:{case_key}")
    except Exception as e:
        # Награду выдать не удалось — возвращаем кейс, чтобы он не пропал
        conn.rollback()
        winter_db.add_case(user_id, case_key, 1, "open_refund")
        print(f"[Winter] Ошибка выдачи награды кейса: {e}")
        return None, "❌ Не удалось выдать награду, кейс возвращён."

    return reward, text


# === Зимний профиль и коллекция титулов ===
"""Random Bot display settings; does not modify Openbot ID."""


_winter_DB = Path(__file__).resolve().parent / DB_NAME
_winter_ROLE_ICONS = {"owner": "👑", "developer": "🌐", "admin": "⭐", "tester": "🧪", "coder": "💻"}

def _winter__connect():
    db = sqlite3.connect(_winter_DB, timeout=10)
    db.execute("CREATE TABLE IF NOT EXISTS winter_profile_settings(user_id INTEGER PRIMARY KEY, role_icon INTEGER NOT NULL DEFAULT 0)")
    return db

def _winter_enabled(user_id):
    with _winter__connect() as db:
        row=db.execute("SELECT role_icon FROM winter_profile_settings WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row[0])

def _winter_toggle(user_id):
    with _winter__connect() as db:
        row = db.execute("SELECT role_icon FROM winter_profile_settings WHERE user_id=?", (user_id,)).fetchone()
        new = not bool(row and row[0])
        db.execute("INSERT INTO winter_profile_settings(user_id,role_icon) VALUES(?,?) "
                   "ON CONFLICT(user_id) DO UPDATE SET role_icon=excluded.role_icon", (user_id, int(new)))
        return new


def _winter_icon(role):
    return _winter_ROLE_ICONS.get(str(role or "").lower(), "")



def random_role(user_id):
    try:
        data = openbot.get_user(user_id)
        if isinstance(data, dict):
            return str(data.get("status", "user")).lower()
    except Exception:
        pass
    return "user"


def profile_display_name(user_id, base_name):
    role_icon = _winter_icon(random_role(user_id)) if _winter_enabled(user_id) else ""
    emoji = role_icon or get_equipped_emoji(user_id)
    return html.escape(f"{emoji} {base_name}".strip())


def owned_titles(user_id):
    owned = {"none"}
    # Winter purchases from the separate event database.
    try:
        owned.update(winter_db.get_titles(user_id))
    except Exception:
        pass
    # Don't lose currently equipped titles from earlier versions.
    row = conn.execute("SELECT profile_title FROM users WHERE user_id=?", (user_id,)).fetchone()
    if row and row[0] in PROFILE_TITLES:
        owned.add(row[0])
    return [(key, PROFILE_TITLES[key]) for key in PROFILE_TITLES if key in owned]


def titles_keyboard(user_id):
    kb = types.InlineKeyboardMarkup(row_width=1)
    current = conn.execute("SELECT profile_title FROM users WHERE user_id=?", (user_id,)).fetchone()
    current_key = current[0] if current and current[0] else "none"
    for key, label in owned_titles(user_id):
        kb.add(types.InlineKeyboardButton(("✅ " if key == current_key else "🎖 ") + label,
                                         callback_data=f"winter_title:{key}"))
    kb.add(types.InlineKeyboardButton("⬅️ В меню", callback_data="back"))
    return kb


def titles_text(user_id):
    owned = owned_titles(user_id)
    return "🏆 <b>МОИ ТИТУЛЫ</b>\n\nПолучено: <b>{}</b>\n✅ — активный\n\nВыбери титул, чтобы надеть его.".format(max(0,len(owned)-1))


def leaders_text():
    """Заблокированные аккаунты не участвуют в рейтинге.

    Проверяем и статус users, и активную запись наказания, чтобы случайная
    синхронизация статуса не вернула забаненного игрока в таблицу.
    """
    now = datetime.now(timezone.utc).isoformat()
    rows = conn.execute(
        """
        SELECT u.user_id,
               COALESCE(u.first_name, u.username, 'Игрок'),
               COALESCE(u.coins, 0)
        FROM users AS u
        WHERE LOWER(COALESCE(u.status, 'user')) != 'banned'
          AND NOT EXISTS (
              SELECT 1 FROM punishments AS p
              WHERE p.user_id = u.user_id
                AND (p.expires_at IS NULL OR p.expires_at > ?)
          )
        ORDER BY u.coins DESC, u.user_id ASC
        LIMIT 10
        """, (now,)
    ).fetchall()
    lines = ["📊 <b>ЛИДЕРЫ RANDOM BOT</b>",
             "💰 По количеству монет · забаненные игроки скрыты", ""]
    for i, (uid, name, coins) in enumerate(rows, 1):
        icon = _winter_icon(random_role(uid))
        lines.append(
            f"{i}. {icon} {html.escape(str(name))} — <b>{coins:,}</b> 🪙".replace(',', ' ')
        )
    if not rows:
        lines.append("Пока нет игроков в рейтинге.")
    return "\n".join(lines)


def _ui_edit(call, text, markup):
    try:
        return bot.edit_message_text(text, chat_id=call.message.chat.id,
                                     message_id=call.message.message_id,
                                     reply_markup=markup, parse_mode='HTML')
    except apihelper.ApiTelegramException as exc:
        if 'message is not modified' not in str(exc).lower():
            raise


def leaders_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(types.InlineKeyboardButton('🔄 Обновить', callback_data='leaders_refresh'),
           types.InlineKeyboardButton('🏠 Главное меню', callback_data='back'))
    return kb


@bot.message_handler(commands=["my_titles"])
def my_titles_command(message):
    bot.send_message(message.chat.id, titles_text(message.from_user.id),
                     reply_markup=titles_keyboard(message.from_user.id), parse_mode="HTML")


@bot.message_handler(commands=["leaders"])
def leaders_command(message):
    bot.send_message(message.chat.id, leaders_text(), reply_markup=leaders_keyboard(), parse_mode="HTML")


@bot.callback_query_handler(func=lambda c: bool(c.data) and (c.data in {"winter_titles", "winter_leaders", "leaders_refresh", "winter_badge"} or c.data.startswith("winter_title:")))
def winter_ui_callback(call):
    uid = call.from_user.id
    if call.data in ("winter_leaders", "leaders_refresh"):
        bot.answer_callback_query(call.id)
        return _ui_edit(call, leaders_text(), leaders_keyboard())
    if call.data == "winter_badge":
        if not _winter_icon(random_role(uid)):
            return bot.answer_callback_query(call.id, "Значок роли доступен только сотрудникам", show_alert=True)
        enabled = _winter_toggle(uid)
        bot.answer_callback_query(call.id, "✅ Значок включён" if enabled else "✅ Обычный эмодзи возвращён")
        try:
            bot.edit_message_text(
                get_profile_text(uid),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=profile_inline_markup(uid),
                parse_mode="HTML",
            )
        except telebot.apihelper.ApiTelegramException as exc:
            if "message is not modified" not in str(exc).lower():
                raise
        return
    if call.data.startswith("winter_title:"):
        key = call.data.split(":", 1)[1]
        if key not in dict(owned_titles(uid)):
            return bot.answer_callback_query(call.id, "Титул не получен", show_alert=True)
        conn.execute("UPDATE users SET profile_title=? WHERE user_id=?", (None if key == "none" else key, uid))
        conn.commit()
        bot.answer_callback_query(call.id, "✅ Титул установлен")
    else:
        bot.answer_callback_query(call.id)
    return _ui_edit(call, titles_text(uid), titles_keyboard(uid))


@bot.message_handler(func=lambda m: (m.text or "") in {"🏆 Мои титулы", "📊 Лидеры"})
def winter_reply_shortcuts(message):
    if message.text == "🏆 Мои титулы":
        my_titles_command(message)
    else:
        leaders_command(message)


# =========== Меню (Без изменений) =========
def main_mune():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('❄️ Зимние игры', callback_data='game'),
        types.InlineKeyboardButton('👤 Профиль', callback_data="profile"))
    
    markup.add(
        types.InlineKeyboardButton('🎁 Зимняя лавка', callback_data='shop'),
        types.InlineKeyboardButton('🎒 Инвентарь', callback_data='open_inventory'))

    markup.add(
        types.InlineKeyboardButton('🏪 Рынок', callback_data='market'),
        types.InlineKeyboardButton('⚙ Настройки', callback_data='settings_user'))
    
    markup.add(types.InlineKeyboardButton("🏆 Мои титулы", callback_data="winter_titles"),
               types.InlineKeyboardButton("📊 Лидеры", callback_data="winter_leaders"))
    markup.add(types.InlineKeyboardButton("📅 Календарь декабря", callback_data="dec_cal_open"))
    return markup

def main_mune_reply():
    """Главное меню Reply-кнопок."""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(types.KeyboardButton("❄️ Зимние игры"), types.KeyboardButton("👤 Профиль"))
    markup.row(types.KeyboardButton("🎁 Зимняя лавка"), types.KeyboardButton("🎒 Инвентарь"))
    markup.row(types.KeyboardButton("🏪 Рынок"), types.KeyboardButton("⚙️ Настройки"))
    markup.row(types.KeyboardButton("🏆 Мои титулы"), types.KeyboardButton("📊 Лидеры"))
    markup.add(types.KeyboardButton("📅 Календарь декабря"))
    return markup


def send_main_reply_menu(chat_id, first_name=None, text=None):
    if text is None:
        text = (
            f"🎄 <b>RANDOM BOT — ЗИМНЕЕ ОБНОВЛЕНИЕ</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👋 Добро пожаловать, <b>{html.escape(first_name or 'Игрок')}</b>!\n\n"
            f"❄️ Игры, праздничные кейсы, титулы и коллекция эмодзи.\n\n"
            f"📅 <b>/calendar</b> — зимний календарь с подарками.\n"
            f"🎁 Пропущенные подарки не сгорают!\n\n"
            f"👇 <b>Выбери раздел:</b>"
        )
    bot.send_message(chat_id, text, reply_markup=main_mune_reply(), parse_mode="HTML")

# ============ Настройки =============
def settings_menu(user_id):
    kb_type, notifications, show_id = get_user_settings(user_id)
    
    kb_text = "⌨ Переключить вид кнопок: Reply" if kb_type == 'inline' else "⌨ Переключить вид кнопок: Inline"
    notif_text = "🔔 Уведомления: ВКЛ" if notifications == 1 else "🔕 Уведомления: ВЫКЛ"
    id_text = "👁 ID для других: Виден" if show_id == 1 else "🙈 ID для других: Скрыт"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(kb_text, callback_data='toggle_kb'))
    markup.add(
        types.InlineKeyboardButton(notif_text, callback_data='toggle_notif'),
        types.InlineKeyboardButton(id_text, callback_data='toggle_show_id'),
        types.InlineKeyboardButton('🔙 В главное меню', callback_data='back')
    )
    return markup

def profile_menu_reply():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("⚙ Настройки ID"),
        types.KeyboardButton("🏆 Мои титулы"),
        types.KeyboardButton("⬅ Главное меню"))
    return markup


def settings_menu_reply(user_id):
    kb_type, notifications, show_id = get_user_settings(user_id)

    kb_text = "⌨ Переключить вид кнопок: Reply" if kb_type == 'inline' else "⌨ Переключить вид кнопок: Inline"
    notif_text = "🔔 Уведомления: ВКЛ" if notifications == 1 else "🔕 Уведомления: ВЫКЛ"
    id_text = "👁 ID для других: Виден" if show_id == 1 else "🙈 ID для других: Скрыт"

    markup = types.ReplyKeyboardMarkup(row_width=1)
    markup.add(types.KeyboardButton(kb_text))
    markup.add(
        types.KeyboardButton(notif_text),
        types.KeyboardButton(id_text),
        types.KeyboardButton('⬅ Главное меню')
    )
    return markup



# ============ REPLY-КЛАВИАТУРЫ ДЛЯ ОСНОВНЫХ МЕНЮ ============

def shop_mune_reply():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton('❄️ Купить за снежинки'))
    markup.add(types.KeyboardButton('🛒 Обычный магазин'))
    markup.add(types.KeyboardButton('⬅ Главное меню'))
    return markup


def regular_shop_reply():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton('🎁 Кейсы'), types.KeyboardButton('🏆 Титулы'),
               types.KeyboardButton('⭐ Магазин Stars'))
    markup.add(types.KeyboardButton('⬅ Зимняя лавка'))
    return markup

def stars_shop_menu_reply():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton("💰 10 000 000 монет — 100 ⭐"), types.KeyboardButton("❄️ 25 снежинок — 50 ⭐"), types.KeyboardButton("⭐ Прокачать до 20 уровня — 150 ⭐"), types.KeyboardButton("⬅ Магазин"))
    return markup

def cases_menu_reply(user_id, page=0):
    case_items, page, total_pages = get_cases_page(page)
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for case_key, c_info in case_items:
        count = get_case_count(user_id, case_key)
        icon = "❄️" if c_info["currency"] == "snowflakes" else "💰"
        markup.add(types.KeyboardButton(f"🛒 {c_info['name']} — {c_info['price']:,} {icon}".replace(",", " ")))
        markup.add(types.KeyboardButton(f"🔓 Открыть {c_info['name']} ({count} шт)"))
    nav=[]
    if page > 0: nav.append(types.KeyboardButton("⬅ Предыдущие кейсы"))
    if page < total_pages-1: nav.append(types.KeyboardButton("Следующие кейсы ➡"))
    if nav: markup.row(*nav)
    markup.add(types.KeyboardButton("⬅ Магазин"))
    return markup

def inventory_menu_reply(user_id, page=1):
    items=[x for x in get_user_inventory(user_id) if x[0]=="emoji"]; per_page=4
    total_pages=max(1,(len(items)+per_page-1)//per_page); page=min(max(1,page),total_pages)
    markup=types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for _, item_value, count in items[(page-1)*per_page:page*per_page]:
        prefix="👕 " if get_equipped_emoji(user_id)==item_value else ""
        icon=get_rarity_icon(get_emoji_rarity(item_value))
        markup.add(types.KeyboardButton(f"{prefix}{item_value} ×{count} · {icon}"))
    if page>1: markup.add(types.KeyboardButton("◀️ Предыдущая страница"))
    if page<total_pages: markup.add(types.KeyboardButton("Следующая страница ▶️"))
    markup.add(types.KeyboardButton("⬅ Главное меню"))
    return markup

def parse_inventory_button(text):
    """'👕 😎 ×3 · 🟣' или '😎 ×3 · 🟣' -> '😎'. Если это не кнопка инвентаря — None."""
    if not text or " ×" not in text or " · " not in text:
        return None
    body = text[len("👕 "):] if (text.startswith("👕 ") and not text.startswith("👕 ×")) else text
    emoji = body.split(" ×", 1)[0].strip()
    return emoji or None

def inventory_reply_text(user_id, page=1):
    items=[x for x in get_user_inventory(user_id) if x[0]=="emoji"]
    if not items:
        return "🎒 <b>Твой инвентарь пуст!</b>\n\nУ тебя ещё нет эмодзи. Играй и открывай кейсы, чтобы собирать их."
    per_page=4; total_pages=max(1,(len(items)+per_page-1)//per_page); page=min(max(1,page),total_pages)
    return f"🎒 <b>ТВОЙ ИНВЕНТАРЬ</b>\nСтраница {page}/{total_pages}\n\nНажми на эмодзи, чтобы открыть информацию."

def inventory_item_reply(user_id, emoji):
    rarity=get_emoji_rarity(emoji); price=get_emoji_price(emoji)
    cursor=conn.cursor(); cursor.execute("SELECT COUNT(*) FROM inventory WHERE user_id=? AND item_type='emoji' AND item_value=?",(user_id,emoji)); count=cursor.fetchone()[0]
    equipped=get_equipped_emoji(user_id)==emoji
    markup=types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton("👕 Снять" if equipped else "👕 Одеть"), types.KeyboardButton(f"💰 Продать {emoji}"))
    markup.add(types.KeyboardButton(f"🏪 Выставить {emoji} на рынок"), types.KeyboardButton("⬅ Инвентарь"))
    text=f"<b>{emoji}</b>\n\n{get_rarity_icon(rarity)} <b>Редкость:</b> {rarity}\n💰 <b>Цена:</b> {price:,} 🪙\n📦 <b>Количество:</b> {count}".replace(","," ")
    if equipped: text += "\n\n👕 <b>Сейчас надето</b>"
    return text, markup

reply_my_lots = {}  # True, если пользователь сейчас на экране «Мои лоты»

def market_menu_reply(user_id, page=1):
    """Праздничный Reply-рынок без изменения callback / текстовых команд."""
    reply_my_lots.pop(user_id, None)
    lots, total = get_market_lots(page)
    total_pages = max(1, (total + MARKET_PAGE_SIZE - 1) // MARKET_PAGE_SIZE)
    page = min(max(1, page), total_pages)
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    lines = [
        '🎄 <b>НОВОГОДНЯЯ ЯРМАРКА ЭМОДЗИ</b>',
        '━━━━━━━━━━━━━━━━━━',
        f'❄️ Лотов: <b>{total}</b> · 📜 Страница <b>{page}/{total_pages}</b>',
        '🎁 Покупай и продавай эмодзи за монеты!', ''
    ]
    for lot_id, seller_id, emoji, price, username, first_name in lots:
        seller = 'ты' if seller_id == user_id else market_seller_name(username, first_name)
        lines.append(f'🎁 <b>Лот #{lot_id}</b>  {html.escape(str(emoji))}\n'
                     f'💰 <b>{_fmt(price)}</b> монет · 👤 {html.escape(str(seller))}\n')
        if seller_id == user_id:
            markup.add(types.KeyboardButton(f'❌ Снять лот #{lot_id} {emoji} · {_fmt(price)} 🪙'))
        else:
            markup.add(types.KeyboardButton(f'🛒 Купить {emoji} за {_fmt(price)} 🪙 · #{lot_id}'))
    if not lots:
        lines.append('☃️ Пока здесь тихо. Выставь первый эмодзи из инвентаря!')
    nav = []
    if page > 1:
        nav.append(types.KeyboardButton('◀️ Предыдущая страница рынка'))
    if page < total_pages:
        nav.append(types.KeyboardButton('Следующая страница рынка ▶️'))
    if nav:
        markup.row(*nav)
    markup.add(types.KeyboardButton('📦 Мои лоты'), types.KeyboardButton('⬅ Главное меню'))
    return '\n'.join(lines), markup


def my_market_reply(user_id):
    reply_my_lots[user_id] = True
    lots = conn.execute(
        "SELECT lot_id,item_value,price FROM auction "
        "WHERE seller_id=? AND item_type='emoji' ORDER BY lot_id DESC", (user_id,)
    ).fetchall()
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    lines = ['🎁 <b>МОИ ЛОТЫ · ЗИМНЯЯ ЯРМАРКА</b>', '━━━━━━━━━━━━━━━━━━',
             f'📦 Выставлено: <b>{len(lots)}</b>', '']
    for lot_id, emoji, price in lots:
        lines.append(f'❄️ #{lot_id} {html.escape(str(emoji))} · <b>{_fmt(price)}</b> 🪙')
        markup.add(types.KeyboardButton(f'❌ Снять лот #{lot_id} {emoji}'))
    if not lots:
        lines.append('☃️ Ты ещё не выставил ни одного эмодзи.')
    markup.add(types.KeyboardButton('⬅ Рынок'))
    return '\n'.join(lines), markup

# ============== Магазин =========
# Покупки за Telegram Stars (XTR). Цены указаны в Stars.
STARS_SHOP = {
    "coins_10m": {
        "title": "💰 10 000 000 монет",
        "description": "Пополнение игрового баланса на 10 000 000 💰",
        "stars": 100,
    },
    "snowflakes_25": {
        "title": "❄️ 25 снежинок",
        "description": "Получи 25 ❄️ снежинок для праздничных кейсов",
        "stars": 50,
    },
    "level_20": {
        "title": "⭐ Уровень 20",
        "description": "Прокачка игрового уровня до 20",
        "stars": 150,
    },
}

WINTER_TITLES = {
    "snow_master": ("❄️ Повелитель снега", 2500),
    "gift_hunter": ("🎁 Охотник за подарками", 5000),
    "ice_wizard": ("🧊 Ледяной маг", 10000),
    "winter_guard": ("🛷 Зимний страж", 25000),
    "snow_king": ("👑 Снежный король", 50000),
    "winter_legend": ("🌟 Легенда зимы", 100000),
}

# Новый годские титулы должны отображаться в профиле
for _key, (_name, _price) in WINTER_TITLES.items():
    PROFILE_TITLES[_key] = _name

def winter_titles_text(user_id, note=None):
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(coins, 0), profile_title FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    coins = int(row[0]) if row else 0
    current = PROFILE_TITLES.get(row[1] if row else "none", "Без титула")
    text = "🏆 <b>ТИТУЛЫ НОВЫЙ ГОДА</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    if note:
        text += f"{note}\n\n"
    text += f"💰 Твой баланс: <b>{_fmt(coins)}</b> 🪙\n🎖 Текущий титул: <b>{current}</b>\n\nВыбери титул:"
    return text

def winter_titles_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, (name, price) in WINTER_TITLES.items():
        markup.add(types.InlineKeyboardButton(f"{name} — {price:,} 🪙".replace(',', ' '), callback_data=f"buy_title_{key}"))
    markup.add(types.InlineKeyboardButton("⬅ Обычный магазин", callback_data="shop_regular"))
    return markup

def buy_winter_title(user_id, title_key):
    if _tech_disabled('shop'):
        return False, '🛠 Магазин временно недоступен.'
    item = WINTER_TITLES.get(title_key)
    if not item:
        return False, "❌ Такой титул не найден."
    name, price = item
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(coins, 0), profile_title FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return False, "❌ Профиль не найден."
    if row[1] == title_key:
        return False, f"✅ Титул {name} у тебя уже установлен."
    if int(row[0] or 0) < price:
        return False, f"❌ Не хватает монет. Нужно {price:,} 🪙.".replace(',', ' ')
    cursor.execute("UPDATE users SET coins=coins-?, profile_title=? WHERE user_id=? AND coins>=?", (price, title_key, user_id, price))
    if cursor.rowcount != 1:
        conn.rollback()
        return False, "❌ Не удалось купить титул."
    conn.commit()
    try:
        winter_db.record_title(user_id, title_key, price)  # запись о покупке — в базу события
    except Exception as e:
        print(f"[Winter] Не удалось записать покупку титула: {e}")
    return True, f"🏆 Титул {name} куплен и установлен!"

def winter_titles_reply():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for name, price in WINTER_TITLES.values():
        markup.add(types.KeyboardButton(f"🏆 {name} — {price:,} 🪙".replace(',', ' ')))
    markup.add(types.KeyboardButton("⬅ Магазин"))
    return markup

def shop_hub_text(user_id):
    return ('🎁 <b>ЗИМНЯЯ ЛАВКА</b>\n\n'
            f'❄️ Твои снежинки: <b>{get_candies(user_id)}</b>\n\n'
            'Потрать снежинки на праздничные титулы или открой обычный магазин.')


def shop_mune():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton('❄️ Купить за снежинки', callback_data='snow_shop'))
    markup.add(types.InlineKeyboardButton('🛒 Обычный магазин', callback_data='shop_regular'))
    markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='back'))
    return markup


def regular_shop_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton('🎁 Кейсы', callback_data='cases'))
    kb.add(types.InlineKeyboardButton('🏆 Титулы за монеты', callback_data='shop_coin_titles'))
    kb.add(types.InlineKeyboardButton('⭐ Магазин Stars', callback_data='buy_coins'))
    kb.add(types.InlineKeyboardButton('⬅ Зимняя лавка', callback_data='shop'))
    return kb


# Ограниченная коллекция: день рождения и кастомные титулы добавим отдельным патчем.
SNOW_TITLES = {
    'winter_2027': ('🎆 Новый год 2027', 90),
    'snow_collector': ('❄️ Снежный коллекционер', 150),
}
for _key, (_name, _price) in SNOW_TITLES.items():
    PROFILE_TITLES[_key] = _name


def snow_shop_text(uid):
    return (f'❄️ <b>МАГАЗИН СНЕЖИНОК</b>\n\nБаланс: <b>{get_candies(uid)}</b> ❄️\n\n'
            'Купленные титулы доступны в разделе «Мои титулы».\n'
            '🎂 Титулы дня рождения и ✍️ кастомные титулы — в следующих патчах.')


def snow_shop_keyboard(uid):
    owned = {key for key, _ in owned_titles(uid)}
    kb = types.InlineKeyboardMarkup(row_width=1)
    for key, (title, price) in SNOW_TITLES.items():
        label = f'✅ {title} — куплено' if key in owned else f'{title} — {price} ❄️'
        kb.add(types.InlineKeyboardButton(label, callback_data=f'snow_buy:{key}'))
    kb.add(types.InlineKeyboardButton('🔄 Обновить', callback_data='snow_shop'))
    kb.add(types.InlineKeyboardButton('⬅ Зимняя лавка', callback_data='shop'))
    return kb

def stars_shop_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton('💰 10 000 000 монет — 100 ⭐', callback_data='stars_buy_coins_10m'),
        types.InlineKeyboardButton('❄️ 25 снежинок — 50 ⭐', callback_data='stars_buy_snowflakes_25'),
        types.InlineKeyboardButton('⭐ Прокачать до 20 уровня — 150 ⭐', callback_data='stars_buy_level_20'),
        types.InlineKeyboardButton('⬅ Назад', callback_data='shop')
    )
    return markup

def send_stars_invoice(call, product_key):
    if _tech_disabled('shop'):
        bot.answer_callback_query(call.id, '🛠 Магазин на техработах.', show_alert=True)
        return
    product = STARS_SHOP[product_key]
    payload = f"stars:{product_key}:{call.from_user.id}"

    invoice_msg = bot.send_invoice(
        chat_id=call.message.chat.id,
        title=product["title"],
        description=product["description"],
        invoice_payload=payload,
        provider_token="",
        currency="XTR",
        prices=[
            types.LabeledPrice(
                label=product["title"],
                amount=product["stars"]
            )
        ],
        start_parameter=f"buy_{product_key}",
    )

    cancel_markup = types.InlineKeyboardMarkup()
    cancel_markup.add(
        types.InlineKeyboardButton(
            "❌ Отменить оплату",
            callback_data=f"cancel_stars_{invoice_msg.message_id}"
        )
    )

    bot.send_message(
        call.message.chat.id,
        "💳 <b>Оплата создана</b>\n\n"
        "Если передумал покупать, нажми кнопку ниже.",
        reply_markup=cancel_markup,
        parse_mode="HTML"
    )

def send_stars_invoice_from_message(message, product_key):
    if _tech_disabled('shop'):
        bot.reply_to(message, '🛠 Магазин на техработах.')
        return
    product = STARS_SHOP[product_key]
    user_id = message.from_user.id
    chat_id = message.chat.id
    payload = f"stars:{product_key}:{user_id}"

    invoice_msg = bot.send_invoice(
        chat_id=chat_id,
        title=product["title"],
        description=product["description"],
        invoice_payload=payload,
        provider_token="",
        currency="XTR",
        prices=[types.LabeledPrice(label=product["title"], amount=product["stars"])],
        start_parameter=f"buy_{product_key}",
    )

    cancel_markup = types.InlineKeyboardMarkup()
    cancel_markup.add(
        types.InlineKeyboardButton(
            "❌ Отменить оплату",
            callback_data=f"cancel_stars_{invoice_msg.message_id}"
        )
    )
    bot.send_message(
        chat_id,
        "💳 <b>Оплата создана</b>\n\n"
        "Если передумал покупать, нажми кнопку ниже.",
        reply_markup=cancel_markup,
        parse_mode="HTML"
    )

# ============== Игры ============
def game_mune():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔑 Тайна ледяного сундука", callback_data="game_lock"),
        types.InlineKeyboardButton("🏔 Снежная экспедиция", callback_data="game_keys")
    )
    markup.add(
        types.InlineKeyboardButton("🔎 Снежный детектив", callback_data="game_shadow"),
        types.InlineKeyboardButton("🧸 Мастерская игрушек", callback_data="game_potion")
    )
    markup.add(types.InlineKeyboardButton("🎁 Подарки с риском", callback_data="game_pumpkin"))
    markup.add(types.InlineKeyboardButton("❌⭕ Крестики-нолики", callback_data="game_ttt"))
    for key, title in _WG_NAMES.items():
        enabled = _wg_enabled(key)
        markup.add(types.InlineKeyboardButton(
            title if enabled else f'🔒 {title} — скоро',
            callback_data=f'wg:{key}:start' if enabled else f'wg:{key}:locked'
        ))
    markup.add(types.InlineKeyboardButton("⬅️ Главное меню", callback_data="back"))
    return markup

def game_mune_reply():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton("🔑 Тайна ледяного сундука"), types.KeyboardButton("🏔 Снежная экспедиция"))
    markup.add(types.KeyboardButton("🔎 Снежный детектив"), types.KeyboardButton("🧸 Мастерская игрушек"))
    markup.add(types.KeyboardButton("🎁 Подарки с риском"), types.KeyboardButton("❌⭕ Крестики-нолики"))
    for key,title in _WG_NAMES.items():
        markup.add(types.KeyboardButton(title if _wg_enabled(key) else f'🔒 {title} — скоро'))
    markup.add(types.KeyboardButton("⬅ Главное меню"))
    return markup

def game_menu_markup(user_id):
    """Меню игр в том виде кнопок, который выбран у пользователя."""
    kb_type, _, _ = get_user_settings(user_id)
    return game_mune_reply() if kb_type == 'reply' else game_mune()

def game_action_reply(action=None):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    if action == "ttt":
        buttons = [types.KeyboardButton(f"🎁 {i}") for i in range(1, 10)]
        markup.row(buttons[0], buttons[1], buttons[2])
        markup.row(buttons[3], buttons[4], buttons[5])
        markup.row(buttons[6], buttons[7], buttons[8])
        markup.add(types.KeyboardButton("🛑 Выйти из игры"))
    else:
        markup.add(types.KeyboardButton("⬅ Игры"), types.KeyboardButton("⬅ Главное меню"))
    return markup

# ============= Коллекция эмоджи: редкость и цена =============
EMOJI_DATA = json.loads(
    (Path(__file__).resolve().parent / "emoji_data.json").read_text(encoding="utf-8")
)

RARITY_ICONS = {
    "Обычная": "⚪",
    "Необычная": "🟢",
    "Редкая": "🔵",
    "Очень редкая": "💠",
    "Эпическая": "🟣",
    "Легендарная": "🟠",
    "Мифическая": "🔴",
}

def get_emoji_rarity(emoji):
    return EMOJI_DATA.get(emoji, {"rarity": "Обычная", "price": 50})["rarity"]

def get_emoji_price(emoji):
    return EMOJI_DATA.get(emoji, {"rarity": "Обычная", "price": 50})["price"]

def get_rarity_icon(rarity):
    return RARITY_ICONS.get(rarity, "⚪")

def show_emoji_card(chat_id, message_id, user_id, emoji):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ? AND item_type = 'emoji' AND item_value = ?", (user_id, emoji))
    count = cursor.fetchone()[0]
    if count <= 0:
        bot.send_message(chat_id, "❌ Эмоджи больше нет в инвентаре!")
        return
    rarity = get_emoji_rarity(emoji); price = get_emoji_price(emoji); equipped = get_equipped_emoji(user_id) == emoji
    text = f"<b>{emoji}</b>\n\n{get_rarity_icon(rarity)} <b>Редкость:</b> {rarity}\n💰 <b>Цена:</b> {price} 🪙\n📦 <b>Количество:</b> {count}\n"
    if equipped: text += "\n👕 <b>Сейчас надето</b>\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("👕 Снять" if equipped else "👕 Одеть", callback_data=f"emoji_unequip_{emoji}" if equipped else f"emoji_equip_{emoji}"))
    markup.add(types.InlineKeyboardButton(f"💰 Продать за {price} 🪙", callback_data=f"emoji_sell_{emoji}"))
    markup.add(types.InlineKeyboardButton("🏪 На рынок", callback_data=f"emoji_market_{emoji}"))
    markup.add(types.InlineKeyboardButton("🔙 В инвентарь", callback_data="open_inventory"))
    bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")

pending_market = {}

# ============= 🏪 РЫНОК ЭМОДЗИ =============
MARKET_PAGE_SIZE = 5


def get_market_lots(page=1):
    """Возвращает лоты рынка и общее количество лотов."""
    page = max(1, int(page))
    offset = (page - 1) * MARKET_PAGE_SIZE
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM auction WHERE item_type = 'emoji' AND price > 0")
    total = cursor.fetchone()[0]

    cursor.execute("""
        SELECT a.lot_id, a.seller_id, a.item_value, a.price,
               COALESCE(u.username, ''), COALESCE(u.first_name, 'Игрок')
        FROM auction a
        LEFT JOIN users u ON u.user_id = a.seller_id
        WHERE a.item_type = 'emoji' AND a.price > 0
        ORDER BY a.lot_id DESC
        LIMIT ? OFFSET ?
    """, (MARKET_PAGE_SIZE, offset))

    return cursor.fetchall(), total


def notify_market_sale(seller_id, buyer_id, emoji, price):
    """Новогоднее уведомление о продаже, без изменения расчётов."""
    try:
        if get_user_settings(seller_id)[1] != 1:
            return
        row = conn.execute('SELECT username, first_name FROM users WHERE user_id=?',
                           (buyer_id,)).fetchone()
        buyer = market_seller_name(row[0], row[1]) if row else 'Игрок'
        balance_row = conn.execute('SELECT COALESCE(coins,0) FROM users WHERE user_id=?',
                                   (seller_id,)).fetchone()
        balance = int(balance_row[0]) if balance_row else 0
        bot.send_message(
            seller_id,
            '🎄 <b>НОВОГОДНЯЯ ЯРМАРКА · ПРОДАЖА!</b>\n\n'
            f'🎁 {html.escape(str(emoji))} нашёл нового владельца!\n'
            f'💰 Получено: <b>{_fmt(price)}</b> монет\n'
            f'👤 Покупатель: {html.escape(str(buyer))}\n\n'
            f'🪙 Твой баланс: <b>{_fmt(balance)}</b> монет',
            parse_mode='HTML'
        )
    except Exception:
        logging.getLogger('random_bot.market').exception('Ошибка уведомления о продаже')

def market_seller_name(username, first_name):
    if username:
        return '@' + username.lstrip('@')
    return first_name or 'Игрок'


def show_market(chat_id, message_id, user_id, page=1):
    """Зимняя витрина: сохраняет существующие операции и callback-идентификаторы."""
    lots, total = get_market_lots(page)
    total_pages = max(1, (total + MARKET_PAGE_SIZE - 1) // MARKET_PAGE_SIZE)
    page = min(max(1, page), total_pages)
    if not lots and page > 1:
        page = total_pages
        lots, total = get_market_lots(page)
    row = conn.execute('SELECT COALESCE(coins,0) FROM users WHERE user_id=?',
                       (user_id,)).fetchone()
    balance = int(row[0]) if row else 0
    lines = [
        '🎄 <b>НОВОГОДНЯЯ ЯРМАРКА</b> 🎁',
        '━━━━━━━━━━━━━━━━━━',
        '❄️ Здесь игроки обмениваются редкими эмодзи!',
        f'💰 Твой баланс: <b>{_fmt(balance)}</b> 🪙',
        f'📦 Активных лотов: <b>{total}</b> · 📄 <b>{page}/{total_pages}</b>', ''
    ]
    markup = types.InlineKeyboardMarkup(row_width=1)
    if not lots:
        lines.append('☃️ <b>На ярмарке пока нет товаров.</b>\n'
                     '🎁 Выставь эмодзи из инвентаря и открой торговлю!')
    for lot_id, seller_id, emoji, price, username, first_name in lots:
        rarity = get_emoji_rarity(emoji)
        rarity_icon = get_rarity_icon(rarity)
        seller = 'Ты' if seller_id == user_id else market_seller_name(username, first_name)
        lines.extend([
            f'🎁 <b>ЛОТ #{lot_id}</b> · {html.escape(str(emoji))}',
            f'✨ {rarity_icon} {html.escape(str(rarity))}',
            f'👤 Продавец: {html.escape(str(seller))}',
            f'💰 Цена: <b>{_fmt(price)}</b> 🪙',
            '──────────────────'
        ])
        if seller_id == user_id:
            markup.add(types.InlineKeyboardButton(
                f'❌ Снять лот #{lot_id} · {emoji}', callback_data=f'market_cancel_{lot_id}'))
        else:
            markup.add(types.InlineKeyboardButton(
                f'🛒 Купить #{lot_id} · {emoji} · {_fmt(price)} 🪙',
                callback_data=f'market_buy_{lot_id}'))
    nav = []
    if page > 1:
        nav.append(types.InlineKeyboardButton('◀️', callback_data=f'market_page_{page-1}'))
    nav.append(types.InlineKeyboardButton(f'📄 {page}/{total_pages}', callback_data='ignore_click'))
    if page < total_pages:
        nav.append(types.InlineKeyboardButton('▶️', callback_data=f'market_page_{page+1}'))
    markup.row(*nav)
    markup.row(
        types.InlineKeyboardButton('🎁 Мои лоты', callback_data='market_my'),
        types.InlineKeyboardButton('🔄 Обновить', callback_data=f'market_page_{page}')
    )
    markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='back'))
    text = '\n'.join(lines)
    try:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                              reply_markup=markup, parse_mode='HTML')
    except apihelper.ApiTelegramException as exc:
        if 'message is not modified' not in str(exc).lower():
            raise


def show_my_market_lots(chat_id, message_id, user_id):
    lots = conn.execute(
        "SELECT lot_id,item_value,price FROM auction "
        "WHERE seller_id=? AND item_type='emoji' ORDER BY lot_id DESC", (user_id,)
    ).fetchall()
    lines = [
        '🎁 <b>МОИ ЛОТЫ · ЗИМНЯЯ ЯРМАРКА</b>',
        '━━━━━━━━━━━━━━━━━━',
        f'❄️ Сейчас продаётся: <b>{len(lots)}</b>', ''
    ]
    markup = types.InlineKeyboardMarkup(row_width=1)
    if not lots:
        lines.append('☃️ У тебя пока нет лотов. Выставь эмодзи из инвентаря!')
    else:
        for lot_id, emoji, price in lots:
            rarity = get_emoji_rarity(emoji)
            lines.extend([
                f'🎁 <b>#{lot_id}</b> · {html.escape(str(emoji))}',
                f'{get_rarity_icon(rarity)} {html.escape(str(rarity))} · 💰 <b>{_fmt(price)}</b> 🪙', ''
            ])
            markup.add(types.InlineKeyboardButton(
                f'❌ Снять #{lot_id} · {emoji}', callback_data=f'market_cancel_{lot_id}'))
    markup.row(
        types.InlineKeyboardButton('🏪 Вернуться на ярмарку', callback_data='market'),
        types.InlineKeyboardButton('🏠 Главное меню', callback_data='back')
    )
    bot.edit_message_text('\n'.join(lines), chat_id=chat_id, message_id=message_id,
                          reply_markup=markup, parse_mode='HTML')

# ============= Пользователь & Пагинация Инвентаря =========.
def get_user_inventory(user_id):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT item_type, item_value, COUNT(*) 
        FROM inventory 
        WHERE user_id = ? 
        GROUP BY item_type, item_value
    """, (user_id,))
    return cursor.fetchall()

def show_inventory_ui(chat_id, message_id, user_id, page=1):
    items = [x for x in get_user_inventory(user_id) if x[0] == 'emoji']
    per_page = 4; total_pages = max(1, (len(items)+per_page-1)//per_page); page=min(max(1,page),total_pages)
    page_items=items[(page-1)*per_page:page*per_page]
    markup=types.InlineKeyboardMarkup(row_width=2)
    if items:
        text=f"🎒 <b>ТВОЙ ИНВЕНТАРЬ</b>\nСтраница {page}/{total_pages}\n\nНажми на эмоджи, чтобы открыть информацию."
        for _, item_value, count in page_items:
            rarity=get_emoji_rarity(item_value); prefix="👕 " if get_equipped_emoji(user_id)==item_value else ""
            markup.add(types.InlineKeyboardButton(f"{prefix}{item_value} ×{count} · {get_rarity_icon(rarity)}", callback_data=f"emoji_info_{item_value}"))
        nav=[]
        if page>1: nav.append(types.InlineKeyboardButton("◀️",callback_data=f"invpage_{page-1}"))
        nav.append(types.InlineKeyboardButton(f"📄 {page}/{total_pages}",callback_data="ignore_click"))
        if page<total_pages: nav.append(types.InlineKeyboardButton("▶️",callback_data=f"invpage_{page+1}"))
        markup.row(*nav)
    else: text="🎒 <b>Твой инвентарь пуст!</b>\n\nИграй и открывай кейсы, чтобы собирать эмоджи."
    markup.add(types.InlineKeyboardButton('⬅️ Назад',callback_data='back'))
    try: bot.edit_message_text(text,chat_id=chat_id,message_id=message_id,reply_markup=markup,parse_mode="HTML")
    except Exception: pass

# Новогодняя SQLite хранит декабрьские награды и старые записи без удаления.
EVENT_DB = Path(__file__).resolve().parent / WINTER_DB_NAME

# ================================================================
# 📅 ДЕКАБРЬ 2026: 31 подарок, можно забрать пропущенные дни.
# Ноябрьские награды в базе сохраняются, но ноябрьского интерфейса больше нет.
# ================================================================
def december_today():
    return datetime.now(_LAUNCH_TZ).date()

def december_reward(day):
    if day in (10,20,25,31):
        return 'case',1
    if day % 3==0:
        return 'snowflakes',5+day//3
    return 'coins',200+60*day

def december_claimed(uid):
    with sqlite3.connect(EVENT_DB,timeout=15) as db:
        db.execute('CREATE TABLE IF NOT EXISTS december_claims '
                   '(user_id INTEGER NOT NULL,reward_day TEXT NOT NULL,claimed_at TEXT NOT NULL,PRIMARY KEY(user_id,reward_day))')
        return {r[0] for r in db.execute('SELECT reward_day FROM december_claims WHERE user_id=? AND reward_day LIKE ?', (uid,'2026-12-%'))}

def december_calendar_view(uid):
    today=december_today()
    open_until=(31 if today.year>2026 else today.day if today.year==2026 and today.month==12 else 0)
    claimed=december_claimed(uid)
    available=0;kb=types.InlineKeyboardMarkup(row_width=5)
    for start in range(1,32,5):
        row=[]
        for day in range(start,min(start+5,32)):
            stamp=f'2026-12-{day:02d}'
            icon='✅' if stamp in claimed else '🎁' if day<=open_until else '🔒'
            available+=int(icon=='🎁')
            row.append(types.InlineKeyboardButton(f'{icon} {day:02d}',callback_data=f'dec_cal_day:{day:02d}'))
        kb.row(*row)
    if available:
        kb.add(types.InlineKeyboardButton(f'🎁 Забрать всё доступное ({available})',callback_data='dec_cal_claim_all'))
    kb.row(types.InlineKeyboardButton('🔄 Обновить',callback_data='dec_cal_refresh'),
           types.InlineKeyboardButton('🏠 Главное меню',callback_data='dec_cal_back'))
    text=('🎄 <b>ДЕКАБРЬ 2026 — АДВЕНТ-КАЛЕНДАРЬ</b>\n'
          '━━━━━━━━━━━━━━━━━━\n\n'
          '31 день — 31 подарок! 🎁\n'
          'Пропущенные подарки не сгорают.\n\n'
          f'Доступно: <b>{available}</b>\n'
          '🎁 Забрать · ✅ Получено · 🔒 Не открыто\n\n'
          '🎆 31 декабря: золотой кейс и титул «Новый год 2027»!\n'
          'Особые награды: 10, 20 и 25 декабря.\n'
          'Каждый подарок выдаётся один раз.')
    return text,kb

def december_show_calendar(chat_id,uid):
    text,kb=december_calendar_view(uid)
    return bot.send_message(chat_id,text,reply_markup=kb,parse_mode='HTML')

def december_claim_many(uid,days=None):
    if _tech_disabled('calendar') or _tech_disabled('rewards'):
        return 0,'🛠 Календарь временно недоступен.'
    today=december_today()
    if today.year<2026 or (today.year==2026 and today.month<12):
        return 0,'🔒 Открытие 1 декабря 2026 года.'
    open_until=today.day if today.year==2026 and today.month==12 else 31
    selected=list(range(1,open_until+1)) if days is None else sorted(set(days))
    if not selected or any(not isinstance(d,int) or d<1 or d>31 for d in selected):
        return 0,'Неверный день.'
    if selected[-1]>open_until:
        return 0,'🔒 Этот день ещё не наступил.'
    try:
        if _punishment_get(uid) or openbot.get_global_ban(uid).get('banned'):
            return 0,'🚫 Нельзя получать подарки во время блокировки.'
    except Exception:
        return 0,'⚠️ Openbot API недоступен. Награды не выданы.'
    try:
        with sqlite3.connect(DB_NAME,timeout=15) as db:
            db.execute('ATTACH DATABASE ? AS event',(str(EVENT_DB),))
            db.execute('CREATE TABLE IF NOT EXISTS event.december_claims '
                       '(user_id INTEGER NOT NULL,reward_day TEXT NOT NULL,claimed_at TEXT NOT NULL,PRIMARY KEY(user_id,reward_day))')
            db.execute('CREATE TABLE IF NOT EXISTS event.winter_players '
                       '(user_id INTEGER PRIMARY KEY,snowflakes INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS event.winter_cases '
                       '(user_id INTEGER NOT NULL,case_key TEXT NOT NULL,count INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(user_id,case_key))')
            db.execute('CREATE TABLE IF NOT EXISTS event.winter_owned_titles '
                       '(user_id INTEGER NOT NULL, title_key TEXT NOT NULL, price INTEGER DEFAULT 0, '
                       'PRIMARY KEY(user_id,title_key))')
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM users WHERE user_id=?',(uid,)).fetchone():
                return 0,'Создай профиль: /start.'
            count=coins=snow=cases=0
            title_awarded=False
            for day in selected:
                cur=db.execute('INSERT OR IGNORE INTO event.december_claims(user_id,reward_day,claimed_at) VALUES(?,?,?)',
                    (uid,f'2026-12-{day:02d}',datetime.now(_LAUNCH_TZ).isoformat()))
                # 31 декабря — бесплатный праздничный титул, даже если игрок
                # забрал этот день до установки обновления. Повторной выдачи нет.
                if day==31:
                    title_cur=db.execute(
                        'INSERT OR IGNORE INTO event.winter_owned_titles(user_id,title_key,price) '
                        'VALUES(?,?,0)', (uid,'winter_2027'))
                    if title_cur.rowcount==1:
                        title_awarded=True
                if cur.rowcount!=1:continue
                kind,n=december_reward(day)
                if kind=='coins':
                    db.execute('UPDATE users SET coins=COALESCE(coins,0)+? WHERE user_id=?',(n,uid));coins+=n
                elif kind=='snowflakes':
                    db.execute('INSERT INTO event.winter_players(user_id,snowflakes) VALUES(?,?) '
                               'ON CONFLICT(user_id) DO UPDATE SET snowflakes=snowflakes+excluded.snowflakes',(uid,n));snow+=n
                else:
                    db.execute("INSERT INTO event.winter_cases(user_id,case_key,count) VALUES(?,'gold',?) "
                               'ON CONFLICT(user_id,case_key) DO UPDATE SET count=count+excluded.count',(uid,n));cases+=n
                count+=1
        if count==0 and not title_awarded:
            return 0,'✅ Все подарки уже получены.'
        lines=[f'🎉 Получено подарков: {count}!' if count else '🎉 Дополнительная награда получена!']
        if coins:lines.append(f'💰 +{coins} монет')
        if snow:lines.append(f'❄️ +{snow} снежинок')
        if cases:lines.append(f'🎁 +{cases} золотых кейсов')
        if title_awarded:lines.append('🏅 Титул «Новый год 2027»')
        return count + int(title_awarded and count==0),'\n'.join(lines)
    except Exception:
        logging.getLogger('random_bot.december').exception('Ошибка декабрьского календаря uid=%s',uid)
        return 0,'⚠️ Ошибка выдачи подарков. Проверь /logs.'

@bot.callback_query_handler(func=lambda c: bool(c.data) and c.data.startswith('dec_cal_'))
def december_calendar_callback(call):
    data=call.data or '';uid=call.from_user.id
    if data=='dec_cal_back':
        bot.answer_callback_query(call.id)
        return _ui_edit(call, '🏠 <b>Главное меню Random Bot</b>', main_mune())
    if data=='dec_cal_open':
        bot.answer_callback_query(call.id)
        text,kb=december_calendar_view(uid)
        return _ui_edit(call,text,kb)
    if data=='dec_cal_claim_all':
        count,notice=december_claim_many(uid)
    elif data.startswith('dec_cal_day:'):
        try:day=int(data.split(':',1)[1])
        except ValueError:return bot.answer_callback_query(call.id,'Неверный день')
        count,notice=december_claim_many(uid,[day])
    elif data=='dec_cal_refresh':
        count,notice=0,'🔄 Обновлено'
    else:
        return bot.answer_callback_query(call.id,'Неизвестная кнопка')
    bot.answer_callback_query(call.id,notice[:190],show_alert=bool(count))
    text,kb=december_calendar_view(uid)
    try:
        bot.edit_message_text(text,chat_id=call.message.chat.id,message_id=call.message.message_id,
                              reply_markup=kb,parse_mode='HTML')
    except apihelper.ApiTelegramException as exc:
        if 'message is not modified' not in str(exc).lower():raise

@bot.message_handler(commands=['december'])
def december_calendar_command(message):
    # Предпросмотр доступен до релиза; будущие дни забрать нельзя.
    return december_show_calendar(message.chat.id,message.from_user.id)

@bot.message_handler(func=lambda m: (m.text or '')=='📅 Календарь декабря')
def december_calendar_reply(message):
    return december_show_calendar(message.chat.id,message.from_user.id)

@bot.message_handler(commands=['calendar'])
def december_calendar_main_command(message):
    # До 1 декабря показываем закрытые дни, никаких ноябрьских наград.
    return december_show_calendar(message.chat.id, message.from_user.id)


@bot.message_handler(commands=['menu'])
def november_menu_command(message):
    """Показывает обновлённое главное меню в нужном формате кнопок."""
    user_id = message.from_user.id
    if get_user_settings(user_id)[0] == 'reply':
        send_main_reply_menu(message.chat.id, message.from_user.first_name)
    else:
        bot.send_message(
            message.chat.id, '🏠 Главное меню Random Bot',
            reply_markup=main_mune(),
        )


# Старые кнопки из сообщений до патча ведут в декабрь, а не выдают ноябрьские награды.
@bot.message_handler(func=lambda message: (message.text or '').strip() == '📅 Календарь ноября')
def legacy_november_calendar_reply(message):
    return december_show_calendar(message.chat.id, message.from_user.id)

@bot.callback_query_handler(func=lambda call: bool(call.data) and call.data.startswith('nov_cal_'))
def legacy_november_calendar_callback(call):
    bot.answer_callback_query(call.id, '📅 Теперь доступен декабрьский календарь')
    if call.data == 'nov_cal_back':
        return _ui_edit(call, '🏠 Главное меню Random Bot', main_mune())
    text, keyboard = december_calendar_view(call.from_user.id)
    return _ui_edit(call, text, keyboard)


# ============ 🎄 Новый год и день рождения комьюнити ============
from newyear_random_db import HolidayEvents

holiday_events = HolidayEvents(
    bot=bot,
    api=openbot,
    main_db=DB_NAME,
    event_db=Path(__file__).resolve().parent / "Newyear_random.db",
    create_user=create_user,
    profile_titles=PROFILE_TITLES,
)

# ============ Обработчики команд ==============
@bot.message_handler(commands=['start'])
def start_bot(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    reason = check_ban(user_id)


    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return

    create_user(user_id, username, first_name)
    try:
        openbot.create_id(user_id, first_name)
        openbot.register_bot_activity(user_id, "Random_bot")
    except Exception:
        logging.getLogger("random_bot.start").exception(
            "Ошибка синхронизации Openbot ID для user_id=%s", user_id
        )

    # Проверяем, какой тип клавиатуры выбрал пользователь
    kb_type = get_user_settings(user_id)[0]

    if kb_type == "reply":
        # Обычные кнопки снизу
        send_main_reply_menu(
            message.chat.id,
            first_name,
            (
                f"🎄 <b>RANDOM BOT — ЗИМНЕЕ ОБНОВЛЕНИЕ</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👋 Привет, <b>{html.escape(first_name)}</b>!\n\n"
                f"❄️ Добро пожаловать в зимний Random Bot!\n"
                f"🎁 Открывай кейсы • 🪙 торгуй • ❄️ играй • 💎 собирай редкие эмодзи\n\n"
                f"📅 <b>/calendar</b> — подарки зимнего сезона.\n"
                f"🎁 Особые праздничные дни — с редкими наградами!\n\n"
                f"👇 <b>Главное меню:</b>"
            )
        )

    else:
        # Inline-кнопки
        bot.send_message(
            message.chat.id,
            f"🎄 Привет, {html.escape(first_name)}!\n❄️ Добро пожаловать в зимний Random Bot!\n\n"
            "📅 Введи /calendar — зимние подарки!\n"
            "🎁 В праздничные дни — особые призы!",
            reply_markup=main_mune()
        )

def _help_role(uid):
    """Only server-confirmed Openbot ID roles grant an admin help section."""
    try:
        info = openbot.get_user(uid)
        if isinstance(info, dict) and info.get('exists'):
            role = str(info.get('status') or 'user').strip().lower()
            if role in {'owner', 'developer', 'admin', 'tester', 'coder', 'user'}:
                return role
    except Exception:
        logging.getLogger('random_bot.help').warning('Openbot ID role unavailable for %s', uid)
    return 'user'


def _help_text(role):
    common = (
        '📖 <b>ПОМОЩЬ RANDOM BOT</b>\n'
        '━━━━━━━━━━━━━━━━━━\n'
        f'🎭 Статус: <b>{html.escape(STATUS.get(role, ROLE.get(role, role)))}</b>\n\n'
        '👤 <b>КОМАНДЫ ИГРОКА</b>\n'
        '/start — запустить бота\n'
        '/menu — главное меню\n'
        '/help — список доступных команд\n'
        '/profile — игровой профиль\n'
        '/id_profile — глобальный профиль Openbot ID\n'
        '/calendar — текущий адвент-календарь\n'
        '/december — календарь декабря 2026\n'
        '/my_titles — мои титулы\n'
        '/leaders — таблица лидеров\n'
        '/game_stop — выйти из текущей игры\n'
        '/sell_emoji — выставить эмодзи на рынок\n'
        '/bio — изменить описание Openbot ID\n'
        '/feedback — отзыв разработчикам\n'
        '/ban_info — информация о блокировке\n'
        '/support — поддержка (в разработке)\n'
        '/appeal — обращение (в разработке)'
    )
    if role not in {'admin', 'developer', 'owner'}:
        return common + '\n\n🎄 <i>Winter Release 2026</i>'
    admin = (
        '\n\n🛡 <b>АДМИНИСТРИРОВАНИЕ</b>\n'
        '/ban @username 7d Причина — локальный бан\n'
        '/unban @username — снять бан\n'
        '/hard_ban @username 7d Причина — строгий бан\n'
        '/unhard_ban @username — снять строгий бан\n'
        '/global_ban @username 7d Причина — глобальный бан\n'
        '/global_unban @username — снять глобальный бан\n'
        '/global_hard_ban @username 7d Причина — глобальный строгий бан\n'
        '/global_unhard_ban @username — снять глобальный строгий бан\n'
        '/ban_info @username — проверить блокировку\n'
        '/sendall Текст — рассылка\n'
        '/give_coins @username 100 — выдать монеты\n'
        '/take_coins @username 100 — снять монеты\n'
        '/level_up @username 20 — изменить уровень\n'
        '/gift @username 🎁 — подарить эмодзи\n'
        '/tech — управление техработами\n'
        '/launch — режим зимнего запуска\n'
        '/features — новые игры и этапы релиза\n'
        '/testgame memory — тест новых игр\n'
        '/get_status @username — статус Openbot ID'
    )
    if role in {'developer', 'owner'}:
        admin += (
            '\n\n💻 <b>РАЗРАБОТКА</b>\n'
            '/reply_off — временно ограничить Reply\n'
            '/reply_on — вернуть прежние режимы\n'
            '/logs — последние ошибки (при наличии доступа)\n'
            '/get_status @username tester 2 — управление ролями (при наличии прав)'
        )
    return common + admin + '\n\n<i>Доступ к командам проверяется отдельно.</i>'


@bot.message_handler(commands=['help'])
def bot_help(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    if reason:
        return bot.reply_to(message, f'🚫 Вы заблокированы!\nПричина: {reason}')
    role = _help_role(uid)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='back'))
    bot.send_message(message.chat.id, _help_text(role), reply_markup=kb, parse_mode='HTML')

@bot.message_handler(commands=['game_stop'])
def stop_game(message):
    user_id = message.from_user.id
    game_data = get_active_game(user_id)
    if game_data and game_data[0] != 'none':
        game_name = game_data[0].upper()
        delete_active_game(user_id)
        msg = bot.send_message(message.chat.id, f"🛑 Игра «{game_name}» остановлена. Вы вернулись в главное меню.")
        time.sleep(1)
        bot.edit_message_text(f'👋 Привет, {message.from_user.first_name}\nДобро пожаловать!', reply_markup=main_mune(), 
            message_id=msg.message_id, 
            chat_id=message.chat.id)
    else:
        bot.send_message(message.chat.id, "Ты сейчас ни во что не играешь.")

# ============ RANDOM BOT: НАKАЗАНИЯ ============
"""Independent Random Bot punishment registry; does not alter Openbot ID roles."""
import calendar
import re

from datetime import datetime, timedelta, timezone


_punishment_DB_PATH = Path(__file__).resolve().parent / DB_NAME
_punishment_TIME_RE = re.compile(r"^(\d+)(h|d|mo|y)$", re.I)


def _punishment_init():
    with sqlite3.connect(_punishment_DB_PATH, timeout=15) as db:
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("""CREATE TABLE IF NOT EXISTS punishments (
            user_id INTEGER PRIMARY KEY, kind TEXT NOT NULL,
            reason TEXT NOT NULL, issued_by INTEGER NOT NULL,
            issued_at TEXT NOT NULL, expires_at TEXT,
            username TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS punishment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, kind TEXT NOT NULL,
            reason TEXT NOT NULL, actor_id INTEGER NOT NULL,
            action TEXT NOT NULL, created_at TEXT NOT NULL)""")
        columns = {row[1] for row in db.execute("PRAGMA table_info(punishments)")}
        if "previous_status" not in columns:
            db.execute("ALTER TABLE punishments ADD COLUMN previous_status TEXT")
        # Миграция действующих банов из предыдущей версии: ранее их добавляли
        # в punishments, но забывали обновить users.status.
        current_time = datetime.now(timezone.utc).isoformat()
        db.execute(
            """UPDATE punishments SET previous_status = COALESCE(
                   (SELECT NULLIF(status, 'banned') FROM users
                    WHERE users.user_id = punishments.user_id), 'user')
               WHERE previous_status IS NULL
                 AND (expires_at IS NULL OR expires_at > ?)""",
            (current_time,),
        )
        db.execute(
            """UPDATE users SET status='banned', ban_reason=(
                   SELECT p.reason FROM punishments AS p
                   WHERE p.user_id=users.user_id)
               WHERE EXISTS (
                   SELECT 1 FROM punishments AS p
                   WHERE p.user_id=users.user_id
                     AND (p.expires_at IS NULL OR p.expires_at > ?))""",
            (current_time,),
        )


def _punishment__add_months(dt, count):
    month_index = dt.year * 12 + dt.month - 1 + count
    year, month_index = divmod(month_index, 12)
    if year > 9999:
        raise ValueError("Слишком большой срок")
    month = month_index + 1
    return dt.replace(year=year, month=month,
                      day=min(dt.day, calendar.monthrange(year, month)[1]))


def _punishment_expires_from(spec):
    match = _punishment_TIME_RE.fullmatch(spec.lower())
    if not match:
        raise ValueError("Время: 12h, 7d, 3mo или 1y (999y = навсегда)")
    count, unit = int(match[1]), match[2]
    if count < 1:
        raise ValueError("Срок должен быть положительным")
    if spec.lower() == "999y":
        return None
    now = datetime.now(timezone.utc)
    if unit == "h":
        result = now + timedelta(hours=count)
    elif unit == "d":
        result = now + timedelta(days=count)
    elif unit == "mo":
        result = _punishment__add_months(now, count)
    else:
        result = _punishment__add_months(now, 12 * count)
    return result.isoformat()


def _punishment_restore_status(user_id, previous_status=None):
    """После LOCAL UNBAN не снимает GLOBAL BAN и сохраняет настоящую роль."""
    fallback = (
        previous_status if previous_status and previous_status != 'banned'
        else 'user'
    )
    info = get_openbot_user(user_id)
    if info:
        fallback = str(info.get('status') or fallback).lower()

    # Если сервер недоступен, не снимаем сохранённый маркер глобального бана.
    global_ban = None
    try:
        global_ban = openbot.get_global_ban(user_id)
    except Exception:
        pass

    with sqlite3.connect(_punishment_DB_PATH, timeout=15) as db:
        db.execute('PRAGMA busy_timeout=15000')
        db.row_factory = sqlite3.Row
        local = db.execute(
            'SELECT kind, reason FROM punishments WHERE user_id=?',
            (user_id,),
        ).fetchone()
        saved = db.execute(
            'SELECT global_ban_kind, ban_reason FROM users WHERE user_id=?',
            (user_id,),
        ).fetchone()
        if not saved:
            return
        if global_ban is None:
            kind = saved['global_ban_kind']
            global_reason = saved['ban_reason']
        else:
            kind = global_ban.get('kind') if global_ban.get('banned') else None
            global_reason = global_ban.get('reason')
        status = 'banned' if local or kind else fallback
        reason = local['reason'] if local else global_reason if kind else None
        db.execute(
            'UPDATE users SET status=?, ban_reason=?, global_ban_kind=? '
            'WHERE user_id=?', (status, reason, kind, user_id),
        )


def _punishment_notify_unban(user_id, kind, *, expired=False):
    """Не обещает полный доступ, если у игрока остался другой бан."""
    title = 'HARD BAN' if kind == 'hard_ban' else 'BAN'
    reason = (
        'Срок локальной блокировки истёк.' if expired
        else 'Администрация сняла локальную блокировку.'
    )
    row = conn.execute(
        'SELECT status FROM users WHERE user_id=?', (user_id,),
    ).fetchone()
    access = (
        '⚠️ Другие ограничения всё ещё действуют. Проверь /ban_info.'
        if row and row[0] == 'banned'
        else '🎮 Доступ к Random Bot восстановлен.'
    )
    try:
        bot.send_message(user_id, f'✅ {title} снят!\n{reason}\n{access}')
        return True
    except Exception:
        logging.getLogger('random_bot.punishments').warning(
            'Не удалось уведомить о снятии бана user_id=%s', user_id,
        )
        return False


def _punishment_get(user_id):
    expired = None
    with sqlite3.connect(_punishment_DB_PATH, timeout=15) as db:
        db.execute("PRAGMA busy_timeout=15000")
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM punishments WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            return None
        entry = dict(row)
        if entry["expires_at"] and datetime.fromisoformat(entry["expires_at"]) <= datetime.now(timezone.utc):
            db.execute("DELETE FROM punishments WHERE user_id=?", (user_id,))
            db.execute(
                """INSERT INTO punishment_history
                   (user_id,kind,reason,actor_id,action,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (user_id, entry["kind"], entry["reason"], 0,
                 "expired", datetime.now(timezone.utc).isoformat()),
            )
            expired = entry
        else:
            return entry

    if expired:
        _punishment_restore_status(user_id, expired.get("previous_status"))
        _punishment_notify_unban(user_id, expired["kind"], expired=True)
    return None


def _punishment_set_ban(user_id, username, kind, reason, actor_id, duration):
    if kind not in {"ban", "hard_ban"} or not reason.strip():
        raise ValueError("Неверное наказание или пустая причина")
    expiry = _punishment_expires_from(duration)
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(_punishment_DB_PATH, timeout=15) as db:
        db.execute("PRAGMA busy_timeout=15000")
        previous_row = db.execute(
            "SELECT previous_status FROM punishments WHERE user_id=?", (user_id,)
        ).fetchone()
        current_row = db.execute(
            "SELECT status FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        if not current_row:
            raise ValueError("Игрок отсутствует в базе Random Bot")
        previous = (
            previous_row[0] if previous_row and previous_row[0]
            else (current_row[0] if current_row[0] != "banned" else "user")
        )
        db.execute(
            """INSERT INTO punishments
               (user_id,kind,reason,issued_by,issued_at,expires_at,username,previous_status)
               VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
               kind=excluded.kind, reason=excluded.reason, issued_by=excluded.issued_by,
               issued_at=excluded.issued_at, expires_at=excluded.expires_at,
               username=excluded.username, previous_status=excluded.previous_status""",
            (user_id, kind, reason.strip(), actor_id, now, expiry, username, previous),
        )
        # Локальный статус. Глобальную роль Openbot ID не меняем.
        db.execute(
            "UPDATE users SET status='banned', ban_reason=? WHERE user_id=?",
            (reason.strip(), user_id),
        )
        db.execute(
            """INSERT INTO punishment_history
               (user_id,kind,reason,actor_id,action,created_at)
               VALUES(?,?,?,?,?,?)""",
            (user_id, kind, reason.strip(), actor_id, "issued", now),
        )
    return expiry


def _punishment_lift(user_id, kind, actor_id):
    with sqlite3.connect(_punishment_DB_PATH, timeout=15) as db:
        db.execute("PRAGMA busy_timeout=15000")
        row = db.execute(
            "SELECT reason,previous_status FROM punishments WHERE user_id=? AND kind=?",
            (user_id, kind),
        ).fetchone()
        if not row:
            return False
        db.execute("DELETE FROM punishments WHERE user_id=? AND kind=?", (user_id, kind))
        db.execute(
            """INSERT INTO punishment_history
               (user_id,kind,reason,actor_id,action,created_at)
               VALUES(?,?,?,?,?,?)""",
            (user_id, kind, row[0], actor_id, "lifted", datetime.now(timezone.utc).isoformat()),
        )
        previous_status = row[1]
    _punishment_restore_status(user_id, previous_status)
    return True

_punishment_init()



def _punish_admin(message):
    try:
        return (message.chat.type == 'private' and
                openbot.check_access(message.from_user.id,
                                     ('developer', 'tester', 'admin', 'owner'), 1))
    except Exception:
        return False


def _target_username(raw):
    if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}", raw):
        raise ValueError('Укажи @username (от 5 до 32 символов)')
    username = raw[1:].lower()
    row = conn.execute('SELECT user_id FROM users WHERE LOWER(username)=?', (username,)).fetchone()
    if not row:
        raise ValueError('Пользователь не найден в базе Random Bot')
    return int(row[0]), username


# ============ Каждая команда наказания — отдельный обработчик ============
# Вспомогательные функции выше только работают с БД и проверяют username.

@bot.message_handler(commands=['ban'])
def ban_user(message):
    """Обычный BAN: блокировка игр, покупок и получения наград."""
    if not _punish_admin(message):
        bot.reply_to(message, '⛔ Команда доступна администрации в ЛС бота.')
        return

    parts = (message.text or '').split(maxsplit=3)
    if len(parts) != 4:
        bot.reply_to(message, 'Формат: /ban @username 7d Причина\nСроки: h, d, mo, y, 999y')
        return

    try:
        user_id, username = _target_username(parts[1])
        if user_id == message.from_user.id:
            raise ValueError('Нельзя заблокировать самого себя')

        info = openbot.get_user(user_id)
        if not isinstance(info, dict):
            raise RuntimeError('Не удалось проверить глобальную роль пользователя')
        if info.get('status') in ('owner', 'developer', 'admin', 'tester'):
            raise ValueError('Служебные аккаунты защищены от бана')

        reason = parts[3].strip()
        if not reason:
            raise ValueError('Причина обязательна')
        expiry = _punishment_set_ban(user_id, username, 'ban', reason,
                                     message.from_user.id, parts[2])
        details = _punishment_get(user_id)
        if details:
            _global_notify(
                user_id, _local_format_ban(
                    details, admin_username=message.from_user.username
                )
            )
        bot.reply_to(message, f'✅ Игрок @{username} забанен.')
    except (ValueError, OverflowError) as exc:
        bot.reply_to(message, f'❌ {exc}')
    except Exception:
        error_logger.exception('Ошибка /ban')
        bot.reply_to(message, '❌ Не удалось выдать BAN. Проверь /logs.')


@bot.message_handler(commands=['unban'])
def unban_by_username(message):
    """Снять только обычный BAN."""
    if not _punish_admin(message):
        bot.reply_to(message, '⛔ Команда доступна администрации в ЛС бота.')
        return

    parts = (message.text or '').split()
    if len(parts) != 2:
        bot.reply_to(message, 'Формат: /unban @username')
        return

    try:
        user_id, username = _target_username(parts[1])
        if not _punishment_lift(user_id, 'ban', message.from_user.id):
            raise ValueError('У пользователя нет активного обычного BAN')
        delivered = _punishment_notify_unban(user_id, 'ban')
        bot.reply_to(message, f'✅ Обычный BAN снят с @{username}' +
                     ('' if delivered else '\n⚠️ Не удалось доставить уведомление игроку.'))
    except ValueError as exc:
        bot.reply_to(message, f'❌ {exc}')
    except Exception:
        error_logger.exception('Ошибка /unban')
        bot.reply_to(message, '❌ Не удалось снять BAN. Проверь /logs.')


@bot.message_handler(commands=['hard_ban'])
def hard_ban_user(message):
    """HARD BAN: полностью закрывает доступ к Random Bot."""
    if not _punish_admin(message):
        bot.reply_to(message, '⛔ Команда доступна администрации в ЛС бота.')
        return

    parts = (message.text or '').split(maxsplit=3)
    if len(parts) != 4:
        bot.reply_to(message, 'Формат: /hard_ban @username 1mo Причина\nСроки: h, d, mo, y, 999y')
        return

    try:
        user_id, username = _target_username(parts[1])
        if user_id == message.from_user.id:
            raise ValueError('Нельзя заблокировать самого себя')

        info = openbot.get_user(user_id)
        if not isinstance(info, dict):
            raise RuntimeError('Не удалось проверить глобальную роль пользователя')
        if info.get('status') in ('owner', 'developer', 'admin', 'tester'):
            raise ValueError('Служебные аккаунты защищены от бана')

        reason = parts[3].strip()
        if not reason:
            raise ValueError('Причина обязательна')
        expiry = _punishment_set_ban(user_id, username, 'hard_ban', reason,
                                     message.from_user.id, parts[2])
        details = _punishment_get(user_id)
        if details:
            _global_notify(
                user_id, _local_format_ban(
                    details, admin_username=message.from_user.username
                )
            )
        bot.reply_to(message, f'✅ Игрок @{username} забанен.')
    except (ValueError, OverflowError) as exc:
        bot.reply_to(message, f'❌ {exc}')
    except Exception:
        error_logger.exception('Ошибка /hard_ban')
        bot.reply_to(message, '❌ Не удалось выдать HARD BAN. Проверь /logs.')


@bot.message_handler(commands=['unhard_ban'])
def unhard_ban_user(message):
    """Снять только HARD BAN."""
    if not _punish_admin(message):
        bot.reply_to(message, '⛔ Команда доступна администрации в ЛС бота.')
        return

    parts = (message.text or '').split()
    if len(parts) != 2:
        bot.reply_to(message, 'Формат: /unhard_ban @username')
        return

    try:
        user_id, username = _target_username(parts[1])
        if not _punishment_lift(user_id, 'hard_ban', message.from_user.id):
            raise ValueError('У пользователя нет активного HARD BAN')
        delivered = _punishment_notify_unban(user_id, 'hard_ban')
        bot.reply_to(message, f'✅ HARD BAN снят с @{username}' +
                     ('' if delivered else '\n⚠️ Не удалось доставить уведомление игроку.'))
    except ValueError as exc:
        bot.reply_to(message, f'❌ {exc}')
    except Exception:
        error_logger.exception('Ошибка /unhard_ban')
        bot.reply_to(message, '❌ Не удалось снять HARD BAN. Проверь /logs.')


@bot.message_handler(commands=['ban_id'])
def ban_id_user(message):
    """Резерв для ЧС проекта. Не выдаёт HARD BAN под другим названием."""
    bot.reply_to(message,
                 "ℹ️ /ban_id пока зарезервирована для ЧС проекта.\n"
                 "Обычный бан: /ban @username 7d Причина\n"
                 "Строгий бан: /hard_ban @username 7d Причина")


@bot.message_handler(commands=['unban_id'])
def unban_id_user(message):
    """Резерв для разблокировки ЧС проекта."""
    bot.reply_to(message, "ℹ️ /unban_id пока не используется. Для HARD BAN: /unhard_ban @username")


# ============ ГЛОБАЛЬНЫЙ СТАТУС OPENBOT ID ============
@bot.message_handler(commands=['get_status'])
def get_status_command(message):
    """/get_status @username [developer|tester|admin|coder|user] [1-4].

    Без роли показывает текущий статус. С ролью и уровнем отправляет
    изменение через защищённый административный маршрут FastAPI.
    """
    if message.chat.type != 'private':
        bot.reply_to(message, '⛔ Команда доступна только в ЛС бота.')
        return

    try:
        actor = openbot.get_user(message.from_user.id)
        if not isinstance(actor, dict) or not actor.get('exists'):
            raise PermissionError('Не удалось подтвердить твои полномочия через Openbot ID')
        actor_role = str(actor.get('status', 'user')).lower()
        actor_level = int(actor.get('level', 0))
        if not (actor_role == 'owner' or (actor_role == 'developer' and actor_level >= 4)):
            raise PermissionError('Изменять глобальные роли могут только owner и developer IV')

        args = (message.text or '').split()
        if len(args) not in (2, 4):
            raise ValueError('Формат: /get_status @username [статус уровень]\n'
                             'Пример: /get_status @username tester 2')

        user_id, username = _target_username(args[1])
        target = openbot.get_user(user_id)
        if not isinstance(target, dict) or not target.get('exists'):
            raise ValueError('Глобальный Openbot ID пользователя не найден')

        previous_role = str(target.get('status', 'user')).lower()
        previous_level = int(target.get('level', 1))

        if len(args) == 2:
            bot.reply_to(message, f'🌐 @{username}\n🎭 Роль: {ROLE.get(previous_role, previous_role)}'
                                  f'\n⭐ Уровень: {previous_level}')
            return

        role = args[2].strip().lower()
        allowed = {'user', 'coder', 'tester', 'admin', 'developer'}
        if role not in allowed:
            raise ValueError('Разрешённые статусы: user, coder, tester, admin, developer')
        try:
            level = int(args[3])
        except ValueError as exc:
            raise ValueError('Уровень должен быть числом от 1 до 4') from exc
        if level < 1 or level > 4:
            raise ValueError('Уровень Openbot ID должен быть от 1 до 4')
        if role == 'user' and level != 1:
            raise ValueError('Для статуса user используй уровень 1')
        if user_id == message.from_user.id:
            raise PermissionError('Нельзя изменять собственный глобальный статус этой командой')
        if previous_role == 'owner':
            raise PermissionError('Статус владельца нельзя изменять через Random Bot')
        if actor_role != 'owner' and previous_role == 'developer' and previous_level >= 4:
            raise PermissionError('Разработчика IV уровня может изменить только владелец')

        admin_key = os.environ.get('OPENBOT_ADMIN_API_KEY', '').strip()
        if not admin_key:
            raise RuntimeError('Для изменения роли не настроен OPENBOT_ADMIN_API_KEY')
        api_url = os.environ.get('OPENBOT_API_URL', 'http://127.0.0.1:8000').rstrip('/')
        location = urlsplit(api_url)
        if location.scheme not in {'http', 'https'} or not location.hostname:
            raise ValueError('Некорректный OPENBOT_API_URL')
        if location.scheme == 'http' and location.hostname not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError('Для удалённого Openbot API требуется HTTPS')
        body = json.dumps({'user_id': user_id, 'status': role, 'level': level}).encode('utf-8')
        request = Request(
            api_url + '/api/legacy/account/status',
            data=body,
            headers={'X-Admin-Key': admin_key, 'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urlopen(request, timeout=10) as response:
                answer = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            raise RuntimeError(f'FastAPI вернул HTTP {exc.code} (проверь права ключа и маршрут)') from exc
        except URLError as exc:
            raise RuntimeError('Не удалось подключиться к Openbot API') from exc

        if answer.get('ok') is not True:
            raise RuntimeError('FastAPI не подтвердил изменение статуса')

        # Обновление локальной копии статуса сделает существующий sync_global_status.
        sync_global_status(user_id)
        logging.getLogger('random_bot.global_status').info(
            'actor=%s target=%s role=%s level=%s',
            message.from_user.id, user_id, role, level,
        )
        bot.reply_to(message, f'✅ Глобальный статус изменён!\n👤 @{username}\n'
                              f'🎭 {ROLE.get(role, role)}\n⭐ Уровень: {level}')
    except (PermissionError, ValueError) as exc:
        bot.reply_to(message, f'❌ {exc}')
    except Exception as exc:
        error_logger.exception('Ошибка /get_status')
        # Не раскрывать ошибочные ответы сервера и секреты в Telegram.
        bot.reply_to(message, f'❌ Не удалось изменить или получить статус. {exc}')


# ============ 🌐 OPENBOT ID: ГЛОБАЛЬНЫЕ НАКАЗАНИЯ ============
# Команды расположены прямо в основном файле Random Bot.
# Сервер FastAPI хранит наказания в центральной БД.
# Только staff API-ключ, принадлежащий инициатору, может выдать наказание.

from openbot_api import APIError


def _global_target(raw):
    """@username доступен, только если пользователь уже известен Random Bot."""
    normalized = "@" + raw.strip().lstrip("@")
    return _target_username(normalized)


def _global_command_args(message, *, lifting=False):
    if message.chat.type != "private":
        raise ValueError("Глобальные наказания доступны только в ЛС бота")
    args = (message.text or "").split(maxsplit=3)
    if lifting:
        if len(args) != 2:
            raise ValueError("Формат: /global_unban @username")
        uid, username = _global_target(args[1])
        return uid, username
    if len(args) != 4 or not args[3].strip():
        raise ValueError("Формат: /global_ban @username 7d Причина")
    uid, username = _global_target(args[1])
    if uid == message.from_user.id:
        raise ValueError("Нельзя заблокировать самого себя")
    return uid, username, args[2], args[3].strip()


def _global_notify(uid, text):
    try:
        bot.send_message(uid, text)
        return True
    except Exception:
        return False


def _ban_date_time(raw):
    """Переводит сохранённую ISO-дату (UTC) в местное время сервера."""
    if not raw:
        return 'Неизвестно', 'Неизвестно'
    try:
        dt = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone()
        return local.strftime('%d.%m.%Y'), local.strftime('%H:%M')
    except (ValueError, TypeError, OverflowError):
        return 'Неизвестно', 'Неизвестно'


def _ban_admin_username(ban, username=None):
    """Возвращает @username модератора или его ID, если username недоступен."""
    if username:
        return '@' + str(username).strip().lstrip('@')

    actor_id = ban.get('actor_id') or ban.get('issued_by')
    if not actor_id:
        return 'Неизвестен'

    try:
        row = conn.execute(
            'SELECT username FROM users WHERE user_id=?', (actor_id,)
        ).fetchone()
        if row and row[0]:
            return '@' + str(row[0]).lstrip('@')
    except sqlite3.Error:
        pass

    # Для старых записей берём имя через Telegram, если его нет в локальной БД.
    try:
        chat = bot.get_chat(int(actor_id))
        if getattr(chat, 'username', None):
            return '@' + chat.username
    except Exception:
        pass
    return f'ID {actor_id}'


def _ban_notice(ban, *, global_scope, admin_username=None):
    """Компактное уведомление с модератором и датами по времени сервера."""
    names = {
        'ban': 'BAN', 'hard_ban': 'HARD BAN',
        'global_ban': 'GLOBAL BAN', 'global_hard_ban': 'GLOBAL HARD BAN',
    }
    kind = names.get(ban.get('kind'), 'BAN')
    when = ban.get('created_at') if global_scope else ban.get('issued_at')
    start_day, start_clock = _ban_date_time(when)
    expires = ban.get('expires_at')
    end_day, end_clock = _ban_date_time(expires)
    start = f'{start_day} в {start_clock}'
    end = f'{end_day} в {end_clock}' if expires else 'Навсегда'
    place = 'Вся сеть Openbot.Ai' if global_scope else 'Random Bot'
    reason = str(ban.get('reason') or 'Не указана')[:500]
    admin = _ban_admin_username(ban, admin_username)
    return (
        '🚫 Вас забанили!\n\n'
        f'📍 Где: {place}\n'
        f'🔒 Тип: {kind}\n'
        f'📝 Причина: {reason}\n'
        f'👮 Администратор: {admin}\n\n'
        f'📅 Забанили: {start}\n'
        f'⏳ Забанены до: {end}\n\n'
        '📋 Подробности: /ban_info'
    )


def _global_format_ban(ban, *, admin_username=None):
    return _ban_notice(
        ban, global_scope=True, admin_username=admin_username
    )


def _local_format_ban(ban, *, admin_username=None):
    return _ban_notice(
        ban, global_scope=False, admin_username=admin_username
    )


def _sync_global_ban_mirror(user_id, ban):
    """Обновляет локальное отображение после действий на центральном API."""
    return sync_global_status(user_id, global_ban=ban)


@bot.message_handler(commands=['global_ban'])
def global_ban_command(message):
    """Ограничение игр, торговли, наград во всех ботах сети."""
    try:
        uid, name, duration, reason = _global_command_args(message)
        # Передаём все параметры по имени, чтобы исключить путаницу
        # между duration и reason в разных версиях клиента.
        result = openbot.global_ban(
            user_id=uid,
            duration=duration,
            reason=reason,
            actor_id=message.from_user.id,
        )
        _sync_global_ban_mirror(uid, result)
        _global_notify(
            uid, _global_format_ban(
                result, admin_username=message.from_user.username
            )
        )
        bot.reply_to(message, f'✅ Игрок @{name} забанен.')
    except (APIError, ValueError) as exc:
        if "reason is required" in str(exc).lower():
            error_logger.error(
                "Несовместимая версия openbot_api при /global_ban: %s; module=%s",
                exc, getattr(openbot_api, "__file__", "unknown"),
            )
            bot.reply_to(
                message,
                "❌ Библиотека openbot_api не получила причину, хотя она есть "
                "в команде. Вероятно, бот запущен со старой версией пакета. "
                "Проверь путь к библиотеке в /logs.",
            )
        else:
            bot.reply_to(message, f"❌ {exc}")
    except Exception:
        error_logger.exception("Ошибка /global_ban")
        bot.reply_to(message, "❌ Ошибка глобального бана, проверь /logs")


@bot.message_handler(commands=['global_unban'])
def global_unban_command(message):
    """Удаляет только GLOBAL BAN; восстанавливает роль при отсутствии других банов."""
    try:
        uid, name = _global_command_args(message, lifting=True)
        if not openbot.global_unban(uid, actor_id=message.from_user.id):
            return bot.reply_to(message, '❌ У игрока нет GLOBAL BAN')
        # Метод возвращает True только при подтверждённом снятии на FastAPI.
        _sync_global_ban_mirror(uid, {'banned': False, 'kind': None})
        # Даже если зеркало не обновилось из-за временного сбоя, центральный бан снят.
        remaining = _punishment_get(uid)
        access = (
            '⚠️ Локальный бан остаётся активным. Проверь /ban_info.'
            if remaining else '🎮 Доступ восстановлен.'
        )
        _global_notify(uid, f'✅ GLOBAL BAN снят!\n{access}')
        bot.reply_to(message, f'✅ Глобальный бан с @{name} снят.')
    except (APIError, ValueError) as exc:
        bot.reply_to(message, f'❌ {exc}')
    except Exception:
        error_logger.exception('Ошибка /global_unban')
        bot.reply_to(message, '❌ Ошибка снятия бана, проверь /logs')


@bot.message_handler(commands=['global_hard_ban'])
def global_hard_ban_command(message):
    """Полное закрытие игровых функций сети, доступна только информация и поддержка."""
    try:
        uid, name, duration, reason = _global_command_args(message)
        result = openbot.global_hard_ban(
            user_id=uid,
            duration=duration,
            reason=reason,
            actor_id=message.from_user.id,
        )
        _sync_global_ban_mirror(uid, result)
        _global_notify(
            uid, _global_format_ban(
                result, admin_username=message.from_user.username
            )
        )
        bot.reply_to(message, f'✅ Игрок @{name} забанен.')
    except (APIError, ValueError) as exc:
        if "reason is required" in str(exc).lower():
            error_logger.error(
                "Несовместимая версия openbot_api при /global_hard_ban: %s; module=%s",
                exc, getattr(openbot_api, "__file__", "unknown"),
            )
            bot.reply_to(
                message,
                "❌ Библиотека openbot_api не получила причину, хотя она есть "
                "в команде. Вероятно, бот запущен со старой версией пакета. "
                "Проверь путь к библиотеке в /logs.",
            )
        else:
            bot.reply_to(message, f"❌ {exc}")
    except Exception:
        error_logger.exception("Ошибка /global_hard_ban")
        bot.reply_to(message, "❌ Ошибка глобального HARD BAN, проверь /logs")


@bot.message_handler(commands=['global_unhard_ban'])
def global_unhard_ban_command(message):
    """Удаляет только GLOBAL HARD BAN и обновляет отображение статуса."""
    try:
        uid, name = _global_command_args(message, lifting=True)
        if not openbot.global_unhard_ban(uid, actor_id=message.from_user.id):
            return bot.reply_to(message, '❌ У игрока нет GLOBAL HARD BAN')
        _sync_global_ban_mirror(uid, {'banned': False, 'kind': None})
        remaining = _punishment_get(uid)
        access = (
            '⚠️ Локальный бан остаётся активным. Проверь /ban_info.'
            if remaining else '🎮 Доступ восстановлен.'
        )
        _global_notify(uid, f'✅ GLOBAL HARD BAN снят!\n{access}')
        bot.reply_to(message, f'✅ Глобальный HARD BAN с @{name} снят.')
    except (APIError, ValueError) as exc:
        bot.reply_to(message, f'❌ {exc}')
    except Exception:
        error_logger.exception('Ошибка /global_unhard_ban')
        bot.reply_to(message, '❌ Ошибка снятия HARD BAN, проверь /logs')


@bot.message_handler(commands=['ban_info'])
def global_ban_information(message):
    """Владелец видит свои баны; админ может проверить /ban_info @username."""
    parts = (message.text or '').split(maxsplit=1)
    uid = message.from_user.id
    username = message.from_user.username or 'без_username'
    if len(parts) == 2 and parts[1].strip():
        if not _punish_admin(message):
            return bot.reply_to(message, '⛔ Проверять других игроков может администрация.')
        try:
            uid, username = _global_target(parts[1])
        except ValueError as exc:
            return bot.reply_to(message, f'❌ {exc}')

    notices = []
    failed = False
    try:
        central = openbot.get_global_ban(uid)
        if central.get('banned'):
            notices.append(_global_format_ban(central))
    except (APIError, OSError, ValueError):
        failed = True
    local = _punishment_get(uid)
    if local:
        notices.append(_local_format_ban(local))
    if notices:
        content = f'📋 Информация о блокировках @{username}\n\n' + (
            '\n\n──────────────\n\n'.join(notices)
        )
        if failed:
            content += '\n\n⚠️ Глобальный статус временно недоступен.'
    elif failed:
        content = '⚠️ Сейчас не удалось проверить глобальные блокировки.'
    else:
        content = f'✅ У @{username} нет активных блокировок.'
    bot.reply_to(message, content[:4000])


@bot.message_handler(commands=['appeal'])
def global_ban_appeal(message):
    bot.reply_to(message, '🛠 Система поддержки пока в разработке.')


@bot.message_handler(commands=['support'])
def support_placeholder(message):
    bot.reply_to(message, '🛠 Система поддержки пока в разработке.')


class GlobalBanMiddleware(BaseMiddleware):
    """Проверка центральных наказаний перед каждым сообщением и callback.

    При сбое API экономические операции запрещаются; уже совершённые
    Telegram Stars платежи всегда обрабатываются штатным обработчиком.
    """
    SOFT_CMDS = {
        '/start', '/help', '/profile', '/id_profile', '/my_titles',
        '/leaders', '/ban_info', '/appeal', '/get_status',
        '/calendar', '/menu',
    }
    HARD_CMDS = {'/ban_info', '/appeal', '/support'}
    SOFT_TEXT = {
        '👤 Профиль', '🎒 Инвентарь', '⚙️ Настройки',
        '⚙ Настройки ID', '⬅ Главное меню', '⬅ В главное меню',
        '⬅ Инвентарь', '📊 Лидеры', '🏆 Мои титулы',
        '📅 Календарь ноября', '📅 Календарь декабря',
    }
    SOFT_CALLBACKS = {
        'profile', 'settings_user', 'settings_id', 'back',
        'open_inventory', 'winter_titles', 'winter_leaders', 'leaders_refresh',
        'winter_badge', 'toggle_kb', 'toggle_notif', 'toggle_show_id',
        'ignore_click', 'nov_cal_open', 'nov_cal_refresh', 'nov_cal_back',
    }
    SOFT_PREFIXES = (
        'winter_title:', 'invpage_', 'emoji_info_',
        'emoji_equip_', 'emoji_unequip_',
    )

    def __init__(self):
        super().__init__()
        self.update_types = ['message', 'callback_query']

    def pre_process(self, update, data):
        user = getattr(update, 'from_user', None)
        if user is None:
            return None
        # Completed Stars payments must never be discarded.
        if getattr(update, 'successful_payment', None):
            return None
        is_callback = hasattr(update, 'data')
        value = (update.data or '') if is_callback else (getattr(update, 'text', '') or '').strip()
        command = value.split(maxsplit=1)[0].split('@')[0].lower() if value.startswith('/') else ''
        if command in ('/tech', '/reply_off', '/reply_on') or (is_callback and (value.startswith('tech:') or value == 'reply:to_inline')):
            return None  # Проверка прав проводится внутри /tech.
        try:
            ban = openbot.get_global_ban(user.id)
        except (APIError, OSError, ValueError):
            if command in self.HARD_CMDS:
                return None
            response = '⚠️ Openbot API временно недоступен. Действие не выполнено.'
            if is_callback:
                bot.answer_callback_query(update.id, response, show_alert=True)
            else:
                bot.send_message(update.chat.id, response)
            return CancelUpdate()
        kind = ban.get('kind') if ban.get('banned') else None
        try:
            mirrored = conn.execute(
                'SELECT global_ban_kind, status FROM users WHERE user_id=?',
                (user.id,),
            ).fetchone()
            if mirrored and (
                mirrored[0] != kind or (kind and mirrored[1] != 'banned')
            ):
                _sync_global_ban_mirror(user.id, ban)
        except sqlite3.Error:
            logging.getLogger('random_bot.status').exception(
                'Не удалось проверить локальную копию бана')
        if not ban.get('banned'):
            return None
        if is_callback:
            allowed = (kind == 'global_ban' and
                       (value in self.SOFT_CALLBACKS or
                        any(value.startswith(p) for p in self.SOFT_PREFIXES)))
            if not allowed:
                bot.answer_callback_query(
                    update.id, '🚫 Блокировка: действие недоступно. Подробности: /ban_info',
                    show_alert=True,
                )
                return CancelUpdate()
        else:
            allowed = (command in self.HARD_CMDS or
                       (kind == 'global_ban' and
                        (command in self.SOFT_CMDS or value in self.SOFT_TEXT or
                         value.startswith(('⌨ Переключить', '🔔 Уведомления:',
                                           '🔕 Уведомления:', '👁 ID для других:',
                                           '🙈 ID для других:')))))
            if not allowed:
                bot.send_message(update.chat.id, _global_format_ban(ban))
                return CancelUpdate()
        return None

    def post_process(self, update, data, exception):
        pass


bot.setup_middleware(GlobalBanMiddleware())

class PunishmentMiddleware(BaseMiddleware):
    """Stop mutations for soft bans and all actions for hard bans."""
    SAFE_COMMANDS = {'/badge', '/my_titles', '/leaders', '/start', '/help', '/profile', '/id_profile', '/logs', '/ban',
                     '/unban', '/hard_ban', '/unhard_ban', '/ban_id', '/unban_id', '/get_status', '/ban_info', '/appeal', '/calendar', '/menu'}
    SAFE_TEXT = {'👤 Профиль', '🎒 Инвентарь', '⚙️ Настройки', '⚙ Настройки ID',
                 '⬅ Главное меню', '⬅ Инвентарь', '⬅ Главная',
                 '🏆 Лидеры', '📊 Лидеры', '🏆 Мои титулы', '🎄 Праздничное событие', '📅 Календарь ноября'}
    SAFE_CALLBACKS = {'winter_titles', 'winter_leaders', 'leaders_refresh', 'winter_badge', 'back', 'profile', 'open_inventory', 'settings_user',
                      'settings_id', 'toggle_kb', 'toggle_notif', 'toggle_show_id',
                      'ignore_click', 'nov_cal_open', 'nov_cal_refresh', 'nov_cal_back'}
    SAFE_PREFIXES = ('winter_title:', 'invpage_', 'emoji_info_', 'emoji_equip_', 'emoji_unequip_')

    def __init__(self):
        super().__init__()
        self.update_types = ['message', 'callback_query']

    def pre_process(self, update, data):
        person = getattr(update, 'from_user', None)
        if person is None:
            return None
        ban = _punishment_get(person.id)
        if not ban:
            return None
        hard = ban['kind'] == 'hard_ban'
        if hasattr(update, 'data'):
            key = update.data or ''
            allowed = (not hard and
                       (key in self.SAFE_CALLBACKS or
                        any(key.startswith(p) for p in self.SAFE_PREFIXES)))
            if not allowed:
                bot.answer_callback_query(update.id, '🌨️ HARD BAN' if hard else
                                          '🔨 BAN: действие недоступно', show_alert=True)
                return CancelUpdate()
        else:
            # A completed payment must always be fulfilled; don't confiscate purchases.
            if getattr(update, 'successful_payment', None):
                return None
            content = (getattr(update, 'text', '') or '').strip()
            cmd = content.split(maxsplit=1)[0].split('@')[0].lower() if content.startswith('/') else ''
            allowed = (cmd in {'/ban_info', '/appeal', '/support', '/tech', '/reply_off', '/reply_on'} or
                       (not hard and (cmd in self.SAFE_COMMANDS or
                                     content in self.SAFE_TEXT or
                                     content.startswith(('👕 ', '⌨ Переключить',
                                                         '🔔 Уведомления:', '🔕 Уведомления:',
                                                         '👁 ID для других:', '🙈 ID для других:')))))
            if not allowed:
                bot.send_message(update.chat.id, _local_format_ban(ban))
                return CancelUpdate()
        return None

    def post_process(self, update, data, exception):
        pass


bot.setup_middleware(PunishmentMiddleware())


# ================================================================
# 🛠 Частичные техработы. /tech — панель управления.
# Значение 1: функция отключена, 0: доступна.
# ================================================================
_TECH_AREAS = {
    'games': ('🎮 Игры', 'Игры временно закрыты на техработы.'),
    'cases': ('🎁 Кейсы', 'Кейсы временно закрыты на техработы.'),
    'market': ('🏪 Рынок', 'Рынок временно закрыт на техработы.'),
    'shop': ('🛒 Магазин', 'Магазин временно закрыт на техработы.'),
    'calendar': ('📅 Календарь', 'Календарь временно закрыт на техработы.'),
    'rewards': ('🎁 Подарки', 'Получение подарков временно отключено.'),
    'economy': ('🚨 Экономика', 'Экономические операции временно остановлены.'),
}


def _tech_get_states():
    # Отдельное соединение: бот обрабатывает сообщения параллельно.
    keys = {f'tech_{name}': name for name in _TECH_AREAS}
    with sqlite3.connect(DB_NAME, timeout=5) as db:
        rows = db.execute(
            'SELECT key, value FROM system_settings WHERE key LIKE ?', ('tech_%',)
        ).fetchall()
    states = {name: False for name in _TECH_AREAS}
    for key, value in rows:
        if key in keys:
            states[keys[key]] = str(value) == '1'
    return states


def _tech_disabled(area):
    states = _tech_get_states()
    return states.get(area, False) or (
        area in {'games', 'cases', 'market', 'shop', 'calendar', 'rewards'}
        and states['economy']
    )


def _tech_set(area, disabled):
    if area not in _TECH_AREAS:
        raise ValueError('Неизвестный раздел')
    with sqlite3.connect(DB_NAME, timeout=10) as db:
        db.execute(
            'INSERT INTO system_settings(key,value) VALUES(?,?) '
            'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
            (f'tech_{area}', '1' if disabled else '0'),
        )


def _tech_authorized(user, chat):
    if chat.type != 'private' or user is None:
        return False
    try:
        info = openbot.get_user(user.id)
        if not isinstance(info, dict) or not info.get('exists'):
            return False
        if str(info.get('status', '')).lower() not in {'owner', 'developer', 'admin'}:
            return False
        # Заблокированный сотрудник не может управлять техработами.
        try:
            ban = openbot.get_global_ban(user.id)
            if ban.get('banned'):
                return False
        except Exception:
            return False
        return not bool(_punishment_get(user.id))
    except Exception:
        return False


def _tech_panel():
    states=_tech_get_states()
    all_off=is_maintenance()
    kb=types.InlineKeyboardMarkup()
    lines=['🛠 <b>УПРАВЛЕНИЕ RANDOM BOT</b>','',
           f'{"🔴" if all_off else "🟢"} 🤖 Бот: {"техработы" if all_off else "работает"}','']
    kb.add(types.InlineKeyboardButton(f'🤖 Бот: {"🔴 Закрыт" if all_off else "🟢 Работает"}',callback_data='tech:bot'))
    for area,(title,_) in _TECH_AREAS.items():
        disabled=states[area]
        lines.append(f'{"🔴" if disabled else "🟢"} {title}: {"закрыт" if disabled else "работает"}')
        kb.add(types.InlineKeyboardButton(f'{"🔴" if disabled else "🟢"} {title}',callback_data=f'tech:{area}'))
    kb.row(types.InlineKeyboardButton('✅ Открыть всё',callback_data='tech:all:on'),
           types.InlineKeyboardButton('🚫 Закрыть всё',callback_data='tech:all:off'))
    kb.add(types.InlineKeyboardButton('🔄 Обновить',callback_data='tech:refresh'))
    lines+=['','<code>/tech bot on</code> — открыть весь бот',
            '<code>/tech bot off</code> — закрыть весь бот',
            '<code>/tech all on</code> — открыть разделы',
            '<code>/tech all off</code> — закрыть разделы',
            '<code>on</code> = работает · <code>off</code> = закрыто']
    return '\n'.join(lines),kb

@bot.message_handler(commands=['tech'])
def tech_command(message):
    if not _tech_authorized(message.from_user,message.chat):
        return bot.reply_to(message,'⛔ Только администрация в личных сообщениях.')
    parts=(message.text or '').split()
    if len(parts)==1 or len(parts)==2 and parts[1]=='status':
        text,kb=_tech_panel()
        return bot.send_message(message.chat.id,text,reply_markup=kb,parse_mode='HTML')
    if len(parts)!=3 or parts[2] not in ('on','off'):
        return bot.reply_to(message,'Формат: /tech bot|all|games|cases|shop|market|calendar|rewards|economy on|off')
    area,enabled=parts[1],parts[2]=='on'
    if area=='bot':
        set_maintenance(not enabled)
        return bot.reply_to(message,'✅ Бот открыт' if enabled else '🛠 Бот закрыт на техработы')
    if area!='all' and area not in _TECH_AREAS:
        return bot.reply_to(message,'❌ Неизвестный раздел.')
    for item in (_TECH_AREAS if area=='all' else (area,)):
        _tech_set(item,not enabled)
    bot.reply_to(message,'✅ Разделы открыты' if area=='all' and enabled else
                  '🛠 Разделы закрыты' if area=='all' else
                  f'{"✅ Открыто" if enabled else "🛠 Закрыто"}: {_TECH_AREAS[area][0]}')

@bot.callback_query_handler(func=lambda c:bool(c.data) and c.data.startswith('tech:'))
def tech_panel_callback(call):
    if not _tech_authorized(call.from_user,call.message.chat):
        return bot.answer_callback_query(call.id,'⛔ Нет доступа',show_alert=True)
    action=call.data.split(':',1)[1]
    if action=='bot':
        set_maintenance(not is_maintenance())
    elif action=='all:on' or action=='all:off':
        for name in _TECH_AREAS:
            _tech_set(name,action=='all:off')
    elif action in _TECH_AREAS:
        _tech_set(action,not _tech_get_states()[action])
    elif action!='refresh':
        return bot.answer_callback_query(call.id,'Неизвестный раздел',show_alert=True)
    bot.answer_callback_query(call.id,'✅ Настройки обновлены')
    text,kb=_tech_panel()
    try:
        bot.edit_message_text(text,chat_id=call.message.chat.id,message_id=call.message.message_id,
                              reply_markup=kb,parse_mode='HTML')
    except apihelper.ApiTelegramException as exc:
        if 'message is not modified' not in str(exc).lower():raise


def _tech_area_for_update(update):
    """Определяет, к какому разделу относится действие, включая старые кнопки."""
    if getattr(update, 'successful_payment', None) is not None:
        return None  # уже оплаченные Stars всегда нужно выдать
    is_callback = hasattr(update, 'data')
    value = ((update.data or '') if is_callback else
             (getattr(update, 'text', '') or '').strip())
    if is_callback:
        if value.startswith('tech:'):
            return None
        if value in {'game', 'back_to_games'} or value.startswith((
            'game_', 'wg:', 'ng:', 'key_pick_', 'shadow_pick_', 'potion_pick_',
            'pumpkin_pick_', 'ttt_pos_', 'ttt_level_',
        )):
            return 'games'
        if value == 'cases' or value.startswith((
            'casepage_', 'buy_case_', 'open_case_',
        )):
            return 'cases'
        if value == 'market' or value.startswith((
            'market_', 'emoji_market_',
        )):
            return 'market'
        if value in {'shop', 'shop_regular', 'shop_coin_titles', 'snow_shop', 'buy_coins'} or value.startswith(('snow_buy:',
            'buy_title_', 'stars_buy_', 'cancel_stars_',
        )):
            return 'shop'
        if value.startswith(('nov_cal_', 'dec_cal_', 'calendar_')):
            return 'calendar'
        if value.startswith(('holiday_',)):
            return 'rewards'
        return None
    cmd = value.split(maxsplit=1)[0].split('@')[0].lower() if value.startswith('/') else ''
    if cmd == '/tech':
        return None
    if cmd in {'/calendar','/december'} or value in ('📅 Календарь ноября', '📅 Календарь декабря','📅 Календарь декабря'):
        return 'calendar'
    if cmd in {'/daily_gift', '/birthday_gift', '/promo', '/newyear', '/holiday'}:
        return 'rewards'
    if cmd in {'/sell_emoji'} or value == '🏪 Рынок' or value in {
        '📦 Мои лоты', '⬅ Рынок', '◀️ Предыдущая страница рынка',
        'Следующая страница рынка ▶️',
    } or value.startswith(('🏪 Выставить ', '💰 Продать ', '🛒 Купить ', '❌ Снять лот #')):
        return 'market'
    if value in {'🎁 Кейсы', '⬅ Предыдущие кейсы', 'Следующие кейсы ➡'} or value.startswith((
        '🛒 📦', '🛒 🥈', '🛒 🥇', '🛒 💎', '🛒 🔥', '🛒 🌌',
        '🛒 👑', '🛒 🕳️', '🔓 Открыть ',
    )):
        return 'cases'
    if value in {'🎁 Зимняя лавка', '⬅ Магазин', '⬅ Зимняя лавка', '🛒 Обычный магазин', '❄️ Купить за снежинки', '⭐ Магазин Stars',
                 '🏆 Титулы', '💰 10 000 000 монет — 100 ⭐',
                 '❄️ 25 снежинок — 50 ⭐', '⭐ Прокачать до 20 уровня — 150 ⭐'} or (
                 value.startswith('🏆 ') and value.endswith(' 🪙')):
        return 'shop'
    if value in {'❄️ Зимние игры', '🔑 Тайна ледяного сундука', '🏔 Снежная экспедиция',
                 '🔎 Снежный детектив', '🧸 Мастерская игрушек', '🎁 Подарки с риском',
                 '❌⭕ Крестики-нолики', '🧠 Снежная память', '🔐 Ледяной сейф', '🧩 Зимние загадки', '❌⭕ 🟢 Лёгкий', '❌⭕ 🟡 Средний', '❌⭕ 🔴 Сложный'} or value.startswith((
        '❄️ Сугроб ', '🚪 Комната ', '🧪 Шар ', '🎁 Подарок ',
    )) or value in {'1','2','3','4','5','6','7','8','9'}:
        return 'games'
    if cmd in {'/give_coins', '/take_coins', '/level_up', '/gift'}:
        return 'rewards'
    # Игровые ответы и цены на рынке приходят как обычные текстовые сообщения.
    # Читаем состояние только когда соответствующий раздел отключён.
    states = _tech_get_states()
    if (states['market'] or states['economy']) and update.from_user.id in pending_market:
        if not value.startswith('/'):
            return 'market'
    if states['games'] or states['economy']:
        if not value.startswith('/') and value and value not in {
            '👤 Профиль', '🎒 Инвентарь', '⚙️ Настройки', '⬅ Главное меню',
            '⬅ В главное меню', '📅 Календарь ноября', '📅 Календарь декабря',
        }:
            try:
                if get_active_game(update.from_user.id):
                    return 'games'
            except sqlite3.Error:
                pass
    return None


class PartialTechMiddleware(BaseMiddleware):
    """Срабатывает на сообщениях и старых Inline-кнопках до обработчиков."""
    def __init__(self):
        super().__init__()
        self.update_types = ['message', 'callback_query']

    def pre_process(self, update, data):
        if getattr(update, 'successful_payment', None) is not None:
            return None
        area = _tech_area_for_update(update)
        if area is None or not _tech_disabled(area):
            return None
        # Не раскрываем внутренние детали техработ игроку.
        msg = f'🛠 {_TECH_AREAS[area][1]} Остальные разделы доступны.'
        if hasattr(update, 'data'):
            bot.answer_callback_query(update.id, msg[:180], show_alert=True)
        else:
            bot.send_message(update.chat.id, msg)
        return CancelUpdate()

    def post_process(self, update, data, exception):
        pass


bot.setup_middleware(PartialTechMiddleware())

# ================================================================
# 🚀 WINTER LAUNCH — запуск 01.12.2026, 00:00, МСК.
# Используется SQLite: после перезапуска ничего не теряется.
# ================================================================
from zoneinfo import ZoneInfo
_LAUNCH_TZ = ZoneInfo('Europe/Moscow')
_LAUNCH_DATE = datetime(2026,12,1,0,0,tzinfo=_LAUNCH_TZ)

def _launch_enabled():
    row=conn.execute("SELECT value FROM system_settings WHERE key='winter_launch' ").fetchone()
    return row is None or row[0]=='1'  # До релиза экран ожидания включён по умолчанию.

def _launch_pending():
    return _launch_enabled() and datetime.now(_LAUNCH_TZ)<_LAUNCH_DATE

def _launch_claimed(uid):
    row=conn.execute('SELECT 1 FROM winter_launch_gifts WHERE user_id=?',(uid,)).fetchone()
    return bool(row)

def _launch_staff(uid):
    if uid==DEVELOPER_CHAT_ID:
        return True
    try:
        info=openbot.get_user(uid)
        return isinstance(info,dict) and info.get('exists') and str(info.get('status','')).lower() in ('owner','developer','tester','admin')
    except Exception:
        return False

def _launch_admin(uid):
    if uid==DEVELOPER_CHAT_ID:
        return True
    try:
        info=openbot.get_user(uid)
        return isinstance(info,dict) and info.get('exists') and str(info.get('status','')).lower() in ('owner','developer','admin')
    except Exception:
        return False

def _launch_text():
    diff=max(0,int((_LAUNCH_DATE-datetime.now(_LAUNCH_TZ)).total_seconds()))
    if diff>0:
        days, hours=divmod(diff,86400);hours,seconds=divmod(hours,3600);minutes,_=divmod(seconds,60)
        return ('🎄 <b>RANDOM BOT — WINTER RELEASE 2026</b>\n\n'
                '❄️ Зимний сезон скоро начнётся!\n'
                f'⏳ До открытия: <b>{days} д. {hours:02d} ч. {minutes:02d} мин.</b>\n\n'
                '🎁 За ожидание тебя ждёт подарок.\n'
                '📅 Запуск: 1 декабря 2026, 00:00 (МСК).')
    return ('🚀 <b>ЗИМНЕЕ ОБНОВЛЕНИЕ ОТКРЫТО!</b>\n\n'
            'Спасибо, что дождался зимнего сезона! 🎄\n'
            'Нажми «🎮 Играть», чтобы получить подарок и открыть меню.')

def _launch_keyboard():
    kb=types.InlineKeyboardMarkup()
    if _launch_pending():
        kb.add(types.InlineKeyboardButton('⏳ Обновить таймер',callback_data='launch:check'))
    else:
        kb.add(types.InlineKeyboardButton('🎮 Играть',callback_data='launch:play'))
    return kb

def _launch_show(chat_id, edit_id=None):
    text=_launch_text();keyboard=_launch_keyboard()
    if edit_id is not None:
        try:
            return bot.edit_message_text(text,chat_id=chat_id,message_id=edit_id,
                                         reply_markup=keyboard,parse_mode='HTML')
        except apihelper.ApiTelegramException as exc:
            if 'message is not modified' in str(exc).lower():
                return None
            raise
    return bot.send_message(chat_id,text,reply_markup=keyboard,parse_mode='HTML')

def _launch_gift(uid,first_name,username):
    # Транзакция через ATTACH: награда и метка выдачи атомарны.
    create_user(uid,username,first_name)
    with sqlite3.connect(DB_NAME,timeout=15) as db:
        db.execute('ATTACH DATABASE ? AS event',(str(Path(__file__).resolve().parent / WINTER_DB_NAME),))
        db.execute('CREATE TABLE IF NOT EXISTS event.winter_players (user_id INTEGER PRIMARY KEY, snowflakes INTEGER NOT NULL DEFAULT 0)')
        db.execute('CREATE TABLE IF NOT EXISTS event.winter_cases (user_id INTEGER NOT NULL, case_key TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id,case_key))')
        db.execute('CREATE TABLE IF NOT EXISTS event.winter_owned_titles (user_id INTEGER NOT NULL, title_key TEXT NOT NULL, price INTEGER DEFAULT 0, PRIMARY KEY(user_id,title_key))')
        db.execute('BEGIN IMMEDIATE')
        cur=db.execute('INSERT OR IGNORE INTO winter_launch_gifts (user_id,claimed_at) VALUES(?,?)',
                       (uid,datetime.now(_LAUNCH_TZ).isoformat()))
        if cur.rowcount==0:return False
        db.execute('UPDATE users SET coins=COALESCE(coins,0)+5000 WHERE user_id=?',(uid,))
        db.execute('INSERT INTO event.winter_players(user_id,snowflakes) VALUES(?,25) ON CONFLICT(user_id) DO UPDATE SET snowflakes=snowflakes+25',(uid,))
        db.execute("INSERT INTO event.winter_cases(user_id,case_key,count) VALUES(?,'gold',1) ON CONFLICT(user_id,case_key) DO UPDATE SET count=count+1",(uid,))
        db.execute("INSERT OR IGNORE INTO event.winter_owned_titles(user_id,title_key,price) VALUES(?,'winter_pioneer',0)",(uid,))
    return True

conn.execute('CREATE TABLE IF NOT EXISTS winter_launch_gifts (user_id INTEGER PRIMARY KEY, claimed_at TEXT NOT NULL)')
conn.commit()

@bot.message_handler(commands=['launch'])
def winter_launch_admin(message):
    if message.chat.type!='private' or not _launch_admin(message.from_user.id):
        return bot.reply_to(message,'⛔ Доступно только администрации в личных сообщениях.')
    parts=(message.text or '').split()
    if len(parts)==1 or (len(parts)==2 and parts[1]=='status'):
        return bot.reply_to(message,('🟢 Запуск включён' if _launch_enabled() else '🔴 Запуск отключён')+'\n'+_launch_text(),parse_mode='HTML')
    if len(parts)!=2 or parts[1] not in ('on','off'):
        return bot.reply_to(message,'Формат: /launch on | /launch off | /launch status')
    conn.execute('INSERT INTO system_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                 ('winter_launch','1' if parts[1]=='on' else '0'))
    conn.commit()
    bot.reply_to(message,'✅ Winter Launch '+('включён' if parts[1]=='on' else 'отключён'))

@bot.callback_query_handler(func=lambda c: bool(c.data) and c.data.startswith('launch:'))
def winter_launch_callback(call):
    uid=call.from_user.id
    if call.data=='launch:check':
        bot.answer_callback_query(call.id,'⏳ Таймер обновлён')
        return _launch_show(call.message.chat.id,call.message.message_id)
    if call.data!='launch:play':
        return bot.answer_callback_query(call.id,'Неизвестная кнопка')
    if _launch_pending():
        bot.answer_callback_query(call.id,'⏳ До открытия ещё есть время!',show_alert=True)
        return _launch_show(call.message.chat.id,call.message.message_id)
    try:
        claimed=_launch_gift(uid,call.from_user.first_name or 'Игрок',call.from_user.username)
    except Exception:
        logging.getLogger('random_bot.launch').exception('Ошибка выдачи подарка запуска')
        return bot.answer_callback_query(call.id,'Не удалось выдать подарок. Попробуй снова.',show_alert=True)
    try:
        openbot.create_id(uid,call.from_user.first_name or 'Игрок')
        openbot.register_bot_activity(uid,'Random_bot')
    except Exception:
        logging.getLogger('random_bot.launch').warning('Openbot ID sync failed for %s',uid)
    bot.answer_callback_query(call.id,('🎁 Подарок получен!' if claimed else '🎮 Приятной игры!'),show_alert=True)
    text=('🎉 <b>Спасибо за ожидание!</b>\n\n🎁 Твой подарок за релиз:\n'
          '💰 5 000 монет\n❄️ 25 снежинок\n🥇 1 золотой кейс\n🏅 Титул «Первопроходец зимы»\n\n') if claimed else '🎮 <b>С возвращением!</b>\n\n'
    text+='👇 Выбирай, во что сыграть!'
    bot.edit_message_text(text,chat_id=call.message.chat.id,message_id=call.message.message_id,
                          reply_markup=main_mune(),parse_mode='HTML')

class WinterLaunchMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__();self.update_types=['message','callback_query']
    def pre_process(self,update,data):
        user=getattr(update,'from_user',None)
        if not user or getattr(update,'successful_payment',None) is not None:
            return None
        if _launch_staff(user.id):
            return None
        is_callback=hasattr(update,'data')
        value=(update.data or '') if is_callback else (getattr(update,'text','') or '').strip()
        cmd=value.split(maxsplit=1)[0].split('@')[0].lower() if value.startswith('/') else ''
        if is_callback and (value.startswith('launch:') or value == 'reply:to_inline'):
            return None
        if cmd in ('/ban_info','/appeal','/support'):
            return None
        if _launch_pending():
            if is_callback:
                try:
                    bot.answer_callback_query(update.id,'🎄 Скоро открытие! Введи /start.',show_alert=True)
                except Exception:pass
            else:
                _launch_show(update.chat.id)
            return CancelUpdate()
        # После запуска новый игрок видит экран с кнопкой «Играть», пока не получит подарок.
        if _launch_enabled() and cmd=='/start' and not _launch_claimed(user.id):
            _launch_show(update.chat.id)
            return CancelUpdate()
        return None
    def post_process(self,update,data,exception):pass

bot.setup_middleware(WinterLaunchMiddleware())




@bot.message_handler(commands=['sendall'])
def send_all(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 2):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 2 ур.")
        return
    
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(uid):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    
    text = message.text.replace("/sendall", "").strip()
    if not text:
        bot.reply_to(message, "❌ Введи текст для рассылки.\nПример: `/sendall Привет!`", parse_mode="Markdown")
        return
        
    cursor = conn.cursor()
    # Берем только тех, у кого включены уведомления (notifications = 1)
    cursor.execute("SELECT user_id FROM users WHERE notifications = 1")
    users = cursor.fetchall()
    
    bot.send_message(message.chat.id, f"🚀 Рассылка запущена...\nВсего получателей: {len(users)}")
    success = blocked = errors = 0
    
    for user in users:
        target_id = user[0]
        try:
            bot.send_message(target_id, text, parse_mode="HTML")
            success += 1
        except apihelper.ApiTelegramException as e:
            if "bot was blocked by the user" in e.description:
                blocked += 1
                # Отсугробаем уведомления в БД, чтобы больше не пытаться ему писать
                cursor.execute("UPDATE users SET notifications = 0 WHERE user_id = ?", (target_id,))
                conn.commit()
            else:
                errors += 1
        except Exception:
            errors += 1
            
    bot.send_message(message.chat.id, f"✅ Готово!\n👤 Успешно: {success}\n🚫 Заблокировали: {blocked}\n⚠️ Ошибки: {errors}")

@bot.message_handler(commands=['sell_emoji'])
def sell_item(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ Формат: `/sell_emoji [эмодзи] [цена]`", parse_mode="Markdown")
        return
    
    emoji = parts[1]
    try:
        price = int(parts[2])
    except:
        bot.reply_to(message, "❌ Цена должна быть числом!")
        return
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM inventory WHERE user_id = ? AND item_value = ?", (uid, emoji))
    if not cursor.fetchone():
        bot.reply_to(message, "❌ У тебя нет такого эмодзи в инвентаре!")
        return
    cursor.execute("DELETE FROM inventory WHERE user_id = ? AND item_value = ?", (uid, emoji))
    cursor.execute("INSERT INTO auction (seller_id, item_type, item_value, price) VALUES (?, 'emoji', ?, ?)", (uid, emoji, price))
    conn.commit()
    bot.reply_to(message, f"✅ Твой лот {emoji} выставлен на аукцион за {price} 💰")

def looks_like_emoji(text):
    """True, если text — ровно ОДИН настоящий эмодзи (цифры, буквы и обычный текст не проходят)."""
    import unicodedata
    text = (text or "").strip()
    if not text or len(text) > 20:
        return False
    count = 0
    prev_zwj = False
    regional = 0
    for ch in text:
        cp = ord(ch)
        if ch == "\u200d":                      # ZWJ — склейка (👨‍👩‍👧)
            prev_zwj = True
            continue
        if ch == "\ufe0f" or 0x1F3FB <= cp <= 0x1F3FF:   # вариант отображения / оттенок кожи
            continue
        if 0x1F1E6 <= cp <= 0x1F1FF:             # флаги: две региональные буквы = один эмодзи
            regional += 1
            if regional % 2 == 1:
                count += 1
            prev_zwj = False
            continue
        if unicodedata.category(ch) in ("So", "Sk") and cp > 0x7F:
            if not prev_zwj:
                count += 1
            prev_zwj = False
            continue
        return False                            # буква, цифра, пробел, знак — не эмодзи
    return count == 1


def resolve_emoji(item):
    """Эмодзи для выдачи: из каталога игры, а если его там нет — любой настоящий эмодзи (🎁).
    Цифры и текст («11», «hello») не проходят — вернётся None."""
    item = (item or "").strip()
    if item in EMOJI_DATA:
        return item
    plain = item.replace("\ufe0f", "")
    for key in EMOJI_DATA:
        if key.replace("\ufe0f", "") == plain:
            return key
    return item if looks_like_emoji(item) else None

@bot.message_handler(commands=['gift'])
def gift_item(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
    
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(uid):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
        
    parts = message.text.split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, "⚠️ Неверный формат! Пиши так:\n`/gift @юзернейм эмодзи`", parse_mode="Markdown")
        return
        
    target_uname = parts[1].replace("@", "").lower()
    item = resolve_emoji(parts[2])
    if item is None:
        bot.reply_to(message, f"❌ «{parts[2]}» — это не эмодзи.\nПиши так: /gift @юзернейм 🎁")
        return
    
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_uname,))
    res = cursor.fetchone()
    
    if res:
        cursor.execute("INSERT INTO inventory (user_id, item_type, item_value) VALUES (?, 'emoji', ?)", (res[0], item))
        conn.commit()
        bot.send_message(message.chat.id, f"🎁 Предмет {item} успешно подарен @{target_uname}!")
        try:
            bot.send_message(res[0], f"🎁 Админ подарил тебе новый предмет: {item}\nПроверь его в инвентаре!")
        except Exception:
            pass
    else:
        bot.send_message(message.chat.id, f"❌ Пользователь @{target_uname} не найден в базе данных бота!")

@bot.message_handler(commands=['give_coins'])
def give_coins_cmd(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
    
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(uid):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ Формат: /give_coins @username 100")
        return
    username = parts[1].replace("@", "").lower()
    try:
        amount = int(parts[2])
    except:
        bot.reply_to(message, "❌ Сумма должна быть числом!")
        return
    if amount <= 0:
        bot.reply_to(message, "❌ Сумма должна быть больше 0!")
        return
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name FROM users WHERE username = ?", (username,))
    res = cursor.fetchone()
    if not res:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден.")
        return
    add_coins(res[0], amount)
    bot.reply_to(message, f"✅ Пользователю @{username} выдано {amount} 💰")
    try:
        bot.send_message(res[0], f"🎁 Вам выдали {amount} 💰 монет!")
    except:
        pass

@bot.message_handler(commands=['take_coins'])
def take_coins_cmd(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
    
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(uid):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ Формат: /take_coins @username 100")
        return
    username = parts[1].replace("@", "").lower()
    try:
        amount = int(parts[2])
    except:
        bot.reply_to(message, "❌ Сумма должна быть числом!")
        return
    if amount <= 0:
        bot.reply_to(message, "❌ Сумма должна быть больше 0!")
        return
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, coins FROM users WHERE username = ?", (username,))
    res = cursor.fetchone()
    if not res:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден.")
        return
    if res[1] < amount:
        bot.reply_to(message, f"❌ У @{username} только {res[1]} 💰, нельзя снять {amount}!")
        return
    add_coins(res[0], -amount)
    bot.reply_to(message, f"✅ У @{username} снято {amount} 💰")
    try:
        bot.send_message(res[0], f"⚠️ У вас сняли {amount} 💰 монет.")
    except:
        pass

@bot.message_handler(commands=['id_ban', 'id_unban', 'id_freeze', 'id_unfreeze'])
def deprecated_global_id_punishment(message):
    bot.reply_to(message, '⚠️ Старые команды изменения глобального Openbot ID выключены. '
                          'Используй /ban, /hard_ban, /unban, /unhard_ban.')

@bot.message_handler(commands=['level_up'])
def cmd_level_up(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
    
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(uid):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "⚠️ Использование команды:\n`/level_up @username уровень`\n\nПример: `/level_up @username 100`", parse_mode="Markdown")
        return

    target_username = args[1].replace("@", "").strip().lower()
    try:
        new_lvl = int(args[2])
    except ValueError:
        bot.reply_to(message, "❌ Уровень должен быть целым числом!")
        return

    cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name FROM users WHERE username = ?", (target_username,))
    target_row = cursor.fetchone()

    if not target_row:
        bot.reply_to(message, f"❌ Пользователь @{target_username} не найден в базе данных бота.")
        return

    target_id, target_name = target_row
    cursor.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_lvl, target_id))
    conn.commit()

    bot.send_message(
        message.chat.id, 
        f"⭐ *Уровень изменен!*\n\nАдминистратор изменил уровень игроку *{target_name}* (@{target_username}) на *{new_lvl}* 🆙", 
        parse_mode="Markdown"
    )
    try:
        bot.send_message(target_id, f"🆙 Администратор установил твой уровень равным: *{new_lvl}*!", parse_mode="Markdown")
    except:
        pass

@bot.message_handler(commands=['feedback'])
def feedback_command(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(
            message, 
            "⚠️ *Неверный формат!*\nПиши команду и текст отзыва в одном сообщении.\n\n"
            "📝 _Пример:_ `/feedback Нашел баг в игре, бот не засчитал попытку!`", 
            parse_mode="Markdown"
        )
        return

    feedback_text = parts[1].strip()
    username = f"@{message.from_user.username}" if message.from_user.username else "Нет юзернейма"
    first_name = message.from_user.first_name

    admin_report = (
        f"📩 *НОВЫЙ ОТЗЫВ ИГРОКА*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Отправитель:* {first_name} ({username})\n"
        f"🆔 *ID пользователя:* `{uid}`\n"
        f"🕒 *Время:* {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💬 *Текст отзыва:*\n{feedback_text}"
    )

    try:
        bot.send_message(DEVELOPER_CHAT_ID, admin_report, parse_mode="Markdown")
        bot.reply_to(
            message, 
            "✨ *Спасибо за ваш отзыв!*\n"
            "📨 Он успешно доставлен разработчикам проекта. "
            "Мы обязательно его рассмотрим, чтобы сделать Openbot.Ai ещё лучше! 🌐💠",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Ошибка при отправке фидбека админу: {e}")
        bot.reply_to(message, "❌ Произошла ошибка при отправке отзыва. Попробуйте позже.")

@bot.message_handler(commands=['bio'])
def set_bio_command(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❌ Используй так: `/bio твой текст о себе`", parse_mode='Markdown')
        return
    
    new_bio = parts[1].strip()
    if len(new_bio) > 200:
        bot.reply_to(message, "❌ Слишком длинное био, максимум 200 символов")
        return
    
    openbot.update_bio(uid, new_bio)
    bot.reply_to(message, f"✅ Био обновлено:\n`{new_bio}`", parse_mode='Markdown')

@bot.message_handler(commands=['id_profile'])
def id_profile(message):
    uid, cid = message.from_user.id, message.chat.id
    global_data = openbot.get_id(uid)
    reason = check_ban(uid)

    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return

    if global_data:
        g_name = global_data[2]
        g_tag = global_data[5] or "Не установлен"
        g_bio = global_data[8] or "Не установлена"
        g_data = global_data[7]
        
        bots_list = openbot.get_active_bots(uid)
        g_active_bot = ", ".join(bots_list) if bots_list else "Ни в каких"
        g_status = ROLE.get(global_data[6], "👤 Игрок")
            
        text = f"""**🌐 Общий профиль Openbot AI ID**

**🏷 Имя:** `{g_name}`
**🆔 Тег:** `{g_tag}`
**🎭 Статус:** `{g_status}`
**🤖 Боты:** `{g_active_bot}`
**🗄 Создан:** `{g_data}`
**📝 О себе:** `{g_bio}`"""
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton('⬅️ Назад в профиль', callback_data='profile')
        )
        bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")
    else:
        text = "❌ У вас еще не создан Openbot AI ID. Напишите /start."
        bot.send_message(cid, text)

def profile_inline_markup(user_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    if _winter_icon(random_role(user_id)):
        text = "👑 Скрыть значок роли" if _winter_enabled(user_id) else "👑 Показать значок роли"
        kb.add(types.InlineKeyboardButton(text, callback_data="winter_badge"))
    kb.add(types.InlineKeyboardButton("⚙ Настройки ID", callback_data="settings_id"))
    kb.add(types.InlineKeyboardButton("⬅ В главное меню", callback_data="back"))
    return kb


def get_profile_text(user_id):
    user = get_user(user_id)
    global_data = openbot.get_id(user_id)

    if global_data:
        g_name = global_data[2]
        equipped = get_equipped_emoji(user_id) if user else ""
        g_tag = global_data[5] or "Не установлен"

        full_name = profile_display_name(user_id, g_name)
    else:
        full_name = profile_display_name(user_id, user[2] if user else "Игрок")
        g_tag = "Отсутствует"

    display_status = STATUS.get(
        user[3] if user else "👤 Игрок"
    )

    title = PROFILE_TITLES.get(
        user[4] if user else "none",
        "Без титула"
    )

    if not user:
        return "❌ Профиль не найден."

    profile_text = f"""<b>ПРОФИЛЬ</b>
━━━━━━━━━━━━━━━━━━
👤 <b>Имя в сети:</b> {full_name}
🆔 <b>Ваш Тег:</b> <code>{g_tag}</code>
🎭 <b>Статус:</b> {display_status}
🎖 <b>Игровой титул:</b> {title}

📊 <b>ИГРОВАЯ СТАТИСТИКА:</b>
⭐ <b>Уровень:</b> {user[6]}
✨ <b>Опыт:</b> {user[7]}
💰 <b>Монеты:</b> {user[5]} 💰
❄️ <b>Снежинки:</b> {get_candies(user_id)} ❄️
━━━━━━━━━━━━━━━━━━
"""

    return profile_text

@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = uid = message.from_user.id
    user = get_user(user_id)
    
    reason = check_ban(uid)

    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return


    if not user:
        bot.send_message(
            message.chat.id,
            "❌ Профиль не найден."
        )
        return

    profile_text = get_profile_text(user_id)

    bot.send_message(
        message.chat.id,
        profile_text,
        parse_mode="HTML",
        reply_markup=profile_inline_markup(user_id),
    )

@bot.message_handler(commands=['refund'])
def handle_refund(message):
    # 1. Проверяем, что команду отправил именно админ
    # 2. Разбиваем сообщение, чтобы достать ID транзакции
    # Ожидаемый формат в чате: /refund 123456789ABCDEF...
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        bot.reply_to(message, "❌ Ошибка! Введите команду в формате:\n`/refund ИД_ТРАНЗАКЦИИ`", parse_mode="Markdown")
        return
        
    charge_id = args[1].strip()
    
    try:
        # 3. Вызываем официальный метод Telegram для возврата звезд.
        # user_id передаем того, КТО вызвал команду (для теста — вы сами).
        # Метод автоматически найдет плательщика по charge_id.
        bot.refund_star_payment(
            user_id=message.from_user.id, 
            telegram_payment_charge_id=charge_id
        )
        bot.reply_to(message, f"✅ Успешно! 25 Stars по транзакции `{charge_id}` возвращены обратно на ваш личный баланс.", parse_mode="Markdown")
        
    except Exception as e:
        # Ошибка будет, если вы опечатались в ID или с момента теста прошло больше 21 дня
        bot.reply_to(message, f"❌ Не удалось сделать возврат.\nПроверьте ID транзакции или холд (21 день).\n\nОшибка API: `{e}`", parse_mode="Markdown")

# Рандом-мир удалён из бота. Исторические таблицы SQLite не удаляем.
def _fmt(n):
    return f"{int(n):,}".replace(",", " ")

# ================================================================
# 🎮 WINTER GAMES — три самостоятельные игры, состояние в SQLite.
# ================================================================
_WG_QUIZ = (
    ('Что появляется на окнах в мороз?', ('Узоры', 'Цветы', 'Песок'), 0),
    ('Какой месяц завершает год?', ('Ноябрь', 'Декабрь', 'Январь'), 1),
    ('Сколько лучей обычно рисуют у снежинки?', ('Четыре', 'Шесть', 'Десять'), 1),
    ('Что делают из снега?', ('Снеговика', 'Парусник', 'Костёр'), 0),
    ('Что тает в тепле?', ('Камень', 'Лёд', 'Стекло'), 1),
    ('Что используют для катания с горки?', ('Санки', 'Лыжи для воды', 'Лодку'), 0),
    ('Какое дерево часто украшают зимой?', ('Пальму', 'Ёлку', 'Берёзу'), 1),
)
_WG_NAMES = {'memory':'🧠 Снежная память','safe':'🔐 Ледяной сейф','quiz':'🧩 Зимние загадки'}

# Новые игры открываем постепенно: память — к релизу,
# сейф и загадки — отдельными обновлениями по команде /features.
_WG_DEFAULTS = {'memory':True,'safe':False,'quiz':False}

def _wg_enabled(mode):
    if mode not in _WG_DEFAULTS:return False
    row=conn.execute('SELECT value FROM system_settings WHERE key=?',(f'feature_{mode}',)).fetchone()
    return _WG_DEFAULTS[mode] if row is None else str(row[0])=='1'

def _wg_feature_set(mode,enabled):
    if mode not in _WG_DEFAULTS:raise ValueError('Неизвестный раздел')
    with sqlite3.connect(DB_NAME,timeout=10) as db:
        db.execute('INSERT INTO system_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                   (f'feature_{mode}','1' if enabled else '0'))

@bot.message_handler(commands=['features'])
def winter_features_admin(message):
    if message.chat.type!='private' or not _launch_admin(message.from_user.id):
        return bot.reply_to(message,'⛔ Только для разработчиков.')
    parts=(message.text or '').split()
    if len(parts)==1 or len(parts)==2 and parts[1]=='status':
        return bot.reply_to(message,'🎮 Поэтапные обновления:\n'+ '\n'.join(
            f'{"🟢" if _wg_enabled(k) else "🔒"} {v} — {"открыто" if _wg_enabled(k) else "скоро"}'
            for k,v in _WG_NAMES.items())+'\n\nФормат: /features safe on | /features quiz off')
    if len(parts)!=3 or parts[1] not in _WG_DEFAULTS or parts[2] not in ('on','off'):
        return bot.reply_to(message,'Формат: /features memory|safe|quiz on|off')
    _wg_feature_set(parts[1],parts[2]=='on')
    bot.reply_to(message,f'✅ {_WG_NAMES[parts[1]]}: '+('открыто' if parts[2]=='on' else 'скрыто'))

@bot.message_handler(commands=['testgame'])
def winter_testgame_admin(message):
    if message.chat.type!='private' or not _launch_staff(message.from_user.id):
        return bot.reply_to(message,'⛔ Только для разработчиков.')
    args=(message.text or '').split()
    if len(args)!=2 or args[1] not in _WG_NAMES:
        return bot.reply_to(message,'Формат: /testgame memory|safe|quiz')
    mode=args[1]
    state=_wg_start(message.from_user.id,message.chat.id,mode)
    bot.send_message(message.chat.id,_wg_view(mode,state),parse_mode='HTML',reply_markup=_wg_keyboard(mode,state))

def _wg_state(uid):
    row = conn.execute('SELECT game_type,state_json FROM active_games WHERE user_id=?', (uid,)).fetchone()
    if not row or not str(row[0]).startswith('wg_'):
        return None, None
    try:
        return str(row[0])[3:], json.loads(row[1] or '{}')
    except (ValueError, TypeError):
        return None, None

def _wg_save(uid, mode, state):
    conn.execute('UPDATE active_games SET state_json=? WHERE user_id=? AND game_type=?',
                 (json.dumps(state, ensure_ascii=False), uid, 'wg_' + mode))
    conn.commit()

def _wg_start(uid, chat_id, mode):
    if mode not in _WG_NAMES:
        raise ValueError('Неизвестная игра')
    set_active_game(uid, chat_id, 'wg_' + mode)
    if mode == 'memory':
        cards = ['🎄','🎄','🎅','🎅','⭐','⭐']
        random.shuffle(cards)
        state = {'cards':cards,'matched':[],'first':None,'miss':[],'turns':0}
    elif mode == 'safe':
        state = {'secret':random.randint(1,16), 'used':[], 'tries':0, 'hint':'Открой сейф за 5 попыток!'}
    else:
        indices = random.sample(range(len(_WG_QUIZ)),3)
        state = {'questions':indices,'step':0,'correct':0,'lives':2}
    _wg_save(uid, mode, state)
    return state

def _wg_keyboard(mode,state):
    kb = types.InlineKeyboardMarkup(row_width=3)
    if mode == 'memory':
        cards = state['cards']
        visible = set(state['matched']) | set(state['miss'])
        if state['first'] is not None:
            visible.add(state['first'])
        for start in (0,3):
            row=[]
            for i in range(start,start+3):
                char = cards[i] if i in visible else '❔'
                row.append(types.InlineKeyboardButton(char, callback_data=f'wg:memory:pick:{i}'))
            kb.row(*row)
    elif mode == 'safe':
        used = set(state['used'])
        for start in range(1,17,4):
            kb.row(*(types.InlineKeyboardButton('•' if n in used else str(n),
                      callback_data=f'wg:safe:pick:{n}') for n in range(start,start+4)))
    else:
        q = _WG_QUIZ[state['questions'][state['step']]]
        for i,option in enumerate(q[1]):
            kb.add(types.InlineKeyboardButton(option,callback_data=f'wg:quiz:pick:{state["step"]}:{i}'))
    kb.add(types.InlineKeyboardButton('⬅️ К играм',callback_data='game'))
    return kb

def _wg_view(mode,state,detail=''):
    if mode == 'memory':
        return (f'🧠 <b>СНЕЖНАЯ ПАМЯТЬ</b>\nНайди 3 пары за 8 попыток.\n'
                f'Проверок: {state["turns"]}/8 · Пар: {len(state["matched"])//2}/3\n'
                + (f'\n{detail}' if detail else ''))
    if mode == 'safe':
        return (f'🔐 <b>ЛЕДЯНОЙ СЕЙФ</b>\nСекретное число от 1 до 16.\n'
                f'Попыток: {state["tries"]}/5\n\n{state["hint"]}')
    q = _WG_QUIZ[state['questions'][state['step']]]
    return (f'🧩 <b>ЗИМНИЕ ЗАГАДКИ</b>\n'
            f'Вопрос {state["step"]+1}/3 · ❤️ {state["lives"]} · ✅ {state["correct"]}\n\n'
            f'<b>{html.escape(q[0])}</b>')

def _wg_reward(uid, mode):
    amount = {'memory':(180,25,2),'safe':(160,20,2),'quiz':(200,30,3)}[mode]
    add_coins(uid,amount[0]); add_xp(uid,amount[1])
    # Отдельная база подарков уже используется остальными играми.
    add_candies(uid,amount[2],source='game')
    return f'🎉 <b>Победа!</b>\n💰 +{amount[0]} монет · ⭐ +{amount[1]} XP · ❄️ +{amount[2]}'

def _wg_finish(call, mode, won, state, detail=''):
    uid=call.from_user.id
    delete_active_game(uid)
    text = (_wg_reward(uid,mode) if won else '❌ <b>Игра закончена.</b> Попробуй снова!')
    if detail:
        text += '\n' + html.escape(str(detail))
    kb=types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton('🔄 Повторить',callback_data=f'wg:{mode}:start'),
           types.InlineKeyboardButton('⬅ Игры',callback_data='game'))
    bot.edit_message_text(text,chat_id=call.message.chat.id,message_id=call.message.message_id,
                          reply_markup=kb,parse_mode='HTML')
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: bool(c.data) and c.data.startswith('wg:'))
def winter_games_callback(call):
    uid=call.from_user.id
    data=(call.data or '').split(':')
    if len(data)<3 or data[1] not in _WG_NAMES:
        return bot.answer_callback_query(call.id,'Неизвестная игра',show_alert=True)
    mode,action=data[1],data[2]
    if action == 'locked':
        return bot.answer_callback_query(call.id,'🔒 Игра появится в следующем обновлении!',show_alert=True)
    if not _wg_enabled(mode) and not _launch_staff(uid):
        return bot.answer_callback_query(call.id,'🔒 Игра пока не открыта.',show_alert=True)
    if action == 'start':
        state=_wg_start(uid,call.message.chat.id,mode)
        bot.edit_message_text(_wg_view(mode,state),chat_id=call.message.chat.id,
                              message_id=call.message.message_id,reply_markup=_wg_keyboard(mode,state),parse_mode='HTML')
        return bot.answer_callback_query(call.id)
    active,state=_wg_state(uid)
    if active!=mode or not state or action!='pick':
        return bot.answer_callback_query(call.id,'Игра закончена. Начни новую.',show_alert=True)
    try:
        i=int(data[3])
    except (IndexError,ValueError):
        return bot.answer_callback_query(call.id,'Неверный ход',show_alert=True)
    detail=''
    if mode=='memory':
        if not 0<=i<6:
            return bot.answer_callback_query(call.id,'Неверная клетка')
        # После ошибки закрываем две раскрытые карточки при следующем выборе.
        state['miss']=[]
        if i in state['matched'] or i==state['first']:
            return bot.answer_callback_query(call.id,'Выбери другую карточку')
        if state['first'] is None:
            state['first']=i
        else:
            first=state['first'];state['first']=None
            state['turns']+=1
            if state['cards'][first]==state['cards'][i]:
                state['matched'].extend([first,i]);detail='✅ Пара найдена!'
            else:
                state['miss']=[first,i];detail='Не совпало. Следующий ход скроет карточки.'
        if len(state['matched'])==6:
            return _wg_finish(call,mode,True,state)
        if state['turns']>=8:
            return _wg_finish(call,mode,False,state,'Попытки закончились.')
    elif mode=='safe':
        if not 1<=i<=16 or i in state['used']:
            return bot.answer_callback_query(call.id,'Число уже выбрано')
        state['tries']+=1;state['used'].append(i)
        if i==state['secret']:
            return _wg_finish(call,mode,True,state,f'Код: {i}')
        if state['tries']>=5:
            return _wg_finish(call,mode,False,state,f'Код был: {state["secret"]}')
        state['hint']='⬆️ Больше!' if i<state['secret'] else '⬇️ Меньше!'
    else:
        try:
            step=int(data[3]);choice=int(data[4])
        except (ValueError,IndexError):
            return bot.answer_callback_query(call.id,'Неверный ответ')
        if step!=state['step'] or choice not in (0,1,2):
            return bot.answer_callback_query(call.id,'Это старый вопрос')
        q=_WG_QUIZ[state['questions'][step]]
        if choice==q[2]:state['correct']+=1
        else:state['lives']-=1
        state['step']+=1
        if state['lives']<=0 or state['step']>=3:
            return _wg_finish(call,mode,state['correct']>=2 and state['lives']>0,state,
                              f'Правильных ответов: {state["correct"]}/3')
    _wg_save(uid,mode,state)
    bot.edit_message_text(_wg_view(mode,state,detail),chat_id=call.message.chat.id,
                          message_id=call.message.message_id,reply_markup=_wg_keyboard(mode,state),parse_mode='HTML')
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: (m.text or '').startswith('🔒 ') and (m.text or '').endswith(' — скоро'))
def winter_locked_reply(message):
    bot.reply_to(message,'🔒 Игра откроется в следующем обновлении.')

# Reply-пользователи открывают те же Inline-игры внутри сообщения.
@bot.message_handler(func=lambda m: (m.text or '') == '🎲 Рандом-мир')
def _old_random_world_button(message):
    bot.send_message(message.chat.id, 'ℹ️ Рандом-мир удалён из бота. Открой актуальные игры в главном меню.',
                     reply_markup=main_mune())


@bot.message_handler(func=lambda m: (m.text or '') in _WG_NAMES.values())
def winter_games_reply(message):
    mode=next(k for k,v in _WG_NAMES.items() if v==message.text)
    if not _wg_enabled(mode) and not _launch_staff(message.from_user.id):
        return bot.reply_to(message,'🔒 Игра появится в следующем обновлении!')
    state=_wg_start(message.from_user.id,message.chat.id,mode)
    bot.send_message(message.chat.id,_wg_view(mode,state),reply_markup=_wg_keyboard(mode,state),parse_mode='HTML')



# ==============================================================
# 🎮 Пять НОВЫХ механик. Все состояния в active_games.state_json.
# Все сессии защищены от старых inline-кнопок через nonce.
# ==============================================================
_NG_LOCK = threading.RLock()
_NG_NAMES = {
    'lock': '🔑 Тайна ледяного сундука',
    'keys': '🏔 Снежная экспедиция',
    'shadow': '🔎 Снежный детектив',
    'potion': '🧸 Мастерская игрушек',
    'pumpkin': '🎁 Подарки с риском',
}
_NG_REWARDS = {
    'lock': (170, 45, 2), 'keys': (220, 55, 3),
    'shadow': (190, 45, 2), 'potion': (180, 50, 2),
}
_NG_PUZZLES = [
    ('Сколько углов у треугольника?', ['2', '3', '4'], 1),
    ('Что тяжелее: 1 кг снега или 1 кг льда?', ['Снег', 'Лёд', 'Одинаково'], 2),
    ('Сколько сторон у квадрата?', ['3', '4', '5'], 1),
    ('Продолжи ряд: 2, 4, 6, ...', ['7', '8', '10'], 1),
    ('Сколько минут в получасе?', ['20', '30', '45'], 1),
    ('Что не тает при комнатной температуре?', ['Снег', 'Дерево', 'Лёд'], 1),
]
_NG_ORDERS = [
    ('Снеговик', '⛄', ['Снег', 'Бумага', 'Стекло'], 0),
    ('Елочный шар', '🔴', ['Песок', 'Стекло', 'Ткань'], 1),
    ('Тёплая варежка', '🧤', ['Пряжа', 'Лёд', 'Картон'], 0),
    ('Деревянная звезда', '⭐', ['Вата', 'Дерево', 'Снег'], 1),
    ('Бумажная гирлянда', '🎊', ['Металл', 'Бумага', 'Камень'], 1),
]
_NG_SUSPECTS = ['Лис', 'Заяц', 'Пингвин']
_NG_CLUES = {
    0: ['На снегу остались следы с когтями.', 'Очевидец видел рыжий хвост.', 'У лавки нашли рыжую шерсть.'],
    1: ['Следы длинных задних лап.', 'Очевидец заметил длинные уши.', 'В снегу остался след от морковки.'],
    2: ['На снегу нет следов лап с когтями.', 'Очевидец видел чёрно-белую фигуру.', 'У лавки нашли перо.'],
}

def _ng_state(uid):
    row = conn.execute('SELECT game_type, state_json FROM active_games WHERE user_id=?', (uid,)).fetchone()
    if not row or not str(row[0]).startswith('ng_'):
        return None, None
    try:
        return str(row[0])[3:], json.loads(row[1] or '{}')
    except (ValueError, TypeError):
        return None, None

def _ng_save(uid, mode, state):
    conn.execute('UPDATE active_games SET state_json=? WHERE user_id=? AND game_type=?',
                 (json.dumps(state, ensure_ascii=False), uid, 'ng_' + mode))
    conn.commit()

def _ng_start(uid, cid, mode):
    if mode not in _NG_NAMES:
        raise ValueError('Неизвестная игра')
    set_active_game(uid, cid, 'ng_' + mode)
    token = '%06x' % random.getrandbits(24)
    if mode == 'lock':
        state = {'token':token, 'step':0, 'hearts':2, 'puzzles':random.sample(range(len(_NG_PUZZLES)),3), 'hint':''}
    elif mode == 'keys':
        state = {'token':token, 'step':0, 'energy':6, 'supplies':2, 'log':'Выбери маршрут. Нужно пройти 4 участка.'}
    elif mode == 'shadow':
        state = {'token':token, 'suspect':random.randrange(3), 'visited':[], 'log':'Изучи хотя бы две улики.'}
    elif mode == 'potion':
        state = {'token':token, 'step':0, 'errors':0, 'orders':random.sample(range(len(_NG_ORDERS)),3), 'log':'Выполни три заказа!'}
    else:
        state = {'token':token, 'round':0, 'coins':0, 'snow':0, 'boxes':random.sample(['coins','snow','trap'],3), 'log':'Выбирай коробку или вовремя забирай выигрыш.'}
    _ng_save(uid,mode,state)
    return state

def _ng_button(mode, state, label, action):
    return types.InlineKeyboardButton(label, callback_data=f'ng:{mode}:{state["token"]}:{action}')

def _ng_render(uid):
    mode,st = _ng_state(uid)
    if mode is None:
        return 'Игра не найдена.', types.InlineKeyboardMarkup()
    kb=types.InlineKeyboardMarkup(row_width=3)
    title=_NG_NAMES[mode]
    if mode=='lock':
        q = _NG_PUZZLES[st['puzzles'][st['step']]]
        text=f'<b>{title}</b>\nЭтап: {st["step"]+1}/3 · ❤️ {st["hearts"]}\n\n{html.escape(q[0])}'
        for i,v in enumerate(q[1]):
            kb.add(_ng_button(mode,st,v,f'pick:{i}'))
    elif mode=='keys':
        text=(f'<b>{title}</b>\nУчасток: {st["step"]+1}/4\n'
              f'⚡ Силы: {st["energy"]} · 🎒 Припасы: {st["supplies"]}\n\n{html.escape(st["log"])}')
        kb.add(_ng_button(mode,st,'🌲 Лес (-1 сила)','pick:0'))
        kb.add(_ng_button(mode,st,'🧗 Перевал (-2 силы)','pick:1'))
        kb.add(_ng_button(mode,st,'🍪 Отдых (-1 припас, +2 силы)','pick:2'))
    elif mode=='shadow':
        clues='\n'.join('• '+_NG_CLUES[st['suspect']][i] for i in st['visited'])
        text=f'<b>{title}</b>\nНайдено улик: {len(st["visited"])}/3\n\n{clues or "Исследуй места в зимнем городе."}\n\n{html.escape(st["log"])}'
        for i,place in enumerate(('🏪 Лавка','🏠 Домик','🌲 Парк')):
            if i not in st['visited']:
                kb.add(_ng_button(mode,st,place,f'clue:{i}'))
        if len(st['visited'])>=2:
            kb.add(*[_ng_button(mode,st,'🔎 '+n,f'guess:{i}') for i,n in enumerate(_NG_SUSPECTS)])
    elif mode=='potion':
        order=_NG_ORDERS[st['orders'][st['step']]]
        text=(f'<b>{title}</b>\nЗаказ: {st["step"]+1}/3 · Ошибок: {st["errors"]}/2\n\n'
              f'Сделай: {order[1]} {order[0]}\nВыбери подходящий материал.\n\n{html.escape(st["log"])}')
        for i,v in enumerate(order[2]):
            kb.add(_ng_button(mode,st,v,f'pick:{i}'))
    else:
        text=(f'<b>{title}</b>\nРаунд: {st["round"]+1}/3\n'
              f'💰 Накоплено: {st["coins"]} · ❄️ {st["snow"]}\n\n{html.escape(st["log"])}')
        kb.row(*[_ng_button(mode,st,f'🎁 {i+1}',f'pick:{i}') for i in range(3)])
        if st['round']>0:
            kb.add(_ng_button(mode,st,'🏦 Забрать выигрыш','cash'))
    kb.add(types.InlineKeyboardButton('⬅ К играм',callback_data='game'))
    return text,kb

def _ng_show(uid,cid,mid=None):
    text,kb=_ng_render(uid)
    if mid is None:
        return bot.send_message(cid,text,reply_markup=kb,parse_mode='HTML')
    return bot.edit_message_text(text,chat_id=cid,message_id=mid,reply_markup=kb,parse_mode='HTML')

def _ng_finish(uid,mode,won,extra=''):
    delete_active_game(uid)
    if won and mode == 'pumpkin':
        coins,snow=extra
        if coins:add_coins(uid,coins)
        if snow:add_candies(uid,snow,source='game')
        text=f'🎉 <b>Выигрыш сохранён!</b>\n💰 +{coins} монет\n❄️ +{snow} снежинок'
    elif won:
        coins,xp,snow=_NG_REWARDS[mode]
        add_coins(uid,coins);add_xp(uid,xp);add_candies(uid,snow,source='game')
        text=f'🎉 <b>Победа!</b>\n💰 +{coins} монет · ⭐ +{xp} XP · ❄️ +{snow} снежинки'
    else:
        text=f'❄️ <b>Игра завершена.</b>\n{html.escape(str(extra)) or "Попробуй ещё раз!"}'
    kb=types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton('🔄 Повторить',callback_data='game_'+mode),
           types.InlineKeyboardButton('⬅ К играм',callback_data='game'))
    return text,kb

def _ng_step(uid, mode, st, action):
    """Returns (finished, won, extra) and writes state only for unfinished moves."""
    parts=action.split(':')
    kind=parts[0]
    if mode=='lock':
        if kind!='pick' or len(parts)!=2 or parts[1] not in ('0','1','2'):
            raise ValueError('Неверный выбор')
        q=_NG_PUZZLES[st['puzzles'][st['step']]]
        if int(parts[1])==q[2]:
            st['step']+=1
            if st['step']>=3:return True,True,''
        else:
            st['hearts']-=1
            if st['hearts']<=0:return True,False,'Закончились попытки.'
    elif mode=='keys':
        if kind!='pick' or len(parts)!=2 or parts[1] not in ('0','1','2'):
            raise ValueError('Неверный маршрут')
        n=int(parts[1])
        if n==2:
            if st['supplies']<=0:raise ValueError('Припасы закончились')
            st['supplies']-=1
            st['energy']=min(7,st['energy']+2)
            st['log']='Отдохнул и набрался сил.'
        else:
            st['energy']-=1 if n==0 else 2
            st['step']+=1
            st['log']='Преодолел участок!' if n==0 else 'Прошёл сложный перевал!'
            if st['energy']<=0:return True,False,'Силы закончились раньше финиша.'
            if st['step']>=4:return True,True,''
    elif mode=='shadow':
        if kind=='clue':
            if len(parts)!=2 or parts[1] not in ('0','1','2') or int(parts[1]) in st['visited']:
                raise ValueError('Улика уже изучена')
            st['visited'].append(int(parts[1]));st['log']='Улика записана!'
        elif kind=='guess':
            if len(st['visited'])<2 or len(parts)!=2 or parts[1] not in ('0','1','2'):
                raise ValueError('Сначала собери две улики')
            good=int(parts[1])==st['suspect']
            return True,good,'' if good else 'Правильный ответ: '+_NG_SUSPECTS[st['suspect']]
        else:raise ValueError('Неверное действие')
    elif mode=='potion':
        if kind!='pick' or len(parts)!=2 or parts[1] not in ('0','1','2'):
            raise ValueError('Неверный материал')
        order=_NG_ORDERS[st['orders'][st['step']]]
        if int(parts[1])==order[3]:
            st['step']+=1;st['log']='✅ Заказ выполнен!'
            if st['step']>=3:return True,True,''
        else:
            st['errors']+=1;st['log']='❌ Неподходящий материал. Попробуй снова.'
            if st['errors']>=2:return True,False,'Слишком много ошибок в заказах.'
    else:
        if kind=='cash':
            if st['round']<1:raise ValueError('Сначала открой коробку')
            return True,True,(st['coins'],st['snow'])
        if kind!='pick' or len(parts)!=2 or parts[1] not in ('0','1','2'):
            raise ValueError('Выбери коробку')
        item=st['boxes'][int(parts[1])]
        if item=='trap':return True,False,'Попалась пустая коробка — накопленный приз потерян.'
        if item=='coins':st['coins']+=random.randint(100,250)
        if item=='snow':st['snow']+=2
        st['round']+=1
        st['log']='Удача! Можно забрать накопленное или рискнуть.'
        if st['round']>=3:return True,True,(st['coins'],st['snow'])
        st['boxes']=random.sample(['coins','snow','trap'],3)
    st['token'] = '%06x' % random.getrandbits(24)
    _ng_save(uid,mode,st)
    return False,False,''

@bot.callback_query_handler(func=lambda c:bool(c.data) and c.data.startswith('ng:'))
def new_games_callback(call):
    # Сериализация ходов защищает от двойного начисления при быстрых нажатиях.
    with _NG_LOCK:
        return _ng_callback_impl(call)

def _ng_callback_impl(call):
    data=(call.data or '').split(':',3)
    if len(data)!=4:return bot.answer_callback_query(call.id,'Некорректная кнопка')
    _,mode,token,action=data
    uid=call.from_user.id
    active,st=_ng_state(uid)
    if active!=mode or not st or token!=st.get('token'):
        return bot.answer_callback_query(call.id,'Эта партия уже неактивна.',show_alert=True)
    try:
        finished,won,extra=_ng_step(uid,mode,st,action)
    except ValueError as exc:
        return bot.answer_callback_query(call.id,str(exc)[:190],show_alert=True)
    if finished:
        text,kb=_ng_finish(uid,mode,won,extra)
        bot.edit_message_text(text,chat_id=call.message.chat.id,message_id=call.message.message_id,
                              reply_markup=kb,parse_mode='HTML')
    else:
        _ng_show(uid,call.message.chat.id,call.message.message_id)
    bot.answer_callback_query(call.id)

# =========== Обновленный Обработчик кнопок =============
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    uid = call.from_user.id
    cid = call.message.chat.id
    mid = call.message.message_id
    reason = check_ban(uid)
    
    if reason:
        bot.answer_callback_query(call.id, "🚫 Заблокировано. Подробности: /ban_info", show_alert=True)
        return

    
    if call.data == 'back':
        bot.edit_message_text(
            f'👋 Привет, {call.from_user.first_name}\nДобро пожаловать!',
            chat_id=user_id,
            message_id=call.message.message_id,
            reply_markup=main_mune()
        )
        bot.answer_callback_query(call.id)
    elif call.data == 'buy_coins':
        bot.edit_message_text(
            "⭐ <b>МАГАЗИН ЗА STARS</b>\n\n"
            "Выбери покупку. Оплата проходит через Telegram Stars (⭐).\n\n"
            "💰 10 000 000 монет\n"
            "❄️ 25 снежинок\n"
            "⭐ Прокачка игрового уровня до 20",
            chat_id=cid,
            message_id=mid,
            reply_markup=stars_shop_menu(),
            parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)

    elif call.data == 'stars_buy_coins_10m':
        send_stars_invoice(call, "coins_10m")
        bot.answer_callback_query(call.id)

    elif call.data == 'stars_buy_snowflakes_25':
        send_stars_invoice(call, "snowflakes_25")
        bot.answer_callback_query(call.id)

    elif call.data == 'stars_buy_level_20':
        send_stars_invoice(call, "level_20")
        bot.answer_callback_query(call.id)

    elif call.data.startswith("cancel_stars_"):
        invoice_message_id = int(call.data.replace("cancel_stars_", ""))

        try:
            bot.delete_message(
                call.message.chat.id,
                invoice_message_id
            )
        except Exception:
            pass

        try:
            bot.delete_message(
                call.message.chat.id,
                call.message.message_id
            )
        except Exception:
            pass

        bot.answer_callback_query(
            call.id,
            "❌ Оплата отменена"
        )
    elif call.data == "shop":
        _ui_edit(call, shop_hub_text(user_id), shop_mune())
        bot.answer_callback_query(call.id)

    elif call.data == 'shop_regular':
        _ui_edit(call, '🛒 <b>ОБЫЧНЫЙ МАГАЗИН</b>\nВыбери раздел:', regular_shop_menu())
        bot.answer_callback_query(call.id)

    elif call.data == 'shop_coin_titles':
        _ui_edit(call, winter_titles_text(user_id), winter_titles_menu())
        bot.answer_callback_query(call.id)

    elif call.data == 'snow_shop':
        _ui_edit(call, snow_shop_text(user_id), snow_shop_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data.startswith('snow_buy:'):
        key = call.data.partition(':')[2]
        if key not in SNOW_TITLES:
            return bot.answer_callback_query(call.id, 'Товар не найден', show_alert=True)
        if _tech_disabled('shop') or _tech_disabled('rewards'):
            return bot.answer_callback_query(call.id, 'Магазин временно закрыт', show_alert=True)
        title, price = SNOW_TITLES[key]
        try:
            status = winter_db.buy_snow_title(user_id, key, price)
        except Exception:
            logging.getLogger('random_bot.shop').exception('Не удалось купить зимний титул')
            return bot.answer_callback_query(call.id, 'Ошибка покупки. Попробуй позже.', show_alert=True)
        msg = ('✅ Титул уже куплен' if status == 'owned' else
               '❄️ Недостаточно снежинок' if status == 'poor' else
               '🎉 Титул куплен! Открой «Мои титулы».')
        bot.answer_callback_query(call.id, msg, show_alert=True)
        _ui_edit(call, snow_shop_text(user_id), snow_shop_keyboard(user_id))

    elif call.data == 'winter_titles':
        _ui_edit(call, titles_text(user_id), titles_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif call.data.startswith('buy_title_'):
        key = call.data[len('buy_title_'):]
        ok, msg = buy_winter_title(user_id, key)
        bot.answer_callback_query(call.id, msg, show_alert=True)
        if ok:
            bot.edit_message_text(winter_titles_text(user_id, msg), chat_id=cid, message_id=mid, reply_markup=winter_titles_menu(), parse_mode="HTML")
        
    elif call.data == 'profile':
        user = get_user(user_id)
        global_data = openbot.get_id(user_id)
        equipped = get_equipped_emoji(user_id)

        if global_data:
            g_name = global_data[2]
            g_tag = global_data[5] or "Не установлен"
            base_name = g_name
        else:
            base_name = user[2] if user else "Игрок"
            g_tag = "Отсутствует"

        full_name = profile_display_name(user_id, base_name)

        status_key = user[3] if user else "user"
        display_status = STATUS.get(status_key, "👤 Игрок")
        title = PROFILE_TITLES.get(user[4] if user else "none", "Без титула")
        
        if user:
            profile_text = f"""<b>ПРОФИЛЬ</b>
━━━━━━━━━━━━━━━━━━
👤 <b>Имя в сети:</b> {full_name}
🆔 <b>Ваш Тег:</b> <code>{g_tag}</code>
🎭 <b>Статус:</b> {display_status}
🎖 <b>Игровой титул:</b> {title}

📊 <b>ИГРОВАЯ СТАТИСТИКА:</b>
⭐ <b>Уровень:</b> {user[6]}
✨ <b>Опыт:</b> {user[7]}
💰 <b>Монеты:</b> {user[5]} 💰
❄️ <b>Снежинки:</b> {get_candies(user_id)} ❄️
━━━━━━━━━━━━━━━━━━━
"""
            markup = profile_inline_markup(user_id)
            bot.edit_message_text(
                profile_text, 
                chat_id=user_id, 
                message_id=call.message.message_id, 
                reply_markup=markup, 
                parse_mode="HTML"
            )

        bot.answer_callback_query(call.id)

    # --- 🏪 РЫНОК ---
    elif call.data == 'market':
        show_market(cid, mid, user_id, page=1)
        bot.answer_callback_query(call.id)

    elif call.data.startswith('market_page_'):
        try:
            page = int(call.data.split('_')[-1])
        except ValueError:
            page = 1
        show_market(cid, mid, user_id, page=page)
        bot.answer_callback_query(call.id)

    elif call.data == 'market_my':
        show_my_market_lots(cid, mid, user_id)
        bot.answer_callback_query(call.id)

    elif call.data.startswith('market_buy_'):
        try:
            lot_id = int(call.data[len('market_buy_'):])
        except ValueError:
            bot.answer_callback_query(call.id, "❌ Ошибка лота!", show_alert=True)
            return

        cursor = conn.cursor()
        cursor.execute("""
            SELECT seller_id, item_type, item_value, price
            FROM auction
            WHERE lot_id = ?
            LIMIT 1
        """, (lot_id,))
        lot = cursor.fetchone()

        if not lot:
            bot.answer_callback_query(call.id, "❌ Лот уже продан или снят!", show_alert=True)
            show_market(cid, mid, user_id, page=1)
            return

        seller_id, item_type, emoji, price = lot

        if seller_id == user_id:
            bot.answer_callback_query(call.id, "❌ Нельзя купить собственный лот!", show_alert=True)
            return

        if item_type != 'emoji':
            bot.answer_callback_query(call.id, "❌ Этот тип товара пока не поддерживается!", show_alert=True)
            return

        cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
        buyer_row = cursor.fetchone()
        buyer_coins = buyer_row[0] if buyer_row else 0

        if buyer_coins < price:
            bot.answer_callback_query(
                call.id,
                f"❌ Недостаточно монет! Нужно {price} 🪙",
                show_alert=True
            )
            return

        # Повторно удаляем именно этот лот: если два человека нажали одновременно,
        # только первый успешный UPDATE получит товар.
        cursor.execute("""
            DELETE FROM auction
            WHERE lot_id = ?
              AND seller_id = ?
              AND price = ?
        """, (lot_id, seller_id, price))

        if cursor.rowcount != 1:
            conn.rollback()
            bot.answer_callback_query(call.id, "❌ Лот уже купили!", show_alert=True)
            show_market(cid, mid, user_id, page=1)
            return

        cursor.execute("""
            UPDATE users
            SET coins = coins - ?
            WHERE user_id = ?
              AND coins >= ?
        """, (price, user_id, price))

        if cursor.rowcount != 1:
            conn.rollback()
            bot.answer_callback_query(call.id, "❌ Недостаточно монет!", show_alert=True)
            show_market(cid, mid, user_id, page=1)
            return

        cursor.execute("""
            UPDATE users
            SET coins = coins + ?
            WHERE user_id = ?
        """, (price, seller_id))

        cursor.execute("""
            INSERT INTO inventory (user_id, item_type, item_value, is_active)
            VALUES (?, 'emoji', ?, 0)
        """, (user_id, emoji))

        conn.commit()

        bot.answer_callback_query(
            call.id,
            f"🎉 Куплено {emoji} за {price} 🪙!",
            show_alert=True
        )
        notify_market_sale(seller_id, user_id, emoji, price)
        show_market(cid, mid, user_id, page=1)

    elif call.data.startswith('market_cancel_'):
        try:
            lot_id = int(call.data[len('market_cancel_'):])
        except ValueError:
            bot.answer_callback_query(call.id, "❌ Ошибка лота!", show_alert=True)
            return

        cursor = conn.cursor()
        cursor.execute("""
            SELECT item_value, price
            FROM auction
            WHERE lot_id = ?
              AND seller_id = ?
              AND item_type = 'emoji'
            LIMIT 1
        """, (lot_id, user_id))
        lot = cursor.fetchone()

        if not lot:
            bot.answer_callback_query(call.id, "❌ Лот не найден!", show_alert=True)
            show_my_market_lots(cid, mid, user_id)
            return

        emoji, price = lot

        cursor.execute("""
            DELETE FROM auction
            WHERE lot_id = ?
              AND seller_id = ?
        """, (lot_id, user_id))

        if cursor.rowcount != 1:
            conn.rollback()
            bot.answer_callback_query(call.id, "❌ Лот уже снят!", show_alert=True)
            show_my_market_lots(cid, mid, user_id)
            return

        cursor.execute("""
            INSERT INTO inventory (user_id, item_type, item_value, is_active)
            VALUES (?, 'emoji', ?, 0)
        """, (user_id, emoji))

        conn.commit()

        bot.answer_callback_query(
            call.id,
            f"↩️ {emoji} возвращён в инвентарь!",
            show_alert=True
        )
        show_my_market_lots(cid, mid, user_id)

    # --- ИНВЕНТАРЬ И ПАГИНАЦИЯ ---
    elif call.data == 'open_inventory':
        show_inventory_ui(call.message.chat.id, call.message.message_id, user_id, page=1)
        bot.answer_callback_query(call.id)

    elif call.data.startswith('invpage_'):
        page = int(call.data.split('_')[1])
        show_inventory_ui(call.message.chat.id, call.message.message_id, user_id, page=page)
        bot.answer_callback_query(call.id)

    elif call.data == 'ignore_click':
        bot.answer_callback_query(call.id)

    elif call.data.startswith('emoji_info_'):
        emoji=call.data[len('emoji_info_'):]; show_emoji_card(cid,mid,user_id,emoji); bot.answer_callback_query(call.id)

    elif call.data.startswith('emoji_equip_'):
        emoji=call.data[len('emoji_equip_'):]; cursor=conn.cursor()
        cursor.execute("SELECT 1 FROM inventory WHERE user_id=? AND item_type='emoji' AND item_value=? LIMIT 1",(user_id,emoji))
        if not cursor.fetchone(): bot.answer_callback_query(call.id,"❌ Эмоджи не найдено!",show_alert=True); return
        cursor.execute("UPDATE users SET equipped_item=? WHERE user_id=?",(emoji,user_id)); conn.commit()
        bot.answer_callback_query(call.id,f"👕 {emoji} теперь надето!"); show_emoji_card(cid,mid,user_id,emoji)

    elif call.data.startswith('emoji_unequip_'):
        emoji=call.data[len('emoji_unequip_'):]; cursor=conn.cursor(); cursor.execute("UPDATE users SET equipped_item='' WHERE user_id=? AND equipped_item=?",(user_id,emoji)); conn.commit()
        bot.answer_callback_query(call.id,"👕 Эмоджи снято!"); show_emoji_card(cid,mid,user_id,emoji)

    elif call.data.startswith('emoji_sell_'):
        emoji=call.data[len('emoji_sell_'):]; price=get_emoji_price(emoji); cursor=conn.cursor()
        cursor.execute("SELECT id FROM inventory WHERE user_id=? AND item_type='emoji' AND item_value=? LIMIT 1",(user_id,emoji)); row=cursor.fetchone()
        if not row: bot.answer_callback_query(call.id,"❌ Эмоджи не найдено!",show_alert=True); return
        cursor.execute("DELETE FROM inventory WHERE id=?",(row[0],)); cursor.execute("SELECT COUNT(*) FROM inventory WHERE user_id=? AND item_type='emoji' AND item_value=?",(user_id,emoji)); remaining=cursor.fetchone()[0]
        if remaining==0: cursor.execute("UPDATE users SET equipped_item='' WHERE user_id=? AND equipped_item=?",(user_id,emoji))
        cursor.execute("UPDATE users SET coins=coins+? WHERE user_id=?",(price,user_id)); conn.commit()
        bot.answer_callback_query(call.id,f"💰 Продано за {price} 🪙!",show_alert=True); show_inventory_ui(cid,mid,user_id,1)

    elif call.data.startswith('emoji_market_'):
        emoji=call.data[len('emoji_market_'):]; cursor=conn.cursor(); cursor.execute("SELECT 1 FROM inventory WHERE user_id=? AND item_type='emoji' AND item_value=? LIMIT 1",(user_id,emoji))
        if not cursor.fetchone(): bot.answer_callback_query(call.id,"❌ Эмоджи не найдено!",show_alert=True); return
        pending_market[user_id]=emoji; bot.answer_callback_query(call.id)
        bot.send_message(cid,f"🏪 <b>Выставление {emoji} на рынок</b>\n\nВведи цену в монетах. Например: <code>1500</code>",parse_mode="HTML")

    elif call.data == 'cases':
        bot.edit_message_text(
            cases_text(user_id, 0),
            chat_id=cid,
            message_id=mid,
            reply_markup=build_cases_keyboard(user_id, 0),
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id)

    elif call.data.startswith('casepage_'):
        page = int(call.data[len('casepage_'):])
        bot.edit_message_text(
            cases_text(user_id, page),
            chat_id=cid,
            message_id=mid,
            reply_markup=build_cases_keyboard(user_id, page),
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id)

    elif call.data.startswith('buy_case_'):
        parts = call.data[len('buy_case_'):].rsplit('_', 1)
        case_key = parts[0]
        page = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 0
        ok, msg = buy_case(user_id, case_key)
        bot.answer_callback_query(call.id, msg, show_alert=True)
        if ok:
            bot.edit_message_text(
                cases_text(user_id, page),
                chat_id=cid,
                message_id=mid,
                reply_markup=build_cases_keyboard(user_id, page),
                parse_mode="HTML",
            )

    elif call.data.startswith('open_case_'):
        parts = call.data[len('open_case_'):].rsplit('_', 1)
        case_key = parts[0]
        page = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 0
        result, msg = open_case(user_id, case_key)
        if result is None:
            bot.answer_callback_query(call.id, msg, show_alert=True)
            return

        c_info = CASES[case_key]
        count_left = get_case_count(user_id, case_key)
        bot.edit_message_text(
            f"🎁 <b>КЕЙС ОТКРЫТ!</b>\n\n"
            f"{c_info['name']}\n\n"
            f"✨ <b>ТЕБЕ ВЫПАЛО:</b>\n{msg}\n\n"
            f"📦 Осталось таких кейсов: <b>{count_left}</b>\n\n"
            f"{balance_line(user_id)}",
            chat_id=cid,
            message_id=mid,
            reply_markup=build_cases_keyboard(user_id, page),
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id, "🎁 Кейс открыт!", show_alert=True)

    elif call.data == 'settings_user':
        bot.edit_message_text(
            "⚙ **Настройки профиля:**\n\n"
            + ("⌨ Сейчас включены: **Reply-кнопки**" if get_user_settings(user_id)[0] == 'reply' else "⌨ Сейчас включены: **Inline-кнопки**")
            + "\n\nВыберите нужный параметр:",
            chat_id=user_id,
            message_id=call.message.message_id,
            reply_markup=settings_menu(user_id),
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)

    elif call.data == 'toggle_kb':
        if _reply_off_enabled() and _reply_regular_user(user_id):
            # Игрок уже на Inline и нажал переключение в настройках.
            # Не предлагаем повторно переключаться на Inline: только возврат в меню.
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='back'))
            bot.answer_callback_query(call.id)
            try:
                return bot.edit_message_text(
                    _REPLY_EMERGENCY_MESSAGE,
                    chat_id=cid,
                    message_id=mid,
                    reply_markup=keyboard,
                    parse_mode='HTML',
                )
            except apihelper.ApiTelegramException as exc:
                if 'message is not modified' in str(exc).lower():
                    return
                raise
        if not KB_TYPE:
            toggle_user_setting(user_id, 'kb_type')
            kb_type, _, _ = get_user_settings(user_id)
    
            if kb_type == 'reply':
                # 1. Если переключили на Reply:
                # Убираем Inline-клавиатуру у текущего сообщения и информируем
                bot.edit_message_text(
                    chat_id=user_id,
                    message_id=call.message.message_id,
                    text="⌨ Вы переключились на **обычные кнопки** снизу!",
                    parse_mode="Markdown"
                )
            # Отправляем Reply-клавиатуру новым сообщением
                bot.send_message(
                 user_id,
                "Настройки обновлены:",
                reply_markup=settings_menu_reply(user_id))
            else:
                # 2. Если переключили обратно на Inline:
                # Сначала убираем снизу Reply-клавиатуру
                    bot.send_message(
                        user_id,
                    "⌨ Переключено на **Inline-кнопки**!",
                    reply_markup=types.ReplyKeyboardRemove(),
                    parse_mode="Markdown"
                )
                
                # Обновляем Inline-кнопки под исходным сообщением
                    bot.edit_message_reply_markup(
                        chat_id=user_id,
                        message_id=call.message.message_id,
                        reply_markup=settings_menu(user_id))
       
            bot.answer_callback_query(call.id, "Вид кнопок изменен!")
        else:
            bot.answer_callback_query(call.id, '🔴 Переключение Reply-клавиатуры запрещено разработчиками!', show_alert=True)

    elif call.data == 'toggle_notif':
        toggle_user_setting(user_id, 'notifications')
        _, notifications, _ = get_user_settings(user_id)
        
        msg_text = "Уведомления включены 🔔" if notifications == 1 else "Уведомления выключены 🔕"
        bot.edit_message_reply_markup(chat_id=user_id, message_id=call.message.message_id, reply_markup=settings_menu(user_id))
        bot.answer_callback_query(call.id, msg_text)

    elif call.data == 'toggle_show_id':
        toggle_user_setting(user_id, 'show_id')
        _, _, show_id = get_user_settings(user_id)
        
        msg_text = "Ваш ID теперь виден другим 👁" if show_id == 1 else "Ваш ID скрыт от остальных 🙈"
        bot.answer_callback_query(call.id, "Примечание !\nОт тогдо что вы измените этот парамент ничего не изменится пока это парамент не доделан !", show_alert=True)
        bot.edit_message_reply_markup(chat_id=user_id, message_id=call.message.message_id, reply_markup=settings_menu(user_id))
        bot.answer_callback_query(call.id, msg_text)
        
    elif call.data == "settings_id":
        global_data = openbot.get_id(uid)
        
        if global_data:
            g_name = global_data[2]
            g_tag = global_data[5] or "Не установлен"
            g_bio = global_data[8] or "Не установлена"
            g_data = global_data[7]
            g_active_bot = openbot.get_active_bots(uid)

            num_status = openbot.get_user_level(user_id)
            raw_status = openbot.get_status(user_id)
            g_status = ROLE.get(raw_status, f"{raw_status}")

            if raw_status in ["developer", "owner", "admin", "tester"]:
                full_status_display = f"{g_status} [{num_status}]"
            else:
                full_status_display = g_status
            
            text = f"""**🌐 Общий профиль Openbot AI ID**

Вы можете изменить свои глобальные данные. Они обновятся во всех ботах нашей сети!

**🏷 Текущее имя:** `{g_name}`
**🆔 Ваш Тег:** `{g_tag}`
**🎭 Глобальный статус:** `{full_status_display}`
**🤖 Боты:** `{g_active_bot}`
**🗄 Создан аккаунт:** `{g_data}`
**📝 О себе:** `{g_bio}`
"""
        else:
            text = "❌ У вас еще не создан Openbot AI ID. Напишите /start для автоматической регистрации."

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton('⬅️ Назад в профиль', callback_data='profile')
        )
        
        bot.edit_message_text(text, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    
    # ===== Новый игры и обнова =====
    if call.data == 'game' or call.data == 'back_to_games':
        delete_active_game(user_id)
        bot.edit_message_text("🔮 <b>Выберите зимнюю игру:</b>", chat_id=cid, message_id=mid, reply_markup=game_mune(), parse_mode="HTML")
        bot.answer_callback_query(call.id)

    # Пять новых игр: старые callback-имена открывают новые механики.
    elif call.data in ('game_lock', 'game_keys', 'game_shadow', 'game_potion', 'game_pumpkin'):
        mode = call.data[5:]
        _ng_start(user_id, cid, mode)
        bot.answer_callback_query(call.id)
        _ng_show(user_id, cid, mid)

    # Кнопки старых игр больше не начисляют призы.
    elif call.data.startswith(('key_pick_', 'shadow_pick_', 'potion_pick_', 'pumpkin_pick_')):
        bot.answer_callback_query(call.id, 'Это старая кнопка. Открой игру заново.', show_alert=True)

    # Крестики-нолики — выбор сложности и ИИ
    elif call.data == 'game_ttt':
        delete_active_game(user_id)
        bot.edit_message_text(
            '❌⭕ <b>КРЕСТИКИ-НОЛИКИ</b>\n\nВыбери сложность ИИ:',
            chat_id=cid, message_id=mid, reply_markup=ttt_level_markup(), parse_mode='HTML')
        bot.answer_callback_query(call.id)

    elif call.data.startswith('ttt_level_'):
        level = call.data[len('ttt_level_'):]
        if level not in _TTT_LEVELS:
            return bot.answer_callback_query(call.id, 'Неизвестная сложность', show_alert=True)
        ttt_start(user_id, cid, level)
        bot.edit_message_text(
            f'❌⭕ <b>КРЕСТИКИ-НОЛИКИ</b>\nИИ: {_TTT_LEVELS[level]}\n\nТвой ход: ❌',
            chat_id=cid, message_id=mid, reply_markup=build_ttt_keyboard('0' * 9), parse_mode='HTML')
        bot.answer_callback_query(call.id)

    elif call.data == 'ttt_done':
        return bot.answer_callback_query(call.id, 'Партия закончена. Нажми «Играть снова».')

    elif call.data.startswith('ttt_pos_'):
        try:
            pos = int(call.data.rsplit('_', 1)[1])
        except (IndexError, ValueError):
            return bot.answer_callback_query(call.id, 'Некорректный ход', show_alert=True)
        result, board, notice = ttt_play(user_id, pos)
        if result == 'invalid':
            return bot.answer_callback_query(call.id, notice[:190], show_alert=True)
        markup = build_ttt_keyboard(board, finished=(result == 'done'))
        if result == 'done':
            markup.add(types.InlineKeyboardButton('🔄 Играть снова', callback_data='game_ttt'),
                       types.InlineKeyboardButton('⬅ Игры', callback_data='game'))
        bot.edit_message_text(notice, chat_id=cid, message_id=mid,
                              reply_markup=markup, parse_mode='HTML')
        bot.answer_callback_query(call.id)


# ============ ОПЛАТА STARS: подтверждение и выдача товара ============
@bot.pre_checkout_query_handler(func=lambda query: True)
def handle_pre_checkout(query):
    try:
        if _tech_disabled('shop'):
            return bot.answer_pre_checkout_query(
                query.id, ok=False, error_message='🛠 Магазин временно закрыт.'
            )
        parts = (query.invoice_payload or "").split(":")
        ok = len(parts) == 3 and parts[0] == "stars" and parts[1] in STARS_SHOP and parts[2] == str(query.from_user.id)
        if ok:
            # Важная проверка для Telegram Stars: нельзя принимать новый платёж
            # от глобально заблокированного пользователя.
            try:
                ok = not openbot.get_global_ban(query.from_user.id).get('banned', False)
            except APIError:
                ok = False
            if not ok:
                return bot.answer_pre_checkout_query(
                    query.id, ok=False,
                    error_message='Покупки сейчас недоступны.'
                )
            bot.answer_pre_checkout_query(query.id, ok=True)
        else:
            bot.answer_pre_checkout_query(query.id, ok=False, error_message="Товар недоступен, попробуй ещё раз.")
    except Exception as e:
        print(f"[PRE_CHECKOUT ERROR] {e}")

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    payment = message.successful_payment
    user_id = message.from_user.id
    try:
        _, product_key, payer_id = payment.invoice_payload.split(":")
    except ValueError:
        print(f"[PAYMENT] Странный payload: {payment.invoice_payload}")
        return
    if product_key not in STARS_SHOP or payer_id != str(user_id):
        print(f"[PAYMENT] Не удалось сопоставить платёж: {payment.invoice_payload}")
        return

    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS stars_payments ("
        "charge_id TEXT PRIMARY KEY, user_id INTEGER, product TEXT, stars INTEGER)"
    )
    cursor.execute("SELECT 1 FROM stars_payments WHERE charge_id = ?", (payment.telegram_payment_charge_id,))
    if cursor.fetchone():
        return  # этот платёж уже обработан

    paid_candies = 0
    if product_key == "coins_10m":
        cursor.execute("UPDATE users SET coins = COALESCE(coins, 0) + 10000000 WHERE user_id = ?", (user_id,))
        text = "💰 <b>+10 000 000 монет</b> уже на балансе!"
    elif product_key == "snowflakes_25":
        paid_candies = 25  # снежинки выдаются в базе события — сразу после записи платежа
        text = "❄️ <b>+25 снежинок</b> уже у тебя!"
    elif product_key == "level_20":
        cursor.execute("UPDATE users SET level = MAX(COALESCE(level, 1), 20) WHERE user_id = ?", (user_id,))
        text = "⭐ Твой уровень теперь <b>не ниже 20</b>!"
    else:
        return

    cursor.execute(
        "INSERT INTO stars_payments (charge_id, user_id, product, stars) VALUES (?, ?, ?, ?)",
        (payment.telegram_payment_charge_id, user_id, product_key, payment.total_amount)
    )
    conn.commit()
    if paid_candies:
        winter_db.add_keys(user_id, paid_candies, "stars")
    bot.send_message(message.chat.id, f"✅ <b>Оплата прошла!</b>\n\n{text}", parse_mode="HTML")

# ============ СОСТОЯНИЕ REPLY-МЕНЮ ============
# Отдельное состояние Reply-клавиатур для каждого пользователя.
reply_case_page = {}
reply_inventory_page = {}
reply_market_page = {}
reply_selected_emoji = {}

@bot.message_handler(func=lambda message: (
    bool(message.text) and (
        message.text in {
            "❄️ Зимние игры", "👤 Профиль", "🎁 Зимняя лавка", "🎒 Инвентарь",
            "🏪 Рынок", "⚙️ Настройки", "⚙ Настройки",
            "⬅ Главное меню", "⬅ В главное меню",
            "🎁 Кейсы", "🏆 Титулы", "⭐ Магазин Stars", "⬅ Магазин",
            '❄️ Купить за снежинки', '🛒 Обычный магазин', '⬅ Зимняя лавка',
            "💰 10 000 000 монет — 100 ⭐", "❄️ 25 снежинок — 50 ⭐",
            "⭐ Прокачать до 20 уровня — 150 ⭐",
                        "⬅ Инвентарь", "◀️ Предыдущая страница", "Следующая страница ▶️",
            "📦 Мои лоты", "⬅ Рынок",
            "◀️ Предыдущая страница рынка", "Следующая страница рынка ▶️",
            "⬅ Предыдущие кейсы", "Следующие кейсы ➡",
            "🔑 Тайна ледяного сундука", "🏔 Снежная экспедиция", "🔎 Снежный детектив",
            "🧸 Мастерская игрушек", "🎁 Подарки с риском", "❌⭕ Крестики-нолики",
            "⌨ Переключить вид кнопок: Inline", "⌨ Переключить вид кнопок: Reply",
            "🔔 Уведомления: ВКЛ", "🔕 Уведомления: ВЫКЛ",
            "👁 ID для других: Виден", "🙈 ID для других: Скрыт",
            "⚙ Настройки ID",
        }
        or message.text.startswith((
            "🛒 ", "🔓 Открыть ", "👕 ", "💰 Продать ", "🏪 Выставить ",
            "❌ Снять лот #", "🛒 Купить ",
        ))
        or (" ×" in message.text and " · " in message.text)
        or (message.text.startswith("🏆 ") and message.text.endswith(" 🪙"))
    )
))
def handle_all_reply_menus(message):
    if _reply_reject_message(message):
        return
    uid = message.from_user.id
    chat_id = message.chat.id
    text = message.text or ""
    mark_reply_mode(uid)

    # Главное меню
    if text in ("⬅ Главное меню", "⬅ В главное меню"):
        delete_active_game(uid)
        pending_market.pop(uid, None)
        reply_selected_emoji.pop(uid, None)
        send_main_reply_menu(chat_id, message.from_user.first_name)
        return

    if text == "❄️ Зимние игры":
        delete_active_game(uid)
        bot.send_message(chat_id, "🎮 <b>СНЕЖНЫЕ ИГРЫ</b>\n━━━━━━━━━━━━━━━━━━\n\nВыбери игру:", reply_markup=game_mune_reply(), parse_mode="HTML")
        return

    if text == "👤 Профиль":
        delete_active_game(uid)
        bot.send_message(chat_id, get_profile_text(uid), reply_markup=profile_menu_reply(), parse_mode="HTML")
        return
    
    if text == "⚙ Настройки ID":
        try:
            global_data = openbot.get_id(uid)
        except Exception as e:
            print(f"[REPLY SETTINGS ID] {e}")
            global_data = None

        if global_data:
            g_name = global_data[2] or "Не установлено"
            g_tag = global_data[5] or "Не установлен"
            g_bio = global_data[8] or "Не установлена"

            try:
                raw_status = openbot.get_status(uid)
                g_status = ROLE.get(
                    raw_status,
                    str(raw_status)
                )
            except Exception:
                g_status = "👤 Игрок"
    
            try:
                g_level = openbot.get_user_level(uid)
            except Exception:
                g_level = 1

            try:
                g_active_bot = openbot.get_active_bots(uid)
            except Exception:
                g_active_bot = "Неизвестно"

            text_out = (
                "🌐 <b>OPENBOT ID</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 <b>Имя:</b> {html.escape(str(g_name))}\n"
                f"🆔 <b>Тег:</b> <code>{html.escape(str(g_tag))}</code>\n"
                f"🎭 <b>Статус:</b> {html.escape(str(g_status))}\n"
                f"📊 <b>Уровень ID:</b> {g_level}\n"
                f"🤖 <b>Активных ботов:</b> {html.escape(str(g_active_bot))}\n"
                f"📝 <b>О себе:</b> {html.escape(str(g_bio))}\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🌍 <i>Это твой глобальный OpenBot ID.</i>"
            )    

        else:
            text_out = (
                "🌐 <b>OPENBOT AI ID</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "❌ <b>OpenBot ID не найден.</b>\n\n"
                "Для создания ID используй /start."
            )

        markup = types.ReplyKeyboardMarkup(
            row_width=2,
            resize_keyboard=True
        )    

        markup.add(
            types.KeyboardButton("⬅ Главное меню")
        )

        bot.send_message(
            chat_id,
            text_out,
            parse_mode="HTML",
            reply_markup=markup
        )
        return

    if text == "🎒 Инвентарь":
        reply_inventory_page[uid] = 1
        bot.send_message(chat_id, inventory_reply_text(uid, 1), reply_markup=inventory_menu_reply(uid, 1), parse_mode="HTML")
        return

    # Настройки (только для обычных настроек, не для OpenBot ID)
    if text in ("⚙️ Настройки", "⚙ Настройки"):
        bot.send_message(chat_id, "⚙️ <b>НАСТРОЙКИ</b>\n━━━━━━━━━━━━━━━━━━\n\nВыбери параметр:", reply_markup=settings_menu_reply(uid), parse_mode="HTML")
        return

    if text in ("🔔 Уведомления: ВКЛ", "🔕 Уведомления: ВЫКЛ"):
        toggle_user_setting(uid, "notifications")
        _, notifications, _ = get_user_settings(uid)
        msg = "🔔 Уведомления включены" if notifications else "🔕 Уведомления выключены"
        bot.send_message(chat_id, msg, reply_markup=settings_menu_reply(uid))
        return

    if text in ("👁 ID для других: Виден", "🙈 ID для других: Скрыт"):
        toggle_user_setting(uid, "show_id")
        _, _, show_id = get_user_settings(uid)
        msg = "👁 ID теперь виден другим" if show_id else "🙈 ID теперь скрыт от других"
        bot.send_message(chat_id, "Примечание !\nОт тогдо что вы измените этот парамент ничего не изменится пока это парамент не доделан !")
        bot.send_message(chat_id, msg, reply_markup=settings_menu_reply(uid))
        return

    if text in ("⌨ Переключить вид кнопок: Inline", "⌨ Переключить вид кнопок: Reply"):
        if _reply_off_enabled() and _reply_regular_user(uid):
            _reply_reject_message(message)
            return
        new_type = toggle_user_setting(uid, "kb_type")
        bot.send_message(chat_id, "⚙️ Настройки обновлены", reply_markup=types.ReplyKeyboardRemove())
        if new_type == "reply":
            send_main_reply_menu(chat_id, message.from_user.first_name, "⌨️ <b>Обычные кнопки включены.</b>\n\n👇 Главное меню:")
        else:
            bot.send_message(chat_id, "⌨️ <b>Inline-кнопки включены.</b>\n\n👇 Главное меню:", reply_markup=main_mune(), parse_mode="HTML")
        return

    # Магазин
    if text in ('🎁 Зимняя лавка', '⬅ Зимняя лавка'):
        bot.send_message(chat_id, shop_hub_text(uid), reply_markup=shop_mune_reply(), parse_mode='HTML')
        return

    if text == '❄️ Купить за снежинки':
        bot.send_message(chat_id, snow_shop_text(uid), reply_markup=snow_shop_keyboard(uid), parse_mode='HTML')
        return

    if text in ('🛒 Обычный магазин', '⬅ Магазин'):
        bot.send_message(chat_id, '🛒 <b>ОБЫЧНЫЙ МАГАЗИН</b>', reply_markup=regular_shop_reply(), parse_mode='HTML')
        return

    if text == "🎁 Кейсы":
        reply_case_page[uid] = 0
        bot.send_message(chat_id, cases_text(uid, 0), reply_markup=cases_menu_reply(uid, 0), parse_mode="HTML")
        return

    if text == "⭐ Магазин Stars":
        bot.send_message(chat_id, "⭐ <b>МАГАЗИН STARS</b>\n━━━━━━━━━━━━━━━━━━\n\nВыбери покупку:", reply_markup=stars_shop_menu_reply(), parse_mode="HTML")
        return

    stars_map = {
        "💰 10 000 000 монет — 100 ⭐": "coins_10m",
        "❄️ 25 снежинок — 50 ⭐": "snowflakes_25",
        "⭐ Прокачать до 20 уровня — 150 ⭐": "level_20",
    }
    if text in stars_map:
        send_stars_invoice_from_message(message, stars_map[text])
        return

    if text == "🏆 Титулы":
        bot.send_message(chat_id, winter_titles_text(uid), reply_markup=winter_titles_reply(), parse_mode="HTML")
        return

    if text.startswith("🏆 ") and " — " in text and text.endswith(" 🪙"):
        selected = text[2:].rsplit(" — ", 1)[0]
        title_key = next((k for k, (name, price) in WINTER_TITLES.items() if name == selected), None)
        if title_key:
            _, msg = buy_winter_title(uid, title_key)
            bot.send_message(chat_id, winter_titles_text(uid, msg), reply_markup=winter_titles_reply(), parse_mode="HTML")
            return

    # Инвентарь
    if text == "⬅ Инвентарь":
        reply_inventory_page[uid] = 1
        bot.send_message(chat_id, inventory_reply_text(uid, 1), reply_markup=inventory_menu_reply(uid, 1), parse_mode="HTML")
        return

    if text == "◀️ Предыдущая страница":
        page = max(1, reply_inventory_page.get(uid, 1) - 1)
        reply_inventory_page[uid] = page
        bot.send_message(chat_id, inventory_reply_text(uid, page), reply_markup=inventory_menu_reply(uid, page), parse_mode="HTML")
        return

    if text == "Следующая страница ▶️":
        page = reply_inventory_page.get(uid, 1) + 1
        reply_inventory_page[uid] = page
        bot.send_message(chat_id, inventory_reply_text(uid, page), reply_markup=inventory_menu_reply(uid, page), parse_mode="HTML")
        return

    picked = parse_inventory_button(text)
    if picked:
        emoji = picked
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM inventory WHERE user_id=? AND item_type='emoji' AND item_value=? LIMIT 1", (uid, emoji))
        if not cursor.fetchone():
            reply_selected_emoji.pop(uid, None)
            page = reply_inventory_page.get(uid, 1)
            bot.send_message(chat_id, "❌ Такого эмодзи у тебя нет.\n\n" + inventory_reply_text(uid, page), reply_markup=inventory_menu_reply(uid, page), parse_mode="HTML")
            return
        reply_selected_emoji[uid] = emoji
        card_text, markup = inventory_item_reply(uid, emoji)
        bot.send_message(chat_id, card_text, reply_markup=markup, parse_mode="HTML")
        return

    if text.startswith("👕 Одеть") or text.startswith("👕 Снять"):
        emoji = reply_selected_emoji.get(uid)
        if not emoji:
            bot.send_message(chat_id, "❌ Сначала выбери эмодзи в инвентаре.", reply_markup=inventory_menu_reply(uid, reply_inventory_page.get(uid, 1)))
            return
        cursor = conn.cursor()
        if text.startswith("👕 Одеть"):
            cursor.execute("SELECT 1 FROM inventory WHERE user_id=? AND item_type='emoji' AND item_value=? LIMIT 1", (uid, emoji))
            if not cursor.fetchone():
                bot.send_message(chat_id, "❌ Эмодзи больше нет в инвентаре.")
                return
            cursor.execute("UPDATE users SET equipped_item=? WHERE user_id=?", (emoji, uid))
            conn.commit()
            _, markup = inventory_item_reply(uid, emoji)
            bot.send_message(chat_id, f"👕 {emoji} теперь надето!", reply_markup=markup)
        else:
            cursor.execute("UPDATE users SET equipped_item='' WHERE user_id=? AND equipped_item=?", (uid, emoji))
            conn.commit()
            _, markup = inventory_item_reply(uid, emoji)
            bot.send_message(chat_id, f"👕 {emoji} снято.", reply_markup=markup)
        return

    if text.startswith("💰 Продать "):
        emoji = text[len("💰 Продать "):]
        price = get_emoji_price(emoji)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM inventory WHERE user_id=? AND item_type='emoji' AND item_value=? LIMIT 1", (uid, emoji))
        row = cursor.fetchone()
        if not row:
            bot.send_message(chat_id, "❌ Эмодзи не найдено.")
            return
        cursor.execute("DELETE FROM inventory WHERE id=?", (row[0],))
        cursor.execute("SELECT COUNT(*) FROM inventory WHERE user_id=? AND item_type='emoji' AND item_value=?", (uid, emoji))
        if cursor.fetchone()[0] == 0:
            cursor.execute("UPDATE users SET equipped_item='' WHERE user_id=? AND equipped_item=?", (uid, emoji))
        cursor.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (price, uid))
        conn.commit()
        reply_selected_emoji.pop(uid, None)
        bot.send_message(chat_id, f"💰 {emoji} продано за <b>{price:,}</b> 🪙.".replace(",", " ") + "\n\n" + inventory_reply_text(uid, reply_inventory_page.get(uid, 1)), reply_markup=inventory_menu_reply(uid, reply_inventory_page.get(uid, 1)), parse_mode="HTML")
        return

    if text.startswith("🏪 Выставить "):
        emoji = text[len("🏪 Выставить "):].removesuffix(" на рынок")
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM inventory WHERE user_id=? AND item_type='emoji' AND item_value=? LIMIT 1", (uid, emoji))
        if not cursor.fetchone():
            bot.send_message(chat_id, "❌ Эмодзи не найдено.")
            return
        pending_market[uid] = emoji
        bot.send_message(chat_id, f"🏪 <b>Выставление {emoji}</b>\n\nВведи цену в монетах, например <code>1500</code>.", parse_mode="HTML")
        return

    # Рынок
    if text == "🏪 Рынок":
        reply_market_page[uid] = 1
        market_text, markup = market_menu_reply(uid, 1)
        bot.send_message(chat_id, market_text, reply_markup=markup, parse_mode="HTML")
        return

    if text == "◀️ Предыдущая страница рынка":
        page = max(1, reply_market_page.get(uid, 1) - 1)
        reply_market_page[uid] = page
        market_text, markup = market_menu_reply(uid, page)
        bot.send_message(chat_id, market_text, reply_markup=markup, parse_mode="HTML")
        return

    if text == "Следующая страница рынка ▶️":
        page = reply_market_page.get(uid, 1) + 1
        reply_market_page[uid] = page
        market_text, markup = market_menu_reply(uid, page)
        bot.send_message(chat_id, market_text, reply_markup=markup, parse_mode="HTML")
        return

    if text == "📦 Мои лоты":
        market_text, markup = my_market_reply(uid)
        bot.send_message(chat_id, market_text, reply_markup=markup, parse_mode="HTML")
        return

    if text == "⬅ Рынок":
        market_text, markup = market_menu_reply(uid, reply_market_page.get(uid, 1))
        bot.send_message(chat_id, market_text, reply_markup=markup, parse_mode="HTML")
        return

    if text.startswith("🛒 Купить "):
        import re
        m = re.search(r"#(\d+)$", text)
        if not m:
            bot.send_message(chat_id, "❌ Не удалось определить лот.")
            return
        lot_id = int(m.group(1))
        cursor = conn.cursor()
        cursor.execute("SELECT seller_id, item_type, item_value, price FROM auction WHERE lot_id=?", (lot_id,))
        lot = cursor.fetchone()
        if not lot:
            bot.send_message(chat_id, "❌ Лот уже продан или снят.")
            return
        seller_id, item_type, emoji, price = lot
        if seller_id == uid:
            bot.send_message(chat_id, "❌ Нельзя купить собственный лот.")
            return
        if item_type != "emoji":
            bot.send_message(chat_id, "❌ Этот тип товара не поддерживается.")
            return
        cursor.execute("SELECT coins FROM users WHERE user_id=?", (uid,))
        row = cursor.fetchone()
        coins = int((row or [0])[0])
        if coins < price:
            bot.send_message(chat_id, f"❌ Недостаточно монет. Нужно <b>{price:,}</b> 🪙.".replace(",", " "), parse_mode="HTML")
            return
        cursor.execute("DELETE FROM auction WHERE lot_id=? AND seller_id=? AND price=?", (lot_id, seller_id, price))
        if cursor.rowcount != 1:
            conn.rollback()
            bot.send_message(chat_id, "❌ Лот уже купили.")
            return
        cursor.execute("UPDATE users SET coins=coins-? WHERE user_id=? AND coins>=?", (price, uid, price))
        if cursor.rowcount != 1:
            conn.rollback()
            bot.send_message(chat_id, "❌ Недостаточно монет.")
            return
        cursor.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (price, seller_id))
        cursor.execute("INSERT INTO inventory (user_id,item_type,item_value,is_active) VALUES (?,'emoji',?,0)", (uid, emoji))
        conn.commit()
        market_text, markup = market_menu_reply(uid, reply_market_page.get(uid, 1))
        bot.send_message(chat_id, f"🎉 Куплено {emoji} за <b>{price:,}</b> 🪙!".replace(",", " "), reply_markup=markup, parse_mode="HTML")
        notify_market_sale(seller_id, uid, emoji, price)
        return

    if text.startswith("❌ Снять лот #"):
        import re
        m = re.match(r"❌ Снять лот #(\d+)\s*(.*)$", text)
        if not m:
            bot.send_message(chat_id, "❌ Не удалось определить лот.")
            return
        lot_id = int(m.group(1))
        cursor = conn.cursor()
        cursor.execute("SELECT item_value FROM auction WHERE lot_id=? AND seller_id=? AND item_type='emoji'", (lot_id, uid))
        lot = cursor.fetchone()
        if not lot:
            bot.send_message(chat_id, "❌ Лот не найден.")
            return
        emoji = lot[0]
        cursor.execute("DELETE FROM auction WHERE lot_id=? AND seller_id=?", (lot_id, uid))
        if cursor.rowcount != 1:
            conn.rollback()
            bot.send_message(chat_id, "❌ Лот уже снят.")
            return
        cursor.execute("INSERT INTO inventory (user_id,item_type,item_value,is_active) VALUES (?,'emoji',?,0)", (uid, emoji))
        conn.commit()
        if reply_my_lots.get(uid):
            market_text, markup = my_market_reply(uid)
        else:
            market_text, markup = market_menu_reply(uid, reply_market_page.get(uid, 1))
        bot.send_message(chat_id, f"↩️ {emoji} возвращён в инвентарь.\n\n{market_text}", reply_markup=markup, parse_mode="HTML")
        return

    # Кейсы
    for case_key, c_info in CASES.items():
        if text.startswith(f"🛒 {c_info['name']} —"):
            _, msg = buy_case(uid, case_key)
            bot.send_message(chat_id, f"{msg}\n\n{balance_line(uid)}", reply_markup=cases_menu_reply(uid, reply_case_page.get(uid, 0)), parse_mode="HTML")
            return
        if text.startswith(f"🔓 Открыть {c_info['name']} ("):
            result, msg = open_case(uid, case_key)
            if result is None:
                bot.send_message(chat_id, f"{msg}\n\n{balance_line(uid)}", reply_markup=cases_menu_reply(uid, reply_case_page.get(uid, 0)), parse_mode="HTML")
            else:
                bot.send_message(chat_id, f"🎁 <b>КЕЙС ОТКРЫТ!</b>\n\n{c_info['name']}\n\n✨ {msg}\n\n📦 Осталось: <b>{get_case_count(uid, case_key)}</b>\n\n{balance_line(uid)}", reply_markup=cases_menu_reply(uid, reply_case_page.get(uid, 0)), parse_mode="HTML")
            return

    if text in ("⬅ Предыдущие кейсы", "Следующие кейсы ➡"):
        current = reply_case_page.get(uid, 0)
        current += -1 if text == "⬅ Предыдущие кейсы" else 1
        _, page, _ = get_cases_page(current)
        reply_case_page[uid] = page
        bot.send_message(chat_id, cases_text(uid, page), reply_markup=cases_menu_reply(uid, page), parse_mode="HTML")
        return

    # Старые названия заменены на пять самостоятельных игр.
    old_games = {
        '🔑 Тайна ледяного сундука': 'lock',
        '🏔 Снежная экспедиция': 'keys',
        '🔎 Снежный детектив': 'shadow',
        '🧸 Мастерская игрушек': 'potion',
        '🎁 Подарки с риском': 'pumpkin',
    }
    if text in old_games:
        mode = old_games[text]
        _ng_start(uid, chat_id, mode)
        bot.send_message(chat_id, _ng_render(uid)[0], reply_markup=_ng_render(uid)[1], parse_mode='HTML')
        return
    if text == '❌⭕ Крестики-нолики':
        delete_active_game(uid)
        bot.send_message(chat_id, '❌⭕ <b>КРЕСТИКИ-НОЛИКИ</b>\n\nВыбери сложность ИИ:',
                         parse_mode='HTML', reply_markup=ttt_level_markup(reply=True))
        return

# Сложность крестиков-ноликов в Reply-режиме.
@bot.message_handler(func=lambda m: (m.text or '') in {
    '❌⭕ 🟢 Лёгкий', '❌⭕ 🟡 Средний', '❌⭕ 🔴 Сложный'
})
def ttt_reply_level(message):
    if _reply_reject_message(message):
        return
    level = next(k for k, title in _TTT_LEVELS.items() if message.text == f'❌⭕ {title}')
    uid = message.from_user.id
    ttt_start(uid, message.chat.id, level)
    bot.send_message(message.chat.id,
                     f'❌⭕ <b>КРЕСТИКИ-НОЛИКИ</b>\nИИ: {_TTT_LEVELS[level]}\n\n'
                     + ttt_board_text('0' * 9) + '\n\nВыбери клетку 1–9:',
                     parse_mode='HTML', reply_markup=game_action_reply('ttt'))


# ============ REPLY-ДЕЙСТВИЯ ИГР ============
@bot.message_handler(func=lambda message: message.text in {
    "🛑 Выйти из игры", "❄️ Сугроб 1", "❄️ Сугроб 2", "❄️ Сугроб 3", "❄️ Сугроб 4",
    "🚪 Комната 1", "🚪 Комната 2", "🚪 Комната 3",
    "🧪 Шар 1", "🧪 Шар 2", "🧪 Шар 3",
    "🎁 Подарок 1", "🎁 Подарок 2", "🎁 Подарок 3", "🎁 Подарок 4", "🎁 Подарок 5",
    "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "⬅ Игры"
})
def handle_reply_game_actions(message):
    if _reply_reject_message(message):
        return
    uid = message.from_user.id
    chat_id = message.chat.id
    text = message.text
    mark_reply_mode(uid)
    game = get_active_game(uid)

    if text == "⬅ Игры":
        delete_active_game(uid)
        bot.send_message(chat_id, "🎮 <b>НОВЫЙ ГОДСКИЕ ИГРЫ</b>\n\nВыбери игру:", reply_markup=game_mune_reply(), parse_mode="HTML")
        return

    if text == "🛑 Выйти из игры":
        delete_active_game(uid)
        bot.send_message(chat_id, "🏃 Игра завершена.", reply_markup=game_mune_reply())
        return

    if not game:
        bot.send_message(chat_id, "ℹ️ Активной игры нет.", reply_markup=game_mune_reply())
        return

    game_type = game[0]

    if game_type == 'ttt' and text.strip() in {str(i) for i in range(1, 10)}:
        try:
            pos = int(text.strip()) - 1
        except (ValueError, IndexError):
            return bot.send_message(chat_id, '❌ Неверная клетка.')
        result, board, notice = ttt_play(uid, pos)
        if result == 'invalid':
            bot.send_message(chat_id, f'❌ {notice}', reply_markup=game_action_reply('ttt'))
            return
        if result == 'playing':
            notice += '\n\n' + ttt_board_text(board)
            keyboard = game_action_reply('ttt')
        else:
            notice += '\n\n' + ttt_board_text(board)
            keyboard = game_mune_reply()
        bot.send_message(chat_id, notice, parse_mode='HTML', reply_markup=keyboard)
        return

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id

    # ===== РЫНОК ЭМОДЗИ =====
    if user_id in pending_market and not message.text.startswith('/'):
        emoji = pending_market.pop(user_id)

        try:
            price = int(message.text.strip())
        except ValueError:
            bot.reply_to(message, "❌ Цена должна быть целым числом!")
            return

        if price <= 0:
            bot.reply_to(message, "❌ Цена должна быть больше 0!")
            return

        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM inventory WHERE user_id=? AND item_type='emoji' AND item_value=? LIMIT 1",
            (user_id, emoji)
        )
        row = cursor.fetchone()

        if not row:
            bot.reply_to(message, "❌ Эмодзи больше нет в инвентаре!")
            return

        try:
            cursor.execute("DELETE FROM inventory WHERE id=?", (row[0],))
            cursor.execute(
                "INSERT INTO auction (seller_id, item_type, item_value, price) VALUES (?, 'emoji', ?, ?)",
                (user_id, emoji, price)
            )
            conn.commit()

            bot.reply_to(
                message,
                f"🏪 <b>{emoji} выставлен на рынок!</b>\n💰 Цена: <b>{price}</b> 🪙",
                parse_mode="HTML"
            )
        except Exception as e:
            conn.rollback()
            print(f"[MARKET ERROR] {e}")
            bot.reply_to(message, "❌ Не удалось выставить эмодзи на рынок!")

        return

    # ===== ИГРЫ =====
    game_data = get_active_game(user_id)

    if not game_data or message.text.startswith('/'):
        return

    game_type = game_data[0]

    # Для старых незавершённых партий после обновления.
    if game_type in ('lock','keys','shadow','potion','pumpkin'):
        delete_active_game(user_id)
        bot.reply_to(message, '🎮 Игры обновились! Открой новый режим через меню.')


# ==============================
# Глобальный обработчик ошибок
# ==============================

# Общая папка logs находится над папками Random_bot и Master_bot.
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "random_bot.log"
error_logger = logging.getLogger("random_bot.errors")
error_logger.setLevel(logging.ERROR)
error_logger.propagate = False
if not error_logger.handlers:
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024,
        backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    error_logger.addHandler(file_handler)
    # Сетевые ошибки polling могут логироваться самой библиотекой telebot.
    for library_logger_name in ("TeleBot", "telebot"):
        library_logger = logging.getLogger(library_logger_name)
        library_logger.addHandler(file_handler)
        library_logger.setLevel(logging.WARNING)

class GlobalExceptionHandler(telebot.ExceptionHandler):

    def handle(self, exception):

        print("\n" + "=" * 60)
        print("🚨 ОШИБКА В БОТЕ")
        print("=" * 60)

        # Получаем полный traceback
        error_log = "".join(traceback.format_exception(
            type(exception), exception, exception.__traceback__
        ))

        # Записываем любой traceback, независимо от настроек Telegram.
        error_logger.error("\n%s", error_log.rstrip())

        print(error_log)

        print("=" * 60)

        # Логи ошибок идут в чат разработчика (DEVELOPER_CHAT_ID)
        developers = [DEVELOPER_CHAT_ID]

        # ==============================
        # Отправка ошибки разработчикам
        # ==============================

        for developer_id in developers:

            # Настройка уведомлений берётся из основной базы пользователей.
            # Если прочитать её не удалось, не отправляем сообщение,
            # а оставляем информацию в локальном логе.
            try:
                if get_user_settings(developer_id)[1] != 1:
                    continue
            except Exception:
                error_logger.exception("Не удалось проверить уведомления для %s", developer_id)
                continue

            try:

                # Первое сообщение
                bot.send_message(
                    developer_id,
                    "🚨 <b>ОШИБКА В БОТЕ</b>\n\n"
                    "Произошла непредвиденная ошибка.\n"
                    "📋 Полный лог ошибки:",
                    parse_mode="HTML"
                )

                # Telegram ограничивает сообщения примерно 4096 символами.
                # Оставляем запас.
                max_length = 3900

                # Разбиваем длинный traceback
                parts = [
                    error_log[i:i + max_length]
                    for i in range(0, len(error_log), max_length)
                ]

                for number, part in enumerate(parts, start=1):

                    # Экранируем HTML
                    safe_part = html.escape(part)

                    # Добавляем номер части только если их несколько
                    if len(parts) > 1:
                        header = f"📄 <b>Часть {number}/{len(parts)}</b>\n\n"
                    else:
                        header = ""

                    bot.send_message(
                        developer_id,
                        f"{header}<pre>{safe_part}</pre>",
                        parse_mode="HTML"
                    )

                print(
                    f"[ERROR] Лог отправлен разработчику "
                    f"{developer_id}"
                )

            except Exception as send_error:

                error_logger.exception("Не удалось отправить ошибку разработчику %s", developer_id)
                print(
                    f"[ERROR] Не удалось отправить ошибку "
                    f"разработчику {developer_id}: {send_error}"
                )

        # True означает, что исключение обработано
        return True


# ==============================
# Подключаем обработчик
# ==============================

bot.exception_handler = GlobalExceptionHandler()


print("[ Успешно ] Бот запущен и готов к работе!")

bot.polling(non_stop=True, timeout=70)