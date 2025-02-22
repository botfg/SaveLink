import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, 
    InlineKeyboardButton, CallbackQuery, LinkPreviewOptions
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from config_reader import config
from database import (
    init_db, save_message, get_messages, get_tags, 
    get_messages_by_tag, delete_messages, delete_message_by_id,
    validate_text, validate_description, validate_tag
)

# Константы для валидации
MAX_TEXT_LENGTH = 4096
MAX_DESCRIPTION_LENGTH = 1000
MAX_TAG_LENGTH = 100
MIN_TEXT_LENGTH = 1

ALLOWED_USER_ID = config.allowed_user_id

class UserState(StatesGroup):
    waiting_for_text = State()
    waiting_for_description = State()
    waiting_for_tag_choice = State()
    waiting_for_tag = State()
    waiting_for_deletion_confirmation = State()
    waiting_for_final_confirmation = State()
    waiting_for_tag_selection = State()

bot = Bot(token=config.bot_token.get_secret_value())
dp = Dispatcher(storage=MemoryStorage())

def get_main_keyboard():
    kb = [
        [KeyboardButton(text="📝 Добавить запись")],
        [KeyboardButton(text="📋 Просмотреть записи")],
        [KeyboardButton(text="🔍 Поиск по тегу")],
        [KeyboardButton(text="🗑 Удалить всё")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_tag_choice_keyboard():
    kb = [
        [KeyboardButton(text="Да")],
        [KeyboardButton(text="Нет")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_cancel_keyboard():
    kb = [
        [KeyboardButton(text="❌ Отменить")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_skip_keyboard():
    kb = [
        [KeyboardButton(text="⏩ Пропустить")],
        [KeyboardButton(text="❌ Отменить")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

async def create_tags_keyboard(user_id: int):
    try:
        tags = await get_tags(user_id)
        if not tags or len(tags) == 0:
            return None
        
        kb = []
        for tag, count in tags:
            if tag != "no_tag":  # Исключаем записи без тегов
                kb.append([KeyboardButton(text=f"{tag} ({count})")])
        
        if len(kb) == 0:  # Если после фильтрации не осталось тегов
            return None
            
        kb.append([KeyboardButton(text="❌ Отменить")])
        return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    except Exception as e:
        print(f"Error in create_tags_keyboard: {e}")  # Для отладки
        return None


async def check_access(message: types.Message):
    if message.from_user.id != ALLOWED_USER_ID:
        await message.answer("Извините, у вас нет доступа к этому боту.")
        return False
    return True
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not await check_access(message):
        return
    
    await message.answer(
        "👋 Привет! Я бот для сохранения заметок. Выберите действие:",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "📝 Добавить запись")
async def add_record(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    
    await message.answer(
        "Введите текст, который хотите сохранить:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserState.waiting_for_text)

@dp.message(F.text == "❌ Отменить")
async def cancel_action(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
    
    await message.answer(
        "Действие отменено. Выберите действие:",
        reply_markup=get_main_keyboard()
    )

@dp.message(UserState.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    
    if message.text == "❌ Отменить":
        await cancel_action(message, state)
        return
    
    # Валидация текста
    is_valid, error_message = await validate_text(message.text)
    if not is_valid:
        await message.answer(
            f"❌ Ошибка: {error_message}",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    await state.update_data(user_text=message.text.strip())
    
    await message.answer(
        "Введите описание для записи\n"
        "(или нажмите «⏩ Пропустить» чтобы продолжить без описания):",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(UserState.waiting_for_description)

@dp.message(UserState.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    
    if message.text == "❌ Отменить":
        await cancel_action(message, state)
        return
    
    if message.text == "⏩ Пропустить":
        await state.update_data(description=None)
    else:
        # Валидация описания
        is_valid, error_message = await validate_description(message.text)
        if not is_valid:
            await message.answer(
                f"❌ Ошибка: {error_message}",
                reply_markup=get_skip_keyboard()
            )
            return
        await state.update_data(description=message.text.strip())
    
    await message.answer(
        "Добавить тег?",
        reply_markup=get_tag_choice_keyboard()
    )
    await state.set_state(UserState.waiting_for_tag_choice)
@dp.message(UserState.waiting_for_tag_choice)
async def process_tag_choice(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    
    if message.text == "❌ Отменить":
        await cancel_action(message, state)
        return
    
    if message.text.lower() == "да":
        try:
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Создать новый тег")],
                    [KeyboardButton(text="❌ Отменить")]
                ],
                resize_keyboard=True
            )
            
            # Добавляем существующие теги
            tags = await get_tags(message.from_user.id)
            if tags:
                for tag, _ in tags:
                    keyboard.keyboard.insert(-1, [KeyboardButton(text=tag)])
            
            await message.answer(
                "Выберите существующий тег или создайте новый:",
                reply_markup=keyboard
            )
            await state.set_state(UserState.waiting_for_tag)
        except Exception:
            await message.answer(
                "❌ Произошла ошибка. Попробуйте позже.",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            
    elif message.text.lower() == "нет":
        try:
            data = await state.get_data()
            user_text = data.get("user_text")
            description = data.get("description")
            
            save_result = await save_message(
                message.from_user.id,
                user_text,
                "no_tag",
                description
            )
            
            if save_result:
                await message.answer(
                    "✅ Сообщение сохранено без тега!",
                    reply_markup=get_main_keyboard()
                )
            else:
                await message.answer(
                    "❌ Такая запись уже существует!",
                    reply_markup=get_main_keyboard()
                )
        except Exception:
            await message.answer(
                "❌ Произошла ошибка при сохранении. Попробуйте позже.",
                reply_markup=get_main_keyboard()
            )
        finally:
            await state.clear()

@dp.message(UserState.waiting_for_tag)
async def process_tag(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    
    if message.text == "❌ Отменить":
        await cancel_action(message, state)
        return
    
    if message.text == "Создать новый тег":
        await message.answer(
            "Введите новый тег:",
            reply_markup=get_cancel_keyboard()
        )
        await state.update_data(creating_new_tag=True)
        return
    
    try:
        # Валидация тега
        is_valid, error_message = await validate_tag(message.text)
        if not is_valid:
            await message.answer(
                f"❌ Ошибка: {error_message}",
                reply_markup=get_cancel_keyboard()
            )
            return

        data = await state.get_data()
        user_text = data.get("user_text")
        description = data.get("description")
        creating_new_tag = data.get("creating_new_tag", False)
        
        save_result = await save_message(
            message.from_user.id,
            user_text,
            message.text.strip(),
            description
        )
        
        if save_result:
            action_type = "новым" if creating_new_tag else "существующим"
            await message.answer(
                f"✅ Сообщение успешно сохранено с {action_type} тегом!",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer(
                "❌ Такая запись уже существует!",
                reply_markup=get_main_keyboard()
            )
    except Exception:
        await message.answer(
            "❌ Произошла ошибка при сохранении. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )
    finally:
        await state.clear()


@dp.message(F.text == "📋 Просмотреть записи")
async def view_records(message: types.Message):
    if not await check_access(message):
        return
    
    try:
        records = await get_messages(message.from_user.id)
        if not records:
            await message.answer(
                "📭 У вас пока нет сохраненных записей.",
                reply_markup=get_main_keyboard()
            )
            return

        for record_id, text, tag, description, timestamp in records:
            # Формируем текст сообщения
            response = f"📝 Текст: {text}\n"
            if description:
                response += f"📋 Описание: {description}\n"
            response += f"🏷 Тег: {tag}\n⏰ Время: {timestamp}"
            
            # Создаем инлайн кнопку для удаления
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🗑 Удалить запись", 
                    callback_data=f"del_{record_id}"
                )]
            ])
            
            await message.answer(response, link_preview_options=LinkPreviewOptions(is_disabled=True), reply_markup=keyboard)
        
        await message.answer(
            "Выберите следующее действие:",
            reply_markup=get_main_keyboard()
        )
    except Exception:
        await message.answer(
            "❌ Произошла ошибка при получении записей. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )

@dp.callback_query(lambda c: c.data.startswith('del_'))
async def process_delete_callback(callback_query: CallbackQuery):
    try:
        # Проверяем доступ
        if callback_query.from_user.id != ALLOWED_USER_ID:
            await callback_query.answer("У вас нет доступа к этой функции")
            return
        
        # Извлекаем ID записи из callback_data
        record_id = int(callback_query.data.split('_')[1])
        
        # Создаем клавиатуру подтверждения
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_del_{record_id}"),
                InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel_del_{record_id}")
            ]
        ])
        
        # Изменяем сообщение, добавляя запрос подтверждения
        await callback_query.message.edit_text(
            callback_query.message.text + "\n\n❓ Вы уверены, что хотите удалить эту запись?",
            reply_markup=keyboard
        )
        await callback_query.answer()
        
    except ValueError:
        await callback_query.answer("❌ Некорректный формат ID записи")
    except Exception:
        await callback_query.answer("❌ Произошла ошибка при удалении")

@dp.callback_query(lambda c: c.data.startswith('confirm_del_'))
async def confirm_delete_callback(callback_query: CallbackQuery):
    try:
        if callback_query.from_user.id != ALLOWED_USER_ID:
            await callback_query.answer("У вас нет доступа к этой функции")
            return
        
        record_id = int(callback_query.data.split('_')[2])
        
        if await delete_message_by_id(callback_query.from_user.id, record_id):
            await callback_query.message.delete()
            await callback_query.answer("✅ Запись успешно удалена!")
        else:
            await callback_query.answer("❌ Не удалось удалить запись")
            
    except Exception:
        await callback_query.answer("❌ Произошла ошибка при удалении")

@dp.callback_query(lambda c: c.data.startswith('cancel_del_'))
async def cancel_delete_callback(callback_query: CallbackQuery):
    try:
        if callback_query.from_user.id != ALLOWED_USER_ID:
            await callback_query.answer("У вас нет доступа к этой функции")
            return
        
        record_id = int(callback_query.data.split('_')[2])
        
        # Возвращаем оригинальную клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🗑 Удалить запись", 
                callback_data=f"del_{record_id}"
            )]
        ])
        
        # Восстанавливаем оригинальный текст (убираем запрос подтверждения)
        original_text = callback_query.message.text.split("\n\n❓")[0]
        await callback_query.message.edit_text(
            original_text,
            reply_markup=keyboard
        )
        await callback_query.answer("Удаление отменено")
        
    except Exception:
        await callback_query.answer("❌ Произошла ошибка")


@dp.message(F.text == "🔍 Поиск по тегу")
async def search_by_tag(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    
    try:
        tags = await get_tags(message.from_user.id)
        
        if not tags:
            await message.answer(
                "📭 У вас пока нет сохраненных тегов.",
                reply_markup=get_main_keyboard()
            )
            return

        # Создаем клавиатуру напрямую здесь
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=f"{tag} ({count})")] for tag, count in tags
            ] + [[KeyboardButton(text="❌ Отменить")]],
            resize_keyboard=True
        )
        
        await message.answer(
            "Выберите тег для поиска:",
            reply_markup=keyboard
        )
        await state.set_state(UserState.waiting_for_tag_selection)
        
    except Exception as e:
        print(f"Error in search_by_tag: {str(e)}")
        await message.answer(
            "❌ Произошла ошибка при поиске. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )



@dp.message(UserState.waiting_for_tag_selection)
async def process_tag_selection(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    
    if message.text == "❌ Отменить":
        await message.answer(
            "Поиск отменен.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    try:
        # Извлекаем тег из формата "тег (количество)"
        tag = message.text.split(" (")[0] if "(" in message.text else message.text
        
        records = await get_messages_by_tag(message.from_user.id, tag)
        if not records:
            await message.answer(
                f"📭 Записи с тегом '{tag}' не найдены.",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            return

        response = f"🔍 Записи с тегом '{tag}':\n\n"
        for i, (text, description, timestamp) in enumerate(records, 1):
            response += f"{i}. Текст: {text}\n"
            if description:
                response += f"📝 Описание: {description}\n"
            response += f"⏰ Время: {timestamp}\n\n"
            
            if len(response) > 3500:
                await message.answer(response)
                response = ""
        
        if response:
            await message.answer(response, link_preview_options=LinkPreviewOptions(is_disabled=True))
        
        await message.answer(
            "Выберите следующее действие:",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
    except Exception:
        await message.answer(
            "❌ Произошла ошибка при поиске. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()



@dp.message(F.text == "🗑 Удалить всё")
async def confirm_deletion(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, удалить всё")],
            [KeyboardButton(text="❌ Нет, отменить")],
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "⚠️ ВНИМАНИЕ!\n\n"
        "Вы собираетесь удалить ВСЕ сохраненные записи.\n"
        "Это действие нельзя будет отменить.\n\n"
        "Вы действительно хотите удалить все записи?",
        reply_markup=keyboard
    )
    await state.set_state(UserState.waiting_for_deletion_confirmation)

@dp.message(UserState.waiting_for_deletion_confirmation)
async def process_deletion(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    
    try:
        if message.text == "✅ Да, удалить всё":
            # Запрашиваем повторное подтверждение
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="✅ Подтверждаю удаление")],
                    [KeyboardButton(text="❌ Отменить удаление")],
                ],
                resize_keyboard=True
            )
            
            await message.answer(
                "⚠️ Последнее предупреждение!\n\n"
                "Вы точно уверены, что хотите удалить ВСЕ записи?\n"
                "Это действие нельзя будет отменить!",
                reply_markup=keyboard
            )
            await state.set_state(UserState.waiting_for_final_confirmation)
            
        elif message.text == "❌ Нет, отменить":
            await message.answer(
                "↩️ Удаление отменено.",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            
    except Exception:
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()

@dp.message(UserState.waiting_for_final_confirmation)
async def process_final_deletion(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    
    try:
        if message.text == "✅ Подтверждаю удаление":
            if await delete_messages(message.from_user.id):
                await message.answer(
                    "🗑 Все записи успешно удалены!",
                    reply_markup=get_main_keyboard()
                )
            else:
                await message.answer(
                    "❌ Произошла ошибка при удалении записей.",
                    reply_markup=get_main_keyboard()
                )
        else:
            await message.answer(
                "↩️ Удаление отменено.",
                reply_markup=get_main_keyboard()
            )
    except Exception:
        await message.answer(
            "❌ Произошла ошибка при удалении записей. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )
    finally:
        await state.clear()

@dp.message()
async def handle_other_messages(message: types.Message):
    if not await check_access(message):
        return
    
    await message.answer(
        "Пожалуйста, используйте кнопки для взаимодействия с ботом:",
        reply_markup=get_main_keyboard()
    )

async def main():
    try:
        await init_db()
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())
