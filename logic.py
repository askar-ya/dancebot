import time

import cv2
import json
import os
import datetime
import requests
import qrcode
import smtplib

from playwright.sync_api import sync_playwright
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import keys

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

SPREADSHEET_VISITS = '1F0SxrzDSW8LKEY2y3nERMQy025oeUakZc6JR5T4KIY8'
SPREADSHEET_USERS = '1kIZDqsifLJc01D4uaeruAS6zWmsk0oLpDuZS4u4ggZg'
SPREADSHEET_SCHEDULE = '17RQRKkP2OrX78ou4XUSFpZGApQCZdumy8nsFI5BRzF8'


def connection_google():
    """Подключение к google sheets"""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if creds.valid is False:
            os.remove('token.json')

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build('sheets', 'v4', credentials=creds)
    sheets = service.spreadsheets()
    return sheets


def rise_exp(error):
    print(error)
    with open('users.json', 'r', encoding='utf-8') as file:
        admins = json.load(file)['admins']
    for admin in admins:
        requests.get(f'https://api.telegram.org/bot{keys.TELEGRAM_TOKEN}'
                     f'/sendMessage?chat_id={admin}&text={error}')


def sheets_check_user(user_id) -> str:
    """Отмечает посещения"""
    #  Подключение к google sheets
    try:
        sheets = connection_google()
    except Exception as e:
        print(e)
        rise_exp('ошибка подключения к google sheets')
        return 'error'
    #  Колонка с id
    data = sheets.values().get(spreadsheetId=SPREADSHEET_USERS,
                               range='Клиенты!A:P').execute()['values']
    user_name = ''
    group = ''
    for row in data:
        if row[-1] == user_id:
            user_name = row[0]
            group = row[6]

    if user_name != '':
        if group == '':
            rise_exp('У клиента не указана группа')
            return 'error'
    else:
        rise_exp('Клиент не найден')
        return 'error'

    sheet = sheets.values().get(spreadsheetId=SPREADSHEET_VISITS,
                                range=f'{group}!1:300').execute()['values']

    n = ''
    for i, user in enumerate(sheet[1]):
        if user == user_name:
            n = i
    if n == '':
        rise_exp('У клиента ошибка в имени в листе посещения')
        return 'error'

    now = str(datetime.datetime.now())[:10].split('-')
    now = '{}.{}.{}'.format(now[2], now[1], now[0])

    row = len(sheet)
    print(row)
    if sheet[-1][0] == now:
        sheets.values().update(spreadsheetId=SPREADSHEET_VISITS,
                               range='{}!{}{}'.format(group, keys.abc[n], row),
                               valueInputOption='USER_ENTERED',
                               body={'values': [['Да']]}).execute()
    else:
        values = []
        for i in range(n+1):
            if i == 0:
                values.append(f'{now}')
            elif i == n:
                values.append('Да')
            else:
                values.append(None)

        sheets.values().update(spreadsheetId=SPREADSHEET_VISITS,
                               range='{}!{}{}'.format(group, 'A', row + 1),
                               valueInputOption='USER_ENTERED',
                               body={'values': [values]}).execute()
    return user_name


def sheets_get_user(qr_id) -> dict | str:
    """Возвращает словарь пользователя с именем, группами, индификатороми групп"""

    #  подключение к google sheets
    try:
        sheets = connection_google()
    except Exception as e:
        print(e)
        rise_exp('ошибка подключения к google sheets')
        return 'error'
    page = 'Клиенты'

    data = sheets.values().get(spreadsheetId=SPREADSHEET_USERS,
                               range='{}!A:P'.format(page)).execute()['values']

    user_data = {'name': '', 'groups': [], 'ids': [qr_id]}

    for row in data:
        if user_data['name'] == '' and row[-1] == qr_id:
            user_data['name'] = row[0]
            user_data['groups'].append(row[6])
        elif row[0] == user_data['name']:
            user_data['groups'].append(row[6])
            user_data['ids'].append(row[-1])

    if user_data['name'] != '':
        if len(user_data['groups']) == len(user_data['ids']):
            return user_data
        elif len(user_data['groups']) < len(user_data['ids']):
            rise_exp('у клиента в одной из строк в таблице "Клиенты", не указана группа')
            return 'error'
        else:
            rise_exp('у клиента в одной из строк в таблице "Клиенты", не указан id')
            return 'error'
    else:
        rise_exp('Не найдено клиента в таблице')
        return 'error'


def view_schedule(group: str) -> list:
    """Возвращает словарь с расписанием группы"""

    #  подключение к google sheets
    try:
        sheets = connection_google()
    except Exception as e:
        print(e)
        rise_exp('ошибка подключения к google sheets')
        return ['error']

    #  получаем расписание группы
    rows = sheets.values().get(spreadsheetId=SPREADSHEET_SCHEDULE,
                               range=f'{group}!A1:D10').execute().get('values')

    #  создаем словарь расписания
    schedule = []
    for row in rows[1:]:
        schedule.append({
            'tag': row[0],
            'day': row[1],
            'time': row[2],
            'teacher': row[3]
        })

    #  возвращаем словарь
    return schedule


