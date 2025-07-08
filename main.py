import asyncio
import re
import logging
import html # <-- Добавлен импорт для экранирования HTML
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery, LinkPreviewOptions, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from config_reader import config
from database import (
    init_db, save_message, get_messages, get_tags,
    get_messages_by_tag, delete_messages, delete_message_by_id,
    validate_text, validate_description, validate_tag
)
from keyboards import (
    get_main_keyboard, get_tag_choice_keyboard,
    get_cancel_keyboard, get_skip_keyboard, create_tags_keyboard,
    get_delete_confirmation_keyboard
)
from states import UserState

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Константы
ALLOWED_USER_ID = config.allowed_user_id

# Инициализация бота и диспетчера
bot = Bot(token=config.bot_token.get_secret_value())
dp = Dispatcher(storage=MemoryStorage())


def is_url(text: str) -> bool:
    """Проверяет, является ли текст URL-адресом."""
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    return bool(url_pattern.match(text))


async def check_access(message: types.Message | types.CallbackQuery) -> bool:
    """Проверяет, имеет ли пользователь доступ к боту."""
    if message.from_user.id != ALLOWED_USER_ID:
        if isinstance(message, types.Message):
            await message.answer("Извините, у вас нет доступа к этому боту.")
        else: # CallbackQuery
            await message.answer("У вас нет доступа к этой функции.", show_alert=True)
        logging.warning(f"Unauthorized access attempt by user {message.from_user.id}")
        return False
    return True

# --- Обработчик URL и стартовая команда ---

@dp.message(lambda message: is_url(message.text))
async def handle_url(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return

    await state.update_data(temp_url=message.text)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="save_url"),
            InlineKeyboardButton(text="❌ Нет", callback_data="cancel_url")
        ]
    ])

    await message.answer("Создать запись с данной ссылкой?", reply_markup=keyboard)


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.clear()
    await message.answer(
        "👋 Привет! Я бот для сохранения заметок. Выберите действие:",
        reply_markup=get_main_keyboard()
    )

# --- Обработчик отмены ---

