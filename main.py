import telebot
import keys
import logic
import markups


bot = telebot.TeleBot(keys.TELEGRAM_TOKEN)


@bot.message_handler(commands=['start', 'add_admin', 'mailing'])
def start(message):
    user_id = message.chat.id
    statys = logic.check_user(user_id)

    if message.text == '/start':
        if statys == 'admin':
            bot.send_message(user_id,
                             'Добро пожаловать!\n'
                             'Сфотографируйте QR и я отмечу клиента',
                             reply_markup=markups.admin_keyboard())

        elif statys == 'default_user':
            markup = markups.main_keyboard()
            bot.send_message(user_id,
                             'С возвращением!\n',
                             reply_markup=markup)

        elif statys == 'new':
            bot.send_message(user_id,
                             'Привет!\n'
                             'Отправьте мне свой qr-код и вы сможете смотреть свои метрики')


@bot.message_handler(content_types=['photo'])
def read_photo(message):

    user_id = message.chat.id
    file_id = message.photo[-1].file_id
    qr_data = logic.read_qr(file_id, user_id)

    if qr_data == '':
        bot.send_message(user_id, 'Извините не могу прочитать QR\n'
                                  'попробуйте еще раз')
    else:
        if logic.check_user(user_id) == 'admin':
            user_name = logic.sheets_check_user(qr_data)
            if user_name != 'error':
                bot.send_message(user_id, f'гость отмечен! {user_name}')

        elif logic.check_user(user_id) == 'default_user':
            bot.send_message(user_id, f'Загружаю...')
            user_data = logic.sheets_get_user(qr_data)
            if user_data != 'error':
                logic.link_google_tg(user_id, user_data)

                markup = markups.main_keyboard()
                bot.send_message(user_id, 'Сохранил! в дальнейшем можете использовать'
                                          ' меню для получения информации и qr-кода',
                                 reply_markup=markup)

                markup = markups.gen_groups_list(user_data['groups'])
                bot.send_message(user_id,
                                 f'> {user_data["name"]}'
                                 f'\nВыберите группу для более подробной информации',
                                 parse_mode='MarkdownV2',
                                 reply_markup=markup)
            else:
                bot.send_message(user_id, 'Произошла ошибка, обратитесь к администратору')


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    call_back = call.data.split(']')
    user_id = call.message.chat.id

    if call_back[0] == 'G':

        group = call_back[1]
        user_data = logic.read_json('users.json')['google_users'][str(user_id)]
        info = logic.get_user_group_info(user_data['name'], group)
        if 'error' not in info:
            group_id = user_data['ids'][user_data['groups'].index(group)]

            active_voucher = {}
            vouchers_count = len(info['vouchers'])
            active_voucher_count = 0
            for voucher in info['vouchers']:
                if voucher['remaining_visits'] != '0':
                    active_voucher['date_start'] = voucher['date_start'].replace('.', '\\.')
                    active_voucher['date_end'] = voucher['date_end'].replace('.', '\\.')
                    active_voucher['remaining_visits'] = voucher['remaining_visits']
                    active_voucher_count += 1

            text = f'\\↑QR для отметки посещения\\↑\nВы были на занятии {info["visits_count"]} раз\\.'\
                   f'\nВ эту группу вы приобретали абонемент {vouchers_count} раз\n'

            if active_voucher_count > 0:
                text += f'> Активный абонемент\n'\
                        f'> Первое занятие\\: {active_voucher["date_start"]} \n'\
                        f'> Дата окончания абонемента\\: {active_voucher["date_end"]}\n'\
                        f'> Осталось занятий\\: {active_voucher["remaining_visits"]}'
            elif active_voucher_count == 0:
                text += '> На данный момент у вас нет активных абонементов'

            path = logic.gen_qr_code(group_id, user_id)
            bot.send_photo(user_id,
                           photo=open(path, 'rb'),
                           caption=text,
                           parse_mode='MarkdownV2')
            logic.dell_qr_pic(path)
        else:
            bot.send_message(user_id, 'Произошла ошибка, обратитесь к администратору')

    elif call_back[0] == 'R':
        group = call_back[1]
        data = logic.view_schedule(group)
        if data[0] != 'error':
            bot.send_message(user_id, f'Расписание для группы "{group}"')
            for item in data:
                text = ''
                tag = item['tag'].replace('-', '\\-')
                text += f'Направление\\: {tag}\n'
                text += f'День\\: {item["day"]}\n'
                time = item["time"].replace('-', '\\-').replace(':', '\\:')
                text += f'Время\\: {time}\n'
                text += f'> {item["teacher"]}'
                bot.send_message(user_id, text, parse_mode='MarkdownV2')
        else:
            bot.send_message(user_id, 'Произошла ошибка, обратитесь к администратору')

    elif call_back[0] == 'M':
        bot.send_message(user_id, 'Отправьте сообщение для рассылки!')
        bot.register_next_step_handler(call.message, mailing, call_back[1])


@bot.message_handler(content_types=['text'])
def menu(message):
    user_id = message.chat.id
    statys = logic.check_user(user_id)

    if statys == 'default_user':
        if message.text == 'Показать мои группы':
            user_data = logic.read_json('users.json')['google_users'][str(user_id)]

            markup = markups.gen_groups_list(user_data['groups'])
            bot.send_message(user_id,
                             f'> {user_data["name"]}'
                             f'\nВыберите группу для более подробной информации',
                             parse_mode='MarkdownV2',
                             reply_markup=markup)

        elif message.text == 'Расписание':
            user_data = logic.read_json('users.json')['google_users'][str(user_id)]
            markup = markups.gen_groups_list(user_data['groups'], for_='R')
            bot.send_message(user_id,
                             'Выберите группу для которой хотите узнать расписание.',
                             reply_markup=markup)

    elif statys == 'admin':
        if message.text == 'Добавить админа':
            bot.send_message(user_id,
                             'Отправьте Telegram id нового админа')
            bot.register_next_step_handler(message, reg_new_admin)
        elif message.text == 'Рассылка':
            bot.send_message(user_id,
                             'выберите группу для рассылки',
                             reply_markup=markups.gen_mailing_list(logic.get_groups()))

        elif message.text == 'отправить первичный qr':
            users = logic.search_users_for_send_qr()

            for user in users:
                logic.send_ya_mail(user['email'], user['group'], user['url'])
            bot.send_message(message.chat.id, 'QR коды отправлены !')


def reg_new_admin(message):
    user_id = message.text
    data = logic.read_json('users.json')
    data['admins'].append(int(user_id))
    logic.dump_json(data, 'users.json')

    bot.send_message(message.chat.id,
                     'Админ добавлен')


def mailing(message, group):
    if group == 'all':
        chats = logic.read_json('users.json')['default_users']

        for chat in chats:
            bot.copy_message(
                chat,
                message.chat.id,
                message.id
            )
    else:
        data = logic.read_json('users.json')
        users = list(data['google_users'])
        chats = []
        for user in users:
            if group in data['google_users'][user]['groups']:
                chats.append(user)
        for chat in chats:
            bot.copy_message(
                chat,
                message.chat.id,
                message.id
            )


bot.infinity_polling()
