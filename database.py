import asyncpg
import logging
from datetime import datetime
from config_reader import config

# Глобальная переменная для хранения пула соединений
pool = None

async def init_db():
    """Инициализирует пул соединений с PostgreSQL и создает таблицы."""
    global pool
    if pool:
        return
        
    try:
        pool = await asyncpg.create_pool(dsn=config.db_dsn)
        async with pool.acquire() as connection:
            await connection.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    message TEXT NOT NULL,
                    name TEXT,
                    tag TEXT DEFAULT 'no_tag',
                    timestamp TIMESTAMPTZ NOT NULL,
                    UNIQUE(user_id, message, tag)
                )
            ''')
        logging.info("Пул соединений с PostgreSQL успешно создан и таблица проверена.")
    except Exception as e:
        logging.error(f"Не удалось инициализировать пул соединений с базой данных: {e}")
        raise

async def validate_text(text: str) -> tuple[bool, str]:
    if not text or len(text) < 1:
        return False, "Текст не может быть пустым!"
    if len(text) > 4096:
        return False, "Текст не должен превышать 4096 символов!"
    return True, ""

async def validate_name(name: str) -> tuple[bool, str]:
    if name and len(name) > 1000:
        return False, "Название не должно превышать 1000 символов!"
    return True, ""

async def validate_tag(tag: str) -> tuple[bool, str]:
    if not tag or len(tag.strip()) == 0:
        return False, "Тег не может быть пустым!"
    if len(tag) > 100:
        return False, "Тег не должен превышать 100 символов!"
    return True, ""

async def save_message(user_id: int, message: str, tag: str = "no_tag", name: str = None, timestamp: datetime = None):
    ts = timestamp or datetime.now()
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                'INSERT INTO messages (user_id, message, tag, name, timestamp) VALUES ($1, $2, $3, $4, $5)',
                user_id, message, tag.strip(), name, ts
            )
        return True
    except asyncpg.UniqueViolationError:
        logging.warning(f"Попытка сохранить дублирующуюся запись для пользователя {user_id}.")
        return False
    except Exception as e:
        logging.error(f"Не удалось сохранить сообщение для пользователя {user_id}: {e}")
        return False

async def get_messages(user_id: int):
    try:
        async with pool.acquire() as connection:
            rows = await connection.fetch('SELECT id, message, tag, name, timestamp FROM messages WHERE user_id = $1 ORDER BY timestamp DESC', user_id)
            return rows
    except Exception as e:
        logging.error(f"Не удалось получить сообщения для пользователя {user_id}: {e}")
        return []

async def get_message_by_id(user_id: int, message_id: int):
    try:
        async with pool.acquire() as connection:
            row = await connection.fetchrow('SELECT id, message, tag, name, timestamp FROM messages WHERE id = $1 AND user_id = $2', message_id, user_id)
            return row
    except Exception as e:
        logging.error(f"Не удалось получить сообщение по id {message_id} для пользователя {user_id}: {e}")
        return None

async def get_tags(user_id: int):
    try:
        async with pool.acquire() as connection:
            rows = await connection.fetch('SELECT tag, COUNT(*) as count FROM messages WHERE user_id = $1 GROUP BY tag ORDER BY tag', user_id)
            return rows
    except Exception as e:
        logging.error(f"Не удалось получить теги для пользователя {user_id}: {e}")
        return []

async def get_messages_by_tag(user_id: int, tag: str):
    try:
        async with pool.acquire() as connection:
            rows = await connection.fetch("SELECT id, message, name, timestamp FROM messages WHERE user_id = $1 AND tag = $2 ORDER BY timestamp DESC", user_id, tag)
            return rows
    except Exception as e:
        logging.error(f"Не удалось получить сообщения по тегу '{tag}' для пользователя {user_id}: {e}")
        return []

async def delete_messages(user_id: int):
    try:
        async with pool.acquire() as connection:
            await connection.execute('DELETE FROM messages WHERE user_id = $1', user_id)
        logging.info(f"Все сообщения удалены для пользователя {user_id}.")
        return True
    except Exception as e:
        logging.error(f"Не удалось удалить все сообщения для пользователя {user_id}: {e}")
        return False

async def delete_message_by_id(user_id: int, message_id: int):
    try:
        async with pool.acquire() as connection:
            await connection.execute('DELETE FROM messages WHERE user_id = $1 AND id = $2', user_id, message_id)
        return True
    except Exception as e:
        logging.error(f"Не удалось удалить сообщение по id {message_id} для пользователя {user_id}: {e}")
        return False

async def update_record_field(record_id: int, field: str, value: str):
    allowed_fields = ["name", "message", "tag"]
    if field not in allowed_fields:
        logging.error(f"Попытка обновить неразрешенное поле: {field}")
        return False
    try:
        async with pool.acquire() as connection:
            query = f"UPDATE messages SET {field} = $1 WHERE id = $2"
            await connection.execute(query, value, record_id)
        logging.info(f"Поле '{field}' записи {record_id} было обновлено.")
        return True
    except Exception as e:
        logging.error(f"Не удалось обновить запись {record_id}: {e}")
        return False

# (ИЗМЕНЕНИЕ): Новая функция для получения статистики
async def get_stats(user_id: int):
    """
    Собирает статистику по записям пользователя.
    Возвращает словарь со статистикой или None в случае ошибки.
    """
    try:
        async with pool.acquire() as connection:
            # Общее количество записей
            total_records_result = await connection.fetchval(
                'SELECT COUNT(*) FROM messages WHERE user_id = $1',
                user_id
            )

            # Количество уникальных тегов (исключая 'no_tag')
            total_tags_result = await connection.fetchval(
                "SELECT COUNT(DISTINCT tag) FROM messages WHERE user_id = $1 AND tag != 'no_tag'",
                user_id
            )

            # Самый популярный тег
            most_popular_tag_result = await connection.fetchrow(
                "SELECT tag, COUNT(*) as count FROM messages WHERE user_id = $1 AND tag != 'no_tag' "
                "GROUP BY tag ORDER BY count DESC, tag ASC LIMIT 1",
                user_id
            )

            return {
                "total_records": total_records_result or 0,
                "total_tags": total_tags_result or 0,
                "popular_tag_info": most_popular_tag_result # Может быть None
            }
    except Exception as e:
        logging.error(f"Не удалось получить статистику для пользователя {user_id}: {e}")
        return None