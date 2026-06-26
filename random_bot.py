import telebot
import sqlite3
import random
import time
import openbot_id
from datetime import datetime, timedelta
from telebot import types
from collections import defaultdict

TOKEN = "Ваш TOKEN"
bot = telebot.TeleBot(TOKEN) # Заминете на свой реальный токен бота

# ========== НАСТРОЙКИ ==========
openbot_id.init_id_system()
DEFAULT_DIFFICULTY = "normal"
DB_NAME = "Random_bot.1.5.db"
MAINTENANCE_MODE = True
ALLOWED_ROLES = ["developer", "coder", "admin"]
DEVELOPER_CHAT_ID = 1234567890 # Замените на свой реальный ID 

# ========== ДОСТИЖЕНИЯ ЗА УРОВНИ ==========
LEVEL_ACHIEVEMENTS = {
    "lvl_5": {"name": "⚡ Опытный", "desc": "Достигни 5 уровня", "target": 5, "reward_type": "coins", "reward_val": 100},
    "lvl_10": {"name": "🎖 Ветеран", "desc": "Достигни 10 уровня", "target": 10, "reward_type": "title", "reward_val": "veteran"},
    "lvl_15": {"name": "🦁 Хищник", "desc": "Достигни 15 уровня", "target": 15, "reward_type": "emoji", "reward_val": "🦁"},
    "lvl_25": {"name": "👑 Король", "desc": "Достигни 25 уровня", "target": 25, "reward_type": "title", "reward_val": "king"},
    "lvl_50": {"name": "🌟 Легенда", "desc": "Достигни 50 уровня", "target": 50, "reward_type": "title", "reward_val": "legend_50"}
}

PROFILE_TITLES = {
    "none": "Без титула", "veteran": "🎖 Ветеран", "king": "👑 Король", "legend_50": "🌟 Легенда",
    "pro": "🔥 Профи", "legend": "👑 Легенда",
}

DAILY_POOL = [
    {"id": "d_win_3", "name": "🥇 Легкий старт", "desc": "Победи 3 раза в любой игре", "type": "wins", "target": 3, "reward": 50},
    {"id": "d_win_5", "name": "🔥 Опытный боец", "desc": "Победи 5 раз в любой игре", "type": "wins", "target": 5, "reward": 100},
    {"id": "d_tic_2", "name": "❌ Крестик-нос", "desc": "Победи 2 раза в Крестики-Нолики", "type": "tic_wins", "target": 2, "reward": 60},
    {"id": "d_coins_150", "name": "💰 Копилка", "desc": "Заработай 150 монет в играх", "type": "coins", "target": 150, "reward": 40},
    {"id": "d_games_10", "name": "🎮 Игроман", "desc": "Сыграй 10 партий в любой игре", "type": "games", "target": 10, "reward": 30},
]

STATUS = {
    "developer": "🌐💠 Openbot.Ai",
    "coder": "🌐 Кодер",
    "admin": "⭐ Администратор",
    "user": "👤 Игрок",
    "banned": "🚫 Забаненный",
}

SHOP_ITEMS = {
    "pro": {"name": PROFILE_TITLES["pro"], "price": 500},
    "legend": {"name": PROFILE_TITLES["legend"], "price": 2000}
}

CASES_CONFIG = {
    "common": {
        "name": "📦 Обычный кейс",
        "price": 150,
        "loot": [
            {"type": "coins", "value": 50, "chance": 50.0, "text": "50 💰"},
            {"type": "coins", "value": 100, "chance": 35.0, "text": "100 💰"},
            {"type": "xp", "value": 30, "chance": 14.9, "text": "30 ✨ Опыта"},
            {"type": "emoji", "value": "🍉", "chance": 0.1, "text": "🔥 СВЕРХРЕДКИЙ ЭМОДЗИ 🍉"}  # Тот самый 0.1%
        ]
    },
    "rare": {
        "name": "💎 Редкий кейс",
        "price": 500,
        "loot": [
            {"type": "emoji", "value": "💎", "chance": 40.0, "text": "Эмодзи 💎"},  # Главный приз кейса
            {"type": "emoji", "value": "👑", "chance": 20.0, "text": "Эмодзи 👑"},  # Еще один эмодзи в призах
            {"type": "coins", "value": 300, "chance": 25.0, "text": "300 💰"},
            {"type": "xp", "value": 100, "chance": 10.0, "text": "100 ✨ Опыта"},
            {"type": "title", "value": "pro", "chance": 5.0, "text": "Титул 🔥 Профи"}
        ]
    }
}

# ========== БАЗА ДАННЫХ ==========
conn = sqlite3.connect("Random_bot.1.5.db", check_same_thread=False)

def init_db():
    cursor = conn.cursor()
    cursor.execute(f"""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, username TEXT UNIQUE, first_name TEXT, status TEXT DEFAULT 'user',
        coins INTEGER DEFAULT 0, total_games INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
        difficulty TEXT DEFAULT '{DEFAULT_DIFFICULTY}', profile_title TEXT DEFAULT NULL,
        profile_emoji TEXT DEFAULT NULL, level INTEGER DEFAULT 1, XP INTEGER DEFAULT 100,
        tic_wins INTEGER DEFAULT 0, rps_wins INTEGER DEFAULT 0, ban_reason TEXT DEFAULT NULL)""")
    try: cursor.execute("ALTER TABLE users ADD COLUMN ban_reason TEXT DEFAULT NULL")
    except: pass
    cursor.execute("""CREATE TABLE IF NOT EXISTS active_games (
        user_id INTEGER PRIMARY KEY, game_name TEXT, game_key TEXT, secret_number INTEGER, attempts INTEGER, started_at TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS daily_config (date TEXT PRIMARY KEY, quest_ids TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS user_daily_progress (
        user_id INTEGER, quest_id TEXT, progress INTEGER DEFAULT 0, claimed INTEGER DEFAULT 0, PRIMARY KEY (user_id, quest_id))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS user_level_achievements (
        user_id INTEGER, achv_id TEXT, claimed INTEGER DEFAULT 0, PRIMARY KEY (user_id, achv_id))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS auction (
        lot_id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER,
        item_type TEXT, item_value TEXT, price INTEGER)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        item_type TEXT, item_value TEXT, is_active INTEGER DEFAULT 0)""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_cases (
        user_id INTEGER,
        case_type TEXT,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, case_type)
    )
    """)
    conn.commit()

init_db()

# ========== ФУНКЦИИ БД ==========
def get_user(user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()

def create_user(user_id, username, first_name):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (id, username, first_name, status) VALUES (?, ?, ?, 'user')",
            (user_id, username.lower() if username else None, first_name))
        conn.commit()

def add_coins(user_id, amount):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (amount, user_id))
    conn.commit()
    update_daily_progress(user_id, "coins", amount)

def update_stats(user_id, won):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET total_games = total_games + 1 WHERE id = ?", (user_id,))
    update_daily_progress(user_id, "games", 1)
    if won:
        cursor.execute("UPDATE users SET wins = wins + 1 WHERE id = ?", (user_id,))
        update_daily_progress(user_id, "wins", 1)
    conn.commit()

def add_tic_win(user_id):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET tic_wins = tic_wins + 1 WHERE id = ?", (user_id,))
    conn.commit()
    update_daily_progress(user_id, "tic_wins", 1)

def add_rps_win(user_id):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET rps_wins = rps_wins + 1 WHERE id = ?", (user_id,))
    conn.commit()

