from dotenv import load_dotenv
from http import HTTPStatus
import os
import requests
import telegram
import logging
import time
from exceptions import APIErrors


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


def check_tokens():
    """Проверяет переменные окружения."""
    vars = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return all(vars)


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
        raise APIErrors(message)
    try:
        if response.status_code != HTTPStatus.OK:
            message = f'status code: {response.status_code},'
            f'error:{response.json}'
            raise Exception(message)
    except Exception:
        raise APIErrors('API ведет себя некорректно')
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
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if not (homework_status and homework_name):
        raise KeyError(
            'В ответе отсутствуют ключи `homework_name` и/или `status`'
        )
    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Неизвестный статус домашней работы'
        raise KeyError(message)
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
