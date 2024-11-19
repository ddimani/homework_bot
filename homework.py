import logging
import os
import time

from dotenv import load_dotenv
import requests
from telebot import TeleBot

from exceptions import ApiError, TokenError
load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка наличия токенов в переменных окружения."""
    is_all_tokens_setted = True
    token_check = (
        ('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
        ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
        ('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID),

    )
    for key, token in token_check:
        if not token:
            logging.critical(f'Отсутствует обязательная переменная'
                             f'окружения {key}')
            is_all_tokens_setted = False
        return is_all_tokens_setted


def send_message(bot, message):
    """Отправка сообщения в телеграм."""
    try:
        logging.info(f'Отправка сообщения в Telegram: {message}')
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logging.debug(f'Сообщение успешно отправлено в Telegram: {message}')
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Запрос к API Яндекс.Практикум."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        logging.error(f'Ошибка при запросе к API Яндекс.Практикум: {error}')
        raise ApiError(
            f'Ошибка при запросе к API Яндекс.Практикум: {error}'
        )
    if response.status_code != 200:
        raise ApiError(
            f'Ошибка при запросе к API: статус код {response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        msg = 'Ожидается словарь response, но получен другой тип'
        logging.error(msg)
        raise TypeError(msg)
    if 'homeworks' not in response:
        msg = 'В ответе API отсутствует ключ "homeworks"'
        logging.error(msg)
        raise KeyError(msg)
    homework = response['homeworks']
    if not isinstance(homework, list):
        msg = f'Ожидается список homeworks, но получен {homework}'
        logging.error(msg)
        raise TypeError(msg)
    return homework


def parse_status(homework):
    """Обработка статуса домашней работы."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        msg = 'В ответе API отсутствует ключ "homework_name"'
        logging.error(msg)
        raise KeyError(msg)
    status = homework.get('status')
    if status is None:
        msg = 'В ответе API отсутствует ключ "status"'
        logging.error(msg)
        raise KeyError(msg)
    verdict = HOMEWORK_VERDICTS.get(status)
    if verdict is None:
        msg = f'Неизвестный статус домашней работы: {status}'
        logging.error(msg)
        raise ValueError(msg)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise TokenError("Отсутствует обязательная переменная окружения")
    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    logging.info('Бот запущен')
    send_message(bot, 'Бот запущен')
    logging.debug('Сообщение успешно отправлено в Telegram: Бот запущен')
    timestamp = int(time.time())
    old_status = ''
    """Основной цикл программы"""
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date', timestamp)
            homeworks = check_response(response)
            if homeworks:
                new_status = parse_status(homeworks[0])
            else:
                new_status = 'Статус не обновился'
            if new_status != old_status:
                send_message(bot, new_status)
                old_status = new_status
            else:
                logging.debug('Отсутствие в ответе новых статусов')
        except Exception as error:
            new_status = f'Сбой в работе программы: {error}.'
            logging.error(new_status)
            if new_status != old_status:
                send_message(bot, new_status)
                old_status = new_status
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':

    logging.basicConfig(
        handlers=[logging.FileHandler('homework.log', 'w', 'utf-8')],
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
    )
    main()