@dp.message(F.text == "❌ Отменить")
async def cancel_action(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()

    await message.answer(
        "Действие отменено. Выберите действие:",
        reply_markup=get_main_keyboard()
    )

# --- FSM для создания новой записи ---

@dp.message(UserState.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    if not await check_access(message): return

    is_valid, error_message = await validate_text(message.text)
    if not is_valid:
        await message.answer(f"❌ Ошибка: {error_message}", reply_markup=get_cancel_keyboard())
        return

    await state.update_data(user_text=message.text.strip())
    await message.answer("Введите описание для записи\n(или нажмите «⏩ Пропустить»):", reply_markup=get_skip_keyboard())
    await state.set_state(UserState.waiting_for_description)


@dp.message(UserState.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    if not await check_access(message): return

    if message.text == "⏩ Пропустить":
        await state.update_data(description=None)
    else:
        is_valid, error_message = await validate_description(message.text)
        if not is_valid:
            await message.answer(f"❌ Ошибка: {error_message}", reply_markup=get_skip_keyboard())
            return
        await state.update_data(description=message.text.strip())

    await message.answer("Добавить тег?", reply_markup=get_tag_choice_keyboard())
    await state.set_state(UserState.waiting_for_tag_choice)


@dp.message(UserState.waiting_for_tag_choice)
async def process_tag_choice(message: types.Message, state: FSMContext):
    if not await check_access(message): return

    if message.text.lower() == "да":
        tags = await get_tags(message.from_user.id)
        kb = [[types.KeyboardButton(text="Создать новый тег")]]
        if tags:
            kb.extend([[types.KeyboardButton(text=tag[0])] for tag, count in tags if tag[0] != "no_tag"])
        kb.append([types.KeyboardButton(text="❌ Отменить")])
        keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

        await message.answer("Выберите существующий тег или создайте новый:", reply_markup=keyboard)
        await state.set_state(UserState.waiting_for_tag)

    elif message.text.lower() == "нет":
        data = await state.get_data()
        save_result = await save_message(
            message.from_user.id,
            data.get("user_text"),
            "no_tag",
            data.get("description"),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        if save_result:
            await message.answer("✅ Сообщение сохранено без тега!", reply_markup=get_main_keyboard())
        else:
            await message.answer("❌ Такая запись уже существует!", reply_markup=get_main_keyboard())
        await state.clear()


@dp.message(UserState.waiting_for_tag)
async def process_tag(message: types.Message, state: FSMContext):
    if not await check_access(message): return

    if message.text == "Создать новый тег":
        await message.answer("Введите новый тег:", reply_markup=get_cancel_keyboard())
        await state.update_data(creating_new_tag=True)
        return

    is_valid, error_message = await validate_tag(message.text)
    if not is_valid:
        await message.answer(f"❌ Ошибка: {error_message}", reply_markup=get_cancel_keyboard())
        return

    data = await state.get_data()
    save_result = await save_message(
        message.from_user.id,
        data.get("user_text"),
        message.text.strip(),
        data.get("description"),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

    if save_result:
        action_type = "новым" if data.get("creating_new_tag", False) else "существующим"
        await message.answer(f"✅ Сообщение успешно сохранено с {action_type} тегом!", reply_markup=get_main_keyboard())
    else:
        await message.answer("❌ Такая запись уже существует!", reply_markup=get_main_keyboard())
    await state.clear()


# --- Обработчики главного меню ---

@dp.message(F.text == "📋 Просмотреть записи")
async def view_records_handler(message: types.Message):
    if not await check_access(message): return

    records = await get_messages(message.from_user.id)
    if not records:
        await message.answer("📭 У вас пока нет сохраненных записей.", reply_markup=get_main_keyboard())
        return

    for record_id, text, tag, description, timestamp in records:
        date_obj = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        formatted_date = date_obj.strftime('%d.%m.%Y')

        # Экранируем пользовательские данные
        safe_text = html.escape(str(text))
        safe_description = html.escape(str(description)) if description else None
        safe_tag = html.escape(str(tag))

        # Используем HTML-теги для форматирования
        response = f"📝 <b>Текст:</b> {safe_text}\n"
        if safe_description:
            response += f"📋 <b>Описание:</b> {safe_description}\n"
        response += f"🏷 <b>Тег:</b> {safe_tag}\n⏰ <b>Время:</b> {formatted_date}"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Удалить запись", callback_data=f"del_{record_id}")]])
        # Отправляем с parse_mode="HTML"
        await message.answer(response, parse_mode="HTML", link_preview_options=LinkPreviewOptions(is_disabled=True), reply_markup=keyboard)


@dp.message(F.text == "🔍 Поиск по тегу")
async def search_by_tag_handler(message: types.Message, state: FSMContext):
    if not await check_access(message): return

    tags = await get_tags(message.from_user.id)
    keyboard = create_tags_keyboard(tags)

    if not keyboard:
        await message.answer("📭 У вас пока нет сохраненных тегов.", reply_markup=get_main_keyboard())
        return

    await message.answer("Выберите тег для поиска:", reply_markup=keyboard)
    await state.set_state(UserState.waiting_for_tag_selection)


@dp.message(UserState.waiting_for_tag_selection)
async def process_tag_selection(message: types.Message, state: FSMContext):
    if not await check_access(message): return

    if message.text == "❌ Отменить":
        await message.answer("Поиск отменен.", reply_markup=get_main_keyboard())
        await state.clear()
        return

    tag = message.text.split(" (")[0]
    records = await get_messages_by_tag(message.from_user.id, tag)
    if not records:
        await message.answer(f"📭 Записи с тегом '{tag}' не найдены.", reply_markup=get_main_keyboard())
        await state.clear()
        return

    await message.answer(f"🔍 Записи с тегом '<b>{html.escape(tag)}</b>':", parse_mode="HTML")
    for record_id, text, description, timestamp in records:
        date_obj = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        formatted_date = date_obj.strftime('%d.%m.%Y')

        # Экранируем пользовательские данные
        safe_text = html.escape(str(text))
        safe_description = html.escape(str(description)) if description else None
        
        # Используем HTML-теги
        response = f"📝 <b>Текст:</b> {safe_text}\n"
        if safe_description:
            response += f"📋 <b>Описание:</b> {safe_description}\n"
        response += f"⏰ <b>Время:</b> {formatted_date}"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Удалить запись", callback_data=f"del_{record_id}")]])
        await message.answer(response, parse_mode="HTML", link_preview_options=LinkPreviewOptions(is_disabled=True), reply_markup=keyboard)

    await message.answer("Выберите следующее действие:", reply_markup=get_main_keyboard())
    await state.clear()


@dp.message(F.text == "🗑 Удалить всё")
async def confirm_deletion_handler(message: types.Message, state: FSMContext):
    if not await check_access(message): return
    keyboard = ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="✅ Да, удалить всё")], [types.KeyboardButton(text="❌ Нет, отменить")]], resize_keyboard=True)
    await message.answer(
        "⚠️ <b>ВНИМАНИЕ!</b>\n\nВы собираетесь удалить ВСЕ сохраненные записи. Это действие нельзя будет отменить.\n\nВы действительно хотите удалить все записи?",
        parse_mode="HTML", reply_markup=keyboard
    )
    await state.set_state(UserState.waiting_for_deletion_confirmation)


# --- Обработчики колбэков (удаление, сохранение URL) ---

@dp.callback_query(F.data == "save_url")
async def process_save_url_callback(callback_query: CallbackQuery, state: FSMContext):
    if not await check_access(callback_query): return

    data = await state.get_data()
    url = data.get("temp_url")
    if url:
        await state.update_data(user_text=url)
        await callback_query.message.edit_text("Ссылка будет сохранена. Введите описание или нажмите 'Пропустить'.")
        await callback_query.message.answer("Введите описание для ссылки:", reply_markup=get_skip_keyboard())
        await state.set_state(UserState.waiting_for_description)
    else:
        await callback_query.message.edit_text("Не удалось сохранить ссылку. Попробуйте снова.")
    await callback_query.answer()


@dp.callback_query(F.data == "cancel_url")
async def process_cancel_url_callback(callback_query: CallbackQuery):
    await callback_query.message.edit_text("Сохранение ссылки отменено.")
    await callback_query.answer()


@dp.callback_query(F.data.startswith('del_'))
async def process_delete_callback(callback_query: CallbackQuery):
    if not await check_access(callback_query): return
    record_id = int(callback_query.data.split('_')[1])
    keyboard = get_delete_confirmation_keyboard(record_id)
    # Используем html_text для безопасного редактирования
    await callback_query.message.edit_text(
        callback_query.message.html_text + "\n\n❓ <b>Вы уверены, что хотите удалить эту запись?</b>",
        parse_mode="HTML", reply_markup=keyboard
    )
    await callback_query.answer()


@dp.callback_query(F.data.startswith('confirm_del_'))
async def confirm_delete_callback(callback_query: CallbackQuery):
    if not await check_access(callback_query): return
    record_id = int(callback_query.data.split('_')[2])
    if await delete_message_by_id(callback_query.from_user.id, record_id):
        await callback_query.message.delete()
        await callback_query.answer("✅ Запись успешно удалена!", show_alert=True)
    else:
        await callback_query.answer("❌ Не удалось удалить запись.", show_alert=True)


@dp.callback_query(F.data.startswith('cancel_del_'))
async def cancel_delete_callback(callback_query: CallbackQuery):
    if not await check_access(callback_query): return
    # Используем html_text для безопасного восстановления
    original_html_text = callback_query.message.html_text.split("\n\n❓")[0]
    record_id = int(callback_query.data.split('_')[2])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Удалить запись", callback_data=f"del_{record_id}")]])
    await callback_query.message.edit_text(original_html_text, parse_mode="HTML", reply_markup=keyboard)
    await callback_query.answer("Удаление отменено.")


# --- Процесс полного удаления ---

@dp.message(UserState.waiting_for_deletion_confirmation)
async def process_deletion_confirmation(message: types.Message, state: FSMContext):
    if not await check_access(message): return

    if message.text == "✅ Да, удалить всё":
        keyboard = ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="✅ Подтверждаю удаление")], [types.KeyboardButton(text="❌ Отменить удаление")]], resize_keyboard=True)
        await message.answer(
            "⚠️ <b>Последнее предупреждение!</b>\n\nВы точно уверены, что хотите удалить ВСЕ записи? Это действие необратимо!",
            parse_mode="HTML", reply_markup=keyboard
        )
        await state.set_state(UserState.waiting_for_final_confirmation)
    else:
        await message.answer("↩️ Удаление отменено.", reply_markup=get_main_keyboard())
        await state.clear()


@dp.message(UserState.waiting_for_final_confirmation)
async def process_final_deletion(message: types.Message, state: FSMContext):
    if not await check_access(message): return

    if message.text == "✅ Подтверждаю удаление":
        if await delete_messages(message.from_user.id):
            await message.answer("🗑 Все записи успешно удалены!", reply_markup=get_main_keyboard())
        else:
            await message.answer("❌ Произошла ошибка при удалении записей.", reply_markup=get_main_keyboard())
    else:
        await message.answer("↩️ Удаление отменено.", reply_markup=get_main_keyboard())
    await state.clear()

# --- Обработчик для всех остальных сообщений ---

@dp.message()
async def handle_other_messages(message: types.Message):
    if not await check_access(message): return
    # Явно создаем новую запись, если текст не является командой
    await message.answer("Введите текст для новой записи:", reply_markup=get_cancel_keyboard())
    await message.answer("Чтобы сохранить ссылку, просто отправьте ее. Для других действий используйте кнопки.")


# --- Основная функция запуска ---

async def main():
    try:
        await init_db()
        await dp.start_polling(bot)
    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())