def get_difficulty(user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT difficulty FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row and row[0] else DEFAULT_DIFFICULTY

def set_difficulty(user_id, diff):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET difficulty = ? WHERE id = ?", (diff, user_id))
    conn.commit()

def set_title(user_id, title_key):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET profile_title = ? WHERE id = ?", (title_key, user_id))
    conn.commit()

def set_emoji(user_id, emoji):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET profile_emoji = ? WHERE id = ?", (emoji, user_id))
    conn.commit()

# ========== ЕЖЕДНЕВНЫЕ ЗАДАНИЯ ==========
def check_and_refresh_daily_quests():
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT quest_ids FROM daily_config WHERE date = ?", (today,))
    row = cursor.fetchone()
    if row: return
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    cursor.execute("SELECT quest_ids FROM daily_config WHERE date = ?", (yesterday,))
    prev_row = cursor.fetchone()
    prev_ids = set(prev_row[0].split(',')) if prev_row else set()
    available = [q for q in DAILY_POOL if q['id'] not in prev_ids]
    if len(available) < 2: available = DAILY_POOL
    selected = random.sample(available, min(2, len(available)))
    new_ids = ",".join([q['id'] for q in selected])
    cursor.execute("INSERT INTO daily_config (date, quest_ids) VALUES (?, ?)", (today, new_ids))
    conn.commit()
    cursor.execute("DELETE FROM user_daily_progress")
    conn.commit()

def update_daily_progress(user_id, progress_type, amount=1):
    check_and_refresh_daily_quests()
    cursor = conn.cursor()
    cursor.execute("SELECT quest_ids FROM daily_config ORDER BY date DESC LIMIT 1")
    config = cursor.fetchone()
    if not config: return
    for q_id in config[0].split(','):
        quest = next((q for q in DAILY_POOL if q['id'] == q_id), None)
        if quest and quest['type'] == progress_type:
            cursor.execute("""INSERT INTO user_daily_progress (user_id, quest_id, progress) VALUES (?, ?, ?)
                ON CONFLICT(user_id, quest_id) DO UPDATE SET progress = progress + ?""", (user_id, q_id, amount, amount))
            conn.commit()

# ========== УРОВНИ ==========
def check_level_up(user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT xp, level FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    if not result: return
    xp, level = result[0], result[1]
    new_level = xp // 200 + 1
    if new_level > level:
        cursor.execute("UPDATE users SET level = ? WHERE id = ?", (new_level, user_id))
        conn.commit()
        try: bot.send_message(user_id, f"🎉 Новый уровень: {new_level}!\nПроверь достижения! 🏆")
        except: pass

def add_xp(user_id, amount):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET xp = xp + ? WHERE id = ?", (amount, user_id))
    conn.commit()
    check_level_up(user_id)

# ========== БАНЫ И ДОСТУП ==========
def has_access(user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    if result and result[0] in ALLOWED_ROLES:
        return True
    return False

def check_ban(user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT status, ban_reason FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    if result and result[0] == 'banned':
        return result[1]
    return None

# ========== КРЕСТИКИ-НОЛИКИ ==========
tic_games = {}

def t_check_winner(b):
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for w in wins:
        if b[w[0]] == b[w[1]] == b[w[2]] != ' ': return b[w[0]]
    return 'Draw' if ' ' not in b else None

def t_minimax(board, depth, is_max):
    res = t_check_winner(board)
    if res == 'O': return 10 - depth
    if res == 'X': return depth - 10
    if res == 'Draw': return 0
    if is_max:
        best = -1000
        for i in range(9):
            if board[i] == ' ':
                board[i] = 'O'
                best = max(best, t_minimax(board, depth+1, False))
                board[i] = ' '
        return best
    else:
        best = 1000
        for i in range(9):
            if board[i] == ' ':
                board[i] = 'X'
                best = min(best, t_minimax(board, depth+1, True))
                board[i] = ' '
        return best

def t_best_move(board, difficulty):
    if difficulty == "easy":
        empty = [i for i in range(9) if board[i] == ' ']
        return random.choice(empty) if empty else -1
    if difficulty == "normal" and random.random() < 0.3:
        empty = [i for i in range(9) if board[i] == ' ']
        return random.choice(empty) if empty else -1
    best_val, move = -1000, -1
    for i in range(9):
        if board[i] == ' ':
            board[i] = 'O'
            val = t_minimax(board, 0, False)
            board[i] = ' '
            if val > best_val:
                best_val = val
                move = i
    return move

def t_keyboard(board):
    kb = types.InlineKeyboardMarkup(row_width=3)
    buttons = [types.InlineKeyboardButton(board[i] if board[i] != ' ' else ' ', callback_data=f"t_{i}") for i in range(9)]
    kb.add(*buttons)
    kb.add(types.InlineKeyboardButton("🚪 Выйти", callback_data="t_exit"))
    return kb

# ========== RPS ==========
RPS_MOVES = {0: "🪨 Камень", 1: "📄 Бумага", 2: "✂️ Ножницы"}
RPS_HISTORY = defaultdict(list)

def rps_predict_move(user_id):
    history = RPS_HISTORY.get(user_id, [])
    if len(history) < 2: return random.randint(0, 2)
    last_move = history[-1]
    potential = [history[i+1] for i in range(len(history)-1) if history[i] == last_move]
    if potential:
        predicted = max(set(potential), key=potential.count)
        return (predicted + 1) % 3
    return random.randint(0, 2)

def rps_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(types.InlineKeyboardButton("🪨", callback_data="rps_0"),
           types.InlineKeyboardButton("📄", callback_data="rps_1"),
           types.InlineKeyboardButton("✂️", callback_data="rps_2"))
    kb.add(types.InlineKeyboardButton("🚪 Выход", callback_data="rps_exit"))
    return kb

# ========== ВСПОМОГАТЕЛЬНЫЕ ==========
def difficulty_menu(user_id):
    current = get_difficulty(user_id)
    icons = {"easy": "🟢", "normal": "🟡", "hard": "🔴"}
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(f"{icons['easy']} Лёгко {'✅' if current=='easy' else ''}", callback_data="diff_easy"),
           types.InlineKeyboardButton(f"{icons['normal']} Нормально {'✅' if current=='normal' else ''}", callback_data="diff_normal"),
           types.InlineKeyboardButton(f"{icons['hard']} Хард {'✅' if current=='hard' else ''}", callback_data="diff_hard"))
    kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
    return kb

def save_game(user_id, name, key, secret, attempts):
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO active_games (user_id, game_name, game_key, secret_number, attempts, started_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, key, secret, attempts, datetime.now().isoformat()))
    conn.commit()

def get_active_game(user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_games WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def delete_active_game(user_id):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_games WHERE user_id = ?", (user_id,))
    conn.commit()

def is_playing(user_id):
    return get_active_game(user_id) is not None

# ========== МЕНЮ ==========
def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🎮 Игры", callback_data="game"),
           types.InlineKeyboardButton("🛍 Магазин", callback_data="shop"),
           types.InlineKeyboardButton("🏆 Достижения", callback_data="achievements"),
           types.InlineKeyboardButton("🙎‍♂️ Профиль", callback_data="prof"),
           types.InlineKeyboardButton("📋 Ежедневные", callback_data="dailies"),
           types.InlineKeyboardButton("⚙ Настройки", callback_data='set'))
    kb.add(types.InlineKeyboardButton('💎 Аукцион', callback_data='auction_list'))
    return kb

def games_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🍉 Арбуз", callback_data="game_watermelon"),
           types.InlineKeyboardButton("🌞 Солнце", callback_data="game_sun"),
           types.InlineKeyboardButton("🍹 Лимонад", callback_data="game_lemonade"),
           types.InlineKeyboardButton("🏝️ Клад", callback_data="game_beach"),
           types.InlineKeyboardButton("❌Крестики нолики⭕", callback_data='crest'),
           types.InlineKeyboardButton("🪨 Камень Ножницы Бумага", callback_data='rps'))
    kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
    return kb

# def setting(): <-- Пока - что функция в разработке 
    mar = types.InlineKeyboardMarkup(row_width=1)
    mar.add(types.InlineKeyboardButton('🎯Сложность', callback_data='level_hard'),
            types.InlineKeyboardButton('👤 Профиль', callback_data='set_prof'),
            types.InlineKeyboardButton('⬅  Назад', callback_data='back_main'))
    return mar

def get_user_cases(user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT case_type, count FROM user_cases WHERE user_id = ?", (user_id,))
    return {row[0]: row[1] for row in cursor.fetchall()}

def add_case(user_id, case_type, amount=1):
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO user_cases (user_id, case_type, count) VALUES (?, ?, ?)
        ON CONFLICT(user_id, case_type) DO UPDATE SET count = count + ?""", (user_id, case_type, amount, amount))
    conn.commit()

def remove_case(user_id, case_type, amount=1):
    cursor = conn.cursor()
    cursor.execute("SELECT count FROM user_cases WHERE user_id = ? AND case_type = ?", (user_id, case_type))
    row = cursor.fetchone()
    if row and row[0] >= amount:
        cursor.execute("UPDATE user_cases SET count = count - ? WHERE user_id = ? AND case_type = ?", (amount, user_id, case_type))
        conn.commit()
        return True
    return False

def give_case_reward(user_id, reward):
    cursor = conn.cursor()
    r_type = reward["type"]
    val = reward["value"]
    
    if r_type == "coins":
        add_coins(user_id, val)
    elif r_type == "xp":
        add_xp(user_id, val)
    elif r_type == "emoji":
        cursor.execute("INSERT INTO inventory (user_id, item_type, item_value) VALUES (?, 'emoji', ?)", (user_id, val))
        conn.commit()
    elif r_type == "title":
        set_title(user_id, val)

def shop_cases_menu(user_id):
    user = get_user(user_id)
    user_cases = get_user_cases(user_id)
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    text = f"📦 *МАГАЗИН И ОТКРЫТИЕ КЕЙСОВ*\n\n💰 Твои монеты: {user[4]} 💰\n━━━━━━━━━━━━━━━━━━\n"
    
    for c_key, c_info in CASES_CONFIG.items():
        count = user_cases.get(c_key, 0)
        text += f"*{c_info['name']}*\n"
        text += f"├ У тебя: `{count} шт.`\n"
        text += f"└ Цена: `{c_info['price']} 💰`\n\n"
        
        # Кнопки покупки и открытия для каждого кейса
        kb.add(
            types.InlineKeyboardButton(f"🛒 Купить ({c_info['price']} 💰)", callback_data=f"buy_case_{c_key}"),
            types.InlineKeyboardButton(f"🔓 Открыть (`{count}` шт)", callback_data=f"open_case_{c_key}")
        )
        
    kb.add(types.InlineKeyboardButton("⬅ Назад в магазин", callback_data="shop"))
    return kb, text

def emoji_menu(user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT profile_emoji FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    current = result[0] if result else None
    emojis = ["😎", "🔥", "🎯", "👑", "🍉", "💎"]
    kb = types.InlineKeyboardMarkup(row_width=3)
    for e in emojis:
        kb.add(types.InlineKeyboardButton(e + (" ✅" if current == e else ""), callback_data=f"emoji_{e}"))
    kb.add(types.InlineKeyboardButton("❌ Убрать эмоджи", callback_data="clear"),
           types.InlineKeyboardButton("⬅ Назад", callback_data="set_prof"))
    return kb

def shop_menu(user_id):
    """Главное меню магазина"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🎖 Магазин Титулов", callback_data="shop_titles"),
        types.InlineKeyboardButton("📦 Магазин Кейсов", callback_data="shop_cases"),
        types.InlineKeyboardButton("⬅ Назад в меню", callback_data="back_main")
    )
    text = (
        "🛍 *ГЛАВНЫЙ МАГАЗИН*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Привет! Здесь ты можешь потратить свои заработанные монеты.\n\n"
        "Выбери интересующую тебя категорию товаров ниже:"
    )
    return kb, text

