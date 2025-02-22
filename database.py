import aiosqlite
from datetime import datetime

async def init_db():
    async with aiosqlite.connect('messages.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                description TEXT,
                tag TEXT DEFAULT 'no_tag',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, message, tag)
            )
        ''')
        await db.commit()

async def validate_text(text: str) -> tuple[bool, str]:
    """Валидация текста сообщения"""
    if len(text) < 1:
        return False, "Текст слишком короткий!"
    if len(text) > 4096:
        return False, "Текст не должен превышать 4096 символов!"
    return True, ""

async def validate_description(description: str) -> tuple[bool, str]:
    """Валидация описания"""
    if description and len(description) > 1000:
        return False, "Описание не должно превышать 1000 символов!"
    return True, ""

async def validate_tag(tag: str) -> tuple[bool, str]:
    """Валидация тега"""
    if len(tag) > 100:
        return False, "Тег не должен превышать 100 символов!"
    return True, ""
async def save_message(user_id: int, message: str, tag: str = "no_tag", description: str = None):
    try:
        async with aiosqlite.connect('messages.db') as db:
            await db.execute(
                'INSERT INTO messages (user_id, message, tag, description, timestamp) VALUES (?, ?, ?, ?, ?)',
                (user_id, message, tag, description, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            await db.commit()
            return True
    except aiosqlite.IntegrityError:
        # Обработка дубликата записи
        return False
    except Exception:
        # Обработка других ошибок базы данных
        return False

async def get_messages(user_id: int):
    try:
        async with aiosqlite.connect('messages.db') as db:
            async with db.execute(
                'SELECT id, message, tag, description, timestamp FROM messages WHERE user_id = ?',
                (user_id,)
            ) as cursor:
                return await cursor.fetchall()
    except Exception:
        return []


async def get_tags(user_id: int):
    try:
        async with aiosqlite.connect('messages.db') as db:
            async with db.execute(
                'SELECT tag, COUNT(*) as count FROM messages WHERE user_id = ? GROUP BY tag',
                (user_id,)
            ) as cursor:
                return await cursor.fetchall()
    except Exception:
        return []

async def get_messages_by_tag(user_id: int, tag: str):
    try:
        async with aiosqlite.connect('messages.db') as db:
            async with db.execute(
                'SELECT message, description, timestamp FROM messages WHERE user_id = ? AND tag = ? ORDER BY timestamp DESC',
                (user_id, tag)
            ) as cursor:
                return await cursor.fetchall()
    except Exception:
        return []

async def delete_messages(user_id: int):
    try:
        async with aiosqlite.connect('messages.db') as db:
            await db.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))
            await db.commit()
            return True
    except Exception:
        return False


async def delete_message_by_id(user_id: int, message_id: int):
    try:
        async with aiosqlite.connect('messages.db') as db:
            await db.execute(
                'DELETE FROM messages WHERE user_id = ? AND id = ?',
                (user_id, message_id)
            )
            await db.commit()
            return True
    except Exception:
        return False