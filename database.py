import aiosqlite

async def init_db():
    async with aiosqlite.connect('messages.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                tag TEXT DEFAULT 'no_tag',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()

async def save_message(user_id: int, message: str, tag: str):
    async with aiosqlite.connect('messages.db') as db:
        # Проверяем, существует ли уже такое сообщение у пользователя
        async with db.execute(
            'SELECT COUNT(*) FROM messages WHERE user_id = ? AND message = ?',
            (user_id, message)
        ) as cursor:
            count = (await cursor.fetchone())[0]
            
        if count > 0:
            return False  # Найден дубликат

        # Сохраняем сообщение, если дубликат не найден
        await db.execute(
            'INSERT INTO messages (user_id, message, tag) VALUES (?, ?, ?)',
            (user_id, message, tag)
        )
        await db.commit()
        return True


async def get_user_messages(user_id: int):
    async with aiosqlite.connect('messages.db') as db:
        async with db.execute(
            'SELECT message, tag, timestamp FROM messages WHERE user_id = ?',
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()
        
        
async def get_messages_by_tag(user_id: int, tag: str):
    async with aiosqlite.connect('messages.db') as db:
        async with db.execute(
            'SELECT message, tag, timestamp FROM messages WHERE user_id = ? AND tag = ? ORDER BY timestamp DESC',
            (user_id, tag)
        ) as cursor:
            return await cursor.fetchall()

        

async def get_user_tags(user_id: int):
    async with aiosqlite.connect('messages.db') as db:
        async with db.execute(
            'SELECT DISTINCT tag, COUNT(*) as count FROM messages WHERE user_id = ? GROUP BY tag',
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()

async def delete_all_user_messages(user_id: int):
    async with aiosqlite.connect('messages.db') as db:
        await db.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))
        await db.commit()
