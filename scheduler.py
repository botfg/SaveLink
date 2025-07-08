import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from gdrive_uploader import upload_database_backup

async def perform_auto_backup(bot, user_id: int, is_initial: bool = False):
    """
    Функция, которая будет выполняться по расписанию.
    Выполняет резервное копирование и уведомляет пользователя.
    """
    # Определяем префиксы для логов и сообщений
    log_prefix = "Первичный" if is_initial else "Плановый"
    message_prefix = "первичного" if is_initial else "планового"
    
    logging.info(f"Начинаю {log_prefix.lower()} автоматическое резервное копирование...")
    try:
        # Уведомляем пользователя о начале процесса
        await bot.send_message(user_id, f"⏳ Начинаю процесс {message_prefix} резервного копирования...")
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление о начале бекапа: {e}")

    db_file_path = 'messages.db'
    backup_file_name = f"auto_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.db"

    try:
        # Запускаем синхронную функцию загрузки в отдельном потоке, чтобы не блокировать бота
        file_link = await asyncio.to_thread(upload_database_backup, db_file_path, backup_file_name)

        if file_link:
            await bot.send_message(
                user_id,
                f"✅ Автоматическая резервная копия ({message_prefix}) успешно создана и загружена на Google Drive."
            )
            logging.info(f"{log_prefix} автоматическое резервное копирование успешно завершено.")
        else:
            await bot.send_message(
                user_id,
                f"❌ Произошла ошибка во время автоматического резервного копирования ({message_prefix})."
            )
            logging.warning(f"{log_prefix} автоматическое резервное копирование не удалось на этапе загрузки.")

    except Exception as e:
        logging.error(f"Критическая ошибка в процессе {message_prefix} резервного копирования: {e}")
        await bot.send_message(
            user_id,
            f"❌ Произошла критическая ошибка в процессе автоматического резервного копирования ({message_prefix})."
        )

def setup_scheduler(bot, user_id: int):
    """
    Инициализирует и запускает планировщик для автоматического резервного копирования.
    """
    # Укажите ваш часовой пояс для корректной работы
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow") 
    
    # (ИЗМЕНЕНИЕ 1): Задание для немедленного запуска при старте бота
    scheduler.add_job(
        perform_auto_backup,
        trigger='date', # 'date' запускает задание один раз, сразу после старта
        kwargs={'bot': bot, 'user_id': user_id, 'is_initial': True}
    )
    
    # (ИЗМЕНЕНИЕ 2): Задание для регулярного запуска раз в 2 недели
    scheduler.add_job(
        perform_auto_backup,
        trigger='interval',
        weeks=2,
        kwargs={'bot': bot, 'user_id': user_id, 'is_initial': False}
    )
    scheduler.start()
    logging.info("Планировщик запущен. Первый бекап будет создан немедленно, последующие - каждые 2 недели.")
