import aiosqlite
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def init_db():
    """Инициализирует базу данных и создает таблицы, если они не существуют."""
    try:
        async with aiosqlite.connect('messages.db') as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    description TEXT,
                    tag TEXT DEFAULT 'no_tag',
                    timestamp TEXT NOT NULL,
                    UNIQUE(user_id, message, tag)
                )
            ''')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_messages_tag ON messages(tag)')
            await db.commit()
            logging.info("Database initialized successfully.")
    except aiosqlite.Error as e:
        logging.error(f"Database initialization failed: {e}")
        raise

async def validate_text(text: str) -> tuple[bool, str]:
    """Валидация текста сообщения."""
    if not text or len(text) < 1:
        return False, "Текст не может быть пустым!"
    if len(text) > 4096:
        return False, "Текст не должен превышать 4096 символов!"
    return True, ""

async def validate_description(description: str) -> tuple[bool, str]:
    """Валидация описания."""
    if description and len(description) > 1000:
        return False, "Описание не должно превышать 1000 символов!"
    return True, ""

async def validate_tag(tag: str) -> tuple[bool, str]:
    """Валидация тега."""
    if not tag or len(tag.strip()) == 0:
        return False, "Тег не может быть пустым!"
    if len(tag) > 100:
        return False, "Тег не должен превышать 100 символов!"
    return True, ""

async def save_message(user_id: int, message: str, tag: str = "no_tag", description: str = None, timestamp: str = None):
    """Сохраняет новое сообщение в базу данных."""
    try:
        async with aiosqlite.connect('messages.db') as db:
            ts = timestamp or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            await db.execute(
                'INSERT INTO messages (user_id, message, tag, description, timestamp) VALUES (?, ?, ?, ?, ?)',
                (user_id, message, tag.strip(), description, ts)
            )
            await db.commit()
            return True
    except aiosqlite.IntegrityError:
        logging.warning(f"Attempt to save a duplicate message for user {user_id}.")
        return False
    except aiosqlite.Error as e:
        logging.error(f"Failed to save message for user {user_id}: {e}")
        return False

async def get_messages(user_id: int):
    """Получает все сообщения пользователя."""
    try:
        async with aiosqlite.connect('messages.db') as db:
            async with db.execute('SELECT id, message, tag, description, timestamp FROM messages WHERE user_id = ? ORDER BY timestamp DESC', (user_id,)) as cursor:
                return await cursor.fetchall()
    except aiosqlite.Error as e:
        logging.error(f"Failed to get messages for user {user_id}: {e}")
        return []

async def get_tags(user_id: int):
    """Получает все уникальные теги пользователя и количество записей для каждого."""
    try:
        async with aiosqlite.connect('messages.db') as db:
            async with db.execute('SELECT tag, COUNT(*) as count FROM messages WHERE user_id = ? GROUP BY tag ORDER BY tag', (user_id,)) as cursor:
                return await cursor.fetchall()
    except aiosqlite.Error as e:
        logging.error(f"Failed to get tags for user {user_id}: {e}")
        return []

async def get_messages_by_tag(user_id: int, tag: str):
    """Получает все сообщения пользователя по определенному тегу."""
    try:
        async with aiosqlite.connect('messages.db') as db:
            cursor = await db.execute("SELECT id, message, description, timestamp FROM messages WHERE user_id = ? AND tag = ? ORDER BY timestamp DESC", (user_id, tag))
            return await cursor.fetchall()
    except aiosqlite.Error as e:
        logging.error(f"Failed to get messages by tag '{tag}' for user {user_id}: {e}")
        return []

async def delete_messages(user_id: int):
    """Удаляет все сообщения пользователя."""
    try:
        async with aiosqlite.connect('messages.db') as db:
            await db.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))
            await db.commit()
            logging.info(f"All messages deleted for user {user_id}.")
            return True
    except aiosqlite.Error as e:
        logging.error(f"Failed to delete all messages for user {user_id}: {e}")
        return False

async def delete_message_by_id(user_id: int, message_id: int):
    """Удаляет одно сообщение по его ID."""
    try:
        async with aiosqlite.connect('messages.db') as db:
            await db.execute('DELETE FROM messages WHERE user_id = ? AND id = ?', (user_id, message_id))
            await db.commit()
            return True
    except aiosqlite.Error as e:
        logging.error(f"Failed to delete message by id {message_id} for user {user_id}: {e}")
        return False