def get_user_group_info(user_name: str, group: str) -> dict:
    """Возвращает словарь с данными клиента в конкретной группе"""

    #  Подключение к google sheets
    try:
        sheets = connection_google()
    except Exception as e:
        print(e)
        rise_exp('ошибка подключения к google sheets')
        return {'error': 1}

    #  Получаем всех пользователей группы
    data = sheets.values().get(spreadsheetId=SPREADSHEET_VISITS,
                               range='{}!1:300'.format(group)).execute().get('values')

    colum = ''
    for n, user in enumerate(data[1]):
        if user == user_name:
            colum = n
    #  Находим кол-во посещений
    info = {'visits_count': 0, 'vouchers': []}
    for row in data:
        if len(row) > colum:
            if row[colum] == 'Да':
                info['visits_count'] += 1

    data = sheets.values().get(spreadsheetId=SPREADSHEET_USERS, range='Оплаты!B:L').execute().get('values')
    for row in data:
        if row[1] == user_name:
            if len(row) > 9:
                if group == row[2]:
                    remaining_visit = row[9]
                    if remaining_visit != 0:
                        info['vouchers'].append({
                            'date_start': row[0],
                            'date_end': row[10],
                            'group': group,
                            'remaining_visits': remaining_visit
                        })
                else:
                    info['vouchers'].append({
                        'remaining_visits': row[9],
                        'group': group
                    })

    return info


def read_qr(file_id, user_id) -> str:
    """Функция читает qr и возвращает id"""
    file_path = requests.get(f'https://api.telegram.org/bot{keys.TELEGRAM_TOKEN}/getFile?file_id={file_id}')
    file_path = file_path.json()['result']['file_path']
    file = requests.get(f'https://api.telegram.org/file/bot{keys.TELEGRAM_TOKEN}/{file_path}').content

    save_path = '{}.jpg'.format(user_id)
    with open(save_path, 'wb') as new_file:
        new_file.write(file)
    img = cv2.imread(save_path)
    detector = cv2.QRCodeDetector()
    data, bbox, rectified = detector.detectAndDecode(img)
    os.remove(save_path)
    return data


def search_users_for_send_qr():
    """Находит клиентов для отправки qr"""

    #  Подключаем google sheets
    sheets = connection_google()
    #  Получаем колонку с чек боксами для отправки
    boxs = sheets.values().get(spreadsheetId=SPREADSHEET_USERS,
                               range='Клиенты!N:N').execute().get('values')
    #  Колонка с адресами
    emails = sheets.values().get(spreadsheetId=SPREADSHEET_USERS,
                                 range='Клиенты!M:M').execute()['values']
    #  Колонка с url qr кода
    urls = sheets.values().get(spreadsheetId=SPREADSHEET_USERS,
                               range='Клиенты!Q:Q').execute()['values']
    #  Колонка с группами
    groups = sheets.values().get(spreadsheetId=SPREADSHEET_USERS,
                                 range='Клиенты!G:G').execute()['values']
    users_for_mailing = []

    #  Находим людей кому надо отправить qr
    for n, checker in enumerate(boxs):
        if checker[0] == 'TRUE':
            email = emails[n]
            if len(email) != 0:
                email = email[0]
            else:
                email = 'wallestmer@gmail.com'
            url = urls[n]
            if len(email) != 0:
                url = url[0]
            else:
                url = 'https://i.postimg.cc/HswLXfJm/123.png'
            group = groups[n]
            if len(group) != 0:
                group = group[0]
            else:
                group = '---'
            users_for_mailing.append(
                {
                    'email': emails[n][0],
                    'url': url,
                    'group': group
                }
            )
            sheets.values().update(spreadsheetId=SPREADSHEET_USERS,
                                   range=f'Клиенты!N{n + 1}',
                                   valueInputOption='USER_ENTERED',
                                   body={'values': [['FALSE']]}).execute()
            sheets.values().update(spreadsheetId=SPREADSHEET_USERS,
                                   range=f'Клиенты!O{n + 1}',
                                   valueInputOption='USER_ENTERED',
                                   body={'values': [['Отправлен']]}).execute()
    return users_for_mailing


def send_ya_mail(email: str, group: str, qr_url: str):
    login = 'info@yarsmart.ru'
    password = 'Yarsmart1'

    msg = MIMEMultipart('alternative')
    msg['Subject'] = group
    msg['From'] = login
    msg['To'] = email
    text = "Hi!"
    print(qr_url)
    html = open('email-template.html', 'r').read().replace('group_name', group).replace('qr_url_link', qr_url)
    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')
    msg.attach(part1)
    msg.attach(part2)

    s = smtplib.SMTP('smtp.yandex.ru', 587, timeout=10)

    try:
        s.starttls()
        s.login(login, password)
        s.sendmail(msg['From'], email, msg.as_string())
    except Exception as ex:
        print(ex)
    finally:
        s.quit()


def check_user(user_id: str) -> str:
    data = read_json('users.json')

    if user_id in data['admins']:
        return 'admin'
    elif user_id in data['default_users']:
        return 'default_user'
    else:
        append_user(user_id, 'default_users')
        return 'new'


def append_user(user_id: str, permission: str) -> None:
    data = read_json('users.json')

    data[permission].append(user_id)

    dump_json(data, 'users.json')


def link_google_tg(user_id: str, user_data) -> None:
    data = read_json('users.json')

    data['google_users'][str(user_id)] = user_data

    dump_json(data, 'users.json')


def read_json(path):
    with open(path, 'rb') as file:
        return json.load(file)


def dump_json(data, path):
    with open(path, 'w') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_groups():
    data = read_json('users.json')
    users = list(data['google_users'])
    groups = []
    for user in users:
        user_groups = data['google_users'][user]['groups']
        for group in user_groups:
            if group not in groups:
                groups.append(group)

    return groups


def gen_qr_code(group_id, user_id) -> str:
    img = qrcode.make(group_id)
    img.save(f"{user_id}.png")

    return f"{user_id}.png"


def dell_qr_pic(path: str) -> None:
    os.remove(path)
