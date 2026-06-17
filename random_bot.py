import telebot
import random
import time
import json
import os
import threading
from telebot import types
from datetime import datetime
from datetime import datetime, timedelta
import configparser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(BASE_DIR, "config.cfg")

config = configparser.ConfigParser()
config.read(CFG_PATH, encoding="utf-8")

if not config.has_section("BOT"):
    input("❌ config.cfg НЕ НАЙДЕН ИЛИ ПУСТОЙ. Нажми Enter...")
    exit()

raw_token = config["BOT"]["TOKEN"]


bot = telebot.TeleBot(config["BOT"]["TOKEN"])


gifts = ["📱 Новый телефон", "🎧 Наушники", "🧸 Мишка", "🍫 Шоколадка", "🧦 Носки", "🎮 Геймпад", "🎆 Фейерверк"]
food = ["🍫 Горячий шоколад","☕ Какао с маршмеллоу", "🍰 Медовик", "🍲 Борщ"]
orel = ["Орёл 🦅", "Решка 💰"]
random_games = ["🎲 Рандом число", "🍔 Рандомная еда", "🪙 Орел или решка", "🎯 Снежная рулетка", "✨ Пожелание"]
event = ["🎁 Ты нашёл подарок!",
            "⛄ Снеговик улыбается тебе!",
            "❄️ Снежинка падает прямо на тебя!",
            "🎄 Ёлка сияет для тебя!",
            "🧦 Тёплые носочки под ёлкой!",
            "🧤 Варежки в подарок!",
            "🍪 Имбирное печенье!",
            "🎆 Яркий фейерверк в небе!"]
vip_gifts = [
  "💎 iPhone 17 Pro Max",
  "👑 Rolex Gold",
  "🚗 Tesla Model Y",
  "💠 10 000 алмазов",
  "🔥 Лимитированный скин",
  "🛸 НЛО модель",
  "💵 1 000 000$",
   "🎟 Билет в премиум мир"
]
roulette_items = [
 "💰 Джекпот!", "🔥 Супер шанс", "✨ Удача", "🎯 Почти!", "💀 Не повезло",
 "🚀 Полёт", "👑 Королевский шанс", "💎 Алмазный выигрыш"
]
emotions = [
    "😄 Радость", "😢 Грусть", "😡 Злость", "😱 Страх",
    "😍 Влюблённость", "😴 Сонливость", "🤔 Размышление",
    "😎 Уверенность", "😇 Спокойствие", "🤯 Шок"]
STATUS = {
    "developer": "🌐💠 Openbot.Ai",
    "admin": "⭐ Администратор", 
    "user": "👤 Игрок", 
    "banned": "🚫 Забаненный",
}
# Списки кейсов и их награды
CASES = {
    "обычный": {
        "price": 50,
        "rewards": [
            {"type": "premium", "days": 1, "chance": 40},
            {"type": "premium", "days": 3, "chance": 30},
            {"type": "currency", "amount": 25, "chance": 20},
            {"type": "currency", "amount": 50, "chance": 10}
        ]
    },
    "редкий": {
        "price": 200,
        "rewards": [
            {"type": "premium", "days": 7, "chance": 35},
            {"type": "premium", "days": 15, "chance": 25},
            {"type": "currency", "amount": 100, "chance": 20},
            {"type": "currency", "amount": 200, "chance": 15},
            {"type": "currency", "amount": 500, "chance": 5}
        ]
    },
    "эпический": {
        "price": 500,
        "rewards": [
            {"type": "premium", "days": 30, "chance": 30},
            {"type": "premium", "days": 60, "chance": 25},
            {"type": "currency", "amount": 1000, "chance": 20},
            {"type": "currency", "amount": 2500, "chance": 15},
            {"type": "currency", "amount": 5000, "chance": 10}
        ]
    },
    "легендарный": {
        "price": 1000,
        "rewards": [
            {"type": "premium", "days": 90, "chance": 25},
            {"type": "premium", "days": 180, "chance": 20},
            {"type": "premium_forever", "chance": 5},
            {"type": "currency", "amount": 10000, "chance": 20},
            {"type": "currency", "amount": 25000, "chance": 15},
            {"type": "currency", "amount": 50000, "chance": 10},
            {"type": "currency", "amount": 100000, "chance": 5}
        ]
    }
}
# Цены на премиум
PREMIUM_PRICES = {
    "7_days": {"price": 500, "days": 7},
    "30_days": {"price": 1500, "days": 30},
    "90_days": {"price": 3000, "days": 90},
    "180_days": {"price": 5000, "days": 180},
    "365_days": {"price": 8000, "days": 365}
}
text1 = """<b>🎮 RANDOMBOT - ГИД ПО ИГРАМ</b>

 <b>🎯 ОСНОВНЫЕ КОМАНДЫ</b>

 /start - Запуск бота
 /menu - Главное меню
 /random - Все игры
 /profile - Мой профиль


 <b>🎲 ОБЫЧНЫЕ ИГРЫ</b>
 - 🎯 Кубик +3 🪙
 - 🍔 Еда +2 🪙  
 - 🪙 Орел/решка** +2 🪙
 - 🎁 Подарок +6 🪙
 - 🎯 Рулетка +3 🪙
 - ✨ Пожелание +2 🪙

 <b>💎 ПРЕМИУМ ИГРЫ</b>
 - 🎲 Mega Dice +10 🪙
 - 🎡 Ультра рулетка +8 🪙
 - 🎲 Двойной рандом +12 🪙
 - 😀 Эмоция дня +6 🪙
 - 🎁 VIP подарок +15 🪙

 <b>🎁 КЕЙСЫ</b>
 - 📦 Обычный (50 🪙) - премиум 1-3 дня
 - 🎁 Редкий (200 🪙) - премиум 7-15 дней
 - 💜 Эпический (500 🪙) - премиум 30-60 дней
 - 👑 Легендарный (1000 🪙) - шанс на премиум НАВСЕГДА!

 <b>💰 ЗАРАБОТОК</b>
 - Играй в игры - получай 🪙 за каждую игру
 - Открывай кейсы - выигрывай премиум и валюту
 - Купи премиум - получай больше 🪙 и эксклюзивные игры

 <b>⚙️ НАСТРОЙКИ</b>
 - 🎭 Анимации вкл/выкл
 - 💯 Диапазон чисел
 - 💎 Цвет ника (премиум)

 🚀 Начни играть: /start"""


info_RandomOS = """🎲 <b>RandomOS - Будущая система</b>

 <i>⚙ В разработке</i>

 Предпологается что будет:
 • Лимитами на рандом
 • Статистикой использования
 • Улучшениями генерации
 • Системой удачи пользователей

 <b>Планируется в обновлении 3.0</b>
 <b>Но полный релиз 2.0</b>

 Следите за обновлениями! 🚀"""

BOT_ENABLED = True

# Имя файла для хранения данных
DATA_FILE = 'users_data_random_bot.json'

# Функция для загрузки данных из JSON
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

# Функция для сохранения данных в JSON
def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def register_user(user_id, first_name, username=None):
    user_data = load_data()
    user_id = str(user_id)

    # ID бота (замени на реальный ID твоего бота если нужно)
    BOT_IDS = ['8493714047']  # Добавь сюда ID бота
    
    # Проверяем, не является ли пользователь ботом
    if user_id in BOT_IDS:
        return False  # ⚠️ Бот не может быть зарегистрирован

    if user_id not in user_data:
        user_data[user_id] = {
            "first_name": first_name,
            "color": "",
            "id" : user_id,
            "username": username if username else "нет",
            "data" : datetime.now().strftime("%d.%m.%Y"),
            "number" : 10,
            "number_vip" : 1000,
            "number_two" : 1000,
            "animations" : True,
            "status" : 'user', 
            "currency": 0,
            "premium" : False,
            "banned": False,
            "ban_reason": None,
            "ban_date": None,
            "banned_by": None
        }
        save_data(user_data)
        return True  # ✅ Новый пользователь успешно зарегистрирован
    else:
        return False  # ⚠️ Пользователь уже есть

def antimois(message, text='Выберите действие'):
    markup = types.InlineKeyboardMarkup(row_width=2)
    off = types.InlineKeyboardButton('✅ Включить', callback_data='on1')
    on = types.InlineKeyboardButton('❌ Выключить', callback_data='off2')
    hext = types.InlineKeyboardButton('⬅ Назад', callback_data='hext1')
    markup.add(off, on, hext)
    bot.edit_message_text(
        text,
        message_id=message.message_id,
        chat_id=message.chat.id,
        reply_markup=markup)

def main_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    num1 = types.InlineKeyboardButton("🎲 Рандом_игры", callback_data='num1')
    num2 = types.InlineKeyboardButton("🛍 Магазин", callback_data='mag')
    num3 = types.InlineKeyboardButton("⚙ Настройки", callback_data='num2')
    profel = types.InlineKeyboardButton('👤 Профиль', callback_data='prof')
    markup.add(num1, num2, num3, profel)
    bot.edit_message_text('Добро пожаловать в галвное меню !', message_id=message.message_id, chat_id=message.chat.id, reply_markup=markup)

def setting(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    set1 = types.InlineKeyboardButton("💯 Диопозон рандома", callback_data='set1')
    set2 = types.InlineKeyboardButton("🎭 Анимации", callback_data='set2')
    set3 = types.InlineKeyboardButton('💎 Настройки премиума', callback_data='set3')
    doc1 = types.InlineKeyboardButton('📋 Документация об ОС', callback_data='randomOS_info1')
    hext1 = types.InlineKeyboardButton('⬅ Назад', callback_data='hext')
    markup.add(set1, set2, set3, doc1, hext1)
    bot.edit_message_text("Добро пожаловать в настройки.",message_id=message.message_id, chat_id=message.chat.id, reply_markup=markup)

def premium_random_mune(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🎲 Mega Dice 10К", callback_data='btn8')
    btn2 = types.InlineKeyboardButton("🎡 Ультра рулетка", callback_data='btn9')
    btn3 = types.InlineKeyboardButton("🎲 Двойной рандом", callback_data='btn10')
    btn4 = types.InlineKeyboardButton("😀 Эмоция дня (эксклюзивная)", callback_data='btn11')
    btn5 = types.InlineKeyboardButton("🎁 VIP Подарок", callback_data='btn12')
    btn6 = types.InlineKeyboardButton("📋 Обычное рандом меню", callback_data='btn14')
    btn7 = types.InlineKeyboardButton("⬅ Назад", callback_data='hext')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)
    bot.edit_message_text('Меню игр открыто!', reply_markup=markup, message_id=message.message_id, chat_id=message.chat.id)

def random_menu(message):
    bot.edit_message_text('Загрузка...', message_id=message.message_id, chat_id=message.chat.id)
    time.sleep(2)
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🎲Супер кубик", callback_data='btn1')
    btn2 = types.InlineKeyboardButton("🍔Рандомная еда", callback_data='btn2')
    btn3 = types.InlineKeyboardButton("🪙Орел или решка", callback_data='btn3')
    btn4 = types.InlineKeyboardButton("🎮 Рандомания", callback_data='btn4')
    btn5 = types.InlineKeyboardButton("🎁 Новогодний подарок 🎅", callback_data='btn5')
    btn6 = types.InlineKeyboardButton("🎯 Снежная рулетка", callback_data="btn6")
    btn7 = types.InlineKeyboardButton("✨ Пожелание", callback_data='btn7')
    btn8 = types.InlineKeyboardButton("💎 Премиум меню", callback_data='btn13')
    btn9 = types.InlineKeyboardButton("⬅ Назад", callback_data='hext')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8, btn9)
    bot.edit_message_text('Меню игр открыто!', reply_markup=markup, message_id=message.message_id, chat_id=message.chat.id)

def can_manage_admins(user_id):
    user_data = load_data()
    user_id = str(user_id)
    
    if user_id not in user_data:
        return False
        
    return user_data[user_id]['status'] in ['developer', 'admin']

def can_manage_owners(user_id):
    user_data = load_data()
    user_id = str(user_id)

    if user_id not in user_data:
        return False
        
    return user_data[user_id]['status'] == 'developer'

# Добавляем поле для хранения исходного статуса
def ban_user(target_id, reason="other", banned_by=None, custom_reason=None):
    user_data = load_data()
    target_id = str(target_id)
    
    if target_id not in user_data:
        return False
    
    # Сохраняем исходный статус перед баном
    original_status = user_data[target_id]['status']
    user_data[target_id]['original_status'] = original_status  # ← СОХРАНЯЕМ
    
    user_data[target_id]['banned'] = True
    user_data[target_id]['status'] = 'banned'
    
    if custom_reason:
        user_data[target_id]['ban_reason'] = custom_reason
    else:
        user_data[target_id]['ban_reason'] = reason
        
    user_data[target_id]['ban_date'] = datetime.now().strftime("%d.%m.%Y %H:%M")
    user_data[target_id]['banned_by'] = banned_by
    
    save_data(user_data)
    return True

