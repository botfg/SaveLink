import asyncio
import logging
import os
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from gdrive_uploader import upload_database_backup
from config_reader import config # Импортируем конфиг для доступа к DSN

async def perform_auto_backup(bot, user_id: int, is_initial: bool = False):
    """
    Функция, которая будет выполняться по расписанию.
    Создает дамп PostgreSQL и загружает его на Google Drive.
    """
    log_prefix = "Первичный" if is_initial else "Плановый"
    message_prefix = "первичного" if is_initial else "планового"
    
    logging.info(f"Начинаю {log_prefix.lower()} автоматическое резервное копирование...")
    try:
        await bot.send_message(user_id, f"⏳ Начинаю процесс {message_prefix} резервного копирования...")
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление о начале бекапа: {e}")

    # Имя для временного файла бекапа
    backup_file_path = f"auto_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.sql"

    try:
        # Формируем команду для pg_dump, используя DSN из конфига
        dump_command = [
            'pg_dump',
            '--dbname', config.db_dsn,
            '--file', backup_file_path,
            '--format', 'plain',
            '--clean' # Добавляет команды DROP TABLE для чистого восстановления
        ]

        # Выполняем команду pg_dump
        process = await asyncio.create_subprocess_exec(
            *dump_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_message = stderr.decode().strip()
            logging.error(f"pg_dump завершился с ошибкой: {error_message}")
            await bot.send_message(user_id, f"❌ Ошибка при создании дампа базы данных: {error_message}")
            return

        # Загружаем созданный дамп на Google Drive
        file_link = await asyncio.to_thread(upload_database_backup, backup_file_path, os.path.basename(backup_file_path))

        if file_link:
            await bot.send_message(
                user_id,
                f"✅ Автоматическая резервная копия ({message_prefix}) успешно создана и загружена на Google Drive."
            )
            logging.info(f"{log_prefix} автоматическое резервное копирование успешно завершено.")
        else:
            await bot.send_message(
                user_id,
                f"❌ Произошла ошибка во время загрузки резервной копии ({message_prefix}) на Google Drive."
            )
            logging.warning(f"{log_prefix} автоматическое резервное копирование не удалось на этапе загрузки.")

    except FileNotFoundError:
        logging.error("Команда 'pg_dump' не найдена. Убедитесь, что postgresql-client установлен.")
        await bot.send_message(user_id, "❌ Ошибка: команда `pg_dump` не найдена. Установите `postgresql-client`.")
    except Exception as e:
        logging.error(f"Критическая ошибка в процессе {message_prefix} резервного копирования: {e}")
        await bot.send_message(
            user_id,
            f"❌ Произошла критическая ошибка в процессе автоматического резервного копирования ({message_prefix})."
        )
    finally:
        # Обязательно удаляем временный файл дампа после всех операций
        if os.path.exists(backup_file_path):
            os.remove(backup_file_path)

def setup_scheduler(bot, user_id: int):
    """
    Инициализирует и запускает планировщик для автоматического резервного копирования.
    """
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow") 
    
    scheduler.add_job(
        perform_auto_backup,
        trigger='date',
        kwargs={'bot': bot, 'user_id': user_id, 'is_initial': True}
    )
    
    scheduler.add_job(
        perform_auto_backup,
        trigger='interval',
        weeks=2,
        kwargs={'bot': bot, 'user_id': user_id, 'is_initial': False}
    )
    scheduler.start()
    logging.info("Планировщик запущен. Первый бекап будет создан немедленно, последующие - каждые 2 недели.")