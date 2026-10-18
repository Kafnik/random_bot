import telebot
import openbot_id
import sqlite3
import random
import time
import traceback
import html
from telebot import apihelper
from datetime import datetime
from telebot import types
import halloween_random_db as halloween_db
from telebot.handler_backends import BaseMiddleware, CancelUpdate # отдельная база события Random Bot (файл halloween_random_db.py): все её изменения идут только через этот модуль


# ======= Настройка ======
openbot_id.init_id_system()
DB_NAME = "Random_bot.1.6.db"
HALLOWEEN_DB_NAME = "Halloween_random.db"  # база события Random Bot (у Master Bot своя: Halloween_event.db)
DEVELOPER_CHAT_ID = 1234567890 # Замените на свой ID
# ========================

TOKEN = "Token" # Токен бота 

bot = telebot.TeleBot(TOKEN, use_class_middlewares=True)

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
        # Режим выключен — ничего не трогаем
        if not is_maintenance():
            return None
 
        user = getattr(message, "from_user", None)
        # Свои (developer / tester / admin / owner по openbot_id) проходят как обычно
        if user is not None and openbot_id.check_access(user.id, MAINTENANCE_ALLOWED):
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
        # Random Bot 1.6 обычно использует id. Добавляем user_id как совместимый ключ.
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
            'equipped_item': "TEXT DEFAULT ''",
            'kb_type': "TEXT DEFAULT 'inline'",
            'notifications': "INTEGER DEFAULT 1",
            'show_id_to_others': "INTEGER DEFAULT 1",
            'badge': "TEXT DEFAULT ''",
            'spooky_keys': "INTEGER DEFAULT 0",
            'candies': "INTEGER DEFAULT 0",
            'id': "INTEGER",
        }
        candies_is_new = 'candies' not in user_cols
        for name, definition in additions.items():
            if name not in user_cols:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
                except sqlite3.OperationalError:
                    pass
        # Один раз переносим старые Жуткие ключи в конфеты
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

# ======= База события «Хэллоуин» (конфеты, кейсы, титулы) =======
# Конфеты и кейсы больше НЕ хранятся в основной базе (users.candies, case_inventory):
# они живут в Halloween_random.db. В основной базе остаются как резервная копия.
# Внутри модуля конфеты хранятся как «ключи» (один счётчик события).
halloween_db.init(HALLOWEEN_DB_NAME)

# ======= Вспомогательные функции =======
def get_user_settings(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT kb_type, notifications, show_id_to_others FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        kb_type = res[0] or 'inline'
        notifications = res[1] if res[1] is not None else 1
        show_id = res[2] if res[2] is not None else 1
        return kb_type, notifications, show_id
    return 'reply', 1, 1

def mark_reply_mode(user_id):
    """Человек нажал кнопку reply-клавиатуры — значит она реально активна. Синхронизируем настройку."""
    if get_user_settings(user_id)[0] != 'reply':
        c = conn.cursor()
        c.execute("UPDATE users SET kb_type = 'reply' WHERE user_id = ?", (user_id,))
        conn.commit()

def toggle_user_setting(user_id, setting_name):
    kb_type, notifications, show_id = get_user_settings(user_id)

    cursor = conn.cursor()

    if setting_name == 'kb_type':
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
    """Глобальные данные игрока из openbot_id (локально, без HTTP): {'status', 'level'} или None."""
    try:
        data = openbot_id.get_id(user_id)
        if not data:
            return None
        return {
            "status": str(data[6] or "user").strip().lower(),
            "level": int(data[10] or 1),
        }
    except Exception as e:
        print(f"[OpenBot ID] Ошибка чтения данных {user_id}: {e}")
        return None
    

def sync_global_status(user_id):
    """
    Синхронизация GLOBAL -> LOCAL через openbot_id.

    ВАЖНО:
    - статус и role_level берём из openbot_id (get_openbot_user);
    - users.level (игровой уровень) не изменяется;
    - локальный status/role_level обновляются сразу при обращении пользователя.
    """
    try:
        global_data = get_openbot_user(user_id)

        if not global_data:
            print(f"[OpenBot ID] Нет данных пользователя {user_id}")
            return False

        global_status = str(
            global_data.get("status", "user") or "user"
        ).strip().lower()

        try:
            global_role_level = int(global_data.get("level", 1) or 1)
        except (TypeError, ValueError):
            global_role_level = 1

        cursor = conn.cursor()
        cursor.execute(
            "SELECT status, role_level FROM users WHERE user_id = ?",
            (user_id,)
        )
        local = cursor.fetchone()

        if not local:
            return False

        local_status = str(local[0] or "user").strip().lower()

        try:
            local_role_level = int(local[1] or 1)
        except (TypeError, ValueError):
            local_role_level = 1

        # Глобальный статус является источником истины.
        # Поэтому даже admin -> user будет синхронизирован.
        if (
            local_status != global_status
            or local_role_level != global_role_level
        ):
            cursor.execute(
                """
                UPDATE users
                SET status = ?, role_level = ?
                WHERE user_id = ?
                """,
                (global_status, global_role_level, user_id)
            )
            conn.commit()

            print(
                f"[OpenBot Sync] user={user_id}: "
                f"{local_status} {local_role_level} -> "
                f"{global_status} {global_role_level}"
            )
            return True

        return False

    except Exception as e:
        print(f"[OpenBot Sync] Ошибка синхронизации {user_id}: {e}")
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
    """Доступ для команды (developer / tester / admin / owner) — через openbot_id."""
    return openbot_id.check_access(user_id, ("developer", "tester", "admin", "owner"))

def check_ban(user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT status, ban_reason FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result and result[0] == 'banned':
        return result[1]
    return None

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

def build_ttt_keyboard(board_str):
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    symbols = {'0': '⬜', '1': '🎃', '2': '💀'}
    for i in range(9):
        char = board_str[i]
        btn_text = symbols.get(char, '⬜')
        buttons.append(types.InlineKeyboardButton(btn_text, callback_data=f"ttt_pos_{i}"))
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("🛑 Выход из игры", callback_data="back_to_games"))
    return markup

# ============= Конфеты 🍬 =============
CHEST_COST = 5            # цена Жуткого сундука в конфетах (без событий)

def chest_cost():
    return 3 if get_daily_event() == "sale" else CHEST_COST

SPOOKY_REWARDS = [
    ("👻", "Обычная", 45.0),
    ("🩸", "Редкая", 30.0),
    ("☠️", "Очень редкая", 15.0),
    ("😈", "Эпическая", 7.0),
    ("🕷️", "Мифическая", 2.5),
    ("👁️", "Легендарная", 0.5),
]

def add_candies(user_id, amount, source=None):
    """source: 'game' / 'lock' / 'drop' / 'house' / 'gift' — считаются в достижениях."""
    halloween_db.add_keys(user_id, amount, source or "candies")
    if source:
        try:
            rnd_stat_inc(user_id, "candies_earned", amount)
            if source in ("game", "lock"):
                rnd_stat_inc(user_id, "games_won")
            if source == "lock":
                rnd_stat_inc(user_id, "lock_wins")
            check_achievements(user_id)
        except Exception as e:
            print(f"[RND STATS ERROR] {e}")

def get_candies(user_id):
    return halloween_db.get_keys(user_id)


def open_spooky_chest(user_id):
    """Тратит CHEST_COST конфет (база события) и выдаёт случайный эмодзи (основная база)."""

    cost = chest_cost()
    if not halloween_db.spend_keys(user_id, cost, "chest"):
        return None

    emoji, rarity, _ = random.choices(
        SPOOKY_REWARDS,
        weights=[x[2] for x in SPOOKY_REWARDS],
        k=1
    )[0]

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM inventory WHERE user_id = ? AND item_type = 'emoji' AND item_value = ? LIMIT 1",
            (user_id, emoji)
        )
        duplicate = cursor.fetchone()

        if duplicate:
            compensation = {
                "Обычная": 25,
                "Редкая": 50,
                "Очень редкая": 100,
                "Эпическая": 200,
                "Мифическая": 500,
                "Легендарная": 1000
            }[rarity]
            cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (compensation, user_id))
            result = {"emoji": emoji, "rarity": rarity, "coins": compensation}
        else:
            cursor.execute(
                "INSERT INTO inventory (user_id, item_type, item_value) VALUES (?, 'emoji', ?)",
                (user_id, emoji)
            )
            result = {"emoji": emoji, "rarity": rarity, "coins": 0}

        conn.commit()
    except Exception as e:
        # Награду выдать не удалось — возвращаем конфеты, чтобы они не пропали
        conn.rollback()
        halloween_db.add_keys(user_id, cost, "chest_refund")
        print(f"[Halloween] Ошибка выдачи награды сундука: {e}")
        return None

    try:
        rnd_stat_inc(user_id, "chests_opened")
        check_achievements(user_id)
    except Exception as e:
        print(f"[RND STATS ERROR] {e}")

    return result

# ============= КЕЙСЫ =============
# Количество кейсов хранится отдельно в case_inventory.
# Награды используют уже существующие в боте: монеты, XP, эмодзи и конфеты.
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
            {"type": "emoji", "value": "💀", "chance": 6},
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
    if case_info["currency"] == "candies":
        return "🍬", "candies"
    return "💰", "coins"


def get_case_count(user_id, case_key):
    return halloween_db.get_case_count(user_id, case_key)


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
    """Строка с балансом: монеты (основная база) и конфеты (база события)."""
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(coins, 0) FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    coins = int(row[0]) if row else 0
    candies = halloween_db.get_keys(user_id)
    return f"💼 Твой баланс: <b>{_fmt(coins)}</b> 💰 · <b>{_fmt(candies)}</b> 🍬"

def cases_text(user_id, page=0):
    case_items, page, total_pages = get_cases_page(page)
    lines = [
        "🎁 <b>КЕЙСЫ</b>",
        "",
        balance_line(user_id),
        "",
        "Открывай кейсы и получай 💰 монеты, ⭐ XP, 🍬 конфеты и 🎒 эмодзи.",
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
    c_info = CASES.get(case_key)
    if not c_info:
        return False, "❌ Кейс не найден!"

    currency = c_info["currency"]
    price = int(c_info["price"])
    icon = "🍬" if currency == "candies" else "💰"
    not_enough = f"❌ Недостаточно валюты! Нужно {price:,} {icon}.".replace(",", " ")

    if currency == "candies":
        # Конфеты лежат в базе события
        if not halloween_db.spend_keys(user_id, price, f"buy_case:{case_key}"):
            return False, not_enough
        try:
            halloween_db.add_case(user_id, case_key, 1, "buy")
        except Exception as e:
            halloween_db.add_keys(user_id, price, "buy_case_refund")
            print(f"[Halloween] Ошибка покупки кейса: {e}")
            return False, "❌ Не удалось купить кейс, конфеты возвращены."
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
            halloween_db.add_case(user_id, case_key, 1, "buy")
        except Exception as e:
            add_coins(user_id, price)
            print(f"[Halloween] Ошибка покупки кейса: {e}")
            return False, "❌ Не удалось купить кейс, монеты возвращены."

    return True, f"🛒 Куплен {c_info['name']} за {price:,} {icon}!".replace(",", " ")


def open_case(user_id, case_key):
    c_info = CASES.get(case_key)
    if not c_info:
        return None, "❌ Кейс не найден!"
    if halloween_db.get_case_count(user_id, case_key) <= 0:
        return None, "❌ У тебя нет такого кейса!"

    reward = random.choices(
        c_info["rewards"],
        weights=[r["chance"] for r in c_info["rewards"]],
        k=1,
    )[0]

    # Кейс забирается из базы события
    if not halloween_db.take_case(user_id, case_key, "open"):
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
            # Конфеты выдаются в базе события — ниже, после основной базы
            candy_amount = int(reward.get("amount", 1))
            text = f"🍬 +{candy_amount} конфет"
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
            halloween_db.add_keys(user_id, candy_amount, f"case_reward:{case_key}")
    except Exception as e:
        # Награду выдать не удалось — возвращаем кейс, чтобы он не пропал
        conn.rollback()
        halloween_db.add_case(user_id, case_key, 1, "open_refund")
        print(f"[Halloween] Ошибка выдачи награды кейса: {e}")
        return None, "❌ Не удалось выдать награду, кейс возвращён."

    return reward, text


# =========== Меню (Без изменений) =========
def main_mune():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('🔮 Жуткие Игры', callback_data='game'),
        types.InlineKeyboardButton('👤 Профиль', callback_data="profile"))
    
    markup.add(
        types.InlineKeyboardButton('🧹 Лавка Ужасов', callback_data='shop'),
        types.InlineKeyboardButton('🎒 Инвентарь', callback_data='open_inventory'))

    markup.add(
        types.InlineKeyboardButton('🏪 Рынок', callback_data='market'),
        types.InlineKeyboardButton('⚙ Настройки', callback_data='settings_user'))
    
    markup.add(
        types.InlineKeyboardButton("🍬 Жуткий сундук", callback_data="spooky_chest")
    )
    
    markup.add(
        types.InlineKeyboardButton("🎲 Рандом-мир", callback_data="rnd_hub")
    )

    return markup

