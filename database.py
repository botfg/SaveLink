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
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()

async def save_message(user_id: int, message: str, tag: str = "no_tag", description: str = None):
    async with aiosqlite.connect('messages.db') as db:
        # Проверяем наличие дубликата
        async with db.execute('SELECT id FROM messages WHERE user_id = ? AND message = ?', (user_id, message)) as cursor:
            if await cursor.fetchone() is not None:
                return False

        # Сохраняем сообщение
        await db.execute(
            'INSERT INTO messages (user_id, message, tag, description, timestamp) VALUES (?, ?, ?, ?, ?)',
            (user_id, message, tag, description, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        await db.commit()
        return True

async def get_messages(user_id: int):
    async with aiosqlite.connect('messages.db') as db:
        async with db.execute(
            'SELECT message, tag, description, timestamp FROM messages WHERE user_id = ?',
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()

async def get_tags(user_id: int):
    async with aiosqlite.connect('messages.db') as db:
        async with db.execute(
            'SELECT tag, COUNT(*) as count FROM messages WHERE user_id = ? GROUP BY tag',
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()

async def get_messages_by_tag(user_id: int, tag: str):
    async with aiosqlite.connect('messages.db') as db:
        async with db.execute(
            'SELECT message, description, timestamp FROM messages WHERE user_id = ? AND tag = ? ORDER BY timestamp DESC',
            (user_id, tag)
        ) as cursor:
            return await cursor.fetchall()

async def delete_messages(user_id: int):
    async with aiosqlite.connect('messages.db') as db:
        await db.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))
        await db.commit()