def check_premium_expiry():
    user_data = load_data()
    now = datetime.now()
    notifications_sent = []
    
    for user_id, user_info in user_data.items():
        if user_info.get('premium', False) and user_info.get('premium_expires'):
            expire_date_str = user_info['premium_expires']
            
            # Пропускаем бессрочный премиум
            if expire_date_str == "∞ Навсегда":
                continue
                
            try:
                # Пробуем распарсить дату
                expire_date = datetime.strptime(expire_date_str, "%d.%m.%Y")
                days_left = (expire_date - now).days
                
                # Если премиум истек
                if days_left < 0:
                    # Снимаем премиум
                    user_data[user_id]['premium'] = False
                    user_data[user_id]['premium_expires'] = None
                    user_data[user_id]['color'] = ""  # Сбрасываем цвет
                    save_data(user_data)
                    
                    # Отправляем уведомление через твою функцию
                    notify_user(user_id, 'premium_ended')
                    notifications_sent.append(f"❌ Премиум истек у {user_info['first_name']}")
                        
                # Если остался 1 день
                elif days_left == 0:
                    # Отправляем уведомление через твою функцию
                    notify_user(int(user_id), 'premium_ending_1')
                    notifications_sent.append(f"⚠️ Последний день у {user_info['first_name']}")
                        
                # Если осталось 3 дня
                elif days_left == 3:
                    # Отправляем уведомление
                    try:
                        bot.send_message(
                            int(user_id),
                            "⏰ Внимание!\n\n"
                            "Премиум истекает через 3 дня!\n"
                            "Не забудьте продлить подписку."
                        )
                        notifications_sent.append(f"📅 3 дня осталось у {user_info['first_name']}")
                    except:
                        pass
                        
            except ValueError:
                # Если дата в неправильном формате
                continue
    
    return notifications_sent

def unban_user(target_id):
    user_data = load_data()
    target_id = str(target_id)
    
    if target_id not in user_data:
        return False
    
    # Восстанавливаем исходный статус
    original_status = user_data[target_id].get('original_status', 'user')  # ← ВОССТАНАВЛИВАЕМ
    user_data[target_id]['status'] = original_status
    
    user_data[target_id]['banned'] = False
    user_data[target_id]['ban_reason'] = None
    user_data[target_id]['ban_date'] = None
    user_data[target_id]['banned_by'] = None
    user_data[target_id]['original_status'] = None  # ← ОЧИЩАЕМ
    
    save_data(user_data)
    return True

    user_data = load_data()
    user_id = str(user_id)
    
    if user_id not in user_data:
        return False
        
    return user_data[user_id].get('banned', False)

def get_premium_days_left(premium_expires):
    """
    Возвращает количество оставшихся дней премиума
    """
    # ЕСЛИ None ИЛИ ПУСТАЯ СТРОКА - ВОЗВРАЩАЕМ "НЕ АКТИВЕН"
    if not premium_expires or premium_expires == "None":
        return "Не активен"
    
    if premium_expires == "∞ Навсегда":
        return "Навсегда 🎉"
    
    try:
        expire_date = datetime.strptime(premium_expires, "%d.%m.%Y")
        now = datetime.now()
        
        if now > expire_date:
            return "Истек ⏰"
        
        days_left = (expire_date - now).days
        
        if days_left == 0:
            return "Меньше дня"
        elif days_left == 1:
            return "1 день"
        elif days_left < 5:
            return f"{days_left} дня"
        else:
            return f"{days_left} дней"
            
    except ValueError:
        return "Ошибка даты"
    
# Функция для запуска проверки каждые 24 часа
def start_premium_checker():
    def checker():
        while True:
            try:
                notifications = check_premium_expiry()
                if notifications:
                    print(f"📊 Проверка премиума: {len(notifications)} уведомлений отправлено")
                time.sleep(86400)  # 24 часа в секундах
            except Exception as e:
                print(f"Ошибка в проверке премиума: {e}")
                time.sleep(3600)  # Ждем 1 час при ошибке
    
    thread = threading.Thread(target=checker, daemon=True)
    thread.start()
    print("✅ Система проверки премиума запущена")

def notify_user(user_id, action_type, details=""):
    """
    Уведомляет пользователя о важных изменениях
    """
    user_data = load_data()
    if str(user_id) not in user_data:
        return
    
    user_info = user_data[str(user_id)]
    reason = user_data[user_id].get('ban_reason', 'Не указана')
    changes = """Обновление 1.4
Это обвновление нам кажется самым крыпным за этот год. 
Мы добавили кучу функций, переделали код с нуля, в этом боте теперь появилась администрация.
Также сделалили систему профилей это все хрониться тоясть есали бота презапустят то тогда ваши данные не проподут, 
еще есть магазин там есть кейсы и можно купить премиум за вертуальную валюту Рандом коины, 
есть также статусы там написанно для обычных пользователей Игрок для админов Администарция добавили премиум как получать Рандом коины и все остальное или спрашиваете в поддрежке.
Появилось самое галвное feedback и поддержка. Ваш коментарий очень важен и пишите ваши идеи вы прочитаем. Пару фактов о боте в боте сейчас 2625 строк кода, 
второй команда /support при тех работах будет работать, третий факт если вы дали стоющию идею то мы вам выдадим что нибудь толи премиум или же валюты чучуть подсыпим.
Ну все остальное вы канешно все у занете в переди всех с наступающим новым годом !
    """
    
    messages = {
        'became_owner': "🎉 Вы теперь Developer бота! 👑",
        'became_admin': "🎉 Вы теперь Админ бота! ⭐", 
        'became_user' : "🔻 Вас сняли с админ прав вы теперь Игрок",
        'got_ban' : f"🚫 Вы были забанены. \nПричина {reason}",
        'got_unbanned': "✅ Вы были разбанены!",
        'got_premium_forever': "💎 Вам выдан Премиум НАВСЕГДА! 🚀",
        'got_premium_days': f"💎 Вам выдан Премиум на {details} дней!",
        'lost_premium': "❌ Ваш премиум был снят",
        'premium_ending_1': "⏰ ПОСЛЕДНИЙ ДЕНЬ!\n\nПремиум истекает ЗАВТРА!\nСрочно продлите!",
        'premium_ended': "💔 Премиум истек\n\nВаш премиум доступ закончился.\nВы потеряли:\n• Премиум игры\n• Цвет ника.",
        'bot_update': f"🔄 Обновление бота!\n\nБот был обновлен:\n{changes}",
    }
    
    if action_type in messages:
        try:
            bot.send_message(user_id, messages[action_type])
        except:
            pass  # Игнорируем ошибки отправки

def open_case(user_id, case_type):
    user_data = load_data()
    user_id = str(user_id)
    
    if user_id not in user_data:
        return None
    
    if case_type not in CASES:
        return None
    
    case = CASES[case_type]
    
    # Выбираем награду на основе шансов
    total_chance = sum(reward["chance"] for reward in case["rewards"])
    roll = random.randint(1, total_chance)
    
    current_chance = 0
    selected_reward = None
    
    for reward in case["rewards"]:
        current_chance += reward["chance"]
        if roll <= current_chance:
            selected_reward = reward
            break
    
    if not selected_reward:
        selected_reward = case["rewards"][0]
    
    # Обрабатываем награду
    reward_text = ""
    
    if selected_reward["type"] == "premium":
        days = selected_reward["days"]
        if user_data[user_id].get('premium', False):
            # Продлеваем премиум
            current_expires = user_data[user_id].get('premium_expires')
            if current_expires and current_expires != "∞ Навсегда":
                try:
                    expire_date = datetime.strptime(current_expires, "%d.%m.%Y")
                    new_expire_date = expire_date + timedelta(days=days)
                    user_data[user_id]['premium_expires'] = new_expire_date.strftime("%d.%m.%Y")
                except:
                    new_expire_date = datetime.now() + timedelta(days=days)
                    user_data[user_id]['premium_expires'] = new_expire_date.strftime("%d.%m.%Y")
            else:
                new_expire_date = datetime.now() + timedelta(days=days)
                user_data[user_id]['premium_expires'] = new_expire_date.strftime("%d.%m.%Y")
        else:
            # Выдаем новый премиум
            user_data[user_id]['premium'] = True
            new_expire_date = datetime.now() + timedelta(days=days)
            user_data[user_id]['premium_expires'] = new_expire_date.strftime("%d.%m.%Y")
        
        reward_text = f"💎 Премиум на {days} дней"
        
    elif selected_reward["type"] == "premium_forever":
        user_data[user_id]['premium'] = True
        user_data[user_id]['premium_expires'] = "∞ Навсегда"
        reward_text = "👑 ПОЖИЗНЕННЫЙ ПРЕМИУМ!"
        
    elif selected_reward["type"] == "currency":
        amount = selected_reward["amount"]
        user_data[user_id]['currency'] += amount
        reward_text = f"💰 {amount} валюты"
    
    save_data(user_data)
    
    return {
        "reward": selected_reward,
        "text": reward_text,
        "case_name": case_type,
        "case_price": case["price"]
    }

def is_banned(user_id):
    """
    Проверяет, забанен ли пользователь
    """
    user_data = load_data()
    user_id = str(user_id)
    
    if user_id not in user_data:
        return False
        
    return user_data[user_id].get('banned', False)

@bot.message_handler(commands=['status'])
def status_bot(message):
    user_id = str(message.from_user.id)
    
    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда не доступна.")
        return

    bot.send_message(message.chat.id, 'Статус бота: Бот работает')

@bot.message_handler(commands=['start'])
def start_bot(message):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name
    username = message.from_user.username

    if not BOT_ENABLED and not can_manage_admins(str(message.from_user.id)):
       bot.send_message(message.chat.id, "🚫 Бот временно недоступен.")
       return
    
    if is_banned(user_id):
        user_data = load_data()
        reason = user_data[user_id].get('ban_reason', 'Не указана')
        bot.reply_to(message, f"🚫 Вы забанены в этом боте.\nПричина: {reason}")
        return
    
    if register_user(user_id, first_name, username):
        msg = bot.send_message(message.chat.id, '<b>Openbot.AI</b>', parse_mode="HTML")
        time.sleep(2)
        markup = types.InlineKeyboardMarkup(row_width=2)
        ran_men = types.InlineKeyboardButton("🎲 Рандом меню", callback_data='num1')
        mag = types.InlineKeyboardButton("🛍 Магазин", callback_data='mag')
        bot_set = types.InlineKeyboardButton("⚙ Настройки", callback_data='num2')
        bot_prof = types.InlineKeyboardButton("👤 Профиль", callback_data='prof')
        markup.add(ran_men, mag, bot_set, bot_prof)
        bot.edit_message_text(f'Привет {first_name} ! \nЭто бот рандома сечас идет зимнее обновлние удачи.', message_id=msg.message_id, chat_id=message.chat.id, reply_markup=markup)
    else: 
        markup = types.InlineKeyboardMarkup(row_width=2)
        ran_men = types.InlineKeyboardButton("🎲 Рандом меню", callback_data='num1')
        mag = types.InlineKeyboardButton("🛍 Магазин", callback_data='mag')
        bot_set = types.InlineKeyboardButton("⚙ Настройки", callback_data='num2')
        bot_prof = types.InlineKeyboardButton("👤 Профиль", callback_data='prof')
        markup.add(ran_men, mag, bot_set, bot_prof)
        bot.send_message(message.chat.id, f'C возвращением {first_name}. Дай угодаю идешь за новыми подарками.', reply_markup=markup)

@bot.message_handler(commands=['random'])
def random_menu_bot(message):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name
    username = message.from_user.username

    if not BOT_ENABLED and not can_manage_admins(str(message.from_user.id)):
       bot.send_message(message.chat.id, "🚫 Бот временно недоступен.")
       return
    
    if register_user(user_id, first_name, username):
      bot.answer_callback_query(message.id, f'{first_name} вы зарегистрированный, нажмите еще раз на конопку',  show_alert=True)
      return
    
    if is_banned(user_id):
        user_data = load_data()
        reason = user_data[user_id].get('ban_reason', 'Не указана')
        bot.reply_to(message, f"🚫 Вы забанены в этом боте.\nПричина: {reason}")
        return

    msg = bot.send_message(message.chat.id, "Загрузка...")
    time.sleep(2)
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🎲Супер кубик", callback_data='btn1')
    btn2 = types.InlineKeyboardButton("🍔Рандомная еда", callback_data='btn2')
    btn3 = types.InlineKeyboardButton("🪙Орел или решка", callback_data='btn3')
    btn4 = types.InlineKeyboardButton("🎮 Рандомания", callback_data='btn4')
    btn5 = types.InlineKeyboardButton("🎁 Новогодний подарок 🎅", callback_data='btn5')
    btn6 = types.InlineKeyboardButton("🎯 Снежная рулетка", callback_data="btn6")
    btn7 = types.InlineKeyboardButton("✨ Пожелание", callback_data='btn7')
    btn8 = types.InlineKeyboardButton("💎 Премиум меню", callback_data='btn13')
    btn9 = types.InlineKeyboardButton("⬅ Назад", callback_data='hext')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8, btn9)
    bot.edit_message_text('Меню игр открыто!', reply_markup=markup, message_id=msg.message_id, chat_id=message.chat.id)

