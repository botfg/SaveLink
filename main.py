import asyncio
import re
import logging
import html
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery, LinkPreviewOptions, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# Локальные импорты
from config_reader import config
from database import (
    init_db, save_message, get_messages, get_tags,
    get_messages_by_tag, delete_messages, delete_message_by_id,
    validate_text, validate_name, validate_tag, get_message_by_id
)
from keyboards import (
    get_main_keyboard, get_extra_keyboard, get_tag_choice_keyboard,
    get_cancel_keyboard, get_skip_keyboard, create_tags_keyboard,
    get_delete_confirmation_keyboard
)
from states import UserState
from gdrive_uploader import upload_database_backup, download_latest_backup
from scheduler import setup_scheduler

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
    if not await check_access(message): return
    await state.update_data(temp_url=message.text)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="save_url"), InlineKeyboardButton(text="❌ Нет", callback_data="cancel_url")]
    ])
    await message.answer("Создать запись с данной ссылкой?", reply_markup=keyboard)


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    if not await check_access(message): return
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
    await message.answer("Действие отменено. Выберите действие:", reply_markup=get_main_keyboard())

# --- FSM для создания новой записи ---

@dp.message(UserState.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    if not await check_access(message): return
    is_valid, error_message = await validate_text(message.text)
    if not is_valid:
        await message.answer(f"❌ Ошибка: {error_message}", reply_markup=get_cancel_keyboard())
        return
    await state.update_data(user_text=message.text.strip())
    await message.answer("Введите название для записи\n(или нажмите «⏩ Пропустить»):", reply_markup=get_skip_keyboard())
    await state.set_state(UserState.waiting_for_name)

@dp.message(UserState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    if not await check_access(message): return
    if message.text == "⏩ Пропустить":
        await state.update_data(name=None)
    else:
        is_valid, error_message = await validate_name(message.text)
        if not is_valid:
            await message.answer(f"❌ Ошибка: {error_message}", reply_markup=get_skip_keyboard())
            return
        await state.update_data(name=message.text.strip())
    await message.answer("Добавить тег?", reply_markup=get_tag_choice_keyboard())
    await state.set_state(UserState.waiting_for_tag_choice)


@dp.message(UserState.waiting_for_tag_choice)
async def process_tag_choice(message: types.Message, state: FSMContext):
    if not await check_access(message): return
    if message.text.lower() == "да":
        tags = await get_tags(message.from_user.id)
        kb = [[types.KeyboardButton(text="Создать новый тег")]]
        if tags:
            for tag, count in tags:
                if tag != "no_tag":
                    kb.append([types.KeyboardButton(text=f"{tag} ({count})")])
        kb.append([types.KeyboardButton(text="❌ Отменить")])
        keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer("Выберите существующий тег или создайте новый:", reply_markup=keyboard)
        await state.set_state(UserState.waiting_for_tag)
    elif message.text.lower() == "нет":
        data = await state.get_data()
        save_result = await save_message(
            message.from_user.id, data.get("user_text"), "no_tag",
            data.get("name"), datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        if save_result:
            await message.answer("✅ Сообщение сохранено без тега!", reply_markup=get_main_keyboard())
        else:
            await message.answer("❌ Такая запись уже существует!", reply_markup=get_main_keyboard())
        await state.clear()


@dp.message(UserState.waiting_for_tag)
async def process_tag(message: types.Message, state: FSMContext):
    if not await check_access(message): return
    tag_text = message.text.split(" (")[0]
    if tag_text == "Создать новый тег":
        await message.answer("Введите новый тег:", reply_markup=get_cancel_keyboard())
        await state.update_data(creating_new_tag=True)
        return
    is_valid, error_message = await validate_tag(tag_text)
    if not is_valid:
        await message.answer(f"❌ Ошибка: {error_message}", reply_markup=get_cancel_keyboard())
        return
    data = await state.get_data()
    save_result = await save_message(
        message.from_user.id, data.get("user_text"), tag_text.strip(),
        data.get("name"), datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    if save_result:
        action_type = "новым" if data.get("creating_new_tag", False) else "существующим"
        await message.answer(f"✅ Сообщение успешно сохранено с {action_type} тегом!", reply_markup=get_main_keyboard())
    else:
        await message.answer("❌ Такая запись уже существует!", reply_markup=get_main_keyboard())
    await state.clear()

# --- ОБРАБОТЧИКИ ГЛАВНОГО МЕНЮ ---
@dp.message(F.text == "📋 Просмотреть записи")
async def view_records_handler(message: types.Message):
    if not await check_access(message): return
    records = await get_messages(message.from_user.id)
    if not records:
        await message.answer("📭 У вас пока нет сохраненных записей.", reply_markup=get_main_keyboard())
        return

    grouped_records = {}
    for record in records:
        tag = record[2]
        if tag not in grouped_records:
            grouped_records[tag] = []
        grouped_records[tag].append(record)

    builder = InlineKeyboardBuilder()
    for tag, recs in sorted(grouped_records.items()):
        display_tag = "Без тега" if tag == "no_tag" else html.escape(tag)
        builder.row(InlineKeyboardButton(text=f"📌 {display_tag}", callback_data="ignore"))
        for r in recs:
            record_id, record_text, _, record_name, _ = r
            link_text_content = record_name if record_name else record_text
            link_text = (link_text_content[:40] + '...') if len(link_text_content) > 40 else link_text_content
            safe_link_text = html.escape(link_text)
            builder.row(InlineKeyboardButton(
                text=f"• {safe_link_text}",
                callback_data=f"view_record_{record_id}"
            ))

    await message.answer("🗂️ Ваши записи:", reply_markup=builder.as_markup())


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
    raw_tag_text = message.text.split(" (")[0]
    tag_to_search = "no_tag" if raw_tag_text == "Без тега" else raw_tag_text
    records = await get_messages_by_tag(message.from_user.id, tag_to_search)
    if not records:
        await message.answer(f"📭 Записи с тегом '{raw_tag_text}' не найдены.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    await message.answer(f"🔍 Записи с тегом '<b>{html.escape(raw_tag_text)}</b>':", parse_mode="HTML")
    for record_id, text, name, timestamp in records:
        date_obj = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        formatted_date = date_obj.strftime('%d.%m.%Y')
        safe_text = html.escape(str(text))
        safe_name = html.escape(str(name)) if name else "<i>(нет названия)</i>"
        response = (
            f"<b>Название:</b> {safe_name}\n"
            f"<b>Ссылка:</b> {safe_text}\n"
            f"<b>Дата:</b> {formatted_date}"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Удалить запись", callback_data=f"del_{record_id}")]])
        await message.answer(response, parse_mode="HTML", link_preview_options=LinkPreviewOptions(is_disabled=True), reply_markup=keyboard)
    await message.answer("Выберите следующее действие:", reply_markup=get_main_keyboard())
    await state.clear()


# --- ОБРАБОТЧИКИ ДОПОЛНИТЕЛЬНОГО МЕНЮ ---

@dp.message(F.text == "⚙️ Дополнительно")
async def extra_menu_handler(message: types.Message):
    if not await check_access(message): return
    await message.answer(
        "Дополнительные действия:",
        reply_markup=get_extra_keyboard()
    )

@dp.message(F.text == "🔙 Назад")
async def back_to_main_handler(message: types.Message):
    if not await check_access(message): return
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "📤 Создать резервную копию")
@dp.message(Command("backup"))
async def backup_command_handler(message: types.Message):
    if not await check_access(message): return
    await message.answer("⏳ Начинаю процесс резервного копирования...", reply_markup=get_main_keyboard())
    db_file_path = 'messages.db'
    backup_file_name = f"backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.db"
    try:
        file_link = await asyncio.to_thread(upload_database_backup, db_file_path, backup_file_name)
        if file_link:
            await message.answer(
                f"✅ Резервная копия успешно создана и загружена на Google Drive!",
                disable_web_page_preview=True
            )
        else:
            await message.answer("❌ Произошла ошибка во время загрузки резервной копии.")
    except Exception as e:
        logging.error(f"Backup process failed: {e}")
        await message.answer("❌ Произошла критическая ошибка в процессе резервного копирования.")


@dp.message(F.text == "📥 Восстановить из бекапа")
async def restore_backup_start_handler(message: types.Message, state: FSMContext):
    if not await check_access(message): return
    confirm_kb = ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="ДА, Я ПОНИМАЮ РИСКИ")],
            [types.KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        "Вы собираетесь заменить текущую базу данных последней резервной копией с Google Drive. "
        "Все текущие данные будут **безвозвратно удалены**.\n\n"
        "Это действие нельзя отменить. Вы уверены, что хотите продолжить?",
        parse_mode="HTML",
        reply_markup=confirm_kb
    )
    await state.set_state(UserState.waiting_for_restore_confirmation)


@dp.message(UserState.waiting_for_restore_confirmation)
async def process_restore_confirmation(message: types.Message, state: FSMContext):
    if not await check_access(message): return
    if message.text == "ДА, Я ПОНИМАЮ РИСКИ":
        await message.answer("⏳ Начинаю скачивание последней резервной копии...", reply_markup=get_main_keyboard())
        temp_db_path = 'messages.db.tmp'
        try:
            success = await asyncio.to_thread(download_latest_backup, temp_db_path)
            if success:
                os.replace(temp_db_path, 'messages.db')
                await message.answer(
                    "✅ База данных успешно восстановлена!\n\n"
                    "❗️<b>Важно:</b> Пожалуйста, перезапустите бота (остановите и запустите его заново), "
                    "чтобы изменения вступили в силу.",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Не удалось найти или скачать резервную копию с Google Drive.")
        except Exception as e:
            logging.error(f"Restore process failed: {e}")
            await message.answer("❌ Произошла критическая ошибка в процессе восстановления.")
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            await state.clear()
    else:
        await message.answer("Восстановление отменено.", reply_markup=get_main_keyboard())
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


# --- ОБРАБОТЧИКИ КОЛБЭКОВ ---
@dp.callback_query(F.data == "ignore")
async def ignore_callback(callback_query: CallbackQuery):
    await callback_query.answer()

@dp.callback_query(F.data.startswith("view_record_"))
async def show_record_details_callback(callback_query: CallbackQuery):
    if not await check_access(callback_query): return
    try:
        record_id = int(callback_query.data.split("_")[2])
    except (IndexError, ValueError):
        await callback_query.answer("❌ Ошибка ID записи.", show_alert=True)
        return

    record = await get_message_by_id(callback_query.from_user.id, record_id)
    if not record:
        await callback_query.answer("❌ Запись не найдена.", show_alert=True)
        return

    rec_id, text, tag, name, timestamp = record
    date_obj = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    formatted_date = date_obj.strftime('%d.%m.%Y %H:%M')
    safe_text = html.escape(str(text))
    safe_name = html.escape(str(name)) if name else "<i>(нет названия)</i>"
    safe_tag = "Без тега" if tag == "no_tag" else html.escape(str(tag))

    response = (
        f"<b>Название:</b> {safe_name}\n"
        f"<b>Ссылка:</b> {safe_text}\n"
        f"<b>Тег:</b> {safe_tag}\n"
        f"<b>Дата:</b> {formatted_date}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить эту запись", callback_data=f"del_{rec_id}")]
    ])
    await callback_query.message.answer(response, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
    await callback_query.answer()

@dp.callback_query(F.data == "save_url")
async def process_save_url_callback(callback_query: CallbackQuery, state: FSMContext):
    if not await check_access(callback_query): return
    data = await state.get_data()
    url = data.get("temp_url")
    if url:
        await state.update_data(user_text=url)
        await callback_query.message.edit_text("Ссылка будет сохранена. Введите название или нажмите 'Пропустить'.")
        await callback_query.message.answer("Введите название для ссылки:", reply_markup=get_skip_keyboard())
        await state.set_state(UserState.waiting_for_name)
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
    original_html_text = callback_query.message.html_text.split("\n\n❓")[0]
    record_id = int(callback_query.data.split('_')[2])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Удалить запись", callback_data=f"del_{record_id}")]])
    await callback_query.message.edit_text(original_html_text, parse_mode="HTML", reply_markup=keyboard)
    await callback_query.answer("Удаление отменено.")

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

@dp.message()
async def handle_other_messages(message: types.Message, state: FSMContext):
    if not await check_access(message): return
    current_state = await state.get_state()
    if current_state is None:
        await state.set_state(UserState.waiting_for_text)
        await process_text(message, state)
    else:
        await message.answer(
            "Пожалуйста, завершите текущее действие или отмените его.",
        )

async def main():
    try:
        await init_db()
        setup_scheduler(bot, ALLOWED_USER_ID)
        await dp.start_polling(bot)
    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())