def main_mune_reply():
    """Главное меню Reply-кнопок."""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(types.KeyboardButton("🔮 Жуткие Игры"), types.KeyboardButton("👤 Профиль"))
    markup.row(types.KeyboardButton("🧹 Лавка Ужасов"), types.KeyboardButton("🎒 Инвентарь"))
    markup.row(types.KeyboardButton("🏪 Рынок"), types.KeyboardButton("🍬 Жуткий сундук"))
    markup.row(types.KeyboardButton("⚙️ Настройки"), types.KeyboardButton("🎲 Рандом-мир"))
    return markup


def send_main_reply_menu(chat_id, first_name=None, text=None):
    if text is None:
        text = (
            f"🎲 <b>RANDOM BOT</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👋 Добро пожаловать, <b>{html.escape(first_name or 'Игрок')}</b>!\n\n"
            f"🔮 Здесь тебя ждут жуткие игры, кейсы, рынок и коллекция эмодзи.\n\n"
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
    markup.add(
        types.InlineKeyboardButton(kb_text, callback_data='toggle_kb'),
        types.InlineKeyboardButton(notif_text, callback_data='toggle_notif'),
        types.InlineKeyboardButton(id_text, callback_data='toggle_show_id'),
        types.InlineKeyboardButton('🔙 В главное меню', callback_data='back')
    )
    return markup

def profile_menu_reply():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("⚙ Настройки ID"),
        types.KeyboardButton("⬅ Главное меню"))
    return markup


def settings_menu_reply(user_id):
    kb_type, notifications, show_id = get_user_settings(user_id)

    kb_text = "⌨ Переключить вид кнопок: Reply" if kb_type == 'inline' else "⌨ Переключить вид кнопок: Inline"
    notif_text = "🔔 Уведомления: ВКЛ" if notifications == 1 else "🔕 Уведомления: ВЫКЛ"
    id_text = "👁 ID для других: Виден" if show_id == 1 else "🙈 ID для других: Скрыт"

    markup = types.ReplyKeyboardMarkup(row_width=1)
    markup.add(
        types.KeyboardButton(kb_text),
        types.KeyboardButton(notif_text),
        types.KeyboardButton(id_text),
        types.KeyboardButton('⬅ Главное меню')
    )
    return markup



# ============ REPLY-КЛАВИАТУРЫ ДЛЯ ОСНОВНЫХ МЕНЮ ============

def shop_mune_reply():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton("🎁 Кейсы"), types.KeyboardButton("🏆 Титулы"), types.KeyboardButton("⭐ Магазин Stars"))
    markup.add(types.KeyboardButton("⬅ Главное меню"))
    return markup

def stars_shop_menu_reply():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton("💰 10 000 000 монет — 100 ⭐"), types.KeyboardButton("🍬 25 конфет — 50 ⭐"), types.KeyboardButton("⭐ Прокачать до 20 уровня — 150 ⭐"), types.KeyboardButton("⬅ Магазин"))
    return markup

def cases_menu_reply(user_id, page=0):
    case_items, page, total_pages = get_cases_page(page)
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for case_key, c_info in case_items:
        count = get_case_count(user_id, case_key)
        icon = "🍬" if c_info["currency"] == "candies" else "💰"
        markup.add(types.KeyboardButton(f"🛒 {c_info['name']} — {c_info['price']:,} {icon}".replace(",", " ")))
        markup.add(types.KeyboardButton(f"🔓 Открыть {c_info['name']} ({count} шт)"))
    nav=[]
    if page > 0: nav.append(types.KeyboardButton("⬅ Предыдущие кейсы"))
    if page < total_pages-1: nav.append(types.KeyboardButton("Следующие кейсы ➡"))
    if nav: markup.row(*nav)
    markup.add(types.KeyboardButton("⬅ Магазин"))
    return markup

def spooky_chest_reply():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton("🍬 Открыть Жуткий сундук"), types.KeyboardButton("⬅ Главное меню"))
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
        return "🎒 <b>Твой инвентарь пуст!</b>\n\nУ тебя ещё нет эмодзи. Играй и открывай Жуткие сундуки, чтобы собирать их."
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
    reply_my_lots.pop(user_id, None)
    lots,total=get_market_lots(page); total_pages=max(1,(total+MARKET_PAGE_SIZE-1)//MARKET_PAGE_SIZE); page=min(max(1,page),total_pages)
    markup=types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True); lines=["🏪 <b>РЫНОК ЭМОДЗИ</b>",f"📄 Страница <b>{page}/{total_pages}</b>",""]
    for lot_id,seller_id,emoji,price,username,first_name in lots:
        seller="ты" if seller_id==user_id else market_seller_name(username,first_name)
        lines.append(f"#{lot_id} {emoji} — <b>{price:,} 🪙</b> — {seller}".replace(",", " "))
        if seller_id==user_id: markup.add(types.KeyboardButton(f"❌ Снять лот #{lot_id} {emoji} · {price:,} 🪙".replace(",", " ")))
        else: markup.add(types.KeyboardButton(f"🛒 Купить {emoji} за {price:,} 🪙 · #{lot_id}".replace(",", " ")))
    if not lots: lines.append("Пока нет выставленных эмодзи.")
    nav=[]
    if page>1: nav.append(types.KeyboardButton("◀️ Предыдущая страница рынка"))
    if page<total_pages: nav.append(types.KeyboardButton("Следующая страница рынка ▶️"))
    if nav: markup.row(*nav)
    markup.add(types.KeyboardButton("📦 Мои лоты"),types.KeyboardButton("⬅ Главное меню"))
    return "\n".join(lines),markup

def my_market_reply(user_id):
    reply_my_lots[user_id]=True
    cursor=conn.cursor(); cursor.execute("SELECT lot_id,item_value,price FROM auction WHERE seller_id=? AND item_type='emoji' ORDER BY lot_id DESC",(user_id,)); lots=cursor.fetchall()
    markup=types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for lot_id,emoji,price in lots: markup.add(types.KeyboardButton(f"❌ Снять лот #{lot_id} {emoji}"))
    markup.add(types.KeyboardButton("⬅ Рынок"))
    text="📦 <b>МОИ ЛОТЫ</b>\n\n" + ("\n".join(f"#{lot_id} {emoji} — <b>{price:,} 🪙</b>".replace(","," ") for lot_id,emoji,price in lots) if lots else "У тебя нет выставленных эмодзи.")
    return text,markup

# ============== Магазин =========
# Покупки за Telegram Stars (XTR). Цены указаны в Stars.
STARS_SHOP = {
    "coins_10m": {
        "title": "💰 10 000 000 монет",
        "description": "Пополнение игрового баланса на 10 000 000 💰",
        "stars": 100,
    },
    "candies_25": {
        "title": "🍬 25 конфет",
        "description": "Получи 25 🍬 конфет для Жуткого сундука",
        "stars": 50,
    },
    "level_20": {
        "title": "⭐ Уровень 20",
        "description": "Прокачка игрового уровня до 20",
        "stars": 150,
    },
}

HALLOWEEN_TITLES = {
    "pumpkin_boss": ("🎃 Тыквенный магнат", 2500),
    "crypt_master": ("🗝️ Хозяин склепа", 5000),
    "night_wizard": ("🔮 Ночной маг", 10000),
    "ghost_hunter": ("👻 Охотник на призраков", 25000),
    "witch_lord": ("🧙 Повелитель ведьм", 50000),
    "halloween_legend": ("🦇 Легенда Хэллоуина", 100000),
}

# Хэллоуинские титулы должны отображаться в профиле
for _key, (_name, _price) in HALLOWEEN_TITLES.items():
    PROFILE_TITLES[_key] = _name

# Один раз переносим старые данные события из основной базы (основная база только читается, не меняется)
try:
    _migration = halloween_db.migrate_from_main_db(DB_NAME, title_keys=list(HALLOWEEN_TITLES), keys_column="candies")
    if _migration.get("done"):
        print(f"[Halloween] Старые данные перенесены в {HALLOWEEN_DB_NAME}: {_migration}")
except Exception as _e:
    print(f"[Halloween] ❌ Не удалось перенести старые данные: {_e}")

def halloween_titles_text(user_id, note=None):
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(coins, 0), profile_title FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    coins = int(row[0]) if row else 0
    current = PROFILE_TITLES.get(row[1] if row else "none", "Без титула")
    text = "🏆 <b>ТИТУЛЫ ХЭЛЛОУИНА</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    if note:
        text += f"{note}\n\n"
    text += f"💰 Твой баланс: <b>{_fmt(coins)}</b> 🪙\n🎖 Текущий титул: <b>{current}</b>\n\nВыбери титул:"
    return text

def halloween_titles_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, (name, price) in HALLOWEEN_TITLES.items():
        markup.add(types.InlineKeyboardButton(f"{name} — {price:,} 🪙".replace(',', ' '), callback_data=f"buy_title_{key}"))
    markup.add(types.InlineKeyboardButton("⬅ Назад", callback_data="shop"))
    return markup

def buy_halloween_title(user_id, title_key):
    item = HALLOWEEN_TITLES.get(title_key)
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
        halloween_db.record_title(user_id, title_key, price)  # запись о покупке — в базу события
    except Exception as e:
        print(f"[Halloween] Не удалось записать покупку титула: {e}")
    return True, f"🏆 Титул {name} куплен и установлен!"

def halloween_titles_reply():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    for name, price in HALLOWEEN_TITLES.values():
        markup.add(types.KeyboardButton(f"🏆 {name} — {price:,} 🪙".replace(',', ' ')))
    markup.add(types.KeyboardButton("⬅ Магазин"))
    return markup

def shop_mune():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎁 Кейсы", callback_data="cases"),
        types.InlineKeyboardButton("🏆 Титулы", callback_data="halloween_titles"),
        types.InlineKeyboardButton('⭐ Валюта за Stars', callback_data="buy_coins")
    )
    markup.add(
        types.InlineKeyboardButton('⬅ Назад', callback_data='back')
    )
    return markup

def stars_shop_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton('💰 10 000 000 монет — 100 ⭐', callback_data='stars_buy_coins_10m'),
        types.InlineKeyboardButton('🍬 25 конфет — 50 ⭐', callback_data='stars_buy_candies_25'),
        types.InlineKeyboardButton('⭐ Прокачать до 20 уровня — 150 ⭐', callback_data='stars_buy_level_20'),
        types.InlineKeyboardButton('⬅ Назад', callback_data='shop')
    )
    return markup

def send_stars_invoice(call, product_key):
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
        types.InlineKeyboardButton("🔐 Взлом замка", callback_data="game_lock"),
        types.InlineKeyboardButton("🗝️ Испытание ключей", callback_data="game_keys")
    )
    markup.add(
        types.InlineKeyboardButton("👻 Охота на тень", callback_data="game_shadow"),
        types.InlineKeyboardButton("🧪 Ведьмино зелье", callback_data="game_potion")
    )
    markup.add(types.InlineKeyboardButton("🎃 Тыквенный выбор", callback_data="game_pumpkin"))
    markup.add(types.InlineKeyboardButton("❌⭕ Крестики-нолики", callback_data="game_ttt"))
    markup.add(types.InlineKeyboardButton("⬅️ Главное меню", callback_data="back"))
    return markup

def game_mune_reply():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton("🔐 Взлом замка"), types.KeyboardButton("🗝️ Испытание ключей"))
    markup.add(types.KeyboardButton("👻 Охота на тень"), types.KeyboardButton("🧪 Ведьмино зелье"))
    markup.add(types.KeyboardButton("🎃 Тыквенный выбор"), types.KeyboardButton("❌⭕ Крестики-нолики"))
    markup.add(types.KeyboardButton("⬅ Главное меню"))
    return markup

def game_menu_markup(user_id):
    """Меню игр в том виде кнопок, который выбран у пользователя."""
    kb_type, _, _ = get_user_settings(user_id)
    return game_mune_reply() if kb_type == 'reply' else game_mune()

def game_action_reply(action=None):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    if action == "lock":
        markup.add(types.KeyboardButton("🛑 Выйти из игры"), types.KeyboardButton("⬅ Игры"))
    elif action == "keys":
        markup.add(types.KeyboardButton("🗝️ Ключ 1"), types.KeyboardButton("🗝️ Ключ 2"))
        markup.add(types.KeyboardButton("🗝️ Ключ 3"), types.KeyboardButton("🗝️ Ключ 4"))
        markup.add(types.KeyboardButton("🛑 Выйти из игры"))
    elif action == "shadow":
        markup.add(types.KeyboardButton("🚪 Комната 1"), types.KeyboardButton("🚪 Комната 2"), types.KeyboardButton("🚪 Комната 3"))
        markup.add(types.KeyboardButton("🛑 Выйти из игры"))
    elif action == "potion":
        markup.add(types.KeyboardButton("🧪 Котёл 1"), types.KeyboardButton("🧪 Котёл 2"), types.KeyboardButton("🧪 Котёл 3"))
        markup.add(types.KeyboardButton("🛑 Выйти из игры"))
    elif action == "pumpkin":
        markup.add(types.KeyboardButton("🎃 Тыква 1"), types.KeyboardButton("🎃 Тыква 2"), types.KeyboardButton("🎃 Тыква 3"))
        markup.add(types.KeyboardButton("🎃 Тыква 4"), types.KeyboardButton("🎃 Тыква 5"))
        markup.add(types.KeyboardButton("🛑 Выйти из игры"))
    elif action == "ttt":
        buttons = [types.KeyboardButton(f"🎃 {i}") for i in range(1, 10)]
        markup.row(buttons[0], buttons[1], buttons[2])
        markup.row(buttons[3], buttons[4], buttons[5])
        markup.row(buttons[6], buttons[7], buttons[8])
        markup.add(types.KeyboardButton("🛑 Выйти из игры"))
    else:
        markup.add(types.KeyboardButton("⬅ Игры"), types.KeyboardButton("⬅ Главное меню"))
    return markup