@bot.callback_query_handler(func=lambda m: True)
def callback_data(call):
    user_id = str(call.from_user.id)
    user_data = load_data()
    first_name = call.from_user.first_name
    username = call.from_user.username

    if not BOT_ENABLED and not can_manage_admins(str(call.from_user.id)):
        bot.answer_callback_query(call.id, "🚫 Бот недоступен.")
        return

    if is_banned(user_id):
        user_data = load_data()
        reason = user_data[user_id].get('ban_reason', 'Не указана')
        bot.answer_callback_query(call.id, f"🚫 Вы забанены. Причина: {reason}", show_alert=True)
        return
    
    if register_user(user_id, first_name, username):
      bot.answer_callback_query(call.id, f'{first_name} вы зарегистрированный, нажмите еще раз на конопку',  show_alert=True)
      return

    if call.data == 'btn1':
     number = user_data[user_id]['number']
     secret_number = random.randint(1, number)
     if user_data[user_id]['animations'] == False:
        bot.edit_message_text('Думаю какое чило придумать....', message_id=call.message.message_id, chat_id=call.message.chat.id)
        user_data[user_id]['currency'] += 3
        save_data(user_data)
        time.sleep(2)
        bot.edit_message_text(f"✨ Выпало число: <b>{secret_number}</b>", parse_mode="HTML", message_id=call.message.message_id, chat_id=call.message.chat.id)
        time.sleep(2)
        random_menu(call.message)
     else:
        bot.edit_message_text('Генерирую...', message_id=call.message.message_id, chat_id=call.message.chat.id)
        time.sleep(2)
        user_data[user_id]['currency'] += 3
        save_data(user_data)
        bot.edit_message_text(f"✨ Выпало число: <b>{secret_number}</b>", parse_mode="HTML", message_id=call.message.message_id, chat_id=call.message.chat.id)
        time.sleep(2)
        random_menu(call.message)

    elif call.data == 'btn2':
        foods = random.choice(food)
        bot.edit_message_text('Выбераю что можно съесть 😋...', message_id=call.message.message_id, chat_id=call.message.chat.id)
        time.sleep(1)
        user_data[user_id]['currency'] += 2
        save_data(user_data)
        bot.edit_message_text(f'Я выбрал: {foods}', message_id=call.message.message_id, chat_id=call.message.chat.id)
        time.sleep(3)
        random_menu(call.message)

    elif call.data == 'btn3':
        relust = random.choice(orel)
        if user_data[user_id]['animations'] == False:
         bot.edit_message_text('Порбрасываю монетку...', message_id=call.message.message_id, chat_id=call.message.chat.id)
         time.sleep(1)
         user_data[user_id]['currency'] += 2
         save_data(user_data)
         bot.edit_message_text(f'Выподает: {relust}', message_id=call.message_id, chat_id=call.message.chat.id)
         time.sleep(2)
         random_menu(call.message)
        else:
         bot.edit_message_text('Порбрасываю монетку...', message_id=call.message.message_id, chat_id=call.message.chat.id)
         time.sleep(2)
         bot.edit_message_text('🪙', message_id=call.message.message_id, chat_id=call.message.chat.id)
         time.sleep(3)
         user_data[user_id]['currency'] += 2
         save_data(user_data)
         bot.edit_message_text(f'Выподает: {relust}', message_id=call.message.message_id, chat_id=call.message.chat.id)
         time.sleep(2)
         random_menu(call.message)

    elif call.data == 'btn4':
        relust = random.choice(random_games)
        if user_data[user_id]['animations'] == False:
            bot.edit_message_text('Думаю какую игру выбрать...', message_id=call.message.message_id, chat_id=call.message.chat.id)
            time.sleep(1)
            user_data[user_id]['currency'] += 4
            save_data(user_data)
            bot.edit_message_text(f'Тебе выподает: {relust}', message_id=call.message.message_id, chat_id=call.message.chat.id)
            time.sleep(2)
            random_menu(call.message)
        else:
            bot.edit_message_text('Думаю какую игру выбрать...', message_id=call.message.message_id, chat_id=call.message.chat.id)
            time.sleep(1)
            bot.edit_message_text('🎮', message_id=call.message.message_id, chat_id=call.message.chat.id)
            time.sleep(2)
            user_data[user_id]['currency'] += 4
            save_data(user_data)
            bot.edit_message_text(f'Тебе выподает: {relust}', message_id=call.message.message_id, chat_id=call.message.chat.id)
            time.sleep(2)
            random_menu(call.message)

    elif call.data == 'btn5':
       # Используем другое имя для переменной
       selected_gift = random.choice(gifts)  # gift - это список из начала кода
       bot.edit_message_text("🎅Дед Мороз выберает 🎁 подарок...", message_id=call.message.message_id, chat_id=call.message.chat.id)
       time.sleep(2)
       user_data[user_id]['currency'] += 6
       save_data(user_data)
       bot.edit_message_text(f'Тебе выпало: {selected_gift}', message_id=call.message.message_id, chat_id=call.message.chat.id)
       time.sleep(2)
       random_menu(call.message)
        
    elif call.data == 'btn6':
        relust = random.choice(event)
        bot.edit_message_text('🎯 Кручу снежную рулетку...', message_id=call.message.message_id, chat_id=call.message.chat.id)
        time.sleep(1)
        user_data[user_id]['currency'] += 3
        save_data(user_data)
        bot.edit_message_text(relust, message_id=call.message.message_id, chat_id=call.message.chat.id)
        time.sleep(2)
        random_menu(call.message)

    elif call.data == 'btn7':
        relust = random.choice(event)
        bot.edit_message_text("✨ Достаю пожелание...", message_id=call.message.message_id, chat_id=call.message.chat.id)
        time.sleep(1)
        user_data[user_id]['currency'] += 2
        save_data(user_data)
        bot.edit_message_text(f'Тебе выподает: {relust}', message_id=call.message.message_id, chat_id=call.message.chat.id)
        time.sleep(2)
        random_menu(call.message)

    elif call.data == 'hext':
        bot.answer_callback_query(call.id)
        main_menu(call.message)

    elif call.data == 'num1':
        bot.answer_callback_query(call.id)
        random_menu(call.message)

    elif call.data == 'num2':
        bot.answer_callback_query(call.id)
        setting(call.message)

    elif call.data == 'set2':
     antimois(call.message)
    
    elif call.data == 'off2':
        if user_data[user_id]['animations'] == True:
          user_data[user_id]['animations'] = False
          save_data(user_data)
          antimois(call.message, "✅ Анимации выключены.")
        else:
          antimois(call.message, "❌ Анимации уже выключены.")

    elif call.data == 'on1':
      if user_data[user_id]['animations'] == False:
          user_data[user_id]['animations'] = True
          save_data(user_data)
          antimois(call.message, "✅ Анимации включенны")
      else:
          antimois(call.message, "❌ Анимации уже включены.")

    elif call.data == 'hext1':
        bot.answer_callback_query(call.id)
        setting(call.message)

    elif call.data == 'set1':
        numbers = user_data[user_id]['number']
        markup = types.InlineKeyboardMarkup(row_width=2)
        ran1 = types.InlineKeyboardButton("1000", callback_data='range_1000')
        ran2 = types.InlineKeyboardButton("100", callback_data='range_100')
        ran3 = types.InlineKeyboardButton("10", callback_data='range_10')
        hext = types.InlineKeyboardButton("⬅ Назад", callback_data='hext1')
        markup.add(ran1, ran2, ran3, hext)
        bot.edit_message_text(f'Выбирите диапозон, сейчас ваш диопозон: {numbers}', reply_markup=markup, message_id=call.message.message_id, chat_id=call.message.chat.id)
        
    elif call.data.startswith('range_'):
        if register_user(user_id, first_name, username):
            bot.answer_callback_query(call.id, f'{first_name} вы зарегистрированы, нажмите еще раз на кнопку.')
            return
        
        try:
            new_number = int(call.data.split('_')[-1])
            user_data[user_id]['number'] = new_number
            save_data(user_data)
                
            markup = types.InlineKeyboardMarkup()
            hext = types.InlineKeyboardButton('⬅ Назад', callback_data='hext1')
            markup.add(hext)
            bot.edit_message_text(
                    f'Диапазон рандома изменен. Теперь он до {new_number}.',
                    call.message.chat.id,
                    call.message.message_id, reply_markup=markup
                )
        except (ValueError, IndexError):
            bot.send_message(call.message.chat.id, "Произошла ошибка при изменении диапазона.")
    
    elif call.data == 'prof':
        user_info = user_data[user_id]
        color = user_info['color']
        
        # Получаем статус для отображения
        if user_info.get('banned', False):
            display_status = STATUS['banned']
        else:
            display_status = STATUS.get(user_info.get('status', 'user'), '👤 Игрок')
        
        # ФОРМАТИРУЕМ ИНФОРМАЦИЮ О ПРЕМИУМЕ
        premium_info = ""
        premium_expires = user_info.get('premium_expires')
        
        if user_info.get('premium', False):
            if premium_expires == "∞ Навсегда":
                premium_info = "✅ Активирован\n⏰ Премиум до: Навсегда 🎉"
            elif premium_expires and premium_expires != "None":
                days_left = get_premium_days_left(premium_expires)
                premium_info = f"✅ Активирован\n⏰ Премиум до: {premium_expires}\n⏳ Осталось: {days_left}"
            else:
                premium_info = "✅ Активирован (бессрочный)"
        else:
            premium_info = "❌ Не активен"
        
        markup = types.InlineKeyboardMarkup()
        doc = types.InlineKeyboardButton('📋 Документация', callback_data='doc')
        hext = types.InlineKeyboardButton('⬅ Назад', callback_data='hext')
        markup.add(doc, hext)
        
        
        text = f"""📛 Имя: {color} {user_info['first_name']} 
🎭 Статус: {display_status}
🆔 ID: {user_info['id']}
💎 Премиум: {premium_info}
🎭 Анимации: {'✅ Вкл' if user_info.get('animations', True) else '❌ Выкл'}
🎲 Рандом-Коинов: {user_info.get('currency')}
⚙️ Диапазон: {user_info.get('number', 10)} 
📅 Регистрация: {user_info.get('data', 'Неизвестно')}"""
        bot.edit_message_text(text, reply_markup=markup, message_id=call.message.message_id, chat_id=call.message.chat.id)

    elif call.data == 'set3':
        # Возврат из выбора цвета/диапазона в настройки премиума
        if not user_data[user_id]['premium']:
            bot.answer_callback_query(call.id, '❌ Только для премиума')
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        ran1 = types.InlineKeyboardButton('🎯 Диопозон двойного рандома', callback_data='ran1')
        ran2 = types.InlineKeyboardButton('Дипозон Mega Dice 10k', callback_data='ran3')
        ran3 = types.InlineKeyboardButton('🎨 Цвет ника', callback_data='ran2')
        ran4 = types.InlineKeyboardButton('⬅ Назад', callback_data='hext1')
        markup.add(ran1, ran2, ran3, ran4)
        bot.edit_message_text('💎 Настройки премиума', reply_markup=markup, message_id=call.message.message_id, chat_id=call.message.chat.id)

    elif call.data == 'btn8':
        num = user_data[user_id]['number_vip']
        reples = random.randint(1, num)
        user_data[user_id]['currency'] += 10
        save_data(user_data)
        bot.edit_message_text(f'Тебе вапaдает: {reples}', message_id=call.message.message_id, chat_id=call.message.chat.id)
        time.sleep(2)
        premium_random_mune(call.message)

    elif call.data == 'btn9':
        result = random.choice(roulette_items)
        user_data[user_id]['currency'] += 8
        save_data(user_data)
        text = text = f"""
🎡 <b>Ультра Рулетка</b>

Результат: <b>{result}</b>

🎉 Премиум рулетка крутится только для избранных!
"""
        bot.edit_message_text(text, message_id=call.message.message_id, chat_id=call.message.chat.id, parse_mode="HTML")
        time.sleep(2)
        premium_random_mune(call.message)

    elif call.data == 'btn10':
        bot.edit_message_text('Генерирую...', message_id=call.message.message_id, chat_id=call.message.chat.id)
        time.sleep(2)
        num = user_data[user_id]['number_two']
        relust = random.randint(1, num)
        relust1 = random.randint(1, num)
        user_data[user_id]['currency'] += 12
        save_data(user_data)
        again_btn = types.InlineKeyboardButton("🔄 Ещё раз", callback_data="btn10")
        back_btn = types.InlineKeyboardButton("⬅ Назад", callback_data="hext3")
        bot.edit_message_text( f"✨ Выпало два числа: <b>{relust}</b> и <b>{relust1}</b>",
            parse_mode="HTML", message_id=call.message.message_id, chat_id=call.message.chat.id)
        time.sleep(2)
        premium_random_mune(call.message)
        
    elif call.data == 'btn11':
        relust2 = random.choice(emotions)
        markup = types.InlineKeyboardMarkup(row_width=2)
        again_btn = types.InlineKeyboardButton("🔄 Ещё раз", callback_data="btn11")
        back_btn = types.InlineKeyboardButton("⬅ Назад", callback_data="hext3")
        markup.add(again_btn, back_btn)
        user_data[user_id]['currency'] += 6
        save_data(user_data)
        bot.edit_message_text(f"🎯 Твоя эмоция дня: {relust2}", reply_markup=markup, chat_id=call.message.chat.id, message_id=call.message.message_id,)
        
    elif call.data == 'btn12':
        bot.edit_message_text('Выбераю какой подарок выбрать !', message_id=call.message.message_id, chat_id=call.message.chat.id)
        time.sleep(2)
        user_data[user_id]['currency'] += 15
        save_data(user_data)
        gift = random.choice(vip_gifts)
        text = f"""
🎁 <b>VIP Подарок</b>

✨ Твой подарок:
{gift}

💎 Премиум приносит удачу!
"""
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, text, parse_mode="HTML")
        time.sleep(3)
        premium_random_mune(call.message)

    elif call.data == 'hext3':
        premium_random_mune(call.message)

    elif call.data == 'btn13':
        if not user_data[user_id]['premium']:
          bot.answer_callback_query(call.id, "❌ Только для премиума")
        else:
            premium_random_mune(call.message)

    elif call.data == 'btn14':
        random_menu(call.message)

    elif call.data == 'ran1':
     num = user_data[user_id]['number_two']

     markup = types.InlineKeyboardMarkup(row_width=2)
     dip1 = types.InlineKeyboardButton('10000', callback_data='dip_10000')
     dip2 = types.InlineKeyboardButton('50000', callback_data='dip_50000')
     dip3 = types.InlineKeyboardButton('1000000', callback_data='dip_1000000')
     dip4 = types.InlineKeyboardButton('2000000', callback_data='dip_200000')
     hext = types.InlineKeyboardButton('⬅ Назад', callback_data='premium_settings_back')
     markup.add(dip1, dip2, dip3, dip4, hext)
     bot.edit_message_text(f'Выбирите диопозон двойного рандома сейчас у вас {num}', reply_markup=markup, message_id=call.message.message_id, chat_id=call.message.chat.id)

    elif call.data.startswith('dip_'):
        if register_user(user_id, first_name, username):
            bot.answer_callback_query(call.id, f'{first_name} вы зарегистрированы, нажмите еще раз на кнопку.',  show_alert=True)
            return
        
        try:
            new_number = int(call.data.split('_')[-1])
            user_data[user_id]['number_two'] = new_number
            save_data(user_data)
                
            markup = types.InlineKeyboardMarkup()
            hext = types.InlineKeyboardButton('⬅ Назад', callback_data='premium_settings_back')
            markup.add(hext)
            bot.edit_message_text(
                    f'Диапазон рандома изменен. Теперь он до {new_number}.',
                    call.message.chat.id,
                    call.message.message_id, reply_markup=markup
                )
        except (ValueError, IndexError):
            bot.send_message(call.message.chat.id, "⚠ Произошла ошибка при изменении диапазона.")

    elif call.data == 'ran2':
        if not user_data[user_id]['premium']:
            bot.answer_callback_query(call.id, '❌ Только для премиума')
            return
        
        # Создаем клавиатуру с цветами
        markup = types.InlineKeyboardMarkup(row_width=3)
        
        # Добавляем кнопки цветов
        red = types.InlineKeyboardButton('🔴', callback_data='color_red')
        blue = types.InlineKeyboardButton('🔵', callback_data='color_blue') 
        green = types.InlineKeyboardButton('🟢', callback_data='color_green')
        gold = types.InlineKeyboardButton('⭐', callback_data='color_gold')
        purple = types.InlineKeyboardButton('🟣', callback_data='color_purple')
        orange = types.InlineKeyboardButton('🟠', callback_data='color_orange')
        turquoise = types.InlineKeyboardButton('💎', callback_data='color_turquoise')
        pink = types.InlineKeyboardButton('🌸', callback_data='color_pink')
        
        # Первый ряд
        markup.add(red, blue, green)
        # Второй ряд
        markup.add(gold, purple, orange)
        # Третий ряд
        markup.add(turquoise, pink)
        
        # Кнопки управления
        reset_btn = types.InlineKeyboardButton('⚫ Сбросить цвет', callback_data='color_reset')
        back_btn = types.InlineKeyboardButton('⬅ Назад', callback_data='premium_settings_back')
        markup.add(reset_btn, back_btn)
        
        current_color = user_data[user_id].get('color', '')
        if current_color:
            color_text = f"Текущий цвет: {current_color}"
        else:
            color_text = "Текущий цвет: не выбран"
        
        bot.edit_message_text(
            f'🎨 <b>Выбор цвета ника</b>\n\n{color_text}\n\nВыбери эмодзи для твоего ника:',
            message_id=call.message.message_id,
            chat_id=call.message.chat.id,
            parse_mode='HTML',
            reply_markup=markup
        )

    elif call.data.startswith('color_'):
        if not user_data[user_id]['premium']:
            bot.answer_callback_query(call.id, '❌ Только для премиума')
            return
        
        color_type = call.data.replace('color_', '')
        
        if color_type == 'reset':
            # Сброс цвета
            user_data[user_id]['color'] = ""
            save_data(user_data)
            bot.answer_callback_query(call.id, "✅ Цвет сброшен!")
            
            # Обновляем сообщение
            markup = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton('⬅ Назад', callback_data='premium_settings_back')
            markup.add(back_btn)
            
            bot.edit_message_text(
                "✅ Цвет ника сброшен!\nТеперь твой ник будет отображаться без цвета.",
                message_id=call.message.message_id,
                chat_id=call.message.chat.id,
                reply_markup=markup
            )
            
        else:
            # Устанавливаем цвет
            color_emojis = {
                'red': '🔴',
                'blue': '🔵',
                'green': '🟢',
                'gold': '⭐',
                'purple': '🟣',
                'orange': '🟠',
                'turquoise': '💎',
                'pink': '🌸'
            }
            
            if color_type in color_emojis:
                user_data[user_id]['color'] = color_emojis[color_type]
                save_data(user_data)
                
                color_names = {
                    'red': 'красный',
                    'blue': 'синий',
                    'green': 'зеленый',
                    'gold': 'золотой',
                    'purple': 'фиолетовый',
                    'orange': 'оранжевый',
                    'turquoise': 'бирюзовый',
                    'pink': 'розовый'
                }
                
                bot.answer_callback_query(call.id, f"✅ Цвет изменен на {color_names[color_type]}!")
                
                # Показываем пример с новым цветом
                user_info = user_data[user_id]
                colored_name = f"{color_emojis[color_type]} {user_info['first_name']}"
                
                markup = types.InlineKeyboardMarkup()
                change_btn = types.InlineKeyboardButton('🎨 Выбрать другой цвет', callback_data='ran2')
                back_btn = types.InlineKeyboardButton('⬅ В меню', callback_data='premium_settings_back')
                markup.add(change_btn, back_btn)
                
                bot.edit_message_text(
                    f'✅ <b>Цвет ника изменен!</b>\n\n'
                    f'Теперь твой ник выглядит так:\n'
                    f'<b>{colored_name}</b>\n\n'
                    f'Этот цвет будет отображаться в твоем профиле '
                    f'и других местах где упоминается твое имя.',
                    message_id=call.message.message_id,
                    chat_id=call.message.chat.id,
                    parse_mode='HTML',
                    reply_markup=markup
                )

    elif call.data == 'premium_settings_back':
        # Возврат из выбора цвета/диапазона в настройки премиума
        if not user_data[user_id]['premium']:
            bot.answer_callback_query(call.id, '❌ Только для премиума')
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        ran1 = types.InlineKeyboardButton('🎯 Диопозон двойного рандома', callback_data='ran1')
        ran2 = types.InlineKeyboardButton('Дипозон Mega Dice 10k', callback_data='ran3')
        ran3 = types.InlineKeyboardButton('🎨 Цвет ника', callback_data='ran2')
        ran4 = types.InlineKeyboardButton('⬅ Назад', callback_data='hext1')
        markup.add(ran1, ran2, ran3, ran4)
        bot.edit_message_text('💎 Настройки премиума', reply_markup=markup, message_id=call.message.message_id, chat_id=call.message.chat.id)

    elif call.data == 'ran3':
     
     nums = user_data[user_id]['number_vip']

     markup = types.InlineKeyboardMarkup(row_width=2)
     dip1 = types.InlineKeyboardButton('10000', callback_data='dips_10000')
     dip2 = types.InlineKeyboardButton('50000', callback_data='dips_50000')
     dip3 = types.InlineKeyboardButton('60000', callback_data='dips_60000')
     dip4 = types.InlineKeyboardButton('90000', callback_data='dips_90000')
     dip5 = types.InlineKeyboardButton('1000000', callback_data='dips_1000000')
     hext = types.InlineKeyboardButton('⬅ Назад', callback_data='premium_settings_back')
     markup.add(dip1, dip2, dip3, dip4, dip5, hext)
     bot.edit_message_text(f'Выбирите диопозон двойного рандома сейчас у вас {nums}', reply_markup=markup, message_id=call.message.message_id, chat_id=call.message.chat.id)

    elif call.data.startswith('dips_'):
        if register_user(user_id, first_name, username):
            bot.answer_callback_query(call.id, f'{first_name} вы зарегистрированы, нажмите еще раз на кнопку.',  show_alert=True)
            return
        
        try:
            new_number = int(call.data.split('_')[-1])
            user_data[user_id]['number_vip'] = new_number
            save_data(user_data)
                
            markup = types.InlineKeyboardMarkup()
            hext = types.InlineKeyboardButton('⬅ Назад', callback_data='premium_settings_back')
            markup.add(hext)
            bot.edit_message_text(
                    f'Диапазон рандома изменен. Теперь он до {new_number}.',
                    call.message.chat.id,
                    call.message.message_id, reply_markup=markup
                )
        except (ValueError, IndexError):
            bot.send_message(call.message.chat.id, "⚠ Произошла ошибка при изменении диапазона.")

    elif call.data == 'mag':
        markup = types.InlineKeyboardMarkup(row_width=2)
        kes = types.InlineKeyboardButton("🎁 Кейсы", callback_data='kes')
        buy = types.InlineKeyboardButton("💎 Купить премиум", callback_data='buy')
        back_btn = types.InlineKeyboardButton('⬅ Назад', callback_data='hext')
        markup.add(kes, buy, back_btn)
        bot.edit_message_text('🛍 Добро пожаловать в магазин', message_id=call.message.message_id, chat_id=call.message.chat.id, reply_markup=markup)

    elif call.data == 'kes':
        user_currency = user_data[user_id].get('currency', 0)
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # Кнопки для каждого типа кейса
        common_btn = types.InlineKeyboardButton(
            f"📦 Обычный - {CASES['обычный']['price']} рандом-Коинов", 
            callback_data='case_обычный'
        )
        rare_btn = types.InlineKeyboardButton(
            f"🎁 Редкий - {CASES['редкий']['price']} рандом-Коинов", 
            callback_data='case_редкий'
        )
        epic_btn = types.InlineKeyboardButton(
            f"💜 Эпический - {CASES['эпический']['price']} рандом-Коинов", 
            callback_data='case_эпический'
        )
        legendary_btn = types.InlineKeyboardButton(
            f"👑 Легендарный - {CASES['легендарный']['price']} рандом-Коинов", 
            callback_data='case_легендарный'
        )
        
        back_btn = types.InlineKeyboardButton('⬅ Назад', callback_data='mag')
        
        markup.add(common_btn, rare_btn, epic_btn, legendary_btn, back_btn)
        
        text = f"""🎁 <b>Магазин кейсов</b>

💰 Ваша валюта: <b>{user_currency}</b>

📦 <b>Обычный</b> - премиум 1-3 дня
🎁 <b>Редкий</b> - премиум 7-15 дней  
💜 <b>Эпический</b> - премиум 30-60 дней
👑 <b>Легендарный</b> - шанс на премиум НАВСЕГДА

Выберите кейс для открытия:"""
        
        bot.edit_message_text(
            text,
            message_id=call.message.message_id,
            chat_id=call.message.chat.id,
            parse_mode='HTML',
            reply_markup=markup
        )

    elif call.data.startswith('case_'):
        case_type = call.data.replace('case_', '')
        
        if case_type not in CASES:
            bot.answer_callback_query(call.id, "❌ Такого кейса не существует")
            return
        
        user_currency = user_data[user_id].get('currency', 0)
        case_price = CASES[case_type]['price']
        
        if user_currency < case_price:
            bot.answer_callback_query(
                call.id, 
                f"❌ Недостаточно бросков! Нужно {case_price}, у вас {user_currency}",
                show_alert=True
            )
            return
        
        # Спишем валюту
        user_data[user_id]['currency'] -= case_price
        save_data(user_data)
        
        # Открываем кейс
        result = open_case(user_id, case_type)
        
        if result:
            # Показываем анимацию открытия
            bot.edit_message_text(
                "🎰 Открываем кейс...",
                message_id=call.message.message_id,
                chat_id=call.message.chat.id
            )
            time.sleep(2)
            
            # Показываем результат
            new_currency = user_data[user_id].get('currency', 0)
            result_text = f"""🎉 <b>ВЫ ВЫИГРАЛИ!</b>

📦 Кейс: {case_type}
🎁 Награда: {result['text']}

💰 Ваша валюта: {new_currency}"""

            markup = types.InlineKeyboardMarkup()
            open_again = types.InlineKeyboardButton('🎰 Открыть еще', callback_data='kes')
            back_btn = types.InlineKeyboardButton('⬅ В магазин', callback_data='mag')
            markup.add(open_again, back_btn)
            
            bot.edit_message_text(
                result_text,
                message_id=call.message.message_id,
                chat_id=call.message.chat.id,
                parse_mode='HTML',
                reply_markup=markup
            )
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка при открытии кейса")

    elif call.data == 'buy':
        user_currency = user_data[user_id].get('currency', 0)
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # Кнопки для покупки премиума
        premium_7 = types.InlineKeyboardButton(
            f"💎 7 дней - {PREMIUM_PRICES['7_days']['price']} рандом-Коинов", 
            callback_data='buy_premium_7_days'
        )
        premium_30 = types.InlineKeyboardButton(
            f"💎 30 дней - {PREMIUM_PRICES['30_days']['price']} рандом-Коинов", 
            callback_data='buy_premium_30_days'
        )
        premium_90 = types.InlineKeyboardButton(
            f"💎 90 дней - {PREMIUM_PRICES['90_days']['price']} рандом-Коинов", 
            callback_data='buy_premium_90_days'
        )
        premium_180 = types.InlineKeyboardButton(
            f"💎 180 дней - {PREMIUM_PRICES['180_days']['price']} рандом-Коинов", 
            callback_data='buy_premium_180_days'
        )
        premium_365 = types.InlineKeyboardButton(
            f"💎 365 дней - {PREMIUM_PRICES['365_days']['price']} рандом-Коинов", 
            callback_data='buy_premium_365_days'
        )
        
        back_btn = types.InlineKeyboardButton('⬅ Назад', callback_data='mag')
        
        markup.add(premium_7, premium_30, premium_90, premium_180, premium_365, back_btn)
        
        text = f"""💎 <b>Покупка премиума</b>

💰 Ваша валюта: <b>{user_currency}</b>

💎 <b>7 дней</b> - базовые премиум функции
💎 <b>30 дней</b> - полный доступ на месяц  
💎 <b>90 дней</b> - выгодный пакет на 3 месяца
💎 <b>180 дней</b> - полгода премиум доступа
💎 <b>365 дней</b> - целый год премиума!

Выберите срок премиума:"""
        
        bot.edit_message_text(
            text,
            message_id=call.message.message_id,
            chat_id=call.message.chat.id,
            parse_mode='HTML',
            reply_markup=markup
        )

    elif call.data.startswith('buy_premium_'):
        premium_type = call.data.replace('buy_premium_', '')
        
        if premium_type not in PREMIUM_PRICES:
            bot.answer_callback_query(call.id, "❌ Такого варианта премиума не существует")
            return
        
        premium_info = PREMIUM_PRICES[premium_type]
        user_currency = user_data[user_id].get('currency', 0)
        premium_price = premium_info['price']
        premium_days = premium_info['days']
        
        if user_currency < premium_price:
            bot.answer_callback_query(
                call.id, 
                f"❌ Недостаточно валюты! Нужно {premium_price}, у вас {user_currency}",
                show_alert=True
            )
            return
        
        # Проверяем, есть ли уже премиум
        current_premium = user_data[user_id].get('premium', False)
        current_expires = user_data[user_id].get('premium_expires')
        
        # Спишем валюту
        user_data[user_id]['currency'] -= premium_price
        
        # Выдаем/продлеваем премиум
        if current_premium and current_expires and current_expires != "∞ Навсегда":
            try:
                # Продлеваем существующий премиум
                expire_date = datetime.strptime(current_expires, "%d.%m.%Y")
                new_expire_date = expire_date + timedelta(days=premium_days)
                user_data[user_id]['premium_expires'] = new_expire_date.strftime("%d.%m.%Y")
            except:
                # Если ошибка с датой, начинаем с сегодня
                new_expire_date = datetime.now() + timedelta(days=premium_days)
                user_data[user_id]['premium_expires'] = new_expire_date.strftime("%d.%m.%Y")
        else:
            # Выдаем новый премиум
            user_data[user_id]['premium'] = True
            new_expire_date = datetime.now() + timedelta(days=premium_days)
            user_data[user_id]['premium_expires'] = new_expire_date.strftime("%d.%m.%Y")
        
        save_data(user_data)
        
        # Показываем результат покупки
        new_currency = user_data[user_id].get('currency', 0)
        result_text = f"""🎉 <b>ПРЕМИУМ АКТИВИРОВАН!</b>

💎 Срок: {premium_days} дней
📅 Истекает: {new_expire_date.strftime("%d.%m.%Y")}
💰 Списано: {premium_price} рандом-Коинов
💳 Осталось: {new_currency} рандом-Коинов

✨ Теперь вам доступны:
• Премиум игры 🎮
• Улучшенный рандом ⚡
• Эксклюзивные функции 💫"""

        markup = types.InlineKeyboardMarkup()
        to_games = types.InlineKeyboardButton('🎮 К играм', callback_data='num1')
        back_btn = types.InlineKeyboardButton('⬅ В магазин', callback_data='mag')
        markup.add(to_games, back_btn)
        
        bot.edit_message_text(
            result_text,
            message_id=call.message.message_id,
            chat_id=call.message.chat.id,
            parse_mode='HTML',
            reply_markup=markup
        )
        
        # Уведомляем о успешной покупке
        bot.answer_callback_query(call.id, f"✅ Премиум на {premium_days} дней активирован!")

    elif call.data == 'doc':
        markup = types.InlineKeyboardMarkup(row_width=1)
        doc1 = types.InlineKeyboardButton('📋 Документация о разработчиках 👨‍💻', callback_data='doc1')
        doc2 = types.InlineKeyboardButton('📋 Документация о боте 🤖', callback_data='doc2')
        doc3 = types.InlineKeyboardButton('📋 Свединие об ОС', callback_data='randomOS_info')
        hext = types.InlineKeyboardButton('⬅ Назад', callback_data='prof')
        markup.add(doc1, doc2, doc3, hext)
        bot.edit_message_text('Добро пожаловать !', message_id=call.message.message_id, chat_id=call.message.chat.id, reply_markup=markup)

    elif call.data == 'doc1':
        VERSION = 2.0
        markup = types.InlineKeyboardMarkup()
        hext = types.InlineKeyboardButton('⬅ Назад', callback_data='doc')
        markup.add(hext)
        text2 = f"""Бот cделан команиями: <b>OpenbotAI</b> и <b>VECTORBOT</b>
Но большую чать выполнила комания: <b>OpenbotAI</b>
Что есть прикольного команды /random
<i>Версия бота: {VERSION}</i>"""
        bot.edit_message_text(text2, message_id=call.message.message_id, chat_id=call.message.chat.id, reply_markup=markup, parse_mode="HTML")

    elif call.data == 'doc2':
        markup = types.InlineKeyboardMarkup()
        hext = types.InlineKeyboardButton('⬅ Назад', callback_data='doc')
        markup.add(hext)
        bot.edit_message_text(text1, message_id=call.message.message_id, chat_id=call.message.chat.id, reply_markup=markup, parse_mode="HTML")

    elif call.data == 'randomOS_info':
        markup = types.InlineKeyboardMarkup()
        hext = types.InlineKeyboardButton('⬅ Назад', callback_data='doc')
        markup.add(hext)
        bot.edit_message_text(info_RandomOS, message_id=call.message.message_id, chat_id=call.message.chat.id, reply_markup=markup, parse_mode="HTML")

    elif call.data == 'randomOS_info1':
        markup = types.InlineKeyboardMarkup()
        hext2 = types.InlineKeyboardButton('⬅ Назад', callback_data='hext1')
        markup.add(hext2)
        bot.edit_message_text(info_RandomOS, message_id=call.message.message_id, chat_id=call.message.chat.id, reply_markup=markup, parse_mode="HTML")

