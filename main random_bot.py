import telebot
import random 
from time import sleep
from telebot import types

bot = telebot.TeleBot('8318795699:AAGYwR5IDaAZ_YCkoP8DKSY0l6d-UEAG2Fw')

foods = ["🧠Варенный мозг", "🎃Суп из тьмы", "💀Паучий пирог", "🩸Кровавый смузи", "🎃Пирожок с тыквой"]
coin = ["👁Орел потусторонний", "🩸Решка демона"]
roles = [ "🧙 Ведьма из тумана",
            "🧛 Вампир с красными глазами",
            "🧟‍♂️ Зомби, ищущий мозги",
            "🕸 Призрак старого замка",
            "🐺 Оборотень из ночного леса",
            "🎭 Таинственный незнакомец"]
treats = ["🍫 Шоколадка с привидениями",
            "🍭 Карамельный череп",
            "🍪 Печенье с пауками",
            "🍬 Конфета с сюрпризом",
            "🧃 Кровавый сок (клюквенный конечно!)"]
mosters = [ "👹 Крик болотного чудовища",
            "🦇 Вампир-охотник за сладостями",
            "🪦 Призрак кладбища",
            "💀 Скелет, танцующий в тумане",
            "🕷 Огромный паук с красными глазами"]
challenges = [
            "🎃 Расскажи страшную историю!",
            "💀 Сделай фото в темноте и отправь другу",
            "🧟‍♀️ Притворись зомби на 10 секунд",
            "🕸️ Скажи 'Бу!' кому-нибудь неожиданно",
            "🦇 Придумай себе страшное имя"
        ]
spooky_phrases = [
        "🕯 Призываю духов...",
        "🌑 Тьма сгущается...",
        "🕸 Что-то движется в темноте...",
        "💀 Шепот из темноты...",
        "🦇 Ночь пробуждает монстров..."
    ]


def complate_play(message):
    msg = bot.send_message(message.chat.id, random.choice(spooky_phrases))
    sleep(1)
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🎲Рандомное число", callback_data='btn1')
    btn2 = types.InlineKeyboardButton("🍔Рандомная еда", callback_data='btn2')
    btn3 = types.InlineKeyboardButton("🪙Орел или решка", callback_data='btn3')
    who = types.InlineKeyboardButton("🧛‍♂️Кто ты на Хуллоуин?", callback_data="who")
    treat = types.InlineKeyboardButton("🍬Угощение или жизнь", callback_data="treat")
    monster = types.InlineKeyboardButton("👻Монстр дня",callback_data="monster")
    challenge = types.InlineKeyboardButton("🎲Испытание",callback_data="challenge")
    markup.add(btn1, btn2, btn3, who, treat, monster, challenge)
    bot.edit_message_text(chat_id=message.chat.id, message_id=msg.message_id, text="🎃 *Игра завершена!* 🎃\n\n"
            "Вы отлично справились, смертный!\n\n"
            "👇 *Выбери следующую игру или рискни вызвать духов снова...* 👇",parse_mode='Markdown',
        reply_markup=markup)
        
#-----------------Обновление 1.3----------------------
@bot.message_handler(commands=['halloween'])
def halloween(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    who = types.InlineKeyboardButton("🧛🏻‍♀️Кто ты на Хуллоуин?", callback_data="who")
    treat = types.InlineKeyboardButton("🍬Угощение или жизнь", callback_data="treat")
    monster = types.InlineKeyboardButton("👻Монстр дня",callback_data="monster")
    challenge = types.InlineKeyboardButton("🎲Испытание",callback_data="challenge")
    markup.add(who, treat, monster, challenge)
    bot.send_message(message.chat.id, "🎃 Добро пожаловать в *Halloween Random!*", reply_markup=markup)
    

# ---------------- Меню рандомных игр ----------------
@bot.message_handler(commands=['random'])
def random_menu(message):
    msg = bot.send_message(message.chat.id, 'Загрузка...')
    sleep(1)
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🎲Рандомное число", callback_data='btn1')
    btn2 = types.InlineKeyboardButton("🍔Рандомная еда", callback_data='btn2')
    btn3 = types.InlineKeyboardButton("🪙Орел или решка", callback_data='btn3')
    markup.add(btn1, btn2, btn3)
    bot.edit_message_text('Меню игр открыто!', reply_markup=markup, message_id=msg.message_id, chat_id=message.chat.id)

@bot.callback_query_handler(func=lambda m: True)
def  callback_data(call):
    if call.data == 'btn1':
        msg = bot.send_message(call.message.chat.id, 'Генерирую...')
        sleep(1)
        number = random.randint(1, 666)
        bot.edit_message_text(f"Твое число: {number}", message_id=msg.message_id, chat_id=call.message.chat.id)
        sleep(1)
        bot.answer_callback_query(call.id)
        complate_play(call.message)

    elif call.data == 'btn2': 
        food = random.choice(foods)
        bot.send_message(call.message.chat.id, f'Тебе выподает: {food}')
        sleep(1)
        bot.answer_callback_query(call.id)
        complate_play(call.message)


    elif call.data == 'btn3':
        orel = random.choice(coin)
        bot.send_message(call.message.chat.id, f'Тебе выподает: {orel}')
        sleep(1)
        bot.answer_callback_query(call.id)
        complate_play(call.message)


#-------------Хелуин------------
    elif call.data == 'who':
        relust = random.choice(roles)
        bot.send_message(call.message.chat.id, f'На Хэллоуин ты - {relust}')
        sleep(1)
        bot.answer_callback_query(call.id)
        complate_play(call.message)

    elif call.data == 'treat':
        relust = random.choice(treats)
        bot.send_message(call.message.chat.id, f'Тебе досталось: {relust}')
        sleep(1)
        bot.answer_callback_query(call.id)
        complate_play(call.message)

    elif call.data == 'monster':
        relust = random.choice(mosters)
        bot.send_message(call.message.chat.id, f'Сегодня тебя преследует: {relust}')
        sleep(1)
        bot.answer_callback_query(call.id)
        complate_play(call.message)
  
    elif call.data == 'challenge':
        relust = random.choice(challenges)
        bot.send_message(call.message.chat.id, f'Твое испытание: {relust}')
        sleep(1)
        bot.answer_callback_query(call.id)
        complate_play(call.message)


# ---------------- Запуск бота ----------------
print('Бот запущен!')
bot.polling(none_stop=True)