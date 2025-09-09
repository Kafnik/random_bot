import telebot
from time import sleep
import random

bot = telebot.TeleBot('8318795699:AAGyD4zsJAqi8xdRoPRppO4tTiddheu6f0w')


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 'VECTORBOT')
    sleep(1)
    bot.send_message(message.chat.id, 'Привет я бот рандома пропиши команду /random. Или ознакомьтесь со списком команд напишите в чат /help')


@bot.message_handler(commands=['random'])
def random_bot(message):
    number = random.randint(1, 100)
    bot.send_message(message.chat.id, f'Ваше случайное число: {number}')


@bot.message_handler(commands=['help'])
def info(message):
    bot.send_message(message.chat.id, 'В данном боте присутствую команды'
                                      ' /start, /random, /help, /progress')

@bot.message_handler(commands=['progress'])
def progress(message):
    bot.send_message(message.chat.id, 'Мы научились делать команды, если отправите фото тогада он скажет какое красивое фото, тригер на определенное слово напишите слово привет то он напшите привет и ваш user_name если  id то бот напишет ваше айди.')

@bot.message_handler(content_types=['photo'])
def get_photo(message):
    bot.send_message(message.chat.id,'Какое красивое фото! ')

@bot.message_handler()
def info(message, massage=None):
    if message.text.lower() == 'привет':
        bot.send_message(message.chat.id, f'Привет, {message.from_user.first_name}')
    elif message.text.lower() == 'id':
        bot.reply_to(message,f'ID:{message.from_user.id}')



bot.polling(non_stop=True)