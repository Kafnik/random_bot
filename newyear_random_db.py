"""Random Bot holiday SQLite database: promos, gifts, titles, claims.

All holiday tables reside only in Newyear_random.db. Main game coins and
equipped title must remain in the existing game database; ATTACH ensures
reward and redemption records are committed in one transaction.
"""
import re
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path
from random import SystemRandom

from telebot import types

STAFF = frozenset({'owner', 'developer', 'admin', 'tester'})
NEWYEAR_START = date(2026, 12, 20)
NEWYEAR_END = date(2027, 1, 10)
BIRTHDAY = date(2026, 12, 27)
TITLES = {'winter26': '❄️ Зимний герой', 'birthday26': '🎂 С нами 1 год'}
_rng = SystemRandom()


class HolidayEvents:
    def __init__(self, bot, api, main_db, event_db, create_user, profile_titles):
        self.bot = bot
        self.api = api
        self.main_db = Path(main_db).resolve()
        self.event_db = Path(event_db).resolve()
        self.create_user = create_user
        profile_titles.update(TITLES)
        if not self.main_db.is_file():
            raise FileNotFoundError(f'Основная база не найдена: {self.main_db}')
        self.event_db.parent.mkdir(parents=True, exist_ok=True)
        previous_db = self.event_db.parent / "holiday_promo.db"
        if not self.event_db.exists() and previous_db.is_file():
            # SQLite online backup is safe even if the old database is in WAL mode.
            with sqlite3.connect(str(previous_db), timeout=15) as original:
                with sqlite3.connect(str(self.event_db), timeout=15) as destination:
                    original.backup(destination)
        self._initialize()
        self._handlers()

    def _db(self):
        conn = sqlite3.connect(str(self.main_db), timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA busy_timeout=15000')
        conn.execute('ATTACH DATABASE ? AS holiday', (str(self.event_db),))
        return conn

    def _initialize(self):
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS holiday.promos (
                code TEXT PRIMARY KEY, kind TEXT NOT NULL, reward TEXT NOT NULL,
                max_uses INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0,
                expires TEXT NOT NULL, author_id INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS holiday.claims (
                code TEXT NOT NULL, user_id INTEGER NOT NULL,
                claimed_at TEXT NOT NULL, PRIMARY KEY(code,user_id))''')
            db.execute('''CREATE TABLE IF NOT EXISTS holiday.gifts (
                user_id INTEGER NOT NULL, gift_key TEXT NOT NULL,
                amount INTEGER NOT NULL, received_at TEXT NOT NULL,
                PRIMARY KEY(user_id,gift_key))''')
            db.execute("""CREATE TABLE IF NOT EXISTS holiday.calendar_claims (
                user_id INTEGER NOT NULL, reward_day TEXT NOT NULL,
                claimed_at TEXT NOT NULL, PRIMARY KEY(user_id,reward_day))""")
            db.execute('''CREATE TABLE IF NOT EXISTS holiday.titles (
                user_id INTEGER NOT NULL, title_key TEXT NOT NULL,
                earned_at TEXT NOT NULL, PRIMARY KEY(user_id,title_key))''')

    def _staff(self, uid):
        # Check the remote Openbot API directly; local bot roles aren't authoritative.
        try:
            info = self.api.get_user(uid)
            return bool(info and info.get('exists') and
                        str(info.get('status', '')).lower() in STAFF)
        except Exception:
            return False

    def _allowed(self, uid):
        try:
            return not self.api.is_globally_banned(uid)
        except Exception:
            return False

    def _ensure_user(self, message):
        uid = message.from_user.id
        self.create_user(uid, message.from_user.username, message.from_user.first_name)
        return uid

    def _reward(self, db, user_id, kind, reward):
        if kind == 'coins':
            amount = int(reward)
            row = db.execute('UPDATE users SET coins=COALESCE(coins,0)+? WHERE user_id=?',
                             (amount, user_id))
            if row.rowcount != 1:
                raise ValueError('Профиль не найден. Сначала /start')
            return f'🪙 +{amount:,} монет'.replace(',', ' ')
        if kind == 'title':
            if reward not in TITLES:
                raise ValueError('Неизвестный титул')
            db.execute('INSERT OR IGNORE INTO holiday.titles VALUES (?,?,?)',
                       (user_id, reward, datetime.now().isoformat()))
            db.execute('UPDATE users SET profile_title=? WHERE user_id=?', (reward, user_id))
            return f'🏅 Титул «{TITLES[reward]}»'
        raise ValueError('Неподдерживаемая награда')

    def _claim_gift(self, message, key, amount, kind='coins'):
        if not self._allowed(message.from_user.id):
            return self.bot.reply_to(message, '⛔ Нет доступа или API временно недоступен.')
        uid = self._ensure_user(message)
        try:
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO holiday.gifts VALUES (?,?,?,?)',
                           (uid, key, amount, datetime.now().isoformat()))
                result = self._reward(db, uid, kind, str(amount))
                if key == 'birthday:2026':
                    self._reward(db, uid, 'title', 'birthday26')
                    result += '\n🏅 Титул «🎂 С нами 1 год»'
                elif key.startswith('daily:'):
                    first_title = db.execute(
                        'SELECT 1 FROM holiday.titles WHERE user_id=? AND title_key=?',
                        (uid, 'winter26')).fetchone()
                    if not first_title:
                        self._reward(db, uid, 'title', 'winter26')
                        result += '\n🏅 Титул «❄️ Зимний герой»'
            self.bot.reply_to(message, f'🎁 Подарок получен! {result}')
        except sqlite3.IntegrityError:
            self.bot.reply_to(message, '✅ Ты уже забрал этот подарок.')
        except Exception:
            self.bot.reply_to(message, '⚠️ Не удалось получить подарок. Проверь логи бота.')
            raise

    # 13 independent daily rewards. No automatic menu switching.
    CALENDAR_REWARDS = (
        ('2026-12-20', '🪙', 500),
        ('2026-12-21', '❄️', 5),
        ('2026-12-22', '🪙', 750),
        ('2026-12-23', '❄️', 10),
        ('2026-12-24', '🪙', 1000),
        ('2026-12-25', '🎁', 1),
        ('2026-12-26', '❄️', 15),
        ('2026-12-27', '🪙', 2026),
        ('2026-12-28', '🪙', 2000),
        ('2026-12-29', '❄️', 20),
        ('2026-12-30', '🎁', 1),
        ('2026-12-31', '🪙', 5000),
        ('2027-01-01', '🎆', 100000),
    )

    def _calendar_info(self, user_id):
        with self._db() as db:
            claimed = {r[0] for r in db.execute(
                'SELECT reward_day FROM holiday.calendar_claims WHERE user_id=?',
                (user_id,)).fetchall()}
        return claimed

    def show_calendar(self, message):
        uid = message.from_user.id
        claimed = self._calendar_info(uid)
        now = date.today().isoformat()
        lines = ['🎄 <b>НОВОГОДНИЙ КАЛЕНДАРЬ</b>',
                 '20 декабря 2026 — 1 января 2027', '',
                 '🎁 Один подарок в день. Пропущенные дни не открываются.', '']
        for day, icon, amount in self.CALENDAR_REWARDS:
            label = date.fromisoformat(day).strftime('%d.%m')
            mark = '✅' if day in claimed else ('🎁' if day == now else '🔒')
            reward = f'{amount:,} монет'.replace(',', ' ') if icon in ('🪙', '🎆') else (
                f'{amount} снежинок' if icon == '❄️' else '1 праздничный кейс')
            lines.append(f'{mark} <b>{label}</b> — {icon} {reward}')
        lines += ['', '🎆 1 января — главный приз: 100 000 монет!',
                  'Нажми кнопку ниже, чтобы забрать сегодняшний подарок.']
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton('🎁 Забрать подарок дня', callback_data='calendar_claim'))
        self.bot.send_message(message.chat.id, '\n'.join(lines),
                              reply_markup=kb, parse_mode='HTML')

    def claim_calendar(self, message):
        today = date.today().isoformat()
        items = {d: (icon, amount) for d, icon, amount in self.CALENDAR_REWARDS}
        if today not in items:
            return '🔒 Календарь работает с 20.12.2026 по 01.01.2027.'
        uid = message.from_user.id
        if not self._allowed(uid):
            return '⛔ Нет доступа или API недоступен.'
        self._ensure_user(message)
        icon, amount = items[today]
        try:
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO holiday.calendar_claims(user_id,reward_day,claimed_at) '
                           'VALUES(?,?,?)', (uid, today, datetime.now().isoformat()))
                if icon in ('🪙', '🎆'):
                    result = db.execute('UPDATE users SET coins=COALESCE(coins,0)+? WHERE user_id=?',
                                        (amount, uid))
                    if result.rowcount != 1:
                        raise ValueError('Профиль не найден, используй /start')
                    text = f'{amount:,} монет'.replace(',', ' ')
                elif icon == '❄️':
                    db.execute('CREATE TABLE IF NOT EXISTS holiday.winter_players '
                               '(user_id INTEGER PRIMARY KEY, snowflakes INTEGER NOT NULL DEFAULT 0)')
                    db.execute('INSERT INTO holiday.winter_players(user_id,snowflakes) VALUES(?,?) '
                               'ON CONFLICT(user_id) DO UPDATE SET snowflakes=snowflakes+excluded.snowflakes',
                               (uid, amount))
                    text = f'{amount} снежинок'
                else:
                    db.execute('CREATE TABLE IF NOT EXISTS holiday.winter_cases '
                               '(user_id INTEGER NOT NULL, case_key TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0, '
                               'PRIMARY KEY(user_id,case_key))')
                    db.execute('INSERT INTO holiday.winter_cases(user_id,case_key,count) VALUES(?,?,1) '
                               'ON CONFLICT(user_id,case_key) DO UPDATE SET count=count+1',
                               (uid, 'gold'))
                    text = 'золотой кейс'
            return f'🎁 Подарок получен! {icon} {text}'
        except sqlite3.IntegrityError:
            return '✅ Подарок за сегодня уже получен.'
        except Exception:
            import logging
            logging.exception('Ошибка выдачи календарной награды')
            return '⚠️ Не удалось выдать подарок. Проверь логи.'

    def _handlers(self):
        bot = self.bot

        @bot.message_handler(commands=['calendar'])
        def calendar_command(message):
            self.show_calendar(message)

        @bot.callback_query_handler(func=lambda c: c.data == 'calendar_claim')
        def calendar_callback(call):
            class Msg:
                chat = call.message.chat
                from_user = call.from_user
                message_id = call.message.message_id
            bot.answer_callback_query(call.id, self.claim_calendar(Msg()), show_alert=True)

        @bot.message_handler(commands=['newyear', 'holiday'])
        def holiday(message):
            today = date.today()
            status = '🟢 Идёт!' if NEWYEAR_START <= today <= NEWYEAR_END else '🔒 Пока закрыто'
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton('🎁 Ежедневный подарок', callback_data='holiday_daily'))
            kb.add(types.InlineKeyboardButton('🎂 Подарок на день рождения', callback_data='holiday_birthday'))
            bot.reply_to(message, '🎄 Новогоднее событие Openbot.Ai\n'
                         '20.12.2026–10.01.2027\n'
                         f'Статус: {status}\n\n'
                         '🎂 27 декабря — день рождения комьюнити!\n'
                         '🎟 /promo КОД — использовать промокод\n'
                         '🎁 /daily_gift — подарок дня\n'
                         '🎂 /birthday_gift — праздничный подарок', reply_markup=kb)

        @bot.callback_query_handler(func=lambda c: c.data in ('holiday_daily', 'holiday_birthday'))
        def holiday_callback(call):
            bot.answer_callback_query(call.id)
            class Msg:
                chat = call.message.chat
                from_user = call.from_user
                message_id = call.message.message_id
            if call.data == 'holiday_daily':
                daily(Msg())
            else:
                birthday(Msg())

        @bot.message_handler(commands=['daily_gift'])
        def daily(message):
            if not NEWYEAR_START <= date.today() <= NEWYEAR_END:
                return bot.reply_to(message, '🔒 Подарки доступны с 20.12.2026 по 10.01.2027.')
            amount = 250  # fixed daily reward; retrying cannot reroll
            self._claim_gift(message, 'daily:' + date.today().isoformat(), amount)

        @bot.message_handler(commands=['birthday_gift'])
        def birthday(message):
            if date.today() != BIRTHDAY:
                return bot.reply_to(message, '🎂 Подарок доступен только 27 декабря 2026 года.')
            self._claim_gift(message, 'birthday:2026', 2026)

        @bot.message_handler(commands=['promo'])
        def redeem(message):
            parts = (message.text or '').split()
            if len(parts) != 2:
                return bot.reply_to(message, '🎟 Использование: /promo НАЗВАНИЕ')
            code = parts[1].strip().upper()
            if not re.fullmatch(r'[A-Z0-9_-]{3,32}', code):
                return bot.reply_to(message, '❌ Неверный формат промокода.')
            if not self._allowed(message.from_user.id):
                return bot.reply_to(message, '⛔ Нет доступа или API временно недоступен.')
            uid = self._ensure_user(message)
            try:
                with self._db() as db:
                    db.execute('BEGIN IMMEDIATE')
                    p = db.execute('SELECT * FROM holiday.promos WHERE code=?', (code,)).fetchone()
                    if not p or not p['active']:
                        return bot.reply_to(message, '❌ Промокод не существует или отключён.')
                    if date.fromisoformat(p['expires']) < date.today():
                        return bot.reply_to(message, '⌛ Промокод истёк.')
                    if p['used'] >= p['max_uses']:
                        return bot.reply_to(message, '❌ Активации закончились.')
                    db.execute('INSERT INTO holiday.claims VALUES (?,?,?)',
                               (code, uid, datetime.now().isoformat()))
                    result = self._reward(db, uid, p['kind'], p['reward'])
                    db.execute('UPDATE holiday.promos SET used=used+1 WHERE code=?', (code,))
                bot.reply_to(message, f'🎉 Промокод {code} активирован!\n{result}')
            except sqlite3.IntegrityError:
                bot.reply_to(message, '✅ Ты уже активировал этот промокод.')
            except Exception:
                bot.reply_to(message, '⚠️ Ошибка активации. Смотри логи.')
                raise

        @bot.message_handler(commands=['new_promo'])
        def create(message):
            if not self._staff(message.from_user.id):
                return bot.reply_to(message, '⛔ Создание доступно owner, developer, admin и tester.')
            parts = (message.text or '').split()
            if len(parts) != 5:
                return bot.reply_to(message, '⚙️ /new_promo КОД НАГРАДА ЛИМИТ ДАТА\n'
                                    'Пример: /new_promo WINTER2026 500 50 2027-01-10\n'
                                    'Титул: /new_promo WINTERTITLE title:winter26 20 2027-01-10')
            _, code, prize, count, expiry = parts
            code = code.upper()
            if not re.fullmatch(r'[A-Z0-9_-]{3,32}', code):
                return bot.reply_to(message, '❌ Код: 3–32 символа A-Z, 0-9, _ или -.')
            try:
                limit = int(count)
                end = date.fromisoformat(expiry)
                if not 1 <= limit <= 100000 or end < date.today():
                    raise ValueError()
                if prize.startswith('title:'):
                    kind, value = 'title', prize.removeprefix('title:')
                    if value not in TITLES:
                        raise ValueError()
                else:
                    kind, value = 'coins', str(int(prize))
                    if not 1 <= int(value) <= 1000000:
                        raise ValueError()
            except ValueError:
                return bot.reply_to(message, '❌ Проверь награду (1–1 000 000), лимит и дату YYYY-MM-DD.')
            try:
                with self._db() as db:
                    db.execute('INSERT INTO holiday.promos '
                               '(code,kind,reward,max_uses,expires,author_id,created_at) '
                               'VALUES (?,?,?,?,?,?,?)',
                               (code, kind, value, limit, end.isoformat(),
                                message.from_user.id, datetime.now().isoformat()))
                bot.reply_to(message, f'✅ Создан промокод {code}. Лимит: {limit}, до {end}.')
            except sqlite3.IntegrityError:
                bot.reply_to(message, '❌ Такой промокод уже существует.')

        @bot.message_handler(commands=['promos'])
        def promos(message):
            if not self._staff(message.from_user.id):
                return bot.reply_to(message, '⛔ Нет прав.')
            with self._db() as db:
                rows = db.execute('SELECT code,used,max_uses,expires,active FROM holiday.promos '
                                  'ORDER BY created_at DESC LIMIT 20').fetchall()
            txt = '\n'.join(f"{p['code']}: {p['used']}/{p['max_uses']}, "
                            f"до {p['expires']} {'✅' if p['active'] else '⛔'}" for p in rows)
            bot.reply_to(message, '🎟 Промокоды:\n' + (txt or 'Пока нет.'))

        @bot.message_handler(commands=['del_promo'])
        def delete(message):
            if not self._staff(message.from_user.id):
                return bot.reply_to(message, '⛔ Нет прав.')
            parts = (message.text or '').split()
            if len(parts) != 2:
                return bot.reply_to(message, 'Использование: /del_promo КОД')
            code = parts[1].upper()
            with self._db() as db:
                n = db.execute('UPDATE holiday.promos SET active=0 WHERE code=?', (code,)).rowcount
            bot.reply_to(message, '✅ Промокод отключён.' if n else '❌ Промокод не найден.')

# --- Winter game inventory: entirely inside Newyear_random.db ---
import threading
import os

_winter_lock = threading.RLock()
_winter_file = Path(__file__).resolve().parent / 'Newyear_random.db'


def init(db_path=None):
    global _winter_file
    with _winter_lock:
        target = Path(db_path or 'Newyear_random.db')
        if not target.is_absolute():
            target = Path(__file__).resolve().parent / target
        _winter_file = target.resolve()
        _winter_file.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(_winter_file) as db:
            db.execute('CREATE TABLE IF NOT EXISTS winter_players (user_id INTEGER PRIMARY KEY, snowflakes INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS winter_cases (user_id INTEGER NOT NULL, case_key TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id,case_key))')
            db.execute('CREATE TABLE IF NOT EXISTS winter_owned_titles (user_id INTEGER NOT NULL, title_key TEXT NOT NULL, price INTEGER DEFAULT 0, PRIMARY KEY(user_id,title_key))')
        return str(_winter_file)


def _winter_connection():
    if not _winter_file.is_file():
        init()
    return sqlite3.connect(_winter_file, timeout=15)


def get_keys(user_id):
    with _winter_lock, _winter_connection() as db:
        row = db.execute('SELECT snowflakes FROM winter_players WHERE user_id=?', (user_id,)).fetchone()
        return int(row[0]) if row else 0


def add_keys(user_id, amount=1, reason=''):
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise ValueError('Количество снежинок должно быть положительным')
    with _winter_lock, _winter_connection() as db:
        db.execute('INSERT INTO winter_players(user_id,snowflakes) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET snowflakes=snowflakes+excluded.snowflakes', (user_id, amount))
    return get_keys(user_id)


def spend_keys(user_id, amount=1, reason=''):
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise ValueError('Неверное количество снежинок')
    with _winter_lock, _winter_connection() as db:
        row = db.execute('UPDATE winter_players SET snowflakes=snowflakes-? WHERE user_id=? AND snowflakes>=?', (amount,user_id,amount))
        return row.rowcount == 1


def get_case_count(user_id, case_key):
    with _winter_lock, _winter_connection() as db:
        row = db.execute('SELECT count FROM winter_cases WHERE user_id=? AND case_key=?', (user_id,case_key)).fetchone()
        return int(row[0]) if row else 0


def add_case(user_id, case_key, amount=1, reason=''):
    if amount <= 0: raise ValueError('Неверное количество кейсов')
    with _winter_lock, _winter_connection() as db:
        db.execute('INSERT INTO winter_cases(user_id,case_key,count) VALUES(?,?,?) ON CONFLICT(user_id,case_key) DO UPDATE SET count=count+excluded.count', (user_id,case_key,amount))
    return get_case_count(user_id,case_key)


def take_case(user_id, case_key, reason=''):
    with _winter_lock, _winter_connection() as db:
        row = db.execute('UPDATE winter_cases SET count=count-1 WHERE user_id=? AND case_key=? AND count>0', (user_id,case_key))
        return row.rowcount == 1


def record_title(user_id,title_key,price=0):
    with _winter_lock, _winter_connection() as db:
        row=db.execute('INSERT OR IGNORE INTO winter_owned_titles(user_id,title_key,price) VALUES(?,?,?)',(user_id,title_key,price))
        return row.rowcount == 1


def get_titles(user_id):
    with _winter_lock, _winter_connection() as db:
        rows=db.execute('SELECT title_key FROM winter_owned_titles WHERE user_id=? ORDER BY rowid',(user_id,)).fetchall()
        return [r[0] for r in rows]
