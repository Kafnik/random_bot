import telebot
import random
from telebot import types
from confing import TELEGRAM_TOKEN
from time import sleep

bot = telebot.TeleBot(TELEGRAM_TOKEN)

VERSION = 1.2
x = 1000
junk_food= ["Пицца", "Бургер", "Суши","Салат","Рамен","Картошка фри","Шаурма"]
orel_talis = ["Орел","Решка"]



@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 'OpenbotAI')
    sleep(1)
    bot.send_message(message.chat.id, 'Привет я бот рандома пропиши команду /random. Или ознакомьтесь со списком команд напишите в чат /help')

@bot.message_handler(commands=['random'])
def random_mune(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    food = types.InlineKeyboardButton('Случайная еда', callback_data='food1')
    orel = types.InlineKeyboardButton('Орел решка', callback_data='orel1')
    number = types.InlineKeyboardButton('Случайное число', callback_data='number1')
    markup.add(food, orel, number)
    bot.send_message(message.chat.id, f'Добро пожаловать в меню игр {message.from_user.first_name}', reply_markup=markup)
    
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data =='food1':
        markup = types.InlineKeyboardMarkup(row_width=1)
        random_food = types.InlineKeyboardButton('Сделать случайную еду', callback_data='eda')
        markup.add(random_food)
        bot.send_message(call.message.chat.id, 'Напишите в чат /random_food или нажми кнопку', reply_markup=markup)
        
    elif call.data == 'eda':
        result = random.choice(junk_food)
        bot.send_message(call.message.chat.id, f'Сегодня тебе выподает: {result}')
        sleep(1)
        markup = types.InlineKeyboardMarkup(row_width=2)
        yes = types.InlineKeyboardButton('Да', callback_data='yes1')
        no = types.InlineKeyboardButton('Нет', callback_data='no1')
        markup.add(yes, no)
        bot.send_message(call.message.chat.id, 'Желаете продолжить игру ?', reply_markup=markup)

    elif call.data == 'orel1':
        markup = types.InlineKeyboardMarkup(row_width=1)
        orel = types.InlineKeyboardButton('Орел или решка ?🤔', callback_data='num2')
        markup.add(orel)
        bot.send_message(call.message.chat.id, 'Напишите в чат /random_orel или нажми кнопку', reply_markup=markup)
  
    elif call.data == 'num2':
        num = random.choice(orel_talis)
        bot.send_message(call.message.chat.id, f'Тебе вы подает: {num}')
        sleep(1)
        markup = types.InlineKeyboardMarkup(row_width=2)
        yes = types.InlineKeyboardButton('Да', callback_data='yes2')
        no = types.InlineKeyboardButton('Нет', callback_data='no1')
        markup.add(yes, no)
        bot.send_message(call.message.chat.id, 'Желаете продолжить игру ?', reply_markup=markup)
        
    elif call.data == 'yes1':
        result = random.choice(junk_food)
        bot.send_message(call.message.chat.id, f'Сегодня тебе выподает: {result}')
        sleep(1)
        markup = types.InlineKeyboardMarkup(row_width=2)
        yes = types.InlineKeyboardButton('Да', callback_data='yes1')
        no = types.InlineKeyboardButton('Нет', callback_data='no1')
        markup.add(yes, no)
        bot.send_message(call.message.chat.id, 'Желаете продолжить игру ?', reply_markup=markup) 

    elif call.data == 'yes2':
        num = random.choice(orel_talis)
        bot.send_message(call.message.chat.id, f'Тебе вы подает: {num}')
        sleep(1)
        markup = types.InlineKeyboardMarkup(row_width=2)
        yes = types.InlineKeyboardButton('Да', callback_data='yes2')
        no = types.InlineKeyboardButton('Нет', callback_data='no1')
        markup.add(yes, no)
        bot.send_message(call.message.chat.id, 'Желаете продолжить игру ?', reply_markup=markup)

    elif call.data == 'number1':
        markup = types.InlineKeyboardMarkup(row_width=1)
        number2 = types.InlineKeyboardButton('Случайное число', callback_data='number3')
        markup.add(number2)
        bot.send_message(call.message.chat.id, 'Напишите в чат /random_number или нажми кнопку', reply_markup=markup)

    elif call.data == 'number3':
        number = random.randint(1, x)
        bot.send_message(call.message.chat.id, f'Ваше случайное число: {number}')
        sleep(1)
        markup = types.InlineKeyboardMarkup(row_width=2)
        yes = types.InlineKeyboardButton('Да', callback_data='yes3')
        no = types.InlineKeyboardButton('Нет', callback_data='no1')
        markup.add(yes, no)
        bot.send_message(call.message.chat.id, 'Желаете продолжить игру ?', reply_markup=markup)

    elif call.data == 'yes3':
        number1 = random.randint(1, x)
        bot.send_message(call.message.chat.id, f'Ваше случайное число: {number1}')
        sleep(1)
        markup = types.InlineKeyboardMarkup(row_width=2)
        yes = types.InlineKeyboardButton('Да', callback_data='yes3')
        no = types.InlineKeyboardButton('Нет', callback_data='no1')
        markup.add(yes, no)
        bot.send_message(call.message.chat.id, 'Желаете продолжить игру ?', reply_markup=markup)

    elif call.data == 'no1':
         bot.answer_callback_query(call.id)
         random_mune(call.message)

@bot.message_handler(commands=['random_orel'])
def random_orel_user(message):
    num = random.choice(orel_talis)
    bot.send_message(message.chat.id, f'Тебе вы подает: {num}')

@bot.message_handler(commands=['random_food'])
def random_food_user(message):
    result = random.choice(junk_food)
    bot.send_message(message.chat.id, f'Сегодня тебе выподает: {result}')

@bot.message_handler(commands=['random_number'])
def random_bot(message):
    number = random.randint(1, x)
    bot.send_message(message.chat.id, f'Ваше случайное число: {number}')

@bot.message_handler(commands=['help'])
def info(message):
    bot.send_message(message.chat.id, 'В данном боте присутствуют команды ')
    
@bot.message_handler(commands=['info'])
def info_user(message):
    bot.send_message(message.chat.id, f'Бот cделан команиями: OpenbotAI и VECTORBOT \nНо большую чать выполнила комания: OpenbotAI \nЧто есть прикольного команда /credit \nВерсия бота: {VERSION}')

print('Рандом бот запушен!')
bot.polling(non_stop=True)