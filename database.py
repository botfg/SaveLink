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
                timestamp TEXT NOT NULL,
                UNIQUE(user_id, message, tag)
            )
        ''')
        await db.execute('CREATE INDEX idx_messages_user_id ON messages(user_id)')
        await db.execute('CREATE INDEX idx_messages_tag ON messages(tag)')
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

async def save_message(user_id: int, message: str, tag: str = "no_tag", description: str = None, timestamp: str = None):
    try:
        async with aiosqlite.connect('messages.db') as db:
            await db.execute(
                'INSERT INTO messages (user_id, message, tag, description, timestamp) VALUES (?, ?, ?, ?, ?)',
                (user_id, message, tag, description, timestamp or datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
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
            cursor = await db.execute(
                "SELECT id, message, description, timestamp FROM messages WHERE user_id = ? AND tag = ? ORDER BY timestamp DESC",
                (user_id, tag)
            )
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



async def get_all_records(user_id: int):
    async with aiosqlite.connect('messages.db') as db:
        cursor = await db.execute(
            "SELECT message, tag, description, timestamp FROM messages WHERE user_id = ? ORDER BY timestamp DESC",
            (user_id,)
        )
        return await cursor.fetchall()

async def import_records(user_id: int, records: list):
    async with aiosqlite.connect('messages.db') as db:
        for record in records:
            await db.execute(
                "INSERT OR IGNORE INTO messages (user_id, message, tag, description, timestamp) VALUES (?, ?, ?, ?, ?)",
                (user_id, record['message'], record['tag'], record['description'], record['timestamp'])
            )
        await db.commit()