@bot.message_handler(commands=['give_premium'])
def give_premium_command(message):
    user_id = str(message.from_user.id)
    user_data = load_data()

    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда не доступна.")
        return
    
    # Определяем кто выдает премиум
    issuer_status = user_data[user_id]['status']
    
    if issuer_status == 'developer':
        issuer_text = "🌐💠 Openbot.Ai"
    else:
        issuer_text = "⭐ Администратор"
    
    command = message.text.split()
    if len(command) < 2:
        bot.reply_to(message, "❌ Формат: /give_premium @username [дни]\n\n💡 Примеры:\n/give_premium @username - навсегда\n/give_premium @username 30 - на 30 дней")
        return
    
    target_username = command[1].replace('@', '').lower()
    user_data = load_data()
    
    # Проверяем права
    issuer_status = user_data[user_id]['status']
    
    # Ищем пользователя
    target_id = None
    target_username_found = None
    for uid, data in user_data.items():
        if data.get('username', '').lower() == target_username:
            target_id = uid
            target_username_found = data.get('username')
            break
    
    if not target_id:
        bot.reply_to(message, "❌ Пользователь с таким юзернеймом не найден")
        return
    
    # Если НЕ указаны дни - выдаем навсегда
    if len(command) == 2:
        # Выдача навсегда - только для владельца
        if issuer_status != 'developer':
            bot.reply_to(message, "❌ Только Dev может выдавать премиум навсегда")
            return
            
        expire_date = "∞ Навсегда"
        duration_text = "НАВСЕГДА 🎉"
        user_message = "🎉 Вам выдан Премиум НАВСЕГДА! 🚀"
    
    # Если указаны дни - выдаем на указанное количество дней
    elif len(command) > 2:
        try:
            days = int(command[2])
            
            # Ограничение для админов - максимум 30 дней
            if issuer_status == 'admin' and days > 30:
                bot.reply_to(message, "❌ Админ может выдавать премиум максимум на 30 дней")
                return
                
            expire_date = (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y")
            duration_text = f"на {days} дней"
            user_message = f"💎 Вам выдан Премиум на {days} дней!"
            
        except ValueError:
            bot.reply_to(message, "❌ Количество дней должно быть числом")
            return
    
    # Выдаем премиум
    user_data[target_id]['premium'] = True
    user_data[target_id]['premium_expires'] = expire_date
    save_data(user_data)
    
    # Уведомляем пользователя через функцию notify_user
    try:
        if expire_date == "∞ Навсегда":
            notify_user(target_id, 'got_premium_forever')
        else:
            notify_user(target_id, 'got_premium_days', str(days))
        user_notified = True
    except:
        user_notified = False
    
    # Отправляем отчет админу
    notification_status = "✅ Пользователь уведомлен" if user_notified else "⚠️ Не удалось уведомить"
    
    bot.reply_to(message, f"✅ Премиум выдан @{target_username_found} {duration_text}\n{notification_status}")

@bot.message_handler(commands=['remove_premium'])
def remove_premium_command(message):
    user_id = str(message.from_user.id)
    
    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда не доступна.")
        return
    
    command = message.text.split()
    if len(command) < 2:
        bot.reply_to(message, "❌ Формат: /remove_premium @username")
        return
    
    target_username = command[1].replace('@', '').lower()
    user_data = load_data()
    
    # Ищем пользователя
    target_id = None
    target_username_found = None
    for uid, data in user_data.items():
        if data.get('username', '').lower() == target_username:
            target_id = uid
            target_username_found = data.get('username')
            break
    
    if not target_id:
        bot.reply_to(message, "❌ Пользователь с таким юзернеймом не найден")
        return
    
    if not user_data[target_id].get('premium', False):
        bot.reply_to(message, f"❌ У @{target_username_found} нет премиума")
        return
    
    # Снимаем премиум
    user_data[target_id]['premium'] = False
    user_data[target_id]['premium_expires'] = None
    save_data(user_data)
    
    # Уведомляем пользователя
    try:
        notify_user(target_id, 'lost_premium')
        user_notified = True
    except:
        user_notified = False
    
    # Отправляем отчет админу
    notification_status = "✅ Пользователь уведомлен" if user_notified else "⚠️ Не удалось уведомить"
    
    bot.reply_to(message, f"✅ Премиум снят у @{target_username_found}\n{notification_status}")


    user_id = str(message.from_user.id)
    
    if not can_manage_admins(user_id):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    
    global BOT_ENABLED
    BOT_ENABLED = False
    bot.reply_to(message, "🚫 Бот выключен для всех, кроме админов.")

# Обновленная команда добавления админа
@bot.message_handler(commands=['add_admin'])
def add_admin_command(message):
    user_id = str(message.from_user.id)
    
    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда не доступна.")
        return
    
    command = message.text.split()
    if len(command) < 2:
        bot.reply_to(message, "❌ Укажи ID пользователя: /add_admin 123456789")
        return
    
    target_id = command[1]
    user_data = load_data()
    
    if target_id not in user_data:
        bot.reply_to(message, "❌ Пользователь не найден")
        return
    
    # Проверяем, не пытаемся ли сделать админом самого себя
    if target_id == user_id:
        bot.reply_to(message, "❌ Нельзя изменить свой собственный статус")
        return
    
    # Проверяем, не пытаемся ли сделать админом владельца
    if user_data[target_id]['status'] == 'developer':
        bot.reply_to(message, "❌ Нельзя изменить статус Dev")
        return
    
    user_data[target_id]['status'] = 'admin'
    save_data(user_data)
    bot.reply_to(message, f"✅ Пользователь {target_id} теперь администратор")

# Обновленная команда удаления админа
@bot.message_handler(commands=['remove_admin'])
def remove_admin_command(message):
    user_id = str(message.from_user.id)
    
    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда не доступна.")
        return
    
    command = message.text.split()
    if len(command) < 2:
        bot.reply_to(message, "❌ Укажи ID пользователя: /remove_admin 123456789")
        return
    
    target_id = command[1]
    user_data = load_data()
    
    if target_id not in user_data:
        bot.reply_to(message, "❌ Пользователь не найден")
        return
    
    # Проверяем, не пытаемся ли удалить админа у самого себя
    if target_id == user_id:
        bot.reply_to(message, "❌ Нельзя изменить свой собственный статус")
        return
    
    # Проверяем, не пытаемся ли удалить админа у владельца
    if user_data[target_id]['status'] == 'developer':
        bot.reply_to(message, "❌ Нельзя изменить статус владельца")
        return
    
    user_data[target_id]['status'] = 'user'
    save_data(user_data)
    bot.reply_to(message, f"✅ Пользователь {target_id} больше не админ")

@bot.message_handler(commands=['add_dev'])
def add_owner_command(message):
    user_id = str(message.from_user.id)
    user_data = load_data

    if not can_manage_owners(user_id):
        bot.reply_to(message, "❌ Эта команда не доступна.")
        return
    
    command = message.text.split()
    if len(command) < 2:
        bot.reply_to(message, "❌ Укажи ID пользователя: /add_owner 123456789")
        return
    
    target_id = command[1]
    user_data = load_data()
    
    
    # Проверяем, не пытаемся ли сделать владельцем самого себя
    if target_id not in user_data:
        bot.reply_to(message, "❌ Пользователь не найден")
        return
    
    user_data[target_id]['status'] = 'developer'
    save_data(user_data)
    bot.reply_to(message, f"👑 Пользователь {target_id} теперь владелец")

# Команда для удаления владельца (ТОЛЬКО для текущих владельцев)
@bot.message_handler(commands=['remove_dev'])
def remove_owner_command(message):
    user_id = str(message.from_user.id)
    
    if not can_manage_owners(user_id):
        bot.reply_to(message, "❌ Эта команда не доступна.")
        return
    
    command = message.text.split()
    if len(command) < 2:
        bot.reply_to(message, "❌ Укажи ID владельца: /remove_owner 123456789")
        return
    
    target_id = command[1]
    user_data = load_data()
    
    if target_id not in user_data:
        bot.reply_to(message, "❌ Пользователь не найден")
        return
    
    # Проверяем, не пытаемся ли удалить владельца у самого себя
    if target_id == user_id:
        bot.reply_to(message, "❌ Нельзя удалить самого себя")
        return
    
    if user_data[target_id]['status'] != 'developer':
        bot.reply_to(message, "❌ Этот пользователь не является владельцем")
        return
    
    # Понижаем владельца до админа
    user_data[target_id]['status'] = 'adminr'
    save_data(user_data)
    bot.reply_to(message, f"✅ Пользователь {target_id} больше не владелец")

# Команда бана пользователя по юзернейму
@bot.message_handler(commands=['ban'])
def ban_command(message):
    user_id = str(message.from_user.id)
    
    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда не доступна.")
        return
    
    command_parts = message.text.split(' ', 2)  # Разделяем на 3 части
    if len(command_parts) < 2:
        bot.reply_to(message, "❌ Формат: /ban @username [причина]\n\n💡 Примеры:\n/ban @username спам\n/ban @username оскорбления\n/ban @username нарушение правил")
        return
    
    target_username = command_parts[1].replace('@', '').lower()
    
    # Если указана своя причина - испо  льзуем её, иначе "other"
    if len(command_parts) > 2:
        custom_reason = command_parts[2]
        reason = "custom"
    else:
        custom_reason = "Не указана"
        reason = "other"
    
    user_data = load_data()
    
    # Ищем пользователя по юзернейму
    target_id = None
    target_username_found = None
    target_name = None
    for uid, data in user_data.items():
        if data.get('username', '').lower() == target_username:
            target_id = uid
            target_username_found = data.get('username')
            target_name = data.get('first_name')
            break

    if not target_id:
        bot.reply_to(message, "❌ Пользователь с таким юзернеймом не найден")
        return
    
    # Проверяем, не пытаемся ли забанить сами себя
    if target_id == user_id:
        bot.reply_to(message, "❌ Нельзя забанить самого себя")
        return
    
    # Проверяем, не пытаемся ли забанить владельца
    if user_data[target_id]['status'] == 'developer':
        bot.reply_to(message, "❌ Нельзя забанить владельца")
        return
    
    # Проверяем, не пытаемся ли забанить админа (если мы не владелец)
    if user_data[target_id]['status'] == 'admin' and user_data[user_id]['status'] != 'developer':
        bot.reply_to(message, "❌ Только Dev мжет банить админов")
        return
    
    # Проверяем, не забанен ли уже пользователь
    if user_data[target_id].get('banned', False):
        current_reason = user_data[target_id].get('ban_reason', 'Не указана')
        bot.reply_to(message, f"⚠️ Пользователь уже забанен\nТекущая причина: {current_reason}")
        return
    
    if ban_user(target_id, reason, user_id, custom_reason):
        admin_name = user_data[user_id].get('first_name', 'Админ')
        
        response = f"""🔨 Пользователь забанен

👤 Имя: {target_name}
🔗 Юзернейм: @{target_username_found}
🆔 ID: {target_id}
📋 Причина: {custom_reason}
👮 Забанил: {admin_name}
⏰ Время: {datetime.now().strftime("%d.%m.%Y %H:%M")}"""
        
        bot.reply_to(message, response)
        
        # Пытаемся уведомить забаненного пользователя
        try:
            notify_user(target_id, 'got_ban')
        except:
            pass
    else:
        bot.reply_to(message, "❌ Ошибка при бане пользователя")

# Команда разбана пользователя по юзернейму
@bot.message_handler(commands=['unban'])
def unban_command(message):
    user_id = str(message.from_user.id)
    
    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда не доступна.")
        return
    
    command = message.text.split()
    if len(command) < 2:
        bot.reply_to(message, "❌ Формат: /unban @username")
        return
    
    target_username = command[1].replace('@', '').lower()
    user_data = load_data()
    
    # Ищем пользователя по юзернейму
    target_id = None
    target_username_found = None
    target_name = None
    for uid, data in user_data.items():
        if data.get('username', '').lower() == target_username:
            target_id = uid
            target_username_found = data.get('username')
            target_name = data.get('first_name')
            break
    
    if not target_id:
        bot.reply_to(message, "❌ Пользователь с таким юзернеймом не найден")
        return
    
    if not user_data[target_id].get('banned', False):
        bot.reply_to(message, "❌ Этот пользователь не забанен")
        return
    
    if unban_user(target_id):
        admin_name = user_data[user_id].get('first_name', 'Админ')
        ban_reason = user_data[target_id].get('ban_reason', 'Не указана')
        
        response = f"""✅ Пользователь разбанен

👤 Имя: {target_name}
🔗 Юзернейм: @{target_username_found}
🆔 ID: {target_id}
📋 Была причина: {ban_reason}
👮 Разбанил: {admin_name}
⏰ Время: {datetime.now().strftime("%d.%m.%Y %H:%M")}"""
        
        bot.reply_to(message, response)
        
        # Пытаемся уведомить разбаненного пользователя
        try:
            notify_user(target_id, 'got_unbanned')
        except:
            pass
    else:
        bot.reply_to(message, "❌ Ошибка при разбане пользователя")

# Команда списка забаненных пользователей
@bot.message_handler(commands=['banned'])
def banned_list_command(message):
    user_id = str(message.from_user.id)
    
    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда не доступна.")
        return
    
    user_data = load_data()
    banned_users = []
    
    for uid, data in user_data.items():
        if data.get('banned', False):
            reason = data.get('ban_reason', 'Не указана')
            ban_date = data.get('ban_date', 'неизвестно')
            banned_by = data.get('banned_by', 'неизвестно')
            
            banned_users.append(f"🔨 @{data.get('username', 'нет')} (ID: {uid})\n   📋 {reason}\n   📅 {ban_date}\n   👮 {banned_by}\n")
    
    if banned_users:
        text = "🚫 Забаненные пользователи:\n\n" + "\n".join(banned_users)
    else:
        text = "✅ Нет забаненных пользователей"
    
    bot.reply_to(message, text)

# Команда проверки бана пользователя
@bot.message_handler(commands=['check_ban'])
def check_ban_command(message):
    user_id = str(message.from_user.id)
    
    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда не доступна.")
        return
    
    command = message.text.split()
    if len(command) < 2:
        bot.reply_to(message, "❌ Формат: /check_ban @username")
        return
    
    target_username = command[1].replace('@', '').lower()
    user_data = load_data()
    
    # Ищем пользователя по юзернейму
    target_id = None
    user_info = None
    for uid, data in user_data.items():
        if data.get('username', '').lower() == target_username:
            target_id = uid
            user_info = data
            break
    
    if not target_id:
        bot.reply_to(message, "❌ Пользователь с таким юзернеймом не найден")
        return
    
    if user_info.get('banned', False):
        reason = user_info.get('ban_reason', 'Не указана')
        ban_date = user_info.get('ban_date', 'неизвестно')
        banned_by = user_info.get('banned_by', 'неизвестно')
        
        text = f"""🔨 Пользователь ЗАБАНЕН

👤 Имя: {user_info.get('first_name')}
🔗 Юзернейм: @{target_username}
🆔 ID: {target_id}
📋 Причина: {reason}
📅 Дата бана: {ban_date}
👮 Забанил: {banned_by}"""
    else:
        text = f"✅ Пользователь @{target_username} не забанен\n🆔 ID: {target_id}"
    
    bot.reply_to(message, text)

@bot.message_handler(commands=['menu'])
def mune(message):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name
    username = message.from_user.username

    if not BOT_ENABLED and not can_manage_admins(str(message.from_user.id)):
       bot.send_message(message.chat.id, "🚫 Бот временно недоступен.")
       return
    
    if is_banned(user_id):
        user_data = load_data()
        reason = user_data[user_id].get('ban_reason', 'Не указана')
        bot.reply_to(message, f"🚫 Вы забанены в этом боте.\nПричина: {reason}")
        return
    
    msg = bot.send_message(message.chat.id, "Открываю меню...")
    time.sleep(2)
    main_menu(msg)

@bot.message_handler(commands=['profile'])
def profile_user(message):
    user_id = str(message.chat.id)
    user_data = load_data()
    user_info = user_data[user_id]
    color = user_info['color']

    if not BOT_ENABLED and not can_manage_admins(str(message.from_user.id)):
       bot.send_message(message.chat.id, "🚫 Бот временно недоступен.")
       return
    
    if is_banned(user_id):
        user_data = load_data()
        reason = user_data[user_id].get('ban_reason', 'Не указана')
        bot.reply_to(message, f"🚫 Вы забанены в этом боте.\nПричина: {reason}")
        return
    
        
        # Получаем статус для отображения
    if user_info.get('banned', False):
        display_status = STATUS['banned']
    else:
        display_status = STATUS.get(user_info.get('status', 'user'), '👤 Игрок')
        
        # ФОРМАТИРУЕМ ИНФОРМАЦИЮ О ПРЕМИУМЕ
        premium_info = ""
        premium_expires = user_info.get('premium_expires')
        
        if user_info.get('premium', False):
            if premium_expires == "∞ Навсегда":
                premium_info = "✅ Активирован\n⏰ Премиум до: Навсегда 🎉"
            elif premium_expires and premium_expires != "None":
                days_left = get_premium_days_left(premium_expires)
                premium_info = f"✅ Активирован\n⏰ Премиум до: {premium_expires}\n⏳ Осталось: {days_left}"
            else:
                premium_info = "✅ Активирован (бессрочный)"
        else:
            premium_info = "❌ Не активен"
        
        markup = types.InlineKeyboardMarkup()
        doc = types.InlineKeyboardButton('📋 Документация', callback_data='doc')
        hext = types.InlineKeyboardButton('⬅ Назад', callback_data='hext')
        markup.add(doc, hext)
        
        text = f"""📛 Имя: {color} {user_info['first_name']} 
🎭 Статус: {display_status}
🆔 ID: {user_info['id']}
💎 Премиум: {premium_info}
🎭 Анимации: {'✅ Вкл' if user_info.get('animations', True) else '❌ Выкл'}
🎲 Рандом-Коинов: {user_info.get('currency', 0)}
⚙️ Диапазон: {user_info.get('number', 10)} 
📅 Регистрация: {user_info.get('data', 'Неизвестно')}"""
        
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=['setting'])
def start_bot(message):
    user_id = str(message.chat.id)

    if not BOT_ENABLED and not can_manage_admins(str(message.from_user.id)):
       bot.send_message(message.chat.id, "🚫 Бот временно недоступен.")
       return
    
    if is_banned(user_id):
        user_data = load_data()
        reason = user_data[user_id].get('ban_reason', 'Не указана')
        bot.reply_to(message, f"🚫 Вы забанены в этом боте.\nПричина: {reason}")
        return
    
    msg = bot.send_message(message.chat.id, "⚙️ Загружаю настройки...")
    time.sleep(1)
    setting(msg)

