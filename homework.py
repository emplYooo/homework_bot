from dotenv import load_dotenv
from http import HTTPStatus
import os
import requests
import telegram
import logging
import time


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


logging.basicConfig(
    handlers=[logging.StreamHandler()],
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(message)s'
)
logger = logging.getLogger(__name__)


error_sent_messages = []


class APIErrosrs(Exception):
    """Ошибка при работе API."""

    pass


def check_tokens():
    """Проверяет переменные окружения."""
    vars = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return None not in vars


def send_message(bot, message):
    """Отправляет сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Отправлено сообщение: "{message}"')
    except Exception as error:
        logging.error(f'Cбой отправки сообщения, ошибка: {error}')


def get_api_answer(current_timestamp):
    """Отправляет запрос к API домашки на  ENDPOINT."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception:
        message = 'API ведет себя незапланированно'
        raise APIErrosrs(message)
    try:
        if response.status_code != HTTPStatus.OK:
            message = 'От эндотипа нет ответа'
            raise Exception(message)
    except Exception:
        message = 'API ведет себя некорректно'
        raise APIErrosrs(message)
    return response.json()


def check_response(response):
    """Проверяет полученный ответ на корректность."""
    if not isinstance(response, dict):
        message = 'Ответ API не словарь'
        raise TypeError(message)
    if 'homeworks' not in response:
        message = 'В ответе API нет домашней работы'
        raise IndexError(message)
    if 'homeworks' in response and not isinstance(response['homeworks'], list):
        message = 'Ответ под ключом "homeworks" не список'
        raise TypeError(message)
    homework = response.get('homeworks')[0]
    return homework


def parse_status(homework):
    """Формирует сообщение с обновленным статусом для отправки."""
    keys = ['status', 'homework_name']
    for key in keys:
        if key not in homework:
            message = f'Ключа {key} нет в ответе API'
            raise KeyError(message)
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Неизвестный статус домашней работы'
        raise KeyError(message)
    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def log_and_inform(bot, message):
    """Логирует ошибки уровня ERROR.
    Однократно отправляет информацию об ошибках в телеграм,
    если отправка возможна.
    """
    logger.error(message)
    if message not in error_sent_messages:
        try:
            send_message(bot, message)
            error_sent_messages.append(message)
        except Exception as error:
            logger.info('Не удалось отправить сообщение об ошибке, '
                        f'{error}')


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    check_result = check_tokens()
    if check_result is False:
        message = 'Проблемы с переменными окружения'
        logger.critical(message)
        raise SystemExit(message)

    while True:
        try:
            response = get_api_answer(current_timestamp)
            if 'current_date' in response:
                current_timestamp = response['current_date']
            homework = check_response(response)
            if homework is not None:
                message = parse_status(homework)
                if message is not None:
                    send_message(bot, message)
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            log_and_inform(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