def shop_titles_menu(user_id):
    """Магазин титулов"""
    user = get_user(user_id)
    if not user: 
        return types.InlineKeyboardMarkup(), "❌ Ошибка загрузки профиля."
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    text = (
        "🛒 *МАГАЗИН ТИТУЛОВ*\n"
        f"💰 Твой баланс: `{user[4]}` монет\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Доступные титулы для покупки:\n\n"
    )
    
    for key, item in SHOP_ITEMS.items():
        is_owned = (user[8] == key)
        price_text = "✅ Экипировано" if is_owned else f"Цена: {item['price']} 💰"
        btn_text = "Уже куплено" if is_owned else f"Купить {item['name']}"
        
        text += f"▪️ *{item['name']}* — {price_text}\n"
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"buy_title_{key}"))
        
    kb.add(types.InlineKeyboardButton("⬅ Назад в магазин", callback_data="shop"))
    return kb, text

def shop_cases_menu(user_id):
    """Магазин кейсов с отображением текущего инвентаря кейсов"""
    user = get_user(user_id)
    if not user:
        return types.InlineKeyboardMarkup(), "❌ Ошибка загрузки профиля."
        
    user_cases = get_user_cases(user_id)
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    text = (
        "📦 *МАГАЗИН И ОТКРЫТИЕ КЕЙСОВ*\n"
        f"💰 Твой баланс: `{user[4]}` монет\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Испытай свою удачу! Выбери кейс для покупки или открытия:\n\n"
    )
    
    for c_key, c_info in CASES_CONFIG.items():
        count = user_cases.get(c_key, 0)
        text += f"*{c_info['name']}*\n"
        text += f"├ В наличии: `{count} шт.`\n"
        text += f"└ Стоимость: `{c_info['price']} 💰`\n\n"
        
        # Кнопки покупки и открытия в один ряд (row_width=2)
        kb.add(
            types.InlineKeyboardButton(f"🛒 Купить ({c_info['price']} 💰)", callback_data=f"buy_case_{c_key}"),
            types.InlineKeyboardButton(f"🔓 Открыть ({count} шт)", callback_data=f"open_case_{c_key}")
        )
        
    kb.add(types.InlineKeyboardButton("⬅ Назад в магазин", callback_data="shop"))
    return kb, text

def dailies_menu(user_id):
    check_and_refresh_daily_quests()
    user = get_user(user_id)
    if not user: return types.InlineKeyboardMarkup(), "Ошибка"
    kb = types.InlineKeyboardMarkup(row_width=1)
    text = "📅 *ЕЖЕДНЕВНЫЕ ЗАДАНИЯ*\n\nВыполняй задания, чтобы получить монеты!\n\n"
    cursor = conn.cursor()
    cursor.execute("SELECT quest_ids FROM daily_config ORDER BY date DESC LIMIT 1")
    config = cursor.fetchone()
    if config:
        for q_id in config[0].split(','):
            quest = next((q for q in DAILY_POOL if q['id'] == q_id), None)
            if quest:
                cursor.execute("SELECT progress, claimed FROM user_daily_progress WHERE user_id = ? AND quest_id = ?", (user_id, q_id))
                prog_row = cursor.fetchone()
                progress, claimed = (prog_row[0], prog_row[1]) if prog_row else (0, 0)
                is_done = progress >= quest['target']
                text += f"▫️ {quest['name']}\n📝 {quest['desc']}\n🎁 Награда: {quest['reward']} 💰\n📊 Прогресс: {progress}/{quest['target']}\n\n"
                if is_done and not claimed:
                    kb.add(types.InlineKeyboardButton("🎁 Забрать", callback_data=f"claim_daily_{q_id}"))
    else:
        text += "Загрузка заданий..."
    kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
    return kb, text

def achievements_menu(user_id):
    user = get_user(user_id)
    if not user: return types.InlineKeyboardMarkup(), "Ошибка"
    kb = types.InlineKeyboardMarkup(row_width=1)
    text = "🏆 *ДОСТИЖЕНИЯ*\n\nПолучай награды за развитие!\n\n"
    cursor = conn.cursor()
    for achv_id, achv_data in LEVEL_ACHIEVEMENTS.items():
        cursor.execute("SELECT claimed FROM user_level_achievements WHERE user_id = ? AND achv_id = ?", (user_id, achv_id))
        row = cursor.fetchone()
        claimed = row[0] if row else 0
        current_level = user[10]
        is_done = current_level >= achv_data['target']
        r_type, r_val = achv_data['reward_type'], achv_data['reward_val']
        reward_str = f"{r_val} 💰" if r_type == 'coins' else f"Титул: {PROFILE_TITLES.get(r_val, r_val)}" if r_type == 'title' else f"Эмоджи: {r_val}"
        status_btn = "✅ Получено" if claimed else (f"🎁 Забрать ({reward_str})" if is_done else f"Уровень {current_level}/{achv_data['target']}")
        text += f"🔹 {achv_data['name']}\n📝 {achv_data['desc']}\n🎁 Награда: {reward_str}\n📊 {status_btn}\n\n"
        if is_done and not claimed:
            kb.add(types.InlineKeyboardButton(f"🎁 Забрать ({reward_str})", callback_data=f"claim_achv_{achv_id}"))
    kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
    return kb, text

# ========== ИГРЫ ==========
def start_game(chat_id, user_id, name, key, max_num, attempts, call_id=None):
    if is_playing(user_id):
        if call_id:
            # Если игра запущена с инлайн-кнопки, показываем красивое всплывающее окно (alert)
            bot.answer_callback_query(call_id, "⚠️ У тебя уже есть активная игра!", show_alert=True)
        else:
            # Если игра запущена текстовой командой, отправляем обычное сообщение
            # ИСПРАВЛЕНО: Сохраняем сообщение в переменную warn_msg
            warn_msg = bot.send_message(chat_id, "⚠️ У тебя уже есть активная игра!")
            time.sleep(2)
            # ИСПРАВЛЕНО: Передаем ID созданного сообщения для удаления
            try:
                bot.delete_message(chat_id, warn_msg.message_id)
            except:
                pass
        return
    
    secret = random.randint(1, max_num)
    save_game(user_id, name, key, secret, attempts)
    bot.send_message(chat_id, f"🎮 *{name}*\n\nЯ загадал число от 1 до {max_num}\n❤️ Попыток: {attempts}\n\nВведи число:", parse_mode="Markdown")

def process_guess(chat_id, user_id, num, max_num):
    game = get_active_game(user_id)
    if not game: return
    secret, attempts = game[3], game[4] - 1
    mult = 2 if get_difficulty(user_id) == "hard" else 1
    reward = {"watermelon": 10, "sun": 15, "lemonade": 20, "beach": 25}.get(game[2], 10)
    if num == secret:
        update_stats(user_id, True)
        add_coins(user_id, reward * mult)
        add_xp(user_id, reward * 2)
        delete_active_game(user_id)
        msg =bot.send_message(chat_id, f"🎉 Победа!\nТы угадал число {secret}\n💰 +{reward * mult} монет")
        time.sleep(2)
        bot.edit_message_text(text='🎮 Выберите игру', chat_id=chat_id, message_id=msg.message_id, reply_markup=main_menu())
        return 
    if attempts <= 0:
        update_stats(user_id, False)
        delete_active_game(user_id)
        bot.send_message(chat_id, f"😢 Проигрыш\nЧисло было: {secret}")
        return
    cursor = conn.cursor()
    cursor.execute("UPDATE active_games SET attempts = ? WHERE user_id = ?", (attempts, user_id))
    conn.commit()
    bot.send_message(chat_id, f"{'🔥 Горячо!' if abs(num - secret) <= 5 else '❄️ Холодно'}\nОсталось попыток: {attempts}")

# ========== АУКЦИОН ==========
def get_auction_lots():
    conn2 = sqlite3.connect("Random_bot.1.4.db")
    cur = conn2.cursor()
    cur.execute("SELECT lot_id, item_value, price, seller_id FROM auction")
    lots = cur.fetchall()
    conn2.close()
    return lots

def buy_lot(lot_id, buyer_id):
    conn2 = sqlite3.connect(DB_NAME)
    cur = conn2.cursor()
    cur.execute("SELECT seller_id, item_type, item_value, price FROM auction WHERE lot_id = ?", (lot_id,))
    lot = cur.fetchone()
    if not lot: return False, "Лот не найден"
    seller_id, item_type, item_value, price = lot
    cur.execute("SELECT coins FROM users WHERE id = ?", (buyer_id,))
    buyer_coins = cur.fetchone()[0]
    if buyer_coins < price: return False, "Недостаточно монет"
    cur.execute("UPDATE users SET coins = coins - ? WHERE id = ?", (price, buyer_id))
    cur.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (price, seller_id))
    if item_type == 'emoji':
        cur.execute("INSERT INTO inventory (user_id, item_type, item_value) VALUES (?, 'emoji', ?)", (buyer_id, item_value))
    cur.execute("DELETE FROM auction WHERE lot_id = ?", (lot_id,))
    conn2.commit()
    conn2.close()
    return True, f"Успешно куплено: {item_value}"