@bot.message_handler(commands=['balance'])
def check_balance_command(message):
    user_id = str(message.from_user.id)
    
    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда доступна только администраторам.")
        return
    
    command = message.text.split()
    if len(command) < 2:
        bot.reply_to(message, "❌ Формат: /balance @username")
        return
    
    target_username = command[1].replace('@', '').lower()
    user_data = load_data()
    
    # Ищем пользователя
    target_id = None
    target_username_found = None
    target_name = None
    for uid, data in user_data.items():
        if data.get('username', '').lower() == target_username:
            target_id = uid
            target_username_found = data.get('username')
            target_name = data.get('first_name')
            break
    
    if not target_id:
        bot.reply_to(message, "❌ Пользователь с таким юзернеймом не найден")
        return
    
    currency = user_data[target_id].get('currency', 0)
    
    response = f"""💰 Баланс пользователя:

👤 Имя: {target_name}
🔗 Юзернейм: @{target_username_found}
🆔 ID: {target_id}
💳 Текущий баланс: {currency} рандом-Коинов"""
    
    bot.reply_to(message, response)

@bot.message_handler(commands=['give'])
def give_currency_command(message):
    user_id = str(message.from_user.id)
    user_data = load_data()

    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда доступна только администраторам.")
        return
    
    command = message.text.split()
    if len(command) < 3:
        bot.reply_to(message, "❌ Формат: /give @username количество\n\n💡 Пример:\n/give @username 10000")
        return
    
    target_username = command[1].replace('@', '').lower()
    try:
        amount = int(command[2])
        if amount <= 0:
            bot.reply_to(message, "❌ Количество должно быть положительным числом")
            return
    except ValueError:
        bot.reply_to(message, "❌ Количество должно быть числом")
        return
    
    user_data = load_data()
    
    # Ищем пользователя
    target_id = None
    target_username_found = None
    target_name = None
    for uid, data in user_data.items():
        if data.get('username', '').lower() == target_username:
            target_id = uid
            target_username_found = data.get('username')
            target_name = data.get('first_name')
            break
    
    if not target_id:
        bot.reply_to(message, "❌ Пользователь с таким юзернеймом не найден")
        return
    
    # Выдаем валюту
    user_data[target_id]['currency'] = user_data[target_id].get('currency', 0) + amount
    save_data(user_data)
    
    # Получаем информацию о том, кто выдал
    admin_name = user_data[user_id].get('first_name', 'Админ')
    
    response = f"""✅ Валюта выдана успешно!

👤 Получатель: {target_name}
🔗 Юзернейм: @{target_username_found}
🆔 ID: {target_id}
💰 Выдано: {amount} рандом-Коинов
👮 Выдал: {admin_name}
💳 Новый баланс: {user_data[target_id]['currency']}"""
    
    bot.reply_to(message, response)
    
    # Пытаемся уведомить пользователя
    try:
        bot.send_message(
            target_id,
            f"🎉 Вам выдано {amount} валюты!\n\n"
            f"💳 Ваш текущий баланс: {user_data[target_id]['currency']}\n"
            f"💎 Используйте валюту для открытия кейсов в магазине!"
        )
    except:
        pass  # Игнорируем если не удалось уведомить

