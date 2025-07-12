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
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio.client import Redis

# Локальные импорты
from config_reader import config
from database import (
    init_db, save_message, get_messages, get_tags,
    get_messages_by_tag, delete_messages, delete_message_by_id,
    validate_text, validate_name, validate_tag, get_message_by_id,
    update_record_field, get_stats
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

# Инициализация Redis и хранилища
redis_client = Redis(host=config.redis_host, port=config.redis_port)
storage = RedisStorage(redis=redis_client)

# Инициализация бота и диспетчера
bot = Bot(token=config.bot_token.get_secret_value())
dp = Dispatcher(storage=storage)


def is_url(text: str) -> bool:
    """Проверяет, является ли текст валидным URL-адресом, который занимает всю строку."""
    if not isinstance(text, str):
        return False
    # Этот паттерн требует наличия схемы http/https и не позволяет иметь лишний текст в строке
    url_pattern = re.compile(
        r'^https?://'  # Протокол в начале строки
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # домен...
        r'localhost|'  # или localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # или IP
        r'(?::\d+)?'  # порт
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    # Используем fullmatch, чтобы убедиться, что вся строка является URL
    return bool(re.fullmatch(url_pattern, text.strip()))


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

# --- FSM для создания новой записи ---

@dp.message(F.text == "✍️ Создать запись")
async def new_note_handler(message: types.Message, state: FSMContext):
    """Начинает процесс создания новой записи по кнопке."""
    if not await check_access(message): return
    await state.set_state(UserState.waiting_for_text)
    # (ИЗМЕНЕНИЕ): Сообщение изменено по запросу пользователя
    await message.answer("введи ссылку для вашей новой записи", reply_markup=get_cancel_keyboard())


@dp.message(F.text == "❌ Отменить")
async def cancel_action(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
    await message.answer("Действие отменено. Выберите действие:", reply_markup=get_main_keyboard())


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
            data.get("name"), datetime.now()
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
        data.get("name"), datetime.now()
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
        tag = record['tag']
        if tag not in grouped_records:
            grouped_records[tag] = []
        grouped_records[tag].append(record)

    builder = InlineKeyboardBuilder()
    for tag, recs in sorted(grouped_records.items()):
        display_tag = "Без тега" if tag == "no_tag" else html.escape(tag)
        builder.row(InlineKeyboardButton(text=f"📌 {display_tag}", callback_data="ignore"))
        for r in recs:
            record_id = r['id']
            record_text = r['message']
            record_name = r['name']
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
    for record in records:
        formatted_date = record['timestamp'].strftime('%d.%m.%Y')
        safe_text = html.escape(str(record['message']))
        safe_name = html.escape(str(record['name'])) if record['name'] else "<i>(нет названия)</i>"
        response = (
            f"<b>Название:</b> {safe_name}\n"
            f"<b>Ссылка:</b> {safe_text}\n"
            f"<b>Дата:</b> {formatted_date}"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="✏️ Редактировать", callback_data=f"edit_record_{record['id']}")
        builder.button(text="🗑 Удалить", callback_data=f"del_{record['id']}")
        builder.adjust(2)
        
        await message.answer(response, parse_mode="HTML", link_preview_options=LinkPreviewOptions(is_disabled=True), reply_markup=builder.as_markup())
        
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

@dp.message(F.text == "📊 Статистика")
async def stats_handler(message: types.Message):
    if not await check_access(message): return

    stats = await get_stats(message.from_user.id)

    if stats is None:
        await message.answer("❌ Не удалось получить статистику. Попробуйте позже.")
        return

    total_records = stats['total_records']
    total_tags = stats['total_tags']
    popular_tag_info = stats['popular_tag_info']

    if popular_tag_info:
        popular_tag_text = f"<b>Самый популярный тег:</b> {html.escape(popular_tag_info['tag'])} ({popular_tag_info['count']} записей)"
    else:
        popular_tag_text = "<b>Самый популярный тег:</b> (нет тегов)"

    response_text = (
        "📊 <b>Ваша статистика:</b>\n\n"
        f"<b>Всего записей:</b> {total_records}\n"
        f"<b>Уникальных тегов:</b> {total_tags}\n"
        f"{popular_tag_text}"
    )

    await message.answer(response_text, parse_mode="HTML")


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
    
    backup_file_path = f"manual_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.sql"

    try:
        dump_command = [
            'pg_dump',
            '--dbname', config.db_dsn,
            '--file', backup_file_path,
            '--format', 'plain',
            '--clean'
        ]

        process = await asyncio.create_subprocess_exec(
            *dump_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_message = stderr.decode().strip()
            logging.error(f"pg_dump завершился с ошибкой: {error_message}")
            await message.answer(f"❌ Ошибка при создании дампа базы данных: {error_message}")
            return

        file_link = await asyncio.to_thread(upload_database_backup, backup_file_path, os.path.basename(backup_file_path))

        if file_link:
            await message.answer(
                f"✅ Резервная копия успешно создана и загружена на Google Drive!",
                disable_web_page_preview=True
            )
        else:
            await message.answer("❌ Произошла ошибка во время загрузки резервной копии на Google Drive.")

    except FileNotFoundError:
        logging.error("Команда 'pg_dump' не найдена. Убедитесь, что postgresql-client установлен.")
        await message.answer("❌ Ошибка: команда `pg_dump` не найдена. Установите `postgresql-client`.")
    except Exception as e:
        logging.error(f"Manual backup process failed: {e}")
        await message.answer("❌ Произошла критическая ошибка в процессе резервного копирования.")
    finally:
        if os.path.exists(backup_file_path):
            os.remove(backup_file_path)


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
        
        temp_backup_path = f"restore_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.sql"
        
        try:
            success = await asyncio.to_thread(download_latest_backup, temp_backup_path)
            
            if not success:
                await message.answer("❌ Не удалось найти или скачать резервную копию с Google Drive.")
                return

            await message.answer("✅ Бекап скачан. Начинаю восстановление базы данных...")

            restore_command = [
                'psql',
                '--dbname', config.db_dsn,
                '-f', temp_backup_path
            ]

            process = await asyncio.create_subprocess_exec(
                *restore_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_message = stderr.decode().strip()
                logging.error(f"psql завершился с ошибкой: {error_message}")
                await message.answer(f"❌ Ошибка при восстановлении из дампа: {error_message}")
            else:
                await message.answer(
                    "✅ База данных успешно восстановлена из резервной копии!\n\n"
                    "❗️<b>Важно:</b> Пожалуйста, перезапустите бота (остановите и запустите его заново), "
                    "чтобы он начал работать с обновленными данными.",
                    parse_mode="HTML"
                )

        except FileNotFoundError:
            logging.error("Команда 'psql' не найдена. Убедитесь, что postgresql-client установлен.")
            await message.answer("❌ Ошибка: команда `psql` не найдена. Установите `postgresql-client`.")
        except Exception as e:
            logging.error(f"Restore process failed: {e}")
            await message.answer("❌ Произошла критическая ошибка в процессе восстановления.")
        finally:
            if os.path.exists(temp_backup_path):
                os.remove(temp_backup_path)
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

    formatted_date = record['timestamp'].strftime('%d.%m.%Y %H:%M')
    safe_text = html.escape(str(record['message']))
    safe_name = html.escape(str(record['name'])) if record['name'] else "<i>(нет названия)</i>"
    safe_tag = "Без тега" if record['tag'] == "no_tag" else html.escape(str(record['tag']))

    response = (
        f"<b>Название:</b> {safe_name}\n"
        f"<b>Ссылка:</b> {safe_text}\n"
        f"<b>Тег:</b> {safe_tag}\n"
        f"<b>Дата:</b> {formatted_date}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать", callback_data=f"edit_record_{record['id']}")
    builder.button(text="🗑 Удалить", callback_data=f"del_{record['id']}")
    builder.adjust(2)

    await callback_query.message.answer(response, parse_mode="HTML", reply_markup=builder.as_markup(), disable_web_page_preview=True)
    await callback_query.answer()

@dp.callback_query(F.data.startswith("edit_record_"))
async def edit_record_menu_callback(callback_query: CallbackQuery):
    record_id = int(callback_query.data.split("_")[2])
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Изменить название", callback_data=f"edit_name_{record_id}")
    builder.button(text="Изменить ссылку", callback_data=f"edit_link_{record_id}")
    builder.button(text="Изменить тег", callback_data=f"edit_tag_{record_id}")
    builder.button(text="🔙 Закрыть меню", callback_data=f"close_edit_menu")
    builder.adjust(1)

    await callback_query.message.answer(
        "Выберите, что вы хотите изменить:",
        reply_markup=builder.as_markup()
    )
    await callback_query.answer()

@dp.callback_query(F.data == "close_edit_menu")
async def close_edit_menu_callback(callback_query: CallbackQuery):
    await callback_query.message.delete()
    await callback_query.answer()


@dp.callback_query(F.data.startswith("edit_name_"))
async def edit_name_callback(callback_query: CallbackQuery, state: FSMContext):
    record_id = int(callback_query.data.split("_")[2])
    await state.update_data(record_id_to_edit=record_id)
    await state.set_state(UserState.editing_record_name)
    await callback_query.message.edit_text("Введите новое название для записи:")
    await callback_query.answer()

@dp.callback_query(F.data.startswith("edit_link_"))
async def edit_link_callback(callback_query: CallbackQuery, state: FSMContext):
    record_id = int(callback_query.data.split("_")[2])
    await state.update_data(record_id_to_edit=record_id)
    await state.set_state(UserState.editing_record_link)
    await callback_query.message.edit_text("Введите новую ссылку для записи:")
    await callback_query.answer()

@dp.callback_query(F.data.startswith("edit_tag_"))
async def edit_tag_callback(callback_query: CallbackQuery, state: FSMContext):
    record_id = int(callback_query.data.split("_")[2])
    await state.update_data(record_id_to_edit=record_id)
    await state.set_state(UserState.editing_record_tag)
    tags = await get_tags(callback_query.from_user.id)
    kb = [[types.KeyboardButton(text="Создать новый тег")]]
    if tags:
        for tag in tags:
            if tag['tag'] != "no_tag":
                kb.append([types.KeyboardButton(text=f"{tag['tag']} ({tag['count']})")])
    kb.append([types.KeyboardButton(text="❌ Отменить")])
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await callback_query.message.answer("Выберите новый тег или создайте его:", reply_markup=keyboard)
    await callback_query.message.delete()
    await callback_query.answer()

@dp.message(UserState.editing_record_name)
async def process_new_name(message: types.Message, state: FSMContext):
    is_valid, error_message = await validate_name(message.text)
    if not is_valid:
        await message.answer(f"❌ Ошибка: {error_message}\n\nПопробуйте еще раз или отмените действие.")
        return
    
    data = await state.get_data()
    record_id = data.get("record_id_to_edit")
    
    if await update_record_field(record_id, "name", message.text.strip()):
        await message.answer("✅ Название успешно обновлено!", reply_markup=get_main_keyboard())
    else:
        await message.answer("❌ Не удалось обновить название. Попробуйте позже.", reply_markup=get_main_keyboard())
    await state.clear()

@dp.message(UserState.editing_record_link)
async def process_new_link(message: types.Message, state: FSMContext):
    is_valid, error_message = await validate_text(message.text)
    if not is_valid:
        await message.answer(f"❌ Ошибка: {error_message}\n\nПопробуйте еще раз или отмените действие.")
        return
    
    data = await state.get_data()
    record_id = data.get("record_id_to_edit")
    
    if await update_record_field(record_id, "message", message.text.strip()):
        await message.answer("✅ Ссылка успешно обновлена!", reply_markup=get_main_keyboard())
    else:
        await message.answer("❌ Не удалось обновить ссылку. Попробуйте позже.", reply_markup=get_main_keyboard())
    await state.clear()

@dp.message(UserState.editing_record_tag)
async def process_new_tag(message: types.Message, state: FSMContext):
    tag_text = message.text.split(" (")[0]
    if tag_text == "Создать новый тег":
        await message.answer("Введите новый тег:", reply_markup=get_cancel_keyboard())
        return

    is_valid, error_message = await validate_tag(tag_text)
    if not is_valid:
        await message.answer(f"❌ Ошибка: {error_message}\n\nПопробуйте еще раз или отмените действие.")
        return
        
    data = await state.get_data()
    record_id = data.get("record_id_to_edit")
    
    if await update_record_field(record_id, "tag", tag_text.strip()):
        await message.answer("✅ Тег успешно обновлен!", reply_markup=get_main_keyboard())
    else:
        await message.answer("❌ Не удалось обновить тег. Попробуйте позже.", reply_markup=get_main_keyboard())
    await state.clear()


@dp.callback_query(F.data == "save_url")
async def process_save_url_callback(callback_query: CallbackQuery, state: FSMContext):
    if not await check_access(callback_query): return
    data = await state.get_data()
    url = data.get("temp_url")
    if url:
        await state.update_data(user_text=url)
        await callback_query.message.edit_text("Ссылка будет сохранена. Теперь введите название или нажмите 'Пропустить'.")
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
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать", callback_data=f"edit_record_{record_id}")
    builder.button(text="🗑 Удалить", callback_data=f"del_{record_id}")
    builder.adjust(2)
    await callback_query.message.edit_text(original_html_text, parse_mode="HTML", reply_markup=builder.as_markup())
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

# (ИЗМЕНЕНИЕ): Обработчик для любого текста, который не является командой или URL
@dp.message()
async def handle_text_message(message: types.Message, state: FSMContext):
    """
    Обрабатывает текстовые сообщения. Если это не URL и не команда с клавиатуры,
    начинает процесс создания новой заметки.
    """
    if not await check_access(message): return

    # Проверяем, не находимся ли мы уже в каком-то процессе
    current_state = await state.get_state()
    if current_state is not None:
        await message.answer(
            "Пожалуйста, завершите текущее действие или отмените его с помощью кнопки «❌ Отменить».",
        )
        return

    # Если это не URL (проверяется раньше) и не команда с клавиатуры,
    # начинаем процесс создания заметки, передавая текущее сообщение
    await state.set_state(UserState.waiting_for_text)
    await process_text(message, state)


async def main():
    try:
        await init_db()
        setup_scheduler(bot, ALLOWED_USER_ID)
        await dp.start_polling(bot)
    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())