# ========== ИНВЕНТАРЬ ==========
def get_user_inventory(user_id):
    conn2 = sqlite3.connect(DB_NAME)
    cur = conn2.cursor()
    cur.execute("SELECT item_value, is_active FROM inventory WHERE user_id = ? AND item_type = 'emoji'", (user_id,))
    items = cur.fetchall()
    conn2.close()
    return items

def set_active_emoji(user_id, emoji):
    conn2 = sqlite3.connect(DB_NAME)
    cur = conn2.cursor()
    cur.execute("UPDATE inventory SET is_active = 0 WHERE user_id = ? AND item_type = 'emoji'", (user_id,))
    cur.execute("UPDATE inventory SET is_active = 1 WHERE user_id = ? AND item_value = ?", (user_id, emoji))
    cur.execute("UPDATE users SET profile_emoji = ? WHERE id = ?", (emoji, user_id))
    conn2.commit()
    conn2.close()

def get_user_lots(user_id):
    conn2 = sqlite3.connect(DB_NAME)
    cur = conn2.cursor()
    cur.execute("SELECT lot_id, item_value, price FROM auction WHERE seller_id = ?", (user_id,))
    lots = cur.fetchall()
    conn2.close()
    return lots

def cancel_lot(lot_id, user_id):
    conn2 = sqlite3.connect(DB_NAME)
    cur = conn2.cursor()
    cur.execute("SELECT item_value FROM auction WHERE lot_id = ? AND seller_id = ?", (lot_id, user_id))
    lot = cur.fetchone()
    if lot:
        cur.execute("INSERT INTO inventory (user_id, item_type, item_value) VALUES (?, 'emoji', ?)", (user_id, lot[0]))
        cur.execute("DELETE FROM auction WHERE lot_id = ?", (lot_id,))
        conn2.commit()
        conn2.close()
        return True
    conn2.close()
    return False

# ========== ОБРАБОТЧИКИ ==========
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    first_name = message.from_user.first_name
    reason = check_ban(uid)
    if MAINTENANCE_MODE and not has_access(uid):
        bot.reply_to(message, "🟠 Ведутся технические работы. Зайдите позже!")
        return
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    
    create_user(uid, message.from_user.username, message.from_user.first_name)
    openbot_id.create_id(uid, first_name)
    openbot_id.register_bot_activity(uid, "Random_bot")
    bot.send_message(message.chat.id, f"👋 Привет, {message.from_user.first_name}!\nДобро пожаловать!", reply_markup=main_menu())