@bot.message_handler(commands=['buy_premium'])
def buy_premium_command(message):
    user_id = str(message.from_user.id)
    user_data = load_data()
    
    if is_banned(user_id):
        user_data = load_data()
        reason = user_data[user_id].get('ban_reason', 'Не указана')
        bot.reply_to(message, f"🚫 Вы забанены в этом боте.\nПричина: {reason}")
        return
    
    user_currency = user_data[user_id].get('currency', 0)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    premium_7 = types.InlineKeyboardButton(f"💎 7 дней - 500 валюты", callback_data='buy_premium_7_days')
    premium_30 = types.InlineKeyboardButton(f"💎 30 дней - 1500 валюты", callback_data='buy_premium_30_days')
    premium_90 = types.InlineKeyboardButton(f"💎 90 дней - 3000 валюты", callback_data='buy_premium_90_days')
    premium_180 = types.InlineKeyboardButton(f"💎 180 дней - 5000 валюты", callback_data='buy_premium_180_days')
    premium_365 = types.InlineKeyboardButton(f"💎 365 дней - 8000 валюты", callback_data='buy_premium_365_days')
    
    markup.add(premium_7, premium_30, premium_90, premium_180, premium_365)
    
    text = f"""💎 <b>Покупка премиума</b>

💰 Ваша валюта: <b>{user_currency}</b>

Выберите срок премиума:"""
    
    bot.send_message(
        message.chat.id,
        text,
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.message_handler(commands=['feedback'])
def feedback_command(message):
    user_id = str(message.from_user.id)

    if not BOT_ENABLED and not can_manage_admins(str(message.from_user.id)):
       bot.send_message(message.chat.id, "🚫 Бот временно недоступен.")
       return
    

    if is_banned(user_id):
        user_data = load_data()
        reason = user_data[user_id].get('ban_reason', 'Не указана')
        bot.reply_to(message, f"🚫 Вы забанены в этом боте.\nПричина: {reason}")
        return
    
    # Сохраняем что пользователь начал писать фидбек
    user_data = load_data()
    if user_id not in user_data:
        user_data[user_id] = {}
    
    user_data[user_id]['waiting_feedback'] = True
    save_data(user_data)
    
    bot.reply_to(
        message,
        "💬 <b>Напишите ваш отзыв или предложение</b>\n\n"
        "Опишите что вам нравится, что можно улучшить, "
        "или предложите новые функции для бота!\n\n"
        "<i>Ваше сообщение будет отправлено разработчикам</i>",
        parse_mode="HTML"
    )

@bot.message_handler(commands=['feedback_stats'])
def feedback_stats_command(message):
    user_id = str(message.from_user.id)
    
    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда не доступна.")
        return
    
    user_data = load_data()
    total_users = len(user_data)
    active_users = sum(1 for user in user_data.values() if not user.get('banned', False))
    
    bot.reply_to(
        message,
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🎯 Активных пользователей: {active_users}\n"
        f"🚫 Забаненных: {total_users - active_users}\n\n"
        f"💎 Премиум пользователей: {sum(1 for user in user_data.values() if user.get('premium', False))}\n"
        f"🪙 Средний баланс: {sum(user.get('currency', 0) for user in user_data.values()) // total_users if total_users > 0 else 0}\n\n"
        f"<i>Для получения фидбеков используйте команду /feedback</i>",
        parse_mode="HTML"
    )

@bot.message_handler(commands=['cancel'])
def cancel_reply(message):
    """Отменяет процесс ответа на тикет"""
    user_id = str(message.from_user.id)
    user_data = load_data()
    user = user_data[user_id]['status'] in ['developer']

    if is_banned(user_id):
        user_data = load_data()
        reason = user_data[user_id].get('ban_reason', 'Не указана')
        bot.reply_to(message, f"🚫 Вы забанены в этом боте.\nПричина: {reason}")
        return

    if not user:
        bot.reply_to(message, '🚧 Команда в разработке')
        return
    
    if user_id in user_data and user_data[user_id].get('replying_to_ticket'):
        user_data[user_id]['replying_to_ticket'] = None
        save_data(user_data)
        
        bot.reply_to(
            message,
            "❌ <b>Ответ отменен</b>",
            parse_mode="HTML"
        )
    else:
        bot.reply_to(
            message,
            "ℹ️ <b>Нечего отменять</b>",
            parse_mode="HTML"
        )

def send_feedback_to_admins(user_id, user_name, username, feedback_text):
    """Отправляет фидбек всем админам"""
    user_data = load_data()
    admin_count = 0
    
    for uid, user_info in user_data.items():
        if user_info.get('status') in ['developer', 'admin']:
            try:
                bot.send_message(
                    int(uid),
                    f"📝 <b>НОВЫЙ ФИДБЕК</b>\n\n"
                    f"👤 <b>Пользователь:</b> {user_name}\n"
                    f"🔗 <b>Юзернейм:</b> {username}\n"
                    f"🆔 <b>ID:</b> {user_id}\n"
                    f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"💬 <b>Сообщение:</b>\n{feedback_text}\n\n"
                    f"━━━━━━━━━━━━━━━━",
                    parse_mode="HTML"
                )
                admin_count += 1
                time.sleep(0.1)
            except Exception as e:
                print(f"Не удалось отправить фидбек админу {uid}: {e}")
    
    return admin_count

@bot.message_handler(commands=['info'])
def bot_info(message):
    user_id = str(message.from_user.id)

    if not BOT_ENABLED and not can_manage_admins(str(message.from_user.id)):
       bot.send_message(message.chat.id, "🚫 Бот временно недоступен.")
       return
    
    if is_banned(user_id):
        user_data = load_data()
        reason = user_data[user_id].get('ban_reason', 'Не указана')
        bot.reply_to(message, f"🚫 Вы забанены в этом боте.\nПричина: {reason}")

    msg = bot.send_message(message.chat.id, 'Загрука...')
    markup = types.InlineKeyboardMarkup(row_width=1)
    doc1 = types.InlineKeyboardButton('📋 Документация о разработчиках 👨‍💻', callback_data='doc1')
    doc2 = types.InlineKeyboardButton('📋 Документация о боте 🤖', callback_data='doc2')
    hext = types.InlineKeyboardButton('⬅ Назад', callback_data='prof')
    markup.add(doc1, doc2, hext)
    bot.edit_message_text('Добро пожаловать !', message_id=msg.message_id, chat_id=message.chat.id, reply_markup=markup)

@bot.message_handler(commands=['help'])
def bot_help(message):
    user_id = str(message.from_user.id)

    if not BOT_ENABLED and not can_manage_admins(str(message.from_user.id)):
       bot.send_message(message.chat.id, "🚫 Бот временно недоступен.")
       return
    
    if is_banned(user_id):
        user_data = load_data()
        reason = user_data[user_id].get('ban_reason', 'Не указана')
        bot.reply_to(message, f"🚫 Вы забанены в этом боте.\nПричина: {reason}")

    text = """Доступные команды
/start - перезапуск бота
/random - открывает рандом меню  
/profile - открывает профиль
/mune - открывает главное меню
/feedback - отзыв
/buy_premium - открывает покупку премиума
/setting - открывает меню настроек

<i>Обновлено 2025 года</i>"""
    msg = bot.send_message(message.chat.id, 'Загрузка...')
    bot.edit_message_text(text, message_id=msg.message_id, chat_id=message.chat.id, parse_mode="HTML")

@bot.message_handler(commands=['maintenance'])
def maintenance_command(message):
    user_id = str(message.from_user.id)
    global BOT_ENABLED

    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда доступна только администраторам.")
        return
    
    BOT_ENABLED = False
    user_data = load_data()
    sent_count = 0
    failed_count = 0
    
    # Отправляем сообщение автору команды
    bot.reply_to(message, "🔄 Начинаю рассылку сообщения о технических работах...")
    
    for uid, user_info in user_data.items():
        try:
            # Пропускаем забаненных пользователей если нужно
            if user_info.get('banned', False):
                continue
                
            bot.send_message(
                int(uid),
                "🔧 <b>Технические работы</b>\n\n"
                "Бот временно недоступен из за тех работ.\n"
                "Приносим извинения за неудобства! 🛠️",
                parse_mode="HTML"
            )
            sent_count += 1
            time.sleep(0.1)  # Чтобы не превысить лимиты Telegram
        
        except Exception as e:
            print(f"Не удалось отправить пользователю {uid}: {e}")
            failed_count += 1

    # Отчет админу
    bot.send_message(
        message.chat.id,
        f"✅ Рассылка завершена!\n\n"
        f"📤 Отправлено: {sent_count} пользователям\n"
        f"❌ Не удалось: {failed_count}\n"
        f"👥 Всего в базе: {len(user_data)} пользователей"
    )

@bot.message_handler(commands=['maintenance_end'])
def maintenance_end_command(message):
    user_id = str(message.from_user.id)
    global BOT_ENABLED
    
    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда доступна только администраторам.")
        return
    
    user_data = load_data()
    sent_count = 0
    failed_count = 0
    
    bot.reply_to(message, "🔄 Уведомляю пользователей о завершении тех. работ...")
    
    for uid, user_info in user_data.items():
        try:
            if user_info.get('banned', False):
                continue
                
            bot.send_message(
                int(uid),
                "✅ <b>Технические работы завершены!</b>\n\n"
                "Бот снова работает в штатном режиме.\n"
                "Приносим извинения за неудобства! 🎉",
                parse_mode="HTML"
            )
            sent_count += 1
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Не удалось отправить пользователю {uid}: {e}")
            failed_count += 1
    BOT_ENABLED = True
    bot.send_message(
        message.chat.id,
        f"✅ Уведомления отправлены!\n\n"
        f"📤 Получили: {sent_count} пользователей\n"
        f"❌ Не получили: {failed_count}"
    )

@bot.message_handler(commands=['update'])
def update_bot(message):
    user_id = str(message.from_user.id)

    if not can_manage_admins(user_id):
        bot.reply_to(message, "❌ Эта команда доступна только администраторам.")
        return
    
    user_data = load_data()
    sent_count = 0
    failed_count = 0
    
    bot.reply_to(message, "🔄 Уведомляю пользователей о обновлении...")
    
    for uid, user_info in user_data.items():
        try:
            if user_info.get('banned', False):
                continue
                
            notify_user(
                uid, 'bot_update'
            )
            sent_count += 1
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Не удалось отправить пользователю {uid}: {e}")
            failed_count += 1
    
    bot.send_message(
        message.chat.id,
        f"✅ Уведомления отправлены!\n\n"
        f"📤 Получили: {sent_count} пользователей\n"
        f"❌ Не получили: {failed_count}"
    )

@bot.message_handler(commands=['tickets'])
def tickets_list_command(message):
    pass

@bot.message_handler(commands=['new_year'])
def new_year_command(message):
    """Новогодняя пасхалка с секретным подарком (команда на английском)"""
    user_id = str(message.from_user.id)
    user_data = load_data()
    
    if user_id not in user_data:
        bot.reply_to(message, "❌ Сначала зарегистрируйся командой /start")
        return
    
    # Получаем текущую дату
    now = datetime.now()
    
    # Проверяем новогодний период (20 декабря - 10 января)
    is_new_year_period = (
        (now.month == 12 and now.day >= 20) or 
        (now.month == 1 and now.day <= 10)
    )
    
    if not is_new_year_period:
        # Если не новогодний период, показываем таймер до НГ
        if now.month == 12:
            days_left = 31 - now.day
            message_text = (
                f"🎄 <b>Новогодняя пасхалка еще спит</b>\n\n"
                f"До Нового года осталось: <b>{days_left} дней</b>!\n\n"
                f"Вернись с 20 декабря по 10 января, чтобы найти секретный подарок! 🎅"
            )
        else:
            # Если январь, но уже после 10 числа
            days_left = 360  # примерно до следующего декабря
            message_text = (
                f"🎄 <b>Новогодняя пасхалка ушла в спячку</b>\n\n"
                f"До следующего Нового года: <b>{days_left} дней</b>!\n\n"
                f"Жди с 20 декабря по 10 января следующего года! ⛄"
            )
        
        bot.reply_to(message, message_text, parse_mode="HTML")
        return
    
    # Проверяем, получал ли пользователь подарок в этом году
    last_gift_year = user_data[user_id].get('last_new_year_gift', 0)
    
    if last_gift_year == now.year:
        # Уже получал подарок в этом году
        message_text = (
            f"🎅 <b>Ты уже нашел новогодний подарок в этом году!</b>\n\n"
            f"Твой подарок уже ждет тебя в профиле!\n"
            f"Вернись в следующем году за новым сюрпризом! 🎄\n\n"
            f"🎁 <b>Твой новогодний бонус:</b>\n"
            f"• +1000 валюты\n"
            f"• +7 дней премиума\n"
            f"• Эксклюзивный новогодний цвет ника: 🎄"
        )
        
        bot.reply_to(message, message_text, parse_mode="HTML")
        return
    
    # Секретный новогодний подарок!
    # 1. Даем валюту
    user_data[user_id]['currency'] = user_data[user_id].get('currency', 0) + 1000
    
    # 2. Даем премиум на 7 дней
    current_premium = user_data[user_id].get('premium', False)
    current_expires = user_data[user_id].get('premium_expires')
    
    if current_premium and current_expires and current_expires != "∞ Навсегда":
        try:
            expire_date = datetime.strptime(current_expires, "%d.%m.%Y")
            new_expire_date = expire_date + timedelta(days=7)
            user_data[user_id]['premium_expires'] = new_expire_date.strftime("%d.%m.%Y")
        except:
            new_expire_date = datetime.now() + timedelta(days=7)
            user_data[user_id]['premium_expires'] = new_expire_date.strftime("%d.%m.%Y")
    else:
        user_data[user_id]['premium'] = True
        new_expire_date = datetime.now() + timedelta(days=7)
        user_data[user_id]['premium_expires'] = new_expire_date.strftime("%d.%m.%Y")
    
    # 3. Даем новогодний цвет ника (если его нет)
    current_color = user_data[user_id].get('color', '')
    if '🎄' not in current_color and '🎅' not in current_color and '⛄' not in current_color:
        user_data[user_id]['color'] = '🎄 ' + current_color
    
    # 4. Отмечаем, что пользователь получил подарок в этом году
    user_data[user_id]['last_new_year_gift'] = now.year
    
    save_data(user_data)
    
    # Создаем красивую анимацию
    msg = bot.reply_to(message, "🔍 Ищу новогодний подарок...")
    time.sleep(2)
    
    bot.edit_message_text("🎄 Нашел ёлку...", message_id=msg.message_id, chat_id=message.chat.id)
    time.sleep(1)
    
    bot.edit_message_text("🎅 Вижу Деда Мороза...", message_id=msg.message_id, chat_id=message.chat.id)
    time.sleep(1)
    
    bot.edit_message_text("🎁 Открываю подарок...", message_id=msg.message_id, chat_id=message.chat.id)
    time.sleep(2)
    
    # Финальное сообщение с подарком
    message_text = f"""
🎉 <b>С НОВЫМ ГОДОМ, {user_data[user_id]['first_name']}!</b> 🎉

✨ <b>Ты нашел секретную новогоднюю пасхалку!</b>

🎁 <b>Твой подарок:</b>

💰 <b>+1000 валюты</b> - теперь у тебя {user_data[user_id]['currency']}!
💎 <b>+7 дней премиума</b> - до {user_data[user_id].get('premium_expires', '?')}
🎄 <b>Новогодний цвет ника</b> - теперь в профиле будет ёлочка!

🎅 <b>Секретная фраза этого года:</b>
"В Новый год все возможно, даже нахождение секретной пасхалки!"

⛄ <b>Пожелание от Деда Мороза:</b>
{random.choice([
    "Пусть следующий год будет полон радости и удачи!",
    "Желаю, чтобы все твои мечты сбылись!",
    "Пусть каждый день приносит новые возможности!",
    "Желаю крепкого здоровья и счастливых моментов!",
    "Пусть Новый год будет лучше предыдущего!"
])}

🎆 <b>Вернись в следующем году за новым сюрпризом!</b>

<i>Используй команду /profile чтобы увидеть свой подарок!</i>
"""
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    profile_btn = types.InlineKeyboardButton('👤 Посмотреть профиль', callback_data='prof')
    games_btn = types.InlineKeyboardButton('🎲 Играть в игры', callback_data='num1')
    markup.add(profile_btn, games_btn)
    
    bot.edit_message_text(
        message_text, 
        message_id=msg.message_id, 
        chat_id=message.chat.id, 
        parse_mode="HTML",
        reply_markup=markup
    )
    
    # Уведомляем пользователя
    try:
        bot.send_message(
            int(user_id),
            "🎄 <b>С новогодним подарком!</b>\n\n"
            "Ты успешно активировал новогоднюю пасхалку! 🎅\n"
            "Проверь свой профиль командой /profile",
            parse_mode="HTML"
        )
    except:
        pass

# Команда для проверки статуса пасхалки (тоже на английском)
@bot.message_handler(commands=['easter_status'])
def easter_egg_status(message):
    """Показывает статус новогодней пасхалки"""
    user_id = str(message.from_user.id)
    user_data = load_data()
    
    if user_id not in user_data:
        bot.reply_to(message, "❌ Сначала зарегистрируйся командой /start")
        return
    
    now = datetime.now()
    
    # Проверяем период
    is_new_year_period = (
        (now.month == 12 and now.day >= 20) or 
        (now.month == 1 and now.day <= 10)
    )
    
    last_gift_year = user_data[user_id].get('last_new_year_gift', 0)
    has_gift_this_year = last_gift_year == now.year
    
    message_text = f"🎄 <b>Статус новогодней пасхалки</b>\n\n"
    
    if is_new_year_period:
        message_text += "✅ <b>Период активен:</b> 20 декабря - 10 января\n\n"
        
        if has_gift_this_year:
            message_text += (
                f"🎁 <b>Ты уже получил подарок в {now.year} году!</b>\n\n"
                f"Вернись в следующем году за новым сюрпризом.\n"
                f"Твой подарок уже в профиле! 🎅"
            )
        else:
            message_text += (
                f"✨ <b>Пасхалка доступна!</b>\n\n"
                f"Используй команду /new_year чтобы найти подарок!\n"
                f"Таймер: осталось {10 - now.day if now.month == 1 else 31 - now.day + 10} дней"
            )
    else:
        # Показываем таймер до следующего НГ
        if now.month < 12:
            days_until_dec_20 = (datetime(now.year, 12, 20) - now).days
        else:
            days_until_dec_20 = (datetime(now.year + 1, 12, 20) - now).days
        
        message_text += (
            f"⏳ <b>Пасхалка не активна</b>\n\n"
            f"До следующего новогоднего периода: <b>{days_until_dec_20} дней</b>\n\n"
            f"🎅 <b>Период активности:</b>\n"
            f"• 20 декабря - 31 декабря\n"
            f"• 1 января - 10 января\n\n"
            f"Вернись в эти даты за подарком!"
        )
    
    bot.reply_to(message, message_text, parse_mode="HTML")

@bot.message_handler(commands=['support'])
def support_command(message):
    bot.send_message(message.chat.id, '🚧 Эта команда в разработке ⚙')
 

@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = str(message.from_user.id)
    user_data = load_data()
    
    # Пропускаем команды
    if message.text.startswith('/'):
        return
    
    # Проверяем, находится ли пользователь в режиме написания фидбека
    if user_id in user_data and user_data[user_id].get('waiting_feedback'):
        # Сбрасываем флаг
        user_data[user_id]['waiting_feedback'] = False
        save_data(user_data)
        
        # Проверяем длину сообщения
        if len(message.text) < 5:
            markup = types.InlineKeyboardMarkup()
            retry_btn = types.InlineKeyboardButton('🔄 Попробовать снова', callback_data='retry_feedback')
            markup.add(retry_btn)
            
            bot.reply_to(
                message,
                "❌ <b>Сообщение слишком короткое</b>\n\n"
                "Пожалуйста, напишите более подробный отзыв (минимум 5 символов).\n"
                "Опишите что конкретно вам понравилось или что можно улучшить.",
                parse_mode="HTML",
                reply_markup=markup
            )
            return
        
        if len(message.text) > 2000:
            markup = types.InlineKeyboardMarkup()
            retry_btn = types.InlineKeyboardButton('🔄 Попробовать снова', callback_data='retry_feedback')
            markup.add(retry_btn)
            
            bot.reply_to(
                message,
                "❌ <b>Сообщение слишком длинное</b>\n\n"
                "Пожалуйста, сократите ваш отзыв до 2000 символов.\n"
                "Вы можете разбить его на несколько сообщений.",
                parse_mode="HTML",
                reply_markup=markup
            )
            return
        
        # Проверяем на спам/многочисленные символы
        if message.text.count(message.text[0]) > len(message.text) * 0.7:
            bot.reply_to(
                message,
                "❌ <b>Сообщение содержит слишком много повторяющихся символов</b>\n\n"
                "Пожалуйста, напишите содержательный отзыв.",
                parse_mode="HTML"
            )
            return
        
        # Получаем информацию о пользователе
        user_info = user_data[user_id]
        username = user_info.get('username', 'нет')
        user_name = user_info.get('first_name', 'Неизвестно')
        
        # Отправляем фидбек админам
        admin_count = send_feedback_to_admins(user_id, user_name, username, message.text)
        
        # Отправляем подтверждение пользователю
        if admin_count > 0:
            bot.reply_to(
                message,
                f"✅ <b>Спасибо за ваш отзыв!</b>\n\n"
                f"Ваше сообщение было отправлено {admin_count} администраторам.\n"
                f"Мы обязательно рассмотрим ваше предложение!\n\n"
                f"<i>Ваш отзыв помогает нам улучшать бота!</i>",
                parse_mode="HTML"
            )
        else:
            bot.reply_to(
                message,
                "✅ <b>Спасибо за ваш отзыв!</b>\n\n"
                "Ваше сообщение сохранено и будет рассмотрено в ближайшее время.\n\n"
                "<i>К сожалению, сейчас нет активных администраторов.</i>",
                parse_mode="HTML"
            )
        
        # Сохраняем историю фидбеков (опционально)
        try:
            # Создаем или открываем файл для истории фидбеков
            feedback_file = 'feedback_history.json'
            if os.path.exists(feedback_file):
                with open(feedback_file, 'r', encoding='utf-8') as f:
                    feedback_history = json.load(f)
            else:
                feedback_history = []
            
            # Добавляем новый фидбек
            feedback_entry = {
                'user_id': user_id,
                'user_name': user_name,
                'username': username,
                'message': message.text,
                'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            }
            
            feedback_history.append(feedback_entry)
            
            # Сохраняем обратно
            with open(feedback_file, 'w', encoding='utf-8') as f:
                json.dump(feedback_history, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Не удалось сохранить фидбек в историю: {e}")
        
        return
    
    # Если это обычное сообщение (не фидбек)
    bot.reply_to(
        message,
        "🤖 <b>Я не понимаю ваше сообщение</b>\n\n"
        "Используйте команды для взаимодействия с ботом:\n"
        "• /start - Перезапуск бота\n"
        "• /menu - Главное меню\n"
        "• /help - Список команд\n"
        "• /feedback - Отправить отзыв\n\n"
        "<i>Если вы хотите отправить отзыв, используйте команду /feedback</i>",
        parse_mode="HTML"
    )

print('Бот запущен !')
bot.polling(non_stop=True, timeout=120)