# ============= Коллекция эмоджи: редкость и цена =============
EMOJI_DATA = {

    # ⚪ Обычные — 1 000–5 000
    "😀": {"rarity": "Обычная", "price": 1000},
    "😃": {"rarity": "Обычная", "price": 1138},
    "😄": {"rarity": "Обычная", "price": 1276},
    "😁": {"rarity": "Обычная", "price": 1414},
    "😆": {"rarity": "Обычная", "price": 1552},
    "😅": {"rarity": "Обычная", "price": 1690},
    "😂": {"rarity": "Обычная", "price": 1828},
    "🤣": {"rarity": "Обычная", "price": 1966},
    "😊": {"rarity": "Обычная", "price": 2103},
    "🙂": {"rarity": "Обычная", "price": 2241},
    "🙃": {"rarity": "Обычная", "price": 2379},
    "😉": {"rarity": "Обычная", "price": 2517},
    "😌": {"rarity": "Обычная", "price": 2655},
    "😇": {"rarity": "Обычная", "price": 2793},
    "🥰": {"rarity": "Обычная", "price": 2931},
    "😍": {"rarity": "Обычная", "price": 3069},
    "🤗": {"rarity": "Обычная", "price": 3207},
    "🤔": {"rarity": "Обычная", "price": 3345},
    "😐": {"rarity": "Обычная", "price": 3483},
    "😑": {"rarity": "Обычная", "price": 3621},
    "😶": {"rarity": "Обычная", "price": 3759},
    "🙄": {"rarity": "Обычная", "price": 3897},
    "😏": {"rarity": "Обычная", "price": 4034},
    "😴": {"rarity": "Обычная", "price": 4172},
    "🤓": {"rarity": "Обычная", "price": 4310},
    "😎": {"rarity": "Обычная", "price": 4448},
    "🤪": {"rarity": "Обычная", "price": 4586},
    "😜": {"rarity": "Обычная", "price": 4724},
    "😝": {"rarity": "Обычная", "price": 4862},
    "😛": {"rarity": "Обычная", "price": 5000},

    # 🟢 Необычные — 7 500–25 000
    "🤩": {"rarity": "Необычная", "price": 7500},
    "🥳": {"rarity": "Необычная", "price": 8103},
    "🥶": {"rarity": "Необычная", "price": 8707},
    "🥵": {"rarity": "Необычная", "price": 9310},
    "🤯": {"rarity": "Необычная", "price": 9914},
    "😱": {"rarity": "Необычная", "price": 10517},
    "😡": {"rarity": "Необычная", "price": 11121},
    "🤬": {"rarity": "Необычная", "price": 11724},
    "🥺": {"rarity": "Необычная", "price": 12328},
    "😭": {"rarity": "Необычная", "price": 12931},
    "😤": {"rarity": "Необычная", "price": 13534},
    "🫡": {"rarity": "Необычная", "price": 14138},
    "🫠": {"rarity": "Необычная", "price": 14741},
    "🫣": {"rarity": "Необычная", "price": 15345},
    "🫢": {"rarity": "Необычная", "price": 15948},
    "🤫": {"rarity": "Необычная", "price": 16552},
    "🤭": {"rarity": "Необычная", "price": 17155},
    "🧐": {"rarity": "Необычная", "price": 17759},
    "🤠": {"rarity": "Необычная", "price": 18362},
    "😮": {"rarity": "Необычная", "price": 18966},
    "😲": {"rarity": "Необычная", "price": 19569},
    "😳": {"rarity": "Необычная", "price": 20172},
    "😨": {"rarity": "Необычная", "price": 20776},
    "😰": {"rarity": "Необычная", "price": 21379},
    "😥": {"rarity": "Необычная", "price": 21983},
    "😓": {"rarity": "Необычная", "price": 22586},
    "😞": {"rarity": "Необычная", "price": 23190},
    "😔": {"rarity": "Необычная", "price": 23793},
    "😟": {"rarity": "Необычная", "price": 24397},
    "😬": {"rarity": "Необычная", "price": 25000},

    # 🔵 Редкие — 35 000–100 000
    "👻": {"rarity": "Редкая", "price": 35000},
    "👽": {"rarity": "Редкая", "price": 36912},
    "🤖": {"rarity": "Редкая", "price": 38824},
    "🎃": {"rarity": "Редкая", "price": 40735},
    "😺": {"rarity": "Редкая", "price": 42647},
    "😸": {"rarity": "Редкая", "price": 44559},
    "😹": {"rarity": "Редкая", "price": 46471},
    "😻": {"rarity": "Редкая", "price": 48382},
    "😼": {"rarity": "Редкая", "price": 50294},
    "🙀": {"rarity": "Редкая", "price": 52206},
    "😿": {"rarity": "Редкая", "price": 54118},
    "😾": {"rarity": "Редкая", "price": 56029},
    "🐶": {"rarity": "Редкая", "price": 57941},
    "🐱": {"rarity": "Редкая", "price": 59853},
    "🦊": {"rarity": "Редкая", "price": 61765},
    "🐻": {"rarity": "Редкая", "price": 63676},
    "🐼": {"rarity": "Редкая", "price": 65588},
    "🐨": {"rarity": "Редкая", "price": 67500},
    "🐯": {"rarity": "Редкая", "price": 69412},
    "🦁": {"rarity": "Редкая", "price": 71324},
    "🐵": {"rarity": "Редкая", "price": 73235},
    "🙈": {"rarity": "Редкая", "price": 75147},
    "🙉": {"rarity": "Редкая", "price": 77059},
    "🙊": {"rarity": "Редкая", "price": 78971},
    "🐸": {"rarity": "Редкая", "price": 80882},
    "🐷": {"rarity": "Редкая", "price": 82794},
    "🐮": {"rarity": "Редкая", "price": 84706},
    "🐹": {"rarity": "Редкая", "price": 86618},
    "🐰": {"rarity": "Редкая", "price": 88529},
    "🐭": {"rarity": "Редкая", "price": 90441},
    "🐲": {"rarity": "Редкая", "price": 92353},
    "🦋": {"rarity": "Редкая", "price": 94265},
    "🐝": {"rarity": "Редкая", "price": 96176},
    "🦂": {"rarity": "Редкая", "price": 98088},
    "🐙": {"rarity": "Редкая", "price": 100000},

    # 🟦 Очень редкие — 125 000–300 000
    "🦈": {"rarity": "Очень редкая", "price": 125000},
    "🐊": {"rarity": "Очень редкая", "price": 130303},
    "🦖": {"rarity": "Очень редкая", "price": 135606},
    "🦕": {"rarity": "Очень редкая", "price": 140909},
    "🌈": {"rarity": "Очень редкая", "price": 146212},
    "🌙": {"rarity": "Очень редкая", "price": 151515},
    "⭐": {"rarity": "Очень редкая", "price": 156818},
    "🌟": {"rarity": "Очень редкая", "price": 162121},
    "✨": {"rarity": "Очень редкая", "price": 167424},
    "⚡": {"rarity": "Очень редкая", "price": 172727},
    "🔥": {"rarity": "Очень редкая", "price": 178030},
    "❄️": {"rarity": "Очень редкая", "price": 183333},
    "🌊": {"rarity": "Очень редкая", "price": 188636},
    "☄️": {"rarity": "Очень редкая", "price": 193939},
    "☀️": {"rarity": "Очень редкая", "price": 199242},
    "🌑": {"rarity": "Очень редкая", "price": 204545},
    "🌕": {"rarity": "Очень редкая", "price": 209848},
    "🌞": {"rarity": "Очень редкая", "price": 215152},
    "🌚": {"rarity": "Очень редкая", "price": 220455},
    "🌍": {"rarity": "Очень редкая", "price": 225758},
    "🌎": {"rarity": "Очень редкая", "price": 231061},
    "🌏": {"rarity": "Очень редкая", "price": 236364},
    "🌀": {"rarity": "Очень редкая", "price": 241667},
    "🌪️": {"rarity": "Очень редкая", "price": 246970},
    "🌋": {"rarity": "Очень редкая", "price": 252273},
    "🌠": {"rarity": "Очень редкая", "price": 257576},
    "🪐": {"rarity": "Очень редкая", "price": 262879},
    "🍀": {"rarity": "Очень редкая", "price": 268182},
    "🌸": {"rarity": "Очень редкая", "price": 273485},
    "🌺": {"rarity": "Очень редкая", "price": 278788},
    "🌹": {"rarity": "Очень редкая", "price": 284091},
    "🌻": {"rarity": "Очень редкая", "price": 289394},
    "🍁": {"rarity": "Очень редкая", "price": 294697},
    "🍂": {"rarity": "Очень редкая", "price": 300000},

    # 🟣 Эпические — 400 000–800 000
    "👑": {"rarity": "Эпическая", "price": 400000},
    "💎": {"rarity": "Эпическая", "price": 411765},
    "💠": {"rarity": "Эпическая", "price": 423529},
    "🔮": {"rarity": "Эпическая", "price": 435294},
    "🪄": {"rarity": "Эпическая", "price": 447059},
    "🧿": {"rarity": "Эпическая", "price": 458824},
    "⚜️": {"rarity": "Эпическая", "price": 470588},
    "🏆": {"rarity": "Эпическая", "price": 482353},
    "🥇": {"rarity": "Эпическая", "price": 494118},
    "🎖️": {"rarity": "Эпическая", "price": 505882},
    "💰": {"rarity": "Эпическая", "price": 517647},
    "💵": {"rarity": "Эпическая", "price": 529412},
    "🤑": {"rarity": "Эпическая", "price": 541176},
    "🎰": {"rarity": "Эпическая", "price": 552941},
    "🎲": {"rarity": "Эпическая", "price": 564706},
    "🃏": {"rarity": "Эпическая", "price": 576471},
    "♠️": {"rarity": "Эпическая", "price": 588235},
    "♥️": {"rarity": "Эпическая", "price": 600000},
    "♦️": {"rarity": "Эпическая", "price": 611765},
    "♣️": {"rarity": "Эпическая", "price": 623529},
    "🗡️": {"rarity": "Эпическая", "price": 635294},
    "⚔️": {"rarity": "Эпическая", "price": 647059},
    "🛡️": {"rarity": "Эпическая", "price": 658824},
    "🏹": {"rarity": "Эпическая", "price": 670588},
    "🔱": {"rarity": "Эпическая", "price": 682353},
    "🪓": {"rarity": "Эпическая", "price": 694118},
    "🔨": {"rarity": "Эпическая", "price": 705882},
    "💣": {"rarity": "Эпическая", "price": 717647},
    "🧨": {"rarity": "Эпическая", "price": 729412},
    "🚀": {"rarity": "Эпическая", "price": 741176},
    "🛸": {"rarity": "Эпическая", "price": 752941},
    "🌌": {"rarity": "Эпическая", "price": 764706},
    "🏰": {"rarity": "Эпическая", "price": 776471},
    "🏯": {"rarity": "Эпическая", "price": 788235},
    "🗿": {"rarity": "Эпическая", "price": 800000},

    # 🟠 Легендарные — 1 000 000–2 500 000
    "🐉": {"rarity": "Легендарная", "price": 1000000},
    "🦅": {"rarity": "Легендарная", "price": 1078947},
    "🦚": {"rarity": "Легендарная", "price": 1157895},
    "🦄": {"rarity": "Легендарная", "price": 1236842},
    "🧞": {"rarity": "Легендарная", "price": 1315789},
    "🧜": {"rarity": "Легендарная", "price": 1394737},
    "🧚": {"rarity": "Легендарная", "price": 1473684},
    "🧝": {"rarity": "Легендарная", "price": 1552632},
    "🧟": {"rarity": "Легендарная", "price": 1631579},
    "👹": {"rarity": "Легендарная", "price": 1710526},
    "👺": {"rarity": "Легендарная", "price": 1789474},
    "👿": {"rarity": "Легендарная", "price": 1868421},
    "😈": {"rarity": "Легендарная", "price": 1947368},
    "💀": {"rarity": "Легендарная", "price": 2026316},
    "☠️": {"rarity": "Легендарная", "price": 2105263},
    "👁️": {"rarity": "Легендарная", "price": 2184211},
    "👁️‍🗨️": {"rarity": "Легендарная", "price": 2263158},
    "🕳️": {"rarity": "Легендарная", "price": 2342105},
    "🩸": {"rarity": "Легендарная", "price": 2421053},
    "🖤": {"rarity": "Легендарная", "price": 2500000},

    # 🔴 Мифические — 3 000 000–5 000 000
    "❤️": {"rarity": "Мифическая", "price": 3000000},
    "🧡": {"rarity": "Мифическая", "price": 3142857},
    "💛": {"rarity": "Мифическая", "price": 3285714},
    "💚": {"rarity": "Мифическая", "price": 3428571},
    "💙": {"rarity": "Мифическая", "price": 3571429},
    "💜": {"rarity": "Мифическая", "price": 3714286},
    "🩷": {"rarity": "Мифическая", "price": 3857143},
    "🩵": {"rarity": "Мифическая", "price": 4000000},
    "🤍": {"rarity": "Мифическая", "price": 4142857},
    "🤎": {"rarity": "Мифическая", "price": 4285714},
    "💖": {"rarity": "Мифическая", "price": 4428571},
    "💗": {"rarity": "Мифическая", "price": 4571429},
    "💓": {"rarity": "Мифическая", "price": 4714286},
    "💞": {"rarity": "Мифическая", "price": 4857143},
    "💕": {"rarity": "Мифическая", "price": 5000000},
}

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
    """Сообщает продавцу, что его эмодзи купили (если у него включены уведомления)."""
    try:
        if get_user_settings(seller_id)[1] != 1:
            return
        cursor = conn.cursor()
        cursor.execute("SELECT username, first_name FROM users WHERE user_id = ?", (buyer_id,))
        row = cursor.fetchone()
        buyer = market_seller_name(row[0], row[1]) if row else "Игрок"
        cursor.execute("SELECT COALESCE(coins, 0) FROM users WHERE user_id = ?", (seller_id,))
        bal = cursor.fetchone()
        balance = int(bal[0]) if bal else 0
        bot.send_message(
            seller_id,
            f"💰 <b>Твой эмодзи купили!</b>\n\n"
            f"{emoji} — продан за <b>{_fmt(price)}</b> 🪙\n"
            f"👤 Покупатель: {buyer}\n\n"
            f"💼 Твой баланс: <b>{_fmt(balance)}</b> 🪙",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[MARKET NOTIFY ERROR] {e}")

def market_seller_name(username, first_name):
    if username:
        return '@' + username.lstrip('@')
    return first_name or 'Игрок'


def show_market(chat_id, message_id, user_id, page=1):
    lots, total = get_market_lots(page)
    total_pages = max(1, (total + MARKET_PAGE_SIZE - 1) // MARKET_PAGE_SIZE)
    page = min(max(1, page), total_pages)

    # Если страница оказалась пустой после удаления последнего лота — показываем последнюю.
    if not lots and page > 1:
        page -= 1
        lots, total = get_market_lots(page)
        total_pages = max(1, (total + MARKET_PAGE_SIZE - 1) // MARKET_PAGE_SIZE)

    cursor = conn.cursor()
    cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0

    text = (
        "🏪 <b>РЫНОК ЭМОДЗИ</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💰 Твой баланс: <b>{balance}</b> 🪙\n\n"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)

    if not lots:
        text += "📭 <b>Рынок пока пуст.</b>\n\n"
        text += "Выставь эмодзи из своего инвентаря, чтобы он появился здесь."
    else:
        for lot_id, seller_id, emoji, price, username, first_name in lots:
            rarity = get_emoji_rarity(emoji)
            icon = get_rarity_icon(rarity)
            seller = market_seller_name(username, first_name)

            text += (
                f"{emoji} <b>{price}</b> 🪙\n"
                f"{icon} {rarity} • 👤 {seller}\n\n"
            )

            if seller_id == user_id:
                markup.add(
                    types.InlineKeyboardButton(
                        f"❌ Снять {emoji} • {price} 🪙",
                        callback_data=f"market_cancel_{lot_id}"
                    )
                )
            else:
                markup.add(
                    types.InlineKeyboardButton(
                        f"🛒 Купить {emoji} • {price} 🪙",
                        callback_data=f"market_buy_{lot_id}"
                    )
                )

    nav = []
    if page > 1:
        nav.append(types.InlineKeyboardButton("◀️", callback_data=f"market_page_{page - 1}"))
    nav.append(types.InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="ignore_click"))
    if page < total_pages:
        nav.append(types.InlineKeyboardButton("▶️", callback_data=f"market_page_{page + 1}"))
    markup.row(*nav)

    markup.add(
        types.InlineKeyboardButton("📦 Мои лоты", callback_data="market_my"),
        types.InlineKeyboardButton("🔄 Обновить", callback_data=f"market_page_{page}")
    )
    markup.add(types.InlineKeyboardButton("🔙 В меню", callback_data="back"))

    try:
        bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    except Exception:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")


def show_my_market_lots(chat_id, message_id, user_id):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT lot_id, item_value, price
        FROM auction
        WHERE seller_id = ? AND item_type = 'emoji'
        ORDER BY lot_id DESC
    """, (user_id,))
    lots = cursor.fetchall()

    text = "📦 <b>МОИ ЛОТЫ</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    if not lots:
        text += "📭 У тебя нет выставленных лотов."
    else:
        for lot_id, emoji, price in lots:
            rarity = get_emoji_rarity(emoji)
            text += f"{emoji} • {rarity} • <b>{price}</b> 🪙\n"
            markup.add(types.InlineKeyboardButton(
                f"❌ Снять {emoji} • {price} 🪙",
                callback_data=f"market_cancel_{lot_id}"
            ))

    markup.add(types.InlineKeyboardButton("🏪 Назад на рынок", callback_data="market"))
    markup.add(types.InlineKeyboardButton("🔙 В меню", callback_data="back"))

    bot.edit_message_text(
        text,
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=markup,
        parse_mode="HTML"
    )

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
    else: text="🎒 <b>Твой инвентарь пуст!</b>\n\nИграй и открывай Жуткие сундуки, чтобы собирать эмоджи."
    markup.add(types.InlineKeyboardButton('⬅️ Назад',callback_data='back'))
    try: bot.edit_message_text(text,chat_id=chat_id,message_id=message_id,reply_markup=markup,parse_mode="HTML")
    except Exception: pass

# ============ Обработчики команд ==============
@bot.message_handler(commands=['start'])
def start_bot(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    reason = check_ban(user_id)

    if openbot_id.is_globally_banned(user_id):
        bot.reply_to(
            message,
            "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети."
        )
        return

    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return

    openbot_id.create_id(user_id, first_name)
    openbot_id.register_bot_activity(user_id, "Random_bot")
    create_user(user_id, username, first_name)

    # Проверяем, какой тип клавиатуры выбрал пользователь
    kb_type = get_user_settings(user_id)[0]

    if kb_type == "reply":
        # Обычные кнопки снизу
        send_main_reply_menu(
            message.chat.id,
            first_name,
            (
                f"🎲 <b>RANDOM BOT</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👋 Привет, <b>{html.escape(first_name)}</b>!\n\n"
                f"🕯️ Добро пожаловать в мир Жутких Игр.\n"
                f"🎁 Открывай кейсы • 🪙 торгуй • 👻 играй • 💎 собирай редкие эмодзи\n\n"
                f"👇 <b>Главное меню:</b>"
            )
        )

    else:
        # Inline-кнопки
        bot.send_message(
            message.chat.id,
            f"👋 Привет, {first_name}\nДобро пожаловать!",
            reply_markup=main_mune()
        )

@bot.message_handler(commands=['help'])
def bot_help(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    
    text = """Доступные команды:
/start - запуск бота
/help - список команд
/sell_emoji - продать эмодзи на аукцион
/id_profile - открыть глобальный аккаунт
/game_stop - остановить игру
/bio - изменить био в глобальном аккаунте
/feedback - оставить отзыв разработчикам

Административные команды:
/ban - забанить пользователя
/unban - разбанить пользователя
/sendall - рассылка сообщения всем
/give_coins - выдать монеты
/take_coins - забрать монеты
/level_up - изменить уровень игрока
/gift - подарить предмет
/id_ban - глобальный бан ID
/id_unban - глобальный разбан ID
/id_freeze - заморозка ID
/id_unfreeze - разморозка ID
/get_status - проверить статус игрока

<i>Обновлено 2026 года</i>"""
    msg = bot.send_message(message.chat.id, 'Загрузка...')
    bot.edit_message_text(text, message_id=msg.message_id, chat_id=message.chat.id, parse_mode="HTML")

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

@bot.message_handler(commands=['ban'])
def ban_user(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot_id.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
    
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(uid):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Формат: /ban @username [причина]")
        return
    target_username = parts[1].replace("@", "").strip().lower()
    reason_text = parts[2] if len(parts) > 2 else "Без причины"
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, status FROM users WHERE username = ?", (target_username,))
    result = cursor.fetchone()
    if result:
        target_id, current_status = result[0], result[1]
        if current_status in ALLOWED_ROLES:
            bot.reply_to(message, f"⛔ Нельзя забанить {STATUS.get(current_status, current_status)}!")
        elif current_status == 'banned':
            bot.reply_to(message, f"⚠️ @{target_username} уже забанен.")
        else:
            cursor.execute("UPDATE users SET status = 'banned', ban_reason = ? WHERE user_id = ?", (reason_text, target_id))
            conn.commit()
            bot.send_message(message.chat.id, f"✅ @{target_username} забанен!\nПричина: {reason_text}")
            try:
                bot.send_message(target_id, f"🚫 Вы заблокированы!\nПричина: {reason_text}")
            except:
                pass
    else:
        bot.reply_to(message, f"❌ Пользователь @{target_username} не найден.")

@bot.message_handler(commands=['unban'])
def unban_by_username(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot_id.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
    
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(uid):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Формат: /unban @username")
        return
    target_username = parts[1].replace("@", "").strip().lower()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, status FROM users WHERE username = ?", (target_username,))
    result = cursor.fetchone()
    if result:
        target_id, current_status = result[0], result[1]
        if current_status != 'banned':
            bot.reply_to(message, f"❓ Пользователь @{target_username} не забанен.")
        else:
            cursor.execute("UPDATE users SET status = 'user', ban_reason = NULL WHERE user_id = ?", (target_id,))
            conn.commit()
            bot.send_message(message.chat.id, f"✅ Пользователь @{target_username} разбанен!")
            try:
                bot.send_message(target_id, "🔓 Ваш доступ восстановлен!")
            except:
                pass
    else:
        bot.reply_to(message, f"❌ Пользователь @{target_username} не найден.")

@bot.message_handler(commands=['sendall'])
def send_all(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot_id.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 2):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 2 ур.")
        return
    
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
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
                # Отключаем уведомления в БД, чтобы больше не пытаться ему писать
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
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
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
    
    if not openbot_id.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
    
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
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
    
    if not openbot_id.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
    
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
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
    
    if not openbot_id.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
    
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
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

@bot.message_handler(commands=['id_ban'])
def id_ban(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot_id.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
    
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(message.from_user.id):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Формат: /id_ban @username")
        return
    username = parts[1].replace("@", "").lower()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
    res = cursor.fetchone()
    if not res:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден.")
        return
    data = openbot_id.get_id(res[0])
    if not data:
        bot.reply_to(message, f"❌ У @{username} нет OpenbotAI ID.")
        return
    if data[3] == "banned":
        bot.reply_to(message, f"⚠️ @{username} уже забанен в ID!")
        return
    openbot_id.set_status(res[0], "banned")
    bot.reply_to(message, f"☠️ ID пользователя @{username} забанен!")
    try:
        bot.send_message(res[0], "☠️ Ваш OpenbotAI ID был забанен!")
    except:
        pass

@bot.message_handler(commands=['id_unban'])
def id_unban(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot_id.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
    
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(message.from_user.id):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Формат: /id_unban @username")
        return
    username = parts[1].replace("@", "").lower()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
    res = cursor.fetchone()
    if not res:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден.")
        return
    data = openbot_id.get_id(res[0])
    if not data:
        bot.reply_to(message, f"❌ У @{username} нет OpenbotAI ID.")
        return
    target_status = str(data[6]).strip().lower() if data[6] else "user"
    if target_status != "banned":
        bot.reply_to(message, f"⚠️ @{username} не забанен в ID!")
        return
    
    openbot_id.set_status(res[0], "user")
    bot.reply_to(message, f"✅ ID пользователя @{username} разбанен!")
    try:
        bot.send_message(res[0], "✅ Ваш OpenbotAI ID был разбанен!")
    except:
        pass

@bot.message_handler(commands=['id_freeze'])
def id_freeze(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot_id.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
    
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(message.from_user.id):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Формат: /id_freeze @username")
        return
    username = parts[1].replace("@", "").lower()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
    res = cursor.fetchone()
    if not res:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден.")
        return
    data = openbot_id.get_id(res[0])
    if not data:
        bot.reply_to(message, f"❌ У @{username} нет OpenbotAI ID.")
        return
    if data[3] == "frozen":
        bot.reply_to(message, f"⚠️ @{username} уже заморожен!")
        return
    if data[3] == "banned":
        bot.reply_to(message, f"⚠️ @{username} забанен, сначала разбань!")
        return
    openbot_id.set_status(res[0], "frozen")
    bot.reply_to(message, f"❄️ ID пользователя @{username} заморожен!")
    try:
        bot.send_message(res[0], "❄️ Ваш OpenbotAI ID был заморожен!")
    except:
        pass

@bot.message_handler(commands=['id_unfreeze'])
def id_unfreeze(message):
    uid = message.from_user.id
    reason = check_ban(uid)

    if not openbot_id.check_access(uid, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return

    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Формат: /id_unfreeze @username")
        return
    username = parts[1].replace("@", "").lower()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
    res = cursor.fetchone()
    if not res:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден.")
        return
    target_id = res[0]

    if not openbot_id.get_id(target_id):
        bot.reply_to(message, f"❌ У @{username} нет OpenbotAI ID.")
        return

    # было: data[3] != "frozen"  (data[3] — эмодзи, а не статус)
    if openbot_id.get_status(target_id) != "frozen":
        bot.reply_to(message, f"⚠️ @{username} не заморожен!")
        return

    openbot_id.set_status(target_id, "user")
    bot.reply_to(message, f"✅ ID пользователя @{username} разморожен!")
    try:
        bot.send_message(target_id, "✅ Ваш OpenbotAI ID был разморожен!")
    except Exception:
        pass

@bot.message_handler(commands=['level_up'])
def cmd_level_up(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot_id.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
    
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
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
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
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
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
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
    
    openbot_id.update_bio(uid, new_bio)
    bot.reply_to(message, f"✅ Био обновлено:\n`{new_bio}`", parse_mode='Markdown')

@bot.message_handler(commands=['id_profile'])
def id_profile(message):
    uid, cid = message.from_user.id, message.chat.id
    global_data = openbot_id.get_id(uid)
    reason = check_ban(uid)

    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return

    if global_data:
        g_name = global_data[2]
        g_tag = global_data[5] or "Не установлен"
        g_bio = global_data[8] or "Не установлена"
        g_data = global_data[7]
        
        bots_list = openbot_id.get_active_bots(uid)
        g_active_bot = ", ".join(bots_list) if bots_list else "Ни в каких"
        g_status = openbot_id.ROLE.get(global_data[6], "👤 Игрок")
            
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

def get_profile_text(user_id):
    user = get_user(user_id)
    global_data = openbot_id.get_id(user_id)

    if global_data:
        g_name = global_data[2]
        equipped = get_equipped_emoji(user_id) if user else ""
        g_tag = global_data[5] or "Не установлен"

        full_name = f"{equipped} {g_name}".strip()
    else:
        full_name = user[2] if user else "Игрок"
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
🍬 <b>Конфеты:</b> {get_candies(user_id)} 🍬
━━━━━━━━━━━━━━━━━━
"""

    return profile_text

@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id, uid = message.from_user.id
    user = get_user(user_id)
    
    reason = check_ban(uid)

    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
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
        parse_mode="HTML"
    )

@bot.message_handler(commands=['MODE_false'])
def mode_false(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot_id.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return

    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return


    set_maintenance(False)   # в БД: maintenance 1 -> 0
    bot.reply_to(message, "🟢 Режим обслуживания отключен (maintenance = 0).")

@bot.message_handler(commands=['MODE_true'])
def mode_tre(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    
    if not openbot_id.check_access(message.from_user.id, ("developer", "tester", "admin", "owner"), 1):
        bot.reply_to(message, "⛔ Нужен статус developer/tester/admin от 1 ур.")
        return
 
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
 
    set_maintenance(True)    # в БД: maintenance 0 -> 1
    bot.reply_to(message, "🟠 Режим обслуживания включен (maintenance = 1).")
 

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

# ======================================================================
# 🎲 РАНДОМ-МИР — то, чего нет в Master Bot
#   • 🎲 Событие дня (меняется каждый день, одно для всех)
#   • 🎁 Подарок дня (случайная награда раз в сутки)
#   • 🏚 Дом с привидениями (здание: копит конфеты, улучшается за монеты)
#   • 🏆 Хэллоуинские достижения
# ======================================================================
def rnd_init_tables():
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS rnd_house (user_id INTEGER PRIMARY KEY, level INTEGER DEFAULT 0, last_collect REAL DEFAULT 0)")
    cur.execute("CREATE TABLE IF NOT EXISTS rnd_stats (user_id INTEGER, stat TEXT, value INTEGER DEFAULT 0, PRIMARY KEY (user_id, stat))")
    cur.execute("CREATE TABLE IF NOT EXISTS rnd_ach (user_id INTEGER, ach_key TEXT, PRIMARY KEY (user_id, ach_key))")
    cur.execute("CREATE TABLE IF NOT EXISTS rnd_gift (user_id INTEGER PRIMARY KEY, last_day TEXT)")
    conn.commit()

rnd_init_tables()

def _fmt(n):
    return f"{int(n):,}".replace(",", " ")

# ---------- 🎲 Событие дня ----------
RND_EVENTS = {
    "sale": ("🏷 Распродажа у призрака", "Жуткий сундук стоит всего 3 🍬."),
    "full_moon": ("🌕 Полнолуние", "Дом с привидениями производит в 2 раза больше конфет."),
    "lucky_gift": ("🎁 Щедрый призрак", "Подарок дня удваивается."),
}

def get_daily_event():
    """Одно и то же событие для всех игроков в течение суток."""
    day = datetime.now().strftime("%Y-%m-%d")
    return random.Random("rnd-event-" + day).choice(sorted(RND_EVENTS))

def daily_event_text():
    name, desc = RND_EVENTS[get_daily_event()]
    return f"{name}\n<i>{desc}</i>"

# ---------- Статистика и достижения ----------
def rnd_stat_inc(user_id, stat, n=1):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO rnd_stats (user_id, stat, value) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, stat) DO UPDATE SET value = value + ?",
        (user_id, stat, n, n)
    )
    conn.commit()

def rnd_value(user_id, stat):
    cur = conn.cursor()
    if stat == "house_level":
        cur.execute("SELECT COALESCE(level, 0) FROM rnd_house WHERE user_id = ?", (user_id,))
    else:
        cur.execute("SELECT COALESCE(value, 0) FROM rnd_stats WHERE user_id = ? AND stat = ?", (user_id, stat))
    row = cur.fetchone()
    return int(row[0]) if row else 0

# (ключ, название, описание, статистика, нужно, тип награды, размер награды)
RND_ACHIEVEMENTS = [
    ("first_win",   "🎃 Первая победа",       "Выиграй любую хэллоуинскую игру",   "games_won",      1,  "candies", 1),
    ("lock_master", "🔐 Взломщик замков",     "Взломай замок 5 раз",               "lock_wins",      5,  "candies", 5),
    ("sweet_tooth", "🍬 Сладкоежка",          "Заработай 50 конфет",               "candies_earned", 50, "coins",   500),
    ("chest_hunter","🕯️ Охотник за сундуками", "Открой Жуткий сундук 5 раз",       "chests_opened",  5,  "coins",   1000),
    ("landlord",    "🏚 Хозяин дома",         "Улучши Дом с привидениями до 3 ур.", "house_level",    3,  "coins",   2000),
    ("ghost_pet",   "👻 Любимчик призрака",   "Забери подарок дня 7 раз",          "gifts_claimed",  7,  "candies", 10),
]

def check_achievements(user_id):
    """Выдаёт новые достижения, присылает уведомление. Награды пишутся напрямую в БД."""
    cur = conn.cursor()
    cur.execute("SELECT ach_key FROM rnd_ach WHERE user_id = ?", (user_id,))
    have = {r[0] for r in cur.fetchall()}
    unlocked = []
    candy_rewards = []
    for key, name, desc, stat, need, rtype, ramount in RND_ACHIEVEMENTS:
        if key in have or rnd_value(user_id, stat) < need:
            continue
        cur.execute("INSERT OR IGNORE INTO rnd_ach (user_id, ach_key) VALUES (?, ?)", (user_id, key))
        if rtype == "candies":
            candy_rewards.append((key, ramount))  # конфеты выдаются в базе события — после commit
            reward = f"🍬 +{ramount}"
        else:
            cur.execute("UPDATE users SET coins = COALESCE(coins, 0) + ? WHERE user_id = ?", (ramount, user_id))
            reward = f"💰 +{_fmt(ramount)}"
        unlocked.append((name, reward))
    conn.commit()
    for _ach_key, _amount in candy_rewards:
        halloween_db.add_keys(user_id, _amount, f"achievement:{_ach_key}")
    for name, reward in unlocked:
        try:
            bot.send_message(user_id, f"🏆 <b>Достижение!</b>\n\n{name}\nНаграда: {reward}", parse_mode="HTML")
        except Exception:
            pass
    return unlocked

def rnd_ach_text(user_id):
    cur = conn.cursor()
    cur.execute("SELECT ach_key FROM rnd_ach WHERE user_id = ?", (user_id,))
    have = {r[0] for r in cur.fetchall()}
    lines = [f"🏆 <b>ДОСТИЖЕНИЯ</b> ({len(have)}/{len(RND_ACHIEVEMENTS)})\n━━━━━━━━━━━━━━━━━━\n"]
    for key, name, desc, stat, need, rtype, ramount in RND_ACHIEVEMENTS:
        reward = f"🍬 {ramount}" if rtype == "candies" else f"💰 {_fmt(ramount)}"
        if key in have:
            lines.append(f"✅ <b>{name}</b>\n    {desc}")
        else:
            cur_val = min(rnd_value(user_id, stat), need)
            lines.append(f"🔒 <b>{name}</b>\n    {desc} — {cur_val}/{need}\n    Награда: {reward}")
    return "\n".join(lines)

# ---------- 🎁 Подарок дня ----------
def claim_daily_gift(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    cur = conn.cursor()
    cur.execute("SELECT last_day FROM rnd_gift WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row and row[0] == today:
        return False, "🎁 Подарок на сегодня уже забран. Приходи завтра!"

    mult = 2 if get_daily_event() == "lucky_gift" else 1
    kind = random.choice(["coins", "candies", "xp"])
    candy_gain = 0
    if kind == "coins":
        amount = random.randint(100, 1000) * mult
        cur.execute("UPDATE users SET coins = COALESCE(coins, 0) + ? WHERE user_id = ?", (amount, user_id))
        text = f"💰 +{_fmt(amount)} монет"
    elif kind == "candies":
        amount = random.randint(2, 6) * mult
        candy_gain = amount  # конфеты выдаются в базе события — после commit
        text = f"🍬 +{amount} конфет"
    else:
        amount = random.randint(50, 200) * mult
        cur.execute("UPDATE users SET XP = COALESCE(XP, 0) + ? WHERE user_id = ?", (amount, user_id))
        text = f"⭐ +{amount} XP"
    cur.execute(
        "INSERT INTO rnd_gift (user_id, last_day) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET last_day = ?",
        (user_id, today, today)
    )
    conn.commit()
    if candy_gain:
        halloween_db.add_keys(user_id, candy_gain, "daily_gift")
    if kind == "candies":
        rnd_stat_inc(user_id, "candies_earned", amount)
    rnd_stat_inc(user_id, "gifts_claimed")
    check_achievements(user_id)
    bonus = "\n🎁 Событие дня: награда удвоена!" if mult == 2 else ""
    return True, f"🎁 <b>ПОДАРОК ДНЯ</b>\n━━━━━━━━━━━━━━━━━━\n\nПризрак оставил тебе:\n{text}{bonus}"

# ---------- 🏚 Дом с привидениями ----------
HOUSE_MAX_LEVEL = 5
HOUSE_STORAGE_HOURS = 8

def house_cost(level):
    """Цена перехода с уровня level на level+1 (0 -> 1 = постройка)."""
    return 5000 * (2 ** level)

def get_house(user_id):
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(level, 0), COALESCE(last_collect, 0) FROM rnd_house WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    return (int(row[0]), float(row[1])) if row else (0, 0.0)

def house_rate(level):
    return level * (2 if get_daily_event() == "full_moon" else 1)

def house_pending(user_id):
    level, last = get_house(user_id)
    if level <= 0:
        return 0
    hours = min((time.time() - last) / 3600, HOUSE_STORAGE_HOURS)
    return int(hours * house_rate(level))

def house_collect(user_id):
    level, _ = get_house(user_id)
    if level <= 0:
        return False, "🏚 У тебя ещё нет Дома с привидениями."
    pending = house_pending(user_id)
    if pending < 1:
        return False, "⏳ Призраки ещё не накопили конфет. Загляни позже!"
    cur = conn.cursor()
    cur.execute("UPDATE rnd_house SET last_collect = ? WHERE user_id = ?", (time.time(), user_id))
    conn.commit()
    add_candies(user_id, pending, source='house')
    return True, f"🏚 Призраки принесли тебе 🍬 <b>{pending}</b> конфет!"

def house_upgrade(user_id):
    level, _ = get_house(user_id)
    if level >= HOUSE_MAX_LEVEL:
        return False, "🏚 Дом уже на максимальном уровне!"
    cost = house_cost(level)
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(coins, 0) FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row or int(row[0]) < cost:
        return False, f"❌ Не хватает монет. Нужно {_fmt(cost)} 🪙."
    # забираем накопленные конфеты, чтобы улучшение их не сбросило
    if level > 0:
        pending = house_pending(user_id)
        if pending >= 1:
            add_candies(user_id, pending, source='house')
    cur.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (cost, user_id))
    cur.execute(
        "INSERT INTO rnd_house (user_id, level, last_collect) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET level = ?, last_collect = ?",
        (user_id, level + 1, time.time(), level + 1, time.time())
    )
    conn.commit()
    check_achievements(user_id)
    verb = "построен" if level == 0 else f"улучшен до уровня {level + 1}"
    return True, f"🔨 Дом с привидениями {verb}!"

def rnd_house_text(user_id):
    level, _ = get_house(user_id)
    if level <= 0:
        return (
            "🏚 <b>ДОМ С ПРИВИДЕНИЯМИ</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            "Заброшенный дом, в котором живут призраки. Построй его — и они будут копить для тебя конфеты, "
            "даже пока ты спишь.\n\n"
            f"🔨 Цена постройки: <b>{_fmt(house_cost(0))}</b> 🪙"
        )
    rate = house_rate(level)
    pending = house_pending(user_id)
    cap = rate * HOUSE_STORAGE_HOURS
    text = (
        "🏚 <b>ДОМ С ПРИВИДЕНИЯМИ</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Уровень: <b>{level}/{HOUSE_MAX_LEVEL}</b>\n"
        f"🍬 Производство: <b>{rate}</b> в час\n"
        f"📦 Накоплено: <b>{pending}</b> из {cap}\n"
    )
    if level < HOUSE_MAX_LEVEL:
        text += f"\n🔨 Улучшение: <b>{_fmt(house_cost(level))}</b> 💰"
    else:
        text += "\n⭐ Максимальный уровень!"
    return text

# ---------- Меню «Рандом-мир» ----------
def rnd_hub_text(user_id):
    return (
        "🎲 <b>РАНДОМ-МИР</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        "🔔 <b>Событие дня:</b>\n"
        f"{daily_event_text()}\n\n"
        f"🍬 Твои конфеты: <b>{get_candies(user_id)}</b>"
    )

def rnd_hub_inline():
    m = types.InlineKeyboardMarkup(row_width=1)
    m.add(
        types.InlineKeyboardButton("🎁 Подарок дня", callback_data="rnd_gift"),
        types.InlineKeyboardButton("🏚 Дом с привидениями", callback_data="rnd_house"),
        types.InlineKeyboardButton("🏆 Достижения", callback_data="rnd_ach"),
        types.InlineKeyboardButton("⬅ Назад", callback_data="back"),
    )
    return m

def rnd_house_inline(user_id):
    level, _ = get_house(user_id)
    m = types.InlineKeyboardMarkup(row_width=1)
    if level > 0:
        m.add(types.InlineKeyboardButton("🍬 Собрать конфеты", callback_data="rnd_house_collect"))
    if level < HOUSE_MAX_LEVEL:
        m.add(types.InlineKeyboardButton("🔨 Построить" if level == 0 else "🔨 Улучшить", callback_data="rnd_house_up"))
    m.add(types.InlineKeyboardButton("⬅ Рандом-мир", callback_data="rnd_hub"))
    return m

def rnd_back_inline():
    return types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅ Рандом-мир", callback_data="rnd_hub"))

def rnd_hub_reply():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    m.row(types.KeyboardButton("🎁 Подарок дня"), types.KeyboardButton("🏚 Дом с привидениями"))
    m.row(types.KeyboardButton("🏆 Достижения"), types.KeyboardButton("⬅ Главное меню"))
    return m

def rnd_house_reply():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    m.row(types.KeyboardButton("🏚 Собрать конфеты"), types.KeyboardButton("🔨 Построить / улучшить дом"))
    m.add(types.KeyboardButton("⬅ Рандом-мир"))
    return m

def _rnd_edit(call, text, markup):
    try:
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id,
                              reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        if "not modified" not in str(e):
            print(f"[RND EDIT ERROR] {e}")

@bot.callback_query_handler(func=lambda call: bool(call.data) and call.data.startswith("rnd_"))
def handle_rnd_callback(call):
    uid = call.from_user.id
    
    reason = check_ban(uid)

    if openbot_id.is_globally_banned(uid):
        bot.answer_callback_query(call.id, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.", show_alert=True)
        return
    if reason:
        bot.answer_callback_query(call.id, f"🚫 Вы заблокированы!\nПричина: {reason}", show_alert=True)
        return

    
    if check_ban(uid) is not None:
        bot.answer_callback_query(call.id, "⛔ Ты заблокирован.", show_alert=True)
        return
    data = call.data

    if data == "rnd_hub":
        _rnd_edit(call, rnd_hub_text(uid), rnd_hub_inline())
        bot.answer_callback_query(call.id)
    elif data == "rnd_gift":
        ok, text = claim_daily_gift(uid)
        if ok:
            _rnd_edit(call, text, rnd_back_inline())
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, text, show_alert=True)
    elif data == "rnd_house":
        _rnd_edit(call, rnd_house_text(uid), rnd_house_inline(uid))
        bot.answer_callback_query(call.id)
    elif data == "rnd_house_collect":
        ok, text = house_collect(uid)
        if ok:
            _rnd_edit(call, rnd_house_text(uid), rnd_house_inline(uid))
            bot.answer_callback_query(call.id, "🍬 Конфеты собраны!")
        else:
            bot.answer_callback_query(call.id, text.replace("<b>", "").replace("</b>", ""), show_alert=True)
    elif data == "rnd_house_up":
        ok, text = house_upgrade(uid)
        if ok:
            _rnd_edit(call, rnd_house_text(uid), rnd_house_inline(uid))
            bot.answer_callback_query(call.id, text)
        else:
            bot.answer_callback_query(call.id, text, show_alert=True)
    elif data == "rnd_ach":
        _rnd_edit(call, rnd_ach_text(uid), rnd_back_inline())
        bot.answer_callback_query(call.id)
    else:
        bot.answer_callback_query(call.id)

RND_REPLY_TEXTS = {
    "🎲 Рандом-мир", "⬅ Рандом-мир", "🎁 Подарок дня", "🏚 Дом с привидениями",
    "🏚 Собрать конфеты", "🔨 Построить / улучшить дом", "🏆 Достижения",
}

@bot.message_handler(func=lambda message: bool(message.text) and message.text in RND_REPLY_TEXTS)
def handle_rnd_reply(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    t = message.text
    mark_reply_mode(uid)
    if check_ban(uid) is not None:
        return
    delete_active_game(uid)

    if t in ("🎲 Рандом-мир", "⬅ Рандом-мир"):
        bot.send_message(chat_id, rnd_hub_text(uid), reply_markup=rnd_hub_reply(), parse_mode="HTML")
    elif t == "🎁 Подарок дня":
        _, text = claim_daily_gift(uid)
        bot.send_message(chat_id, text, reply_markup=rnd_hub_reply(), parse_mode="HTML")
    elif t == "🏆 Достижения":
        bot.send_message(chat_id, rnd_ach_text(uid), reply_markup=rnd_hub_reply(), parse_mode="HTML")
    elif t == "🏚 Дом с привидениями":
        bot.send_message(chat_id, rnd_house_text(uid), reply_markup=rnd_house_reply(), parse_mode="HTML")
    elif t == "🏚 Собрать конфеты":
        _, text = house_collect(uid)
        bot.send_message(chat_id, f"{text}\n\n{rnd_house_text(uid)}", reply_markup=rnd_house_reply(), parse_mode="HTML")
    elif t == "🔨 Построить / улучшить дом":
        _, text = house_upgrade(uid)
        bot.send_message(chat_id, f"{text}\n\n{rnd_house_text(uid)}", reply_markup=rnd_house_reply(), parse_mode="HTML")


# =========== Обновленный Обработчик кнопок =============
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    uid = call.from_user.id
    cid = call.message.chat.id
    mid = call.message.message_id
    reason = check_ban(uid)
    
    if openbot_id.is_globally_banned(uid):
        bot.answer_callback_query(call.id, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.", show_alert=True)
        return
    if reason:
        bot.answer_callback_query(call.id, f"🚫 Вы заблокированы!\nПричина: {reason}", show_alert=True)
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
            "🍬 25 конфет\n"
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

    elif call.data == 'stars_buy_candies_25':
        send_stars_invoice(call, "candies_25")
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
        bot.edit_message_text("Добро пожаловать !", chat_id=user_id, message_id=call.message.message_id, reply_markup=shop_mune())
        bot.answer_callback_query(call.id)

    elif call.data == 'halloween_titles':
        bot.edit_message_text(halloween_titles_text(user_id), chat_id=cid, message_id=mid, reply_markup=halloween_titles_menu(), parse_mode="HTML")
        bot.answer_callback_query(call.id)

    elif call.data.startswith('buy_title_'):
        key = call.data[len('buy_title_'):]
        ok, msg = buy_halloween_title(user_id, key)
        bot.answer_callback_query(call.id, msg, show_alert=True)
        if ok:
            bot.edit_message_text(halloween_titles_text(user_id, msg), chat_id=cid, message_id=mid, reply_markup=halloween_titles_menu(), parse_mode="HTML")
        
    elif call.data == 'profile':
        user = get_user(user_id)
        global_data = openbot_id.get_id(user_id)
        equipped = get_equipped_emoji(user_id)

        if global_data:
            g_name = global_data[2]
            g_tag = global_data[5] or "Не установлен"
            base_name = g_name
        else:
            base_name = user[2] if user else "Игрок"
            g_tag = "Отсутствует"

        full_name = f"{equipped} {base_name}".strip()

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
🍬 <b>Конфеты:</b> {get_candies(user_id)} 🍬
━━━━━━━━━━━━━━━━━━━
"""
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
               types.InlineKeyboardButton('⚙ Настройки ID', callback_data='settings_id'),
               types.InlineKeyboardButton('⬅ В главное меню', callback_data='back')
            )
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

    elif call.data == 'spooky_chest':

        keys = get_candies(user_id)

        markup = types.InlineKeyboardMarkup(row_width=1)

        markup.add(
            types.InlineKeyboardButton(
                "🍬 Открыть сундук",
                callback_data="open_spooky_chest")
        ) 

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Назад к играм",
                callback_data="back_to_games"
            )
        )

        bot.edit_message_text(
            f"🕯️ <b>ЖУТКИЙ СУНДУК</b>\n\n"
            f"🍬 Твоих конфет: <b>{keys}</b>\n\n"
            f"Цена сундука: <b>{chest_cost()}</b> 🍬. Внутри — случайный эмодзи.\n"
            "🎲 Шансы наград скрыты — удача решает всё!",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

        bot.answer_callback_query(call.id)


    elif call.data == 'open_spooky_chest':

        result = open_spooky_chest(user_id)

        if not result:
            bot.answer_callback_query(
                call.id,
                f"❌ Нужно {chest_cost()} 🍬 конфет!",
                show_alert=True
            )
            return

        if result["coins"]:

            reward_text = (
                f"{result['emoji']} <b>{result['rarity']}</b> эмодзи "
                "уже есть у тебя.\n"
                f"💰 Вместо дубликата: +{result['coins']} монет"
            )            
        else:

            reward_text = (
                f"🎁 Тебе выпало: <b>{result['emoji']}</b>\n"
                f"⭐ Редкость: <b>{result['rarity']}</b>\n"
                "🎒 Эмодзи добавлено в инвентарь!"
            )

        keys_left = get_candies(user_id)

        markup = types.InlineKeyboardMarkup(row_width=1)

        markup.add(
            types.InlineKeyboardButton(
                "🍬 Открыть ещё",
                callback_data="open_spooky_chest"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Назад к играм",
                callback_data="back_to_games"
            )
        )

        bot.edit_message_text(
            f"🕯️ <b>ЖУТКИЙ СУНДУК ОТКРЫТ!</b>\n\n"
            f"{reward_text}\n\n"
            f"🍬 Осталось конфет: <b>{keys_left}</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

        bot.answer_callback_query(call.id)
        
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
                reply_markup=settings_menu_reply(user_id)
            )
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
            reply_markup=settings_menu(user_id)
            )
        
        bot.answer_callback_query(call.id, "Вид кнопок изменен!")

    elif call.data == 'toggle_notif':
        toggle_user_setting(user_id, 'notifications')
        _, notifications, _ = get_user_settings(user_id)
        
        msg_text = "Уведомления включены 🔔" if notifications == 1 else "Уведомления отключены 🔕"
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
        global_data = openbot_id.get_id(uid)
        
        if global_data:
            g_name = global_data[2]
            g_tag = global_data[5] or "Не установлен"
            g_bio = global_data[8] or "Не установлена"
            g_data = global_data[7]
            g_active_bot = openbot_id.get_active_bots(uid)

            num_status = openbot_id.get_user_level(user_id)
            raw_status = openbot_id.get_status(user_id)
            g_status = openbot_id.ROLE.get(raw_status, f"{raw_status}")

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
        bot.edit_message_text("🔮 <b>Выберите жуткую игру:</b>", chat_id=cid, message_id=mid, reply_markup=game_mune(), parse_mode="HTML")
        bot.answer_callback_query(call.id)

    # 1. Пророчество Ведьмы
    elif call.data == 'game_lock':
        secret = ''.join(str(random.randint(0, 9)) for _ in range(3))
        set_active_game(user_id, cid, 'lock', attempts=5, secret_code=secret)
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🛑 Выйти", callback_data="back_to_games"))
        bot.edit_message_text("🔐 <b>ВЗЛОМ ЗАМКА</b>\n━━━━━━━━━━━━━━━━━━\n\nУгадай 3-значный код.\n❤️ Попыток: <b>5</b>\n\n✍️ Отправь код сообщением.", chat_id=cid, message_id=mid, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    elif call.data == 'game_keys':
        secret = random.randint(1, 4)
        set_active_game(user_id, cid, 'keys', secret_number=secret, attempts=1)
        kb = types.InlineKeyboardMarkup(row_width=2)
        for i in range(1, 5):
            kb.add(types.InlineKeyboardButton(f"🗝️ Ключ {i}", callback_data=f"key_pick_{i}"))
        kb.add(types.InlineKeyboardButton("🛑 Выйти", callback_data="back_to_games"))
        bot.edit_message_text("🗝️ <b>ИСПЫТАНИЕ КЛЮЧЕЙ</b>\n━━━━━━━━━━━━━━━━━━\n\nТолько один из четырёх ключей открывает сундук.\nВыбирай!", chat_id=cid, message_id=mid, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    elif call.data.startswith('key_pick_'):
        game = get_active_game(user_id)
        if not game or game[0] != 'keys':
            bot.answer_callback_query(call.id, "❌ Игра уже закончена.", show_alert=True)
            return
        choice = int(call.data.rsplit('_', 1)[1])
        secret = int(game[1])
        delete_active_game(user_id)
        if choice == secret:
            add_coins(user_id, 150); add_xp(user_id, 60); add_candies(user_id, 2, source='game')
            result = "🎉 Ключ подошёл!\n\n💰 +150 монет\n⭐ +60 XP\n🍬 +2 конфеты"
        else:
            result = f"💥 Ключ не подошёл.\nПравильный ключ: <b>№{secret}</b>."
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔄 Ещё раз", callback_data="game_keys"), types.InlineKeyboardButton("⬅ Игры", callback_data="game"))
        bot.edit_message_text(f"🗝️ <b>ИСПЫТАНИЕ ЗАКОНЧЕНО</b>\n\n{result}", chat_id=cid, message_id=mid, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    elif call.data == 'game_shadow':
        secret = random.randint(1, 3)
        set_active_game(user_id, cid, 'shadow', secret_number=secret, attempts=1)
        kb = types.InlineKeyboardMarkup(row_width=3)
        for i in range(1, 4):
            kb.add(types.InlineKeyboardButton(f"🚪 {i}", callback_data=f"shadow_pick_{i}"))
        kb.add(types.InlineKeyboardButton("🛑 Выйти", callback_data="back_to_games"))
        bot.edit_message_text("👻 <b>ОХОТА НА ТЕНЬ</b>\n━━━━━━━━━━━━━━━━━━\n\nТень спряталась в одной из трёх комнат. Найди её!", chat_id=cid, message_id=mid, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    elif call.data.startswith('shadow_pick_'):
        game = get_active_game(user_id)
        if not game or game[0] != 'shadow':
            bot.answer_callback_query(call.id, "❌ Игра закончена.", show_alert=True)
            return
        choice = int(call.data.rsplit('_', 1)[1]); secret = int(game[1]); delete_active_game(user_id)
        if choice == secret:
            add_coins(user_id, 100); add_xp(user_id, 40); add_candies(user_id, 2, source='game'); result = "🎉 Ты поймал тень!\n\n💰 +100 монет\n⭐ +40 XP\n🍬 +2 конфеты"
        else:
            result = f"👻 Тень исчезла! Она была в комнате <b>№{secret}</b>."
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔄 Ещё раз", callback_data="game_shadow"), types.InlineKeyboardButton("⬅ Игры", callback_data="game"))
        bot.edit_message_text(f"👻 <b>ОХОТА ЗАКОНЧЕНА</b>\n\n{result}", chat_id=cid, message_id=mid, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    elif call.data == 'game_potion':
        secret = random.randint(1, 3)
        set_active_game(user_id, cid, 'potion', secret_number=secret, attempts=1)
        kb = types.InlineKeyboardMarkup(row_width=3)
        for i in range(1, 4):
            kb.add(types.InlineKeyboardButton(f"🧪 {i}", callback_data=f"potion_pick_{i}"))
        kb.add(types.InlineKeyboardButton("🛑 Выйти", callback_data="back_to_games"))
        bot.edit_message_text("🧪 <b>ВЕДЬМИНО ЗЕЛЬЕ</b>\n━━━━━━━━━━━━━━━━━━\n\nВ одном котле зелье удачи. Выбери его!", chat_id=cid, message_id=mid, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    elif call.data.startswith('potion_pick_'):
        game = get_active_game(user_id)
        if not game or game[0] != 'potion':
            bot.answer_callback_query(call.id, "❌ Игра закончена.", show_alert=True)
            return
        choice = int(call.data.rsplit('_', 1)[1]); secret = int(game[1]); delete_active_game(user_id)
        if choice == secret:
            add_coins(user_id, 125); add_xp(user_id, 50); add_candies(user_id, 2, source='game'); result = "✨ Зелье оказалось правильным!\n\n💰 +125 монет\n⭐ +50 XP\n🍬 +2 конфеты"
        else:
            result = f"💨 Зелье оказалось пустым. Правильный котёл: <b>№{secret}</b>."
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔄 Ещё раз", callback_data="game_potion"), types.InlineKeyboardButton("⬅ Игры", callback_data="game"))
        bot.edit_message_text(f"🧪 <b>РЕЗУЛЬТАТ</b>\n\n{result}", chat_id=cid, message_id=mid, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    elif call.data == 'game_pumpkin':
        secret = random.randint(1, 5)
        set_active_game(user_id, cid, 'pumpkin', secret_number=secret, attempts=1)
        kb = types.InlineKeyboardMarkup(row_width=3)
        for i in range(1, 6):
            kb.add(types.InlineKeyboardButton(f"🎃 {i}", callback_data=f"pumpkin_pick_{i}"))
        kb.add(types.InlineKeyboardButton("🛑 Выйти", callback_data="back_to_games"))
        bot.edit_message_text("🎃 <b>ТЫКВЕННЫЙ ВЫБОР</b>\n━━━━━━━━━━━━━━━━━━\n\nВ одной тыкве спрятан большой приз. Выбирай!", chat_id=cid, message_id=mid, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    elif call.data.startswith('pumpkin_pick_'):
        game = get_active_game(user_id)
        if not game or game[0] != 'pumpkin':
            bot.answer_callback_query(call.id, "❌ Игра закончена.", show_alert=True)
            return
        choice = int(call.data.rsplit('_', 1)[1]); secret = int(game[1]); delete_active_game(user_id)
        if choice == secret:
            add_coins(user_id, 200); add_xp(user_id, 75); add_candies(user_id, 2, source='game'); result = "🎃 Ты нашёл главный приз!\n\n💰 +200 монет\n⭐ +75 XP\n🍬 +2 конфеты"
        else:
            result = f"🎃 В этой тыкве ничего нет. Приз был в тыкве <b>№{secret}</b>."
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔄 Ещё раз", callback_data="game_pumpkin"), types.InlineKeyboardButton("⬅ Игры", callback_data="game"))
        bot.edit_message_text(f"🎃 <b>ТЫКВЕННЫЙ ВЫБОР</b>\n\n{result}", chat_id=cid, message_id=mid, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    # 2. Тыквы vs Черепа
    elif call.data == 'game_ttt':
        board_str = "0" * 9
        set_active_game(user_id, cid, 'ttt', secret_code=board_str)
        bot.edit_message_text("🎃 <b>Тыквы vs 💀 Черепа</b>\n\nТвой ход!", chat_id=cid, message_id=mid, reply_markup=build_ttt_keyboard(board_str), parse_mode="HTML")
        bot.answer_callback_query(call.id)

    elif call.data.startswith('ttt_pos_'):
        game_data = get_active_game(user_id)
        if not game_data or game_data[0] != 'ttt':
            bot.answer_callback_query(call.id, "Игра не активна!", show_alert=True)
            return
        pos = int(call.data.split('_')[2])
        board = list(game_data[3])
        if board[pos] != '0':
            bot.answer_callback_query(call.id, "Клетка занята!", show_alert=False)
            return
        board[pos] = '1'

        win_combos = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
        def check_win(b, p): return any(b[x] == b[y] == b[z] == p for x, y, z in win_combos)

        if check_win(board, '1'):
            add_coins(user_id, 40)
            add_xp(user_id, 25)
            delete_active_game(user_id)
            bot.edit_message_text("🎉 <b>Победа!</b> Тыква одолела Череп!\n💰 +40 монет, +25 XP", chat_id=cid, message_id=mid, parse_mode="HTML")
            return

        empty_indices = [i for i, x in enumerate(board) if x == '0']
        if not empty_indices:
            delete_active_game(user_id)
            bot.edit_message_text("🤝 <b>Ничья!</b>", chat_id=cid, message_id=mid, parse_mode="HTML")
            return

        bot_move = random.choice(empty_indices)
        board[bot_move] = '2'
        if check_win(board, '2'):
            delete_active_game(user_id)
            bot.edit_message_text("☠ <b>Поражение!</b> Череп победил!", chat_id=cid, message_id=mid, parse_mode="HTML")
            return

        new_board_str = "".join(board)
        update_game_state(user_id, secret_code=new_board_str)
        bot.edit_message_text("🎃 <b>Тыквы vs 💀 Черепа</b>\n\nТвой ход!", chat_id=cid, message_id=mid, reply_markup=build_ttt_keyboard(new_board_str), parse_mode="HTML")
        bot.answer_callback_query(call.id)


# ============ ОПЛАТА STARS: подтверждение и выдача товара ============
@bot.pre_checkout_query_handler(func=lambda query: True)
def handle_pre_checkout(query):
    try:
        parts = (query.invoice_payload or "").split(":")
        ok = len(parts) == 3 and parts[0] == "stars" and parts[1] in STARS_SHOP and parts[2] == str(query.from_user.id)
        if ok:
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
    elif product_key == "candies_25":
        paid_candies = 25  # конфеты выдаются в базе события — сразу после записи платежа
        text = "🍬 <b>+25 конфет</b> уже у тебя!"
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
        halloween_db.add_keys(user_id, paid_candies, "stars")
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
            "🔮 Жуткие Игры", "👤 Профиль", "🧹 Лавка Ужасов", "🎒 Инвентарь",
            "🏪 Рынок", "🍬 Жуткий сундук", "⚙️ Настройки", "⚙ Настройки",
            "⬅ Главное меню", "⬅ В главное меню",
            "🎁 Кейсы", "🏆 Титулы", "⭐ Магазин Stars", "⬅ Магазин",
            "💰 10 000 000 монет — 100 ⭐", "🍬 25 конфет — 50 ⭐",
            "⭐ Прокачать до 20 уровня — 150 ⭐",
            "🍬 Открыть Жуткий сундук",
            "⬅ Инвентарь", "◀️ Предыдущая страница", "Следующая страница ▶️",
            "📦 Мои лоты", "⬅ Рынок",
            "◀️ Предыдущая страница рынка", "Следующая страница рынка ▶️",
            "⬅ Предыдущие кейсы", "Следующие кейсы ➡",
            "🔐 Взлом замка", "🗝️ Испытание ключей", "👻 Охота на тень",
            "🧪 Ведьмино зелье", "🎃 Тыквенный выбор", "❌⭕ Крестики-нолики",
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

    if text == "🔮 Жуткие Игры":
        delete_active_game(uid)
        bot.send_message(chat_id, "🎮 <b>ЖУТКИЕ ИГРЫ</b>\n━━━━━━━━━━━━━━━━━━\n\nВыбери игру:", reply_markup=game_mune_reply(), parse_mode="HTML")
        return

    if text == "👤 Профиль":
        delete_active_game(uid)
        bot.send_message(chat_id, get_profile_text(uid), reply_markup=profile_menu_reply(), parse_mode="HTML")
        return
    
    if text == "⚙ Настройки ID":
        try:
            global_data = openbot_id.get_id(uid)
        except Exception as e:
            print(f"[REPLY SETTINGS ID] {e}")
            global_data = None

        if global_data:
            g_name = global_data[2] or "Не установлено"
            g_tag = global_data[5] or "Не установлен"
            g_bio = global_data[8] or "Не установлена"

            try:
                raw_status = openbot_id.get_status(uid)
                g_status = openbot_id.ROLE.get(
                    raw_status,
                    str(raw_status)
                )
            except Exception:
                g_status = "👤 Игрок"
    
            try:
                g_level = openbot_id.get_user_level(uid)
            except Exception:
                g_level = 1

            try:
                g_active_bot = openbot_id.get_active_bots(uid)
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
        msg = "🔔 Уведомления включены" if notifications else "🔕 Уведомления отключены"
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
        new_type = toggle_user_setting(uid, "kb_type")
        bot.send_message(chat_id, "⚙️ Настройки обновлены", reply_markup=types.ReplyKeyboardRemove())
        if new_type == "reply":
            send_main_reply_menu(chat_id, message.from_user.first_name, "⌨️ <b>Обычные кнопки включены.</b>\n\n👇 Главное меню:")
        else:
            bot.send_message(chat_id, "⌨️ <b>Inline-кнопки включены.</b>\n\n👇 Главное меню:", reply_markup=main_mune(), parse_mode="HTML")
        return

    # Магазин
    if text == "🧹 Лавка Ужасов":
        bot.send_message(chat_id, "🧹 <b>ЛАВКА УЖАСОВ</b>\n━━━━━━━━━━━━━━━━━━\n\nВыбери раздел:", reply_markup=shop_mune_reply(), parse_mode="HTML")
        return

    if text == "⬅ Магазин":
        bot.send_message(chat_id, "🧹 <b>ЛАВКА УЖАСОВ</b>", reply_markup=shop_mune_reply(), parse_mode="HTML")
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
        "🍬 25 конфет — 50 ⭐": "candies_25",
        "⭐ Прокачать до 20 уровня — 150 ⭐": "level_20",
    }
    if text in stars_map:
        send_stars_invoice_from_message(message, stars_map[text])
        return

    if text == "🏆 Титулы":
        bot.send_message(chat_id, halloween_titles_text(uid), reply_markup=halloween_titles_reply(), parse_mode="HTML")
        return

    if text.startswith("🏆 ") and " — " in text and text.endswith(" 🪙"):
        selected = text[2:].rsplit(" — ", 1)[0]
        title_key = next((k for k, (name, price) in HALLOWEEN_TITLES.items() if name == selected), None)
        if title_key:
            _, msg = buy_halloween_title(uid, title_key)
            bot.send_message(chat_id, halloween_titles_text(uid, msg), reply_markup=halloween_titles_reply(), parse_mode="HTML")
            return

    # Сундук
    if text == "🍬 Жуткий сундук":
        keys = get_candies(uid)
        bot.send_message(chat_id, f"🕯️ <b>ЖУТКИЙ СУНДУК</b>\n━━━━━━━━━━━━━━━━━━\n\n🍬 Конфет: <b>{keys}</b>\n\nСундук стоит {chest_cost()} 🍬 и выдаёт случайный приз.", reply_markup=spooky_chest_reply(), parse_mode="HTML")
        return

    if text == "🍬 Открыть Жуткий сундук":
        result = open_spooky_chest(uid)
        if result is None:
            bot.send_message(chat_id, f"❌ Нужно {chest_cost()} 🍬 конфет.", reply_markup=spooky_chest_reply())
            return
        coins = result.get("coins", 0)
        extra = f"\n💰 Компенсация: +{coins} монет" if coins else ""
        bot.send_message(chat_id, f"🎁 <b>СУНДУК ОТКРЫТ!</b>\n━━━━━━━━━━━━━━━━━━\n\n{result['emoji']} {get_rarity_icon(result['rarity'])} <b>{result['rarity']}</b>{extra}\n\n🍬 Осталось: <b>{get_candies(uid)}</b>", reply_markup=spooky_chest_reply(), parse_mode="HTML")
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

    # Запуск игр
    if text in {"🔐 Взлом замка", "🗝️ Испытание ключей", "👻 Охота на тень", "🧪 Ведьмино зелье", "🎃 Тыквенный выбор", "❌⭕ Крестики-нолики"}:
        delete_active_game(uid)
        if text == "🔐 Взлом замка":
            secret = ''.join(str(random.randint(0, 9)) for _ in range(3))
            set_active_game(uid, chat_id, "lock", attempts=5, secret_code=secret)
            bot.send_message(chat_id, "🔐 <b>ВЗЛОМ ЗАМКА</b>\n━━━━━━━━━━━━━━━━━━\n\nУгадай 3-значный код.\n❤️ Попыток: <b>5</b>\n\n✍️ Напиши код, например <code>427</code>.", parse_mode="HTML", reply_markup=game_action_reply("lock"))
        elif text == "🗝️ Испытание ключей":
            set_active_game(uid, chat_id, "keys", secret_number=random.randint(1, 4), attempts=1)
            bot.send_message(chat_id, "🗝️ <b>ИСПЫТАНИЕ КЛЮЧЕЙ</b>\n━━━━━━━━━━━━━━━━━━\n\nПеред тобой четыре ключа. Только один открывает сундук.\n\nВыбери ключ:", parse_mode="HTML", reply_markup=game_action_reply("keys"))
        elif text == "👻 Охота на тень":
            set_active_game(uid, chat_id, "shadow", secret_number=random.randint(1, 3), attempts=1)
            bot.send_message(chat_id, "👻 <b>ОХОТА НА ТЕНЬ</b>\n━━━━━━━━━━━━━━━━━━\n\nТень спряталась в одной из комнат. Найди её!", parse_mode="HTML", reply_markup=game_action_reply("shadow"))
        elif text == "🧪 Ведьмино зелье":
            set_active_game(uid, chat_id, "potion", secret_number=random.randint(1, 3), attempts=1)
            bot.send_message(chat_id, "🧪 <b>ВЕДЬМИНО ЗЕЛЬЕ</b>\n━━━━━━━━━━━━━━━━━━\n\nТолько один котёл содержит зелье удачи. Выбирай!", parse_mode="HTML", reply_markup=game_action_reply("potion"))
        elif text == "🎃 Тыквенный выбор":
            set_active_game(uid, chat_id, "pumpkin", secret_number=random.randint(1, 5), attempts=1)
            bot.send_message(chat_id, "🎃 <b>ТЫКВЕННЫЙ ВЫБОР</b>\n━━━━━━━━━━━━━━━━━━\n\nВ одной тыкве спрятан большой приз. Какая она?", parse_mode="HTML", reply_markup=game_action_reply("pumpkin"))
        elif text == "❌⭕ Крестики-нолики":
            set_active_game(uid, chat_id, "ttt", secret_code="0" * 9)
            bot.send_message(chat_id, "❌⭕ <b>КРЕСТИКИ-НОЛИКИ</b>\n━━━━━━━━━━━━━━━━━━\n\nВыбери клетку от 1 до 9:", parse_mode="HTML", reply_markup=game_action_reply("ttt"))
        return

# ============ REPLY-ДЕЙСТВИЯ ИГР ============
@bot.message_handler(func=lambda message: message.text in {
    "🛑 Выйти из игры", "🗝️ Ключ 1", "🗝️ Ключ 2", "🗝️ Ключ 3", "🗝️ Ключ 4",
    "🚪 Комната 1", "🚪 Комната 2", "🚪 Комната 3",
    "🧪 Котёл 1", "🧪 Котёл 2", "🧪 Котёл 3",
    "🎃 Тыква 1", "🎃 Тыква 2", "🎃 Тыква 3", "🎃 Тыква 4", "🎃 Тыква 5",
    "🎃 1", "🎃 2", "🎃 3", "🎃 4", "🎃 5", "🎃 6", "🎃 7", "🎃 8", "🎃 9",
    "⬅ Игры"
})
def handle_reply_game_actions(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    text = message.text
    mark_reply_mode(uid)
    game = get_active_game(uid)

    if text == "⬅ Игры":
        delete_active_game(uid)
        bot.send_message(chat_id, "🎮 <b>ХЭЛЛОУИНСКИЕ ИГРЫ</b>\n\nВыбери игру:", reply_markup=game_mune_reply(), parse_mode="HTML")
        return

    if text == "🛑 Выйти из игры":
        delete_active_game(uid)
        bot.send_message(chat_id, "🏃 Игра завершена.", reply_markup=game_mune_reply())
        return

    if not game:
        bot.send_message(chat_id, "ℹ️ Активной игры нет.", reply_markup=game_mune_reply())
        return

    game_type = game[0]

    if game_type in {"keys", "shadow", "potion", "pumpkin"}:
        try:
            choice = int(text.rsplit(' ', 1)[1])
        except (ValueError, IndexError):
            return
        secret = int(game[1])
        rewards = {"keys": (150, 60), "shadow": (100, 40), "potion": (125, 50), "pumpkin": (200, 75)}
        coins, xp = rewards[game_type]
        delete_active_game(uid)
        if choice == secret:
            add_coins(uid, coins); add_xp(uid, xp); add_candies(uid, 2, source='game')
            bot.send_message(chat_id, f"🎉 <b>Ты угадал!</b>\n\n💰 +{coins} монет\n⭐ +{xp} XP\n🍬 +2 конфеты", parse_mode="HTML", reply_markup=game_mune_reply())
        else:
            bot.send_message(chat_id, f"❌ Не угадал. Правильный вариант: <b>№{secret}</b>.", parse_mode="HTML", reply_markup=game_mune_reply())
        return

    if game_type == "ttt" and text.startswith("🎃 "):
        pos = int(text.split()[1]) - 1
        if not 0 <= pos < 9:
            return
        board = list(game[3])
        if board[pos] != '0':
            bot.send_message(chat_id, "❌ Эта клетка уже занята. Выбери другую.", reply_markup=game_action_reply("ttt"))
            return
        board[pos] = '1'
        wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
        def won(b, symbol):
            return any(b[a] == b[c] == b[d] == symbol for a,c,d in wins)
        if won(board, '1'):
            add_coins(uid, 40); add_xp(uid, 25); add_candies(uid, 2, source='game'); delete_active_game(uid)
            bot.send_message(chat_id, "🎉 <b>Победа!</b> Ты выиграл!\n💰 +40 монет\n✨ +25 XP\n🍬 +2 конфеты", parse_mode="HTML", reply_markup=game_mune_reply())
            return
        empty = [i for i,v in enumerate(board) if v == '0']
        if not empty:
            delete_active_game(uid)
            bot.send_message(chat_id, "🤝 <b>Ничья!</b>", parse_mode="HTML", reply_markup=game_mune_reply())
            return
        bot_move = random.choice(empty)
        board[bot_move] = '2'
        if won(board, '2'):
            delete_active_game(uid)
            bot.send_message(chat_id, "☠️ <b>Поражение!</b> Бот победил.", parse_mode="HTML", reply_markup=game_mune_reply())
            return
        board_str = ''.join(board)
        update_game_state(uid, secret_code=board_str)
        symbols = {'0':'⬜','1':'🎃','2':'💀'}
        pretty = "\n".join(" ".join(symbols[x] for x in board_str[r:r+3]) for r in range(0,9,3))
        bot.send_message(chat_id, f"🎃 <b>Твой ход</b>\n\n{pretty}", parse_mode="HTML", reply_markup=game_action_reply("ttt"))
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

    # ===== ВЗЛОМ ЗАМКА =====
    if game_type == 'lock':
        secret_code, attempts = game_data[3], game_data[2]
        guess = message.text.strip()

        if len(guess) != 3 or not guess.isdigit():
            bot.reply_to(message, "🔐 Введи 3-значный код, например <code>427</code>!", parse_mode="HTML")
            return

        if guess == secret_code:
            add_coins(user_id, 100)
            add_xp(user_id, 40)
            add_candies(user_id, 3, source='lock')
            delete_active_game(user_id)
            bot.reply_to(message, "🔓 <b>ЗАМОК ВЗЛОМАН!</b>\n💰 +100 монет\n✨ +40 XP\n🍬 +3 конфеты", parse_mode="HTML", reply_markup=game_menu_markup(user_id))
        else:
            attempts -= 1
            if attempts <= 0:
                delete_active_game(user_id)
                bot.reply_to(message, f"🔒 <b>Замок не поддался!</b>\nКод был: <code>{secret_code}</code>", parse_mode="HTML", reply_markup=game_menu_markup(user_id))
            else:
                update_game_attempts(user_id, attempts)
                matched = count_matched_digits(secret_code, guess)
                bot.reply_to(message, f"❌ Неверно!\n💡 Цифр на своих местах: {matched}\n❤️ Осталось попыток: {attempts}")


# ==============================
# Глобальный обработчик ошибок
# ==============================

class GlobalExceptionHandler(telebot.ExceptionHandler):

    def handle(self, exception):

        print("\n" + "=" * 60)
        print("🚨 ОШИБКА В БОТЕ")
        print("=" * 60)

        # Получаем полный traceback
        error_log = traceback.format_exc()

        print(error_log)

        print("=" * 60)

        # Логи ошибок идут в чат разработчика (DEVELOPER_CHAT_ID)
        developers = [DEVELOPER_CHAT_ID]

        # ==============================
        # Отправка ошибки разработчикам
        # ==============================

        for developer_id in developers:

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

bot.polling(none_stop=True, timeout=70)