@bot.message_handler(commands=['ban'])
def ban_user(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(message.from_user.id):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    
    if not has_access(uid): return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Формат: /ban @username [причина]")
        return
    target_username = parts[1].replace("@", "").strip()
    reason = parts[2] if len(parts) > 2 else "Без причины"
    cursor = conn.cursor()
    cursor.execute("SELECT id, status FROM users WHERE username = ?", (target_username,))
    result = cursor.fetchone()
    if result:
        target_id, current_status = result[0], result[1]
        if current_status in ALLOWED_ROLES:
            bot.reply_to(message, f"⛔ Нельзя забанить {STATUS.get(current_status, current_status)}!")
        elif current_status == 'banned':
            bot.reply_to(message, f"⚠️ @{target_username} уже забанен.")
        else:
            cursor.execute("UPDATE users SET status = 'banned', ban_reason = ? WHERE id = ?", (reason, target_id))
            conn.commit()
            bot.send_message(message.chat.id, f"✅ @{target_username} забанен!\nПричина: {reason}")
            try: bot.send_message(target_id, f"🚫 Вы заблокированы!\nПричина: {reason}")
            except: pass
    else:
        bot.reply_to(message, f"❌ Пользователь @{target_username} не найден.")

@bot.message_handler(commands=['unban'])
def unban_by_username(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    if not has_access(uid): return
    parts = message.text.split()
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(message.from_user.id):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Формат: /unban @username")
        return
    target_username = parts[1].replace("@", "").strip()
    cursor = conn.cursor()
    cursor.execute("SELECT id, status FROM users WHERE username = ?", (target_username,))
    result = cursor.fetchone()
    if result:
        target_id, current_status = result[0], result[1]
        if current_status != 'banned':
            bot.reply_to(message, f"❓ Пользователь @{target_username} не забанен.")
        else:
            cursor.execute("UPDATE users SET status = 'user', ban_reason = NULL WHERE id = ?", (target_id,))
            conn.commit()
            bot.send_message(message.chat.id, f"✅ Пользователь @{target_username} разбанен!")
            try: bot.send_message(target_id, "🔓 Ваш доступ восстановлен!")
            except: pass
    else:
        bot.reply_to(message, f"❌ Пользователь @{target_username} не найден.")

@bot.message_handler(commands=['sendall'])
def send_all(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    if not has_access(uid): return
    text = message.text.replace("/sendall", "").strip()
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(message.from_user.id):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    if not text:
        bot.reply_to(message, "❌ Введи текст для рассылки.\nПример: `/sendall Привет!`", parse_mode="Markdown")
        return
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users")
    users = cursor.fetchall()
    bot.send_message(message.chat.id, f"🚀 Рассылка запущена...\nВсего: {len(users)}")
    success = blocked = errors = 0
    for user in users:
        try:
            bot.send_message(user[0], text, parse_mode="HTML")
            success += 1
        except telebot.apihelper.ApiTelegramException as e:
            if e.description == "Forbidden: bot was blocked by the user": blocked += 1
            else: errors += 1
        except: errors += 1
    bot.send_message(message.chat.id, f"✅ Готово!\n👤 Успешно: {success}\n🚫 Заблокировали: {blocked}\n⚠️ Ошибки: {errors}")

@bot.message_handler(commands=['sell_emoji'])
def sell_item(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    parts = message.text.split()
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ Формат: `/sell_emoji [эмодзи] [цена]`", parse_mode="Markdown")
        return
    
    emoji = parts[1]
    try: price = int(parts[2])
    except:
        bot.reply_to(message, "❌ Цена должна быть числом!")
        return
    conn2 = sqlite3.connect(DB_NAME)
    cur = conn2.cursor()
    cur.execute("SELECT 1 FROM inventory WHERE user_id = ? AND item_value = ?", (uid, emoji))
    if not cur.fetchone():
        bot.reply_to(message, "❌ У тебя нет такого эмодзи в инвентаре!")
        conn2.close()
        return
    cur.execute("DELETE FROM inventory WHERE user_id = ? AND item_value = ?", (uid, emoji))
    cur.execute("INSERT INTO auction (seller_id, item_type, item_value, price) VALUES (?, 'emoji', ?, ?)", (uid, emoji, price))
    conn2.commit()
    conn2.close()
    bot.reply_to(message, f"✅ Твой лот {emoji} выставлен на аукцион за {price} 💰")

@bot.message_handler(commands=['gift'])
def gift_item(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    # 1. Проверяем доступ
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(message.from_user.id):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    
    if not has_access(message.from_user.id):
        bot.send_message(message.chat.id, "❌ У вас нет прав разработчика/админа для этой команды!")
        return
        
    parts = message.text.split()
    # 2. Проверяем, все ли аргументы ввели
    if len(parts) < 3:
        bot.send_message(message.chat.id, "⚠️ Неверный формат! Пиши так:\n`/gift @юзернейм эмодзи`", parse_mode="Markdown")
        return
        
    target_uname = parts[1].replace("@", "").lower()
    item = parts[2]
    
    conn2 = sqlite3.connect('Random_bot.1.4.db')
    cur = conn2.cursor()
    
    # ИСПРАВЛЕНИЕ: ищем юзернейм без учёта больших/маленьких букв через LOWER()
    cur.execute("SELECT id FROM users WHERE LOWER(username) = ?", (target_uname,))
    res = cur.fetchone()
    
    if res:
        # Если нашли — выдаём в инвентарь
        cur.execute("INSERT INTO inventory (user_id, item_type, item_value) VALUES (?, 'emoji', ?)", (res[0], item))
        conn2.commit()
        
        bot.send_message(message.chat.id, f"🎁 Предмет {item} успешно подарен @{target_uname}!")
        
        # Пытаемся уведомить получателя (если он не заблокировал бота)
        try:
            bot.send_message(res[0], f"🎁 Админ подарил тебе новый предмет: {item}\nПроверь его в Профиль -> Инвентарь!")
        except Exception:
            pass # Если бот у него в блоке, чтобы админская команда не падала
    else:
        # 3. Если игрока нет в базе
        bot.send_message(message.chat.id, f"❌ Пользователь @{target_uname} не найден в базе данных бота!")
        
    conn2.close()

@bot.message_handler(commands=['give_coins'])
def give_coins_cmd(message):
    uid = message.from_user.id
    reason = check_ban(uid)
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
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ Формат: /give_coins @username 100")
        return
    username = parts[1].replace("@", "").lower()
    try: amount = int(parts[2])
    except:
        bot.reply_to(message, "❌ Сумма должна быть числом!")
        return
    if amount <= 0:
        bot.reply_to(message, "❌ Сумма должна быть больше 0!")
        return
    cursor = conn.cursor()
    cursor.execute("SELECT id, first_name FROM users WHERE username = ?", (username,))
    res = cursor.fetchone()
    if not res:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден.")
        return
    add_coins(res[0], amount)
    bot.reply_to(message, f"✅ Пользователю @{username} выдано {amount} 💰")
    try: bot.send_message(res[0], f"🎁 Вам выдали {amount} 💰 монет!")
    except: pass

@bot.message_handler(commands=['take_coins'])
def take_coins_cmd(message):
    uid = message.from_user.id
    reason = check_ban(uid)
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
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ Формат: /take_coins @username 100")
        return
    username = parts[1].replace("@", "").lower()
    try: amount = int(parts[2])
    except:
        bot.reply_to(message, "❌ Сумма должна быть числом!")
        return
    if amount <= 0:
        bot.reply_to(message, "❌ Сумма должна быть больше 0!")
        return
    cursor = conn.cursor()
    cursor.execute("SELECT id, coins FROM users WHERE username = ?", (username,))
    res = cursor.fetchone()
    if not res:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден.")
        return
    if res[1] < amount:
        bot.reply_to(message, f"❌ У @{username} только {res[1]} 💰, нельзя снять {amount}!")
        return
    add_coins(res[0], -amount)
    bot.reply_to(message, f"✅ У @{username} снято {amount} 💰")
    try: bot.send_message(res[0], f"⚠️ У вас сняли {amount} 💰 монет.")
    except: pass

@bot.message_handler(commands=['id_ban'])
def id_ban(message):
    uid = message.from_user.id
    reason = check_ban(uid)
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
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
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
    try: bot.send_message(res[0], "☠️ Ваш OpenbotAI ID был забанен!")
    except: pass

@bot.message_handler(commands=['id_unban'])
def id_unban(message):
    uid = message.from_user.id
    reason = check_ban(uid)
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
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    res = cursor.fetchone()
    if not res:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден.")
        return
    data = openbot_id.get_id(res[0])
    if not data:
        bot.reply_to(message, f"❌ У @{username} нет OpenbotAI ID.")
        return
    if data[3] != "banned":
        bot.reply_to(message, f"⚠️ @{username} не забанен в ID!")
        return
    openbot_id.set_status(res[0], "user")
    bot.reply_to(message, f"✅ ID пользователя @{username} разбанен!")
    try: bot.send_message(res[0], "✅ Ваш OpenbotAI ID был разбанен!")
    except: pass

@bot.message_handler(commands=['id_freeze'])
def id_freeze(message):
    uid = message.from_user.id
    reason = check_ban(uid)
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
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
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
    try: bot.send_message(res[0], "❄️ Ваш OpenbotAI ID был заморожен!")
    except: pass

@bot.message_handler(commands=['id_unfreeze'])
def id_unfreeze(message):
    uid = message.from_user.id
    reason = check_ban(uid)
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
        bot.reply_to(message, "⚠️ Формат: /id_unfreeze @username")
        return
    username = parts[1].replace("@", "").lower()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    res = cursor.fetchone()
    if not res:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден.")
        return
    data = openbot_id.get_id(res[0])
    if not data:
        bot.reply_to(message, f"❌ У @{username} нет OpenbotAI ID.")
        return
    if data[3] != "frozen":
        bot.reply_to(message, f"⚠️ @{username} не заморожен!")
        return
    openbot_id.set_status(res[0], "user")
    bot.reply_to(message, f"✅ ID пользователя @{username} разморожен!")
    try: bot.send_message(res[0], "✅ Ваш OpenbotAI ID был разморожен!")
    except: pass

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
    
    uid = message.from_user.id
    
    reason = check_ban(uid)
    if MAINTENANCE_MODE and not has_access(uid):
        bot.reply_to(message, "🟠 Ведутся технические работы. Зайдите позже!")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    
    text = """Доступные команды
/start - запуск бота
/sell_emoji - продать эмоджи на аукцион
/support - открывает поддержку (⚠ Но она в разработке !)
/id_profile - открывает глобальный аккаунт  
/profile - открывает профиль
/feedback - оставте отзыв 

<i>Обновлено 2026 года</i>"""
    msg = bot.send_message(message.chat.id, 'Загрузка...')
    bot.edit_message_text(text, message_id=msg.message_id, chat_id=message.chat.id, parse_mode="HTML")

@bot.message_handler(commands=['level_up'])
def cmd_level_up(message):
    uid = message.from_user.id
    reason = check_ban(uid)
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    if not has_access(message.from_user.id):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    
    # 1. Проверяем, является ли отправитель админом/разработчиком
    user_data = get_user(uid)
    if not user_data or user_data[3] not in ALLOWED_ROLES:  # В твоей таблице роль/status — это 4-й столбец (индекс 3)
        bot.reply_to(message, "❌ У тебя нет прав для использования этой команды!")
        return

    # 2. Разбираем аргументы команды (/level_up @username 100)
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "⚠️ Использование команды:\n`/level_up @username уровень`\n\nПример: `/level_up @kafnik 100`", parse_mode="Markdown")
        return

    target_username = args[1].replace("@", "").strip().lower() # Приводим к нижнему регистру, так как ты сохраняешь username.lower()
    try:
        new_lvl = int(args[2])
    except ValueError:
        bot.reply_to(message, "❌ Уровень должен быть целым числом!")
        return

    # 3. Ищем цель в базе данных по юзернейму (Используем 'first_name' вместо 'character_name')
    cursor = conn.cursor()
    cursor.execute("SELECT id, first_name FROM users WHERE username = ?", (target_username,))
    target_row = cursor.fetchone()

    if not target_row:
        bot.reply_to(message, f"❌ Пользователь @{target_username} не найден в базе данных бота.")
        return

    target_id, target_name = target_row

    # 4. Обновляем уровень
    cursor.execute("UPDATE users SET level = ? WHERE id = ?", (new_lvl, target_id))
    conn.commit()

    # 5. Проверяем автоматические награды за новый уровень для этого игрока
    response_rewards = ""
    for ach_key, ach in LEVEL_ACHIEVEMENTS.items():
        if ach["target"] == new_lvl:
            r_type = ach["reward_type"]
            r_val = ach["reward_val"]
            response_rewards += f"\n\n🏆 *Получено достижение: {ach['name']}!*\n🎁 Награда: "
            
            if r_type == "coins":
                add_coins(target_id, int(r_val))
                response_rewards += f"+{r_val} 💰"
            elif r_type == "title":
                set_title(target_id, r_val)
                response_rewards += f"Новый титул!"
            elif r_type == "emoji":
                cursor.execute("INSERT INTO inventory (user_id, item_type, item_value) VALUES (?, 'emoji', ?)", (target_id, r_val))
                conn.commit()
                response_rewards += f"Эмодзи {r_val} добавлен в инвентарь!"

    # Оповещаем админа об успешном изменении
    bot.send_message(
        message.chat.id, 
        f"⭐ *Уровень изменен!*\n\nАдминистратор изменил уровень игроку *{target_name}* (@{target_username}) на *{new_lvl}* 🆙{response_rewards}", 
        parse_mode="Markdown"
    )
    
    # Уведомляем самого игрока в ЛС
    try:
        bot.send_message(target_id, f"🆙 Администратор установил твой уровень равным: *{new_lvl}*!{response_rewards}", parse_mode="Markdown")
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
    
    # Разбираем текст после команды
    parts = message.text.split(maxsplit=1)
    
    if len(parts) < 2:
        bot.reply_to(
            message, 
            "⚠️ **Неверный формат!**\nПиши команду и текст отзыва в одном сообщении.\n\n"
            "📝 _Пример:_ `/feedback Нашел баг в игре Крестики-Нолики, бот не засчитал ничью!`", 
            parse_mode="Markdown"
        )
        return

    feedback_text = parts[1].strip()
    username = f"@{message.from_user.username}" if message.from_user.username else "Нет юзернейма"
    first_name = message.from_user.first_name

    # Красивое сообщение для тебя (разработчика)
    admin_report = (
        f"📩 **НОВЫЙ ОТЗЫВ ИГРОКА**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Отправитель:** {first_name} ({username})\n"
        f"🆔 **ID пользователя:** `{uid}`\n"
        f"🕒 **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💬 **Текст отзыва:**\n{feedback_text}"
    )

    try:
        # Отправляем отзыв тебе в ЛС
        bot.send_message(DEVELOPER_CHAT_ID, admin_report, parse_mode="Markdown")
        
        # Отвечаем пользователю
        bot.reply_to(
            message, 
            "✨ **Спасибо за ваш отзыв!**\n"
            "📨 Он успешно доставлен разработчикам проекта. "
            "Мы обязательно его рассмотрим, чтобы сделать Openbot.Ai ещё лучше! 🌐💠"
        )
    except Exception as e:
        print(f"Ошибка при отправке фидбека админу: {e}")
        bot.reply_to(message, "❌ Произошла ошибка при отправке отзыва. Попробуйте позже или обратитесь в поддержку.")

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
    
    
    # Берём всё что после команды
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
# ============= Обработчики для профилей =========
@bot.message_handler(commands=['profile'])
def commagd_profile(message):
    uid = message.from_user.id
    user = get_user(uid)
    global_data = openbot_id.get_id(uid)
    reason = check_ban(uid)
    if openbot_id.is_globally_banned(uid):
        bot.reply_to(message, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.reply_to(message, f"🚫 Вы заблокированы!\nПричина: {reason}")
        return
    

    # 1. Задаем значения по умолчанию, чтобы избежать UnboundLocalError
    full_name = "Игрок"
    g_tag = "Отсутствует"
    display_status = "👤 Игрок"
    title = "Без титула"

    if global_data:
        # Индексы согласно новой схеме (user_id=0, active_bots=1, name=2, ...)
        g_name = global_data[2]
        g_emoji = global_data[3] or ""
        g_tag = global_data[5] or "Не установлен"
        full_name = f"{g_emoji} {g_name}".strip()
        display_status = openbot_id.STATUS.get(global_data[6], '👤 Игрок')
    
    if user:
        title = PROFILE_TITLES.get(user[8], "Без титула")
        # Если статус не был получен из global_data, берем из локальной базы
        if global_data is None:
            display_status = STATUS.get(user[3], "👤 Игрок")

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('🎒 Инвентарь', callback_data='open_inventory'),
        types.InlineKeyboardButton('⚙️ Настройки ID', callback_data='manage_openbot_id'),
        types.InlineKeyboardButton('⬅ Назад', callback_data='back_main')
    )

    text = f"""<b>ПРОФИЛЬ</b>
━━━━━━━━━━━━━━━━━━
👤 <b>Имя в сети:</b> {full_name}
🆔 <b>Ваш Тег:</b> <code>{g_tag}</code>
🎭 <b>Статус:</b> {display_status}
🎖 <b>Игровой титул:</b> {title}

📊 <b>ИГРОВАЯ СТАТИСТИКА:</b>
⭐ <b>Уровень:</b> {user[10] if user else 0}
✨ <b>Опыт:</b> {user[11] if user else 0}
💰 <b>Монеты:</b> {user[4] if user else 0} 💰

🎮 <b>Всего игр:</b> {user[5] if user else 0}
🏆 <b>Всего побед:</b> {user[6] if user else 0}
━━━━━━━━━━━━━━━━━━━
"""
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

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
        
        # Получаем список ботов как строку
        bots_list = openbot_id.get_active_bots(uid)
        g_active_bot = ", ".join(bots_list) if bots_list else "Ни в каких"
        
        g_status = openbot_id.STATUS.get(global_data[6], "👤 Игрок")
            
        text = f"""**🌐 Общий профиль Openbot AI ID**

**🏷 Имя:** `{g_name}`
**🆔 Тег:** `{g_tag}`
**🎭 Статус:** `{g_status}`
**🤖 Боты:** `{g_active_bot}`
**🗄 Создан:** `{g_data}`
**📝 О себе:** `{g_bio}`"""
        
        # Редактируем сообщение (если вызываем через команду, используем send_message, 
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            # Сюда можно повесить инлайн-кнопки для смены имени/био, если у тебя есть для них функции
            types.InlineKeyboardButton('📝 Изменить имя сети', callback_data='change_global_name'),
            types.InlineKeyboardButton('⬅️ Назад в профиль', callback_data='prof')
        )
        bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")
    else:
        text = "❌ У вас еще не создан Openbot AI ID. Напишите /start."
        bot.send_message(cid, text)


@bot.message_handler(func=lambda m: is_playing(m.from_user.id) and get_active_game(m.from_user.id)[2] != "tic")
def game_input(message):
    try: num = int(message.text)
    except: return
    game = get_active_game(message.from_user.id)
    if game:
        process_guess(message.chat.id, message.from_user.id, num, {"watermelon": 10, "sun": 15, "lemonade": 20, "beach": 25}.get(game[2], 10))

# +++++++++++++++ Комнады в разработке +++++++++++++

@bot.message_handler(commands=['support'])
def support_command(message):
    bot.send_message(message.chat.id, '🚧 Эта команда в разработке ⚙')

# ========== CALLBACK ==========
@bot.callback_query_handler(func=lambda c: True)
def callbacks(call):
    uid, cid = call.from_user.id, call.message.chat.id
    reason = check_ban(uid)
    if openbot_id.is_globally_banned(uid):
        bot.answer_callback_query(call.id, "☠ Доступ закрыт!\nВаш глобальный аккаунт заблокирован во всех ботах нашей сети.")
        return
    if reason:
        bot.answer_callback_query(call.id, f"🚫 Вы заблокированы!\nПричина: {reason}", show_alert=True)
        return
    
    create_user(uid, call.from_user.username, call.from_user.first_name)
    user = get_user(uid)
    if not user:
        bot.answer_callback_query(call.id, "Ошибка! Напишите /start", show_alert=True)
        return

    if call.data == "game": bot.edit_message_text("🎮 Выбери игру", cid, call.message.message_id, reply_markup=games_menu())
    elif call.data == 'back_main': bot.edit_message_text("Добро пожаловать!", cid, call.message.message_id, reply_markup=main_menu())
    # elif call.data == "back": bot.edit_message_text("Выбирите действие:", cid, call.message.message_id, reply_markup=setting())
    elif call.data == "exit_game": delete_active_game(uid); bot.edit_message_text("🎮 Выбери игру", cid, call.message.message_id, reply_markup=games_menu())
    elif call.data == "game_watermelon": start_game(cid, uid, "🍉 Арбуз", "watermelon", 50, 10)
    elif call.data == "game_sun": start_game(cid, uid, "🌞 Солнце", "sun", 40, 8)
    elif call.data == "game_lemonade": start_game(cid, uid, "🍹 Лимонад", "lemonade", 20, 5)
    elif call.data == "game_beach": start_game(cid, uid, "🏝️ Клад", "beach", 100, 7)

    
    elif call.data == "prof":
        # 1. Получаем игровые данные из локальной базы бота (Random_bot)
        user = get_user(uid)  
        
        # 2. Получаем глобальные паспортные данные из openbot_id
        global_data = openbot_id.get_id(uid)
        
        # Разбираем глобальные данные (из openbot_id.db)
        if global_data:
            # Структура: (user_id, active_bot, name, emoji, old_emoji, player_tag, global_status, created_at, bio, is_col)
            g_name = global_data[2]
            g_emoji = global_data[3] or ""
            g_tag = global_data[5] or "Не установлен"
            g_status_key = global_data[6] 
            
            # Переводим статус в красивый текст
            status_text = openbot_id.STATUS.get(g_status_key, '👤 Игрок')
            full_name = f"{g_emoji} {g_name}".strip()
        else:
            full_name = user[2] if user else "Игрок"
            g_tag = "Отсутствует"

        # 3. Получаем локальный игровой титул (из базы бота)
        title = PROFILE_TITLES.get(user[8] if user else "none", "Без титула")
        display_status = STATUS.get(user[3] if user else "👤 Игрок")
         
        # 4. СОЗДАЕМ КЛАВИАТУРУ С ЛОКАЛЬНЫМИ КНОПКАМИ
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('🎒 Инвентарь', callback_data='open_inventory'),
            # Кнопка ведет на локальный обработчик настроек ID прямо в этом боте:
            types.InlineKeyboardButton('⚙️ Настройки ID', callback_data='manage_openbot_id'),
            types.InlineKeyboardButton('⬅ Назад', callback_data='back_main')
        )
        
        # 5. Выводим красивый объединенный текст
        if user:
            text = f"""<b>ПРОФИЛЬ</b>
━━━━━━━━━━━━━━━━━━
👤 <b>Имя в сети:</b> {full_name}
🆔 <b>Ваш Тег:</b> <code>{g_tag}</code>
🎭 <b>Статус:</b> {display_status}
🎖 <b>Игровой титул:</b> {title}

📊 <b>ИГРОВАЯ СТАТИСТИКА:</b>
⭐ <b>Уровень:</b> {user[10]}
✨ <b>Опыт:</b> {user[11]}
💰 <b>Монеты:</b> {user[4]} 💰

🎮 <b>Всего игр:</b> {user[5]}
🏆 <b>Всего побед:</b> {user[6]}
━━━━━━━━━━━━━━━━━━━
"""
            bot.edit_message_text(text, cid, call.message.message_id, reply_markup=markup, parse_mode="HTML")
    
    elif call.data == "manage_openbot_id":
        global_data = openbot_id.get_id(uid)
        
        if global_data:
            g_name = global_data[2]
            g_tag = global_data[5] or "Не установлен"
            g_bio = global_data[8] or "Не установлена"
            g_data = global_data[7]
            g_active_bot = openbot_id.get_active_bots(uid)
            g_status = openbot_id.STATUS.get(global_data[6], "👤 Игрок")
            
            text = f"""**🌐 Общий профиль Openbot AI ID**

Вы можете изменить свои глобальные данные. Они обновятся во всех ботах нашей сети!

**🏷 Текущее имя:** `{g_name}`
**🆔 Ваш Тег:** `{g_tag}`
**🎭 Глобальный статус:** `{g_status}`
**🤖 Боты:** `{g_active_bot}`
**🗄 Созданн аккаунт:** `{g_data}`
**📝 О себе:** `{g_bio}`
"""
        else:
            text = "❌ У вас еще не создан Openbot AI ID. Напишите /start для автоматической регистрации."

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            # Сюда можно повесить инлайн-кнопки для смены имени/био, если у тебя есть для них функции
            types.InlineKeyboardButton('📝 Изменить имя сети', callback_data='change_global_name'),
            types.InlineKeyboardButton('⬅️ Назад в профиль', callback_data='prof')
        )
        
        bot.edit_message_text(text, cid, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == 'change_global_name': bot.answer_callback_query(call.id, '⚠ Это функция бота в разработке!\n Ожидается в 1.6')
    elif call.data == 'set': bot.answer_callback_query(call.id, '⚠ Это функция бота в разработке !\n Ожидается в 1.6')
    elif call.data == 'level_hard': bot.edit_message_text('Выберите сложность', cid, call.message.message_id, reply_markup=difficulty_menu(uid))
    elif call.data == "diff_easy": set_difficulty(uid, "easy"); bot.answer_callback_query(call.id, "🟢 Лёгкая")
    elif call.data == "diff_normal": set_difficulty(uid, "normal"); bot.answer_callback_query(call.id, "🟡 Нормальная")
    elif call.data == "diff_hard": set_difficulty(uid, "hard"); bot.answer_callback_query(call.id, "🔴 Хард")
    elif call.data == 'set_prof': bot.edit_message_text('Выбирите действие:', cid, call.message.message_id, reply_markup=types.InlineKeyboardMarkup(row_width=1).add(types.InlineKeyboardButton('✨Украшение никнейма.', callback_data='nek_prof'), types.InlineKeyboardButton('⬅ Назад', callback_data='back')))
    elif call.data == 'nek_prof': bot.edit_message_text("😎 Выбери эмоджи для ника:", cid, call.message.message_id, reply_markup=emoji_menu(uid))
    elif call.data.startswith("emoji_"):
        set_emoji(uid, call.data.replace("emoji_", ""))
        bot.answer_callback_query(call.id, "Сохранено")
        bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=emoji_menu(uid))
    elif call.data == "clear":
        set_emoji(uid, None)
        bot.answer_callback_query(call.id, "Убрано")
        bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=emoji_menu(uid))
    # === НАВИГАЦИЯ ПО МАГАЗИНАМ ===
    elif call.data == "shop":
        kb, text = shop_menu(uid)
        try:
            bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in e.description: raise e
        
    elif call.data == "shop_titles":
        kb, text = shop_titles_menu(uid)
        try:
            bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in e.description: raise e
        
    elif call.data == "shop_cases":
        kb, text = shop_cases_menu(uid)
        try:
            bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in e.description: raise e

    # === ПОКУПКА ТИТУЛОВ ===
    elif call.data.startswith("buy_title_"):
        item_key = call.data.replace("buy_title_", "")
        if item_key in SHOP_ITEMS:
            user = get_user(uid)
            if user:
                price = SHOP_ITEMS[item_key]['price']
                if user[8] == item_key: 
                    bot.answer_callback_query(call.id, "Уже есть!", show_alert=True)
                elif user[4] >= price:
                    add_coins(uid, -price)
                    set_title(uid, item_key)
                    kb, text = shop_titles_menu(uid)
                    try:
                        bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
                    except: pass
                    bot.answer_callback_query(call.id, "Куплено!")
                else: 
                    bot.answer_callback_query(call.id, f"Нужно {price} монет!", show_alert=True)

    # === ПОКУПКА КЕЙСОВ ===
    elif call.data.startswith("buy_case_"):
        case_key = call.data.replace("buy_case_", "")
        if case_key in CASES_CONFIG:
            user = get_user(uid)
            price = CASES_CONFIG[case_key]["price"]
            if user[4] >= price:
                add_coins(uid, -price)
                add_case(uid, case_key, 1)
                bot.answer_callback_query(call.id, f"✅ Куплен: {CASES_CONFIG[case_key]['name']}")
                kb, text = shop_cases_menu(uid)
                try:
                    bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
                except: pass
            else:
                bot.answer_callback_query(call.id, f"❌ Недостаточно монет! Нужно {price} 💰", show_alert=True)

    # === ОТКРЫТИЕ КЕЙСОВ С АНИМАЦИЕЙ ===
    elif call.data.startswith("open_case_"):
        case_key = call.data.replace("open_case_", "")
        if case_key in CASES_CONFIG:
            if remove_case(uid, case_key, 1):
                config = CASES_CONFIG[case_key]
                loot_pool = config["loot"]
                rewards = [item for item in loot_pool]
                chances = [item["chance"] for item in loot_pool]
                win_reward = random.choices(rewards, weights=chances, k=1)[0]
                
                give_case_reward(uid, win_reward)
                
                animation_stages = [
                    "🔑 Вставляем ключ...",
                    "🌀 Кейс трясётся... [ 📦 ]",
                    "✨ Открываем замок... [ 🔓 ]",
                    "⚡ Смотрим, что внутри..."
                ]
                
                for stage in animation_stages:
                    try:
                        bot.edit_message_text(
                            f"🎰 *ОТКРЫТИЕ КЕЙСА: {config['name']}*\n\n{stage}", 
                            cid, call.message.message_id, parse_mode="Markdown"
                        )
                        time.sleep(0.5)
                    except:
                        pass
                
                text_win = f"🎉 *КЕЙС ОТКРЫТ!*\n\nТвоя награда:\n👉 **{win_reward['text']}** 🎉\n\n_Предмет уже добавлен на твой аккаунт!_"
                kb_win = types.InlineKeyboardMarkup()
                kb_win.add(types.InlineKeyboardButton("🔄 Вернуться в магазин кейсов", callback_data="shop_cases"))
                
                try:
                    bot.edit_message_text(text_win, cid, call.message.message_id, parse_mode="Markdown", reply_markup=kb_win)
                except: pass
            else:
                bot.answer_callback_query(call.id, "❌ У тебя нет этого кейса! Сначала купи его.", show_alert=True)
    elif call.data.startswith("buy_"):
        item_key = call.data.split("_")[1]
        if item_key in SHOP_ITEMS:
            user = get_user(uid)
            if user:
                price = SHOP_ITEMS[item_key]['price']
                if user[8] == item_key: bot.answer_callback_query(call.id, "Уже есть!", show_alert=True)
                elif user[4] >= price:
                    add_coins(uid, -price); set_title(uid, item_key)
                    kb, text = shop_menu(uid)
                    bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
                    bot.answer_callback_query(call.id, "Куплено!")
                else: bot.answer_callback_query(call.id, f"Нужно {price} монет!", show_alert=True)
    elif call.data == "dailies":
        kb, text = dailies_menu(uid)
        bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)

    # ОБРАБОТКА ОТКРЫТИЯ КЕЙСА
    elif call.data.startswith("open_case_"):
        case_key = call.data.replace("open_case_", "")
        if case_key in CASES_CONFIG:
            if remove_case(uid, case_key, 1):
                config = CASES_CONFIG[case_key]
                
                loot_pool = config["loot"]
                rewards = [item for item in loot_pool]
                chances = [item["chance"] for item in loot_pool]  # Считает наши 14.9 и 0.1
                
                # Выбираем случайную награду с учетом новых весов-шансов
                win_reward = random.choices(rewards, weights=chances, k=1)[0]
                
                give_case_reward(uid, win_reward)
                
                bot.answer_callback_query(call.id, f"🎉 Открытие... Тебе выпало: {win_reward['text']}!", show_alert=True)
                
                kb, text = shop_cases_menu(uid)
                bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
            else:
                bot.answer_callback_query(call.id, "❌ У тебя нет этого кейса! Сначала купи его.", show_alert=True)

    elif call.data.startswith("claim_daily_"):
        q_id = call.data.replace("claim_daily_", "")
        cursor = conn.cursor()
        cursor.execute("SELECT progress, claimed FROM user_daily_progress WHERE user_id = ? AND quest_id = ?", (uid, q_id))
        row = cursor.fetchone()
        if row:
            progress, claimed = row
            quest = next((q for q in DAILY_POOL if q['id'] == q_id), None)
            if quest and progress >= quest['target'] and not claimed:
                add_coins(uid, quest['reward'])
                cursor.execute("UPDATE user_daily_progress SET claimed = 1 WHERE user_id = ? AND quest_id = ?", (uid, q_id))
                conn.commit()
                kb, text = dailies_menu(uid)
                bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
                bot.answer_callback_query(call.id, f"🎁 +{quest['reward']} монет!")
            else: bot.answer_callback_query(call.id, "Уже получено!", show_alert=True)
    elif call.data == "achievements":
        kb, text = achievements_menu(uid)
        bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
    elif call.data.startswith("claim_achv_"):
        achv_id = call.data.replace("claim_achv_", "")
        cursor = conn.cursor()
        cursor.execute("SELECT claimed FROM user_level_achievements WHERE user_id = ? AND achv_id = ?", (uid, achv_id))
        row = cursor.fetchone()
        if row is None or row[0] == 0:
            achv = LEVEL_ACHIEVEMENTS.get(achv_id)
            if achv:
                r_type, r_val = achv['reward_type'], achv['reward_val']
                msg = ""
                if r_type == 'coins': add_coins(uid, r_val); msg = f"+{r_val} монет!"
                elif r_type == 'title': set_title(uid, r_val); msg = "Титул получен!"
                elif r_type == 'emoji': set_emoji(uid, r_val); msg = "Эмоджи получено!"
                cursor.execute("INSERT OR REPLACE INTO user_level_achievements (user_id, achv_id, claimed) VALUES (?, ?, 1)", (uid, achv_id))
                conn.commit()
                kb, text = achievements_menu(uid)
                bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown", reply_markup=kb)
                bot.answer_callback_query(call.id, msg)
        else: bot.answer_callback_query(call.id, "Уже получено!", show_alert=True)
    elif call.data == "rps": bot.edit_message_text("🪨 *КАМЕНЬ НОЖНИЦЫ БУМАГА*\n\nЯ буду анализировать твои ходы!", cid, call.message.message_id, parse_mode="Markdown", reply_markup=rps_keyboard())
    elif call.data == "rps_again": bot.edit_message_text("🪨 *КАМЕНЬ НОЖНИЦЫ БУМАГА*\n\nЯ буду анализировать твои ходы!", cid, call.message.message_id, parse_mode="Markdown", reply_markup=rps_keyboard())
    elif call.data.startswith("rps_"):
        if call.data == "rps_exit": bot.edit_message_text("🎮 Выбери игру", cid, call.message.message_id, reply_markup=games_menu()); return
        user_choice = int(call.data.split("_")[1])
        bot_choice = rps_predict_move(uid)
        RPS_HISTORY[uid].append(user_choice)
        if len(RPS_HISTORY[uid]) > 10: RPS_HISTORY[uid].pop(0)
        result_text = "🤝 Ничья!" if user_choice == bot_choice else "🎉 Ты победил!" if (user_choice == 0 and bot_choice == 2) or (user_choice == 1 and bot_choice == 0) or (user_choice == 2 and bot_choice == 1) else "🤖 Я победил!"
        if result_text == "🎉 Ты победил!": update_stats(uid, True); add_coins(uid, 15); add_xp(uid, 10); add_rps_win(uid)
        else: update_stats(uid, False)
        res_markup = types.InlineKeyboardMarkup()
        res_markup.add(types.InlineKeyboardButton("🔄 Ещё раз", callback_data='rps_again'), types.InlineKeyboardButton("🏠 В меню", callback_data='back_main'))
        bot.edit_message_text(f"🪨 Камень Ножницы Бумага\n\nТы: {RPS_MOVES[user_choice]}\nБот: {RPS_MOVES[bot_choice]}\n\n{result_text}", cid, call.message.message_id, reply_markup=res_markup)
    elif call.data == 'crest':
        tic_games[uid] = [' '] * 9; save_game(uid, "Крестики-Нолики", "tic", 0, 0)
        bot.edit_message_text("❌ Крестики-Нолики ⭕\n\nТы играешь X\nТвой ход:", cid, call.message.message_id, reply_markup=t_keyboard(tic_games[uid]))
    elif call.data.startswith("t_"):
        if uid not in tic_games: return
        if call.data == "t_exit": del tic_games[uid]; bot.edit_message_text("🎮 Выбери игру", cid, call.message.message_id, reply_markup=games_menu()); return
        index = int(call.data.split("_")[1]); board = tic_games[uid]
        if board[index] != ' ' or t_check_winner(board): return
        board[index] = 'X'
        result = t_check_winner(board)
        if not result:
            ai_move = t_best_move(board, get_difficulty(uid))
            if ai_move is not None and ai_move >= 0: board[ai_move] = 'O'
            result = t_check_winner(board)
        if result:
            if result == 'X': update_stats(uid, True); add_coins(uid, 30); add_tic_win(uid); text = "🎉 Ты победил!\n💰 +30 монет"
            elif result == 'O': update_stats(uid, False); text = "🤖 Я победил!"
            else: update_stats(uid, False); text = "🤝 Ничья!"
            delete_active_game(uid); del tic_games[uid]; bot.edit_message_text(text, cid, call.message.message_id)
        else: bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=t_keyboard(board))
    elif call.data.startswith("abuy_"):
        lid = int(call.data.split("_")[1])
        
        # ========== ПРОВЕРКА НА ПОКУПКУ СОБСТВЕННОГО ЛОТА ==========
        conn_check = sqlite3.connect(DB_NAME)
        cur_check = conn_check.cursor()
        cur_check.execute("SELECT seller_id FROM auction WHERE lot_id = ?", (lid,))
        lot_owner = cur_check.fetchone()
        conn_check.close()
        
        if lot_owner and lot_owner[0] == uid:
            bot.answer_callback_query(call.id, "❌ Вы не можете купить собственный товар!", show_alert=True)
            return # Моментально останавливаем функцию, покупка не сработает!
        # ============================================================
        
        # Если это чужой лот, запускаем твою стандартную покупку
        success, message = buy_lot(lid, uid)
        bot.answer_callback_query(call.id, message, show_alert=True)
        
        # Обновляем список лотов на экране
        lots = get_auction_lots()
        kb = types.InlineKeyboardMarkup(row_width=1)
        if not lots:
            text = "🏛 **АУКЦИОН**\n\nСейчас нет active лотов."
        else:
            text = "🏛 **АУКЦИОННЫЙ ДОМ**\n\nНажми на товар, чтобы купить его:"
            for lot in lots:
                lid_new, val, pr, sid = lot
                kb.add(types.InlineKeyboardButton(f"📦 {val} — 💰 {pr}", callback_data=f"abuy_{lid_new}"))
        kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
        bot.edit_message_text(text, cid, call.message.message_id, reply_markup=kb, parse_mode="Markdown")   
    elif call.data == "open_inventory":
        items = get_user_inventory(uid)
        kb = types.InlineKeyboardMarkup(row_width=3)
        if not items:
            text = "🎒 **ТВОЙ ИНВЕНТАРЬ**\n\nТут пока пусто. Покупай редкие значки на аукционе или в магазине!"
        else:
            text = "🎒 **ТВОЙ ИНВЕНТАРЬ**\n\nНажми на значок, чтобы надеть его:"
            btns = []
            for item_val, is_active in items:
                status = "✅" if is_active else ""
                btns.append(types.InlineKeyboardButton(f"{item_val} {status}", callback_data=f"equip_{item_val}"))
            kb.add(*btns)
        kb.add(types.InlineKeyboardButton("⬅ Назад в профиль", callback_data="prof"))
        bot.edit_message_text(text, cid, call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    elif call.data.startswith("equip_"):
        emoji = call.data.replace("equip_", "")
        set_active_emoji(uid, emoji)
        openbot_id.update_emoji(uid, emoji)
        bot.answer_callback_query(call.id, f"Вы установили символ: {emoji}")
        
        # Безопасное обновление кнопок с защитой от вылета
        try:
            bot.edit_message_reply_markup(cid, call.message.message_id, reply_markup=call.message.reply_markup)
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in e.description:
                raise e
    elif call.data == "my_lots":
        user_lots = get_user_lots(uid)
        kb = types.InlineKeyboardMarkup(row_width=1)
        text = "📂 **ВАШИ ТОВАРЫ НА ПРОДАЖЕ**\n\nЗдесь отображаются ваши лоты. Нажмите на товар, чтобы забрать его обратно в инвентарь:"
        if user_lots:
            for lid, val, price in user_lots:
                kb.add(types.InlineKeyboardButton(f"❌ Вернуть {val} ({price} 💰)", callback_data=f"clot_{lid}"))
        kb.add(types.InlineKeyboardButton("⬅ К аукциону", callback_data="auction_list"))
        bot.edit_message_text(text, cid, call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    elif call.data.startswith("clot_"):
        lid = int(call.data.split("_")[1])
        if cancel_lot(lid, uid):
            bot.answer_callback_query(call.id, "✅ Предмет вернулся в инвентарь!")
            user_lots = get_user_lots(uid)
            kb = types.InlineKeyboardMarkup(row_width=1)
            text = "📂 **ВАШИ ТОВАРЫ НА ПРОДАЖЕ**\n\nЗдесь отображаются ваши лоты. Нажмите на товар, чтобы забрать его обратно в инвентарь:"
            if user_lots:
                for l_id, val, pr in user_lots:
                    kb.add(types.InlineKeyboardButton(f"❌ Вернуть {val} ({pr} 💰)", callback_data=f"clot_{l_id}"))
            kb.add(types.InlineKeyboardButton("⬅ К аукциону", callback_data="auction_list"))
            bot.edit_message_text(text, cid, call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    elif call.data == "auction_list":
        lots = get_auction_lots()
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("📦 Мои товары (Управление)", callback_data="my_lots"))
        text = "🏛 **АУКЦИОННЫЙ ДОМ**\n\nВыбирай товары из списка ниже:"
        if lots:
            for lot in lots:
                lid, val, price, sid = lot
                tag = " (Ваш)" if sid == uid else ""
                kb.add(types.InlineKeyboardButton(f"📦 {val} — 💰 {price}{tag}", callback_data=f"abuy_{lid}"))
        kb.add(types.InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
        bot.edit_message_text(text, cid, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

if __name__ == "__main__":
    print(f"[ Успешно ] Бот рапущен и готов к работе!")
    while True:
        try:
            # Используем увеличенные интервалы для стабильности
            bot.polling(non_stop=True, timeout=120)
        except Exception as e:
            print(f"Ошибка сети или API: {e}")
            # Ждем 5 секунд перед перезапуском, чтобы не спамить Telegram
            import time
            time.sleep(5)