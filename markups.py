from telebot import types


def gen_select_types_user() -> types.InlineKeyboardMarkup():
    markup = types.InlineKeyboardMarkup()
    bt1 = types.InlineKeyboardButton('Админ', callback_data='admin')
    bt2 = types.InlineKeyboardButton('Гость', callback_data='user')
    markup.add(bt1, bt2)

    return markup


def gen_groups_list(groups, for_='G') -> types.InlineKeyboardMarkup():
    markup = types.InlineKeyboardMarkup()
    for group in groups:
        bt = types.InlineKeyboardButton(group, callback_data=f'{for_}]{group}')
        markup.add(bt)

    return markup


def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    bt1 = types.KeyboardButton('Показать мои группы')
    bt2 = types.KeyboardButton('Расписание')
    markup.add(bt1)
    markup.add(bt2)
    return markup


def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    bt1 = types.KeyboardButton('Добавить админа')
    bt2 = types.KeyboardButton('отправить первичный qr')
    bt3 = types.KeyboardButton('Рассылка')
    markup.add(bt1, bt3)
    markup.add(bt2)
    return markup


def gen_mailing_list(groups: list):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('Все', callback_data=f'M]all'))
    for group in groups:
        bt = types.InlineKeyboardButton(group, callback_data=f'M]{group}')
        markup.add(bt)
    return markup
