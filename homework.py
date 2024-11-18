import logging
import os
import time

from dotenv import load_dotenv
import requests
from telebot import TeleBot

from exceptions import ExceptionError, TokenError
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
    token_check = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,

    }
    for key, token in token_check.items():
        if not token:
            logging.critical(f'Отсутствует обязательная переменная'
                             f'окружения {key}')
            raise TokenError(f'Отсутствует обязательная переменная'
                             f'окружения {key}')


def send_message(bot, message):
    """Отправка сообщения в телеграм."""
    try:
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
        if response.status_code != 200:
            raise ExceptionError(
                f'Ошибка при запросе к API: статус код {response.status_code}'
            )
        response.raise_for_status()
    except requests.ExceptionError as error:
        logging.error(f'Ошибка при запросе к API Яндекс.Практикум: {error}')
        raise ExceptionError(
            f'Ошибка при запросе к API Яндекс.Практикум: {error}'
        )
    return response.json()


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Ожидается словарь response, но получен другой тип')

    try:
        if 'homeworks' not in response:
            raise KeyError('В ответе API отсутствует ключ "homeworks"')
    except KeyError as error:
        logging.error(f'Ошибка при обработке ответа API: {error}')
        raise KeyError(
            f'Ошибка при обработке ответа API: {error}'
        )
    if not isinstance(response['homeworks'], list):
        raise TypeError(f'Ожидается список homeworks,'
                        f' но получен {response["homeworks"]}')
    return response['homeworks']


def parse_status(homework):
    """Обработка статуса домашней работы."""
    homework_name = homework.get('homework_name')
    try:
        if homework_name is None:

            raise KeyError('В ответе API отсутствует ключ "homework_name"')

        status = homework.get('status')
        if status is None:
            raise KeyError('В ответе API отсутствует ключ "status"')

        verdict = HOMEWORK_VERDICTS.get(status)
        if verdict is None:
            raise ValueError(f'Неизвестный статус домашней работы: {status}')
    except (KeyError, ValueError) as error:
        logging.error(f'Ошибка при обработке статуса домашней работы: {error}')
        raise ExceptionError(
            f'Ошибка при обработке статуса домашней работы: {error}'
        )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    logging.info('Бот запущен')
    send_message(bot, 'Бот запущен')
    logging.debug('Сообщение успешно отправлено в Telegram: Бот запущен')
    timestamp = 0
    old_status = ''
    """Основной цикл программы"""
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date', timestamp)
            homeworks = check_response(response)
            logging.debug('Изменений статуса не найденно')
            if homeworks:
                new_status = parse_status(homeworks[0])
            else:
                new_status = 'Статус не обновился'
            if new_status != old_status:
                send_message(bot, new_status)
                old_status = new_status
            else:
                logging.error('Отсутствие в ответе новых статусов')
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
