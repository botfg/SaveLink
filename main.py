import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
from config_reader import config
from database import init_db, save_message, get_user_messages, get_user_tags, delete_all_user_messages, get_messages_by_tag

ALLOWED_USER_ID = config.allowed_user_id

logging.basicConfig(level=logging.INFO)

class UserState(StatesGroup):
    waiting_for_text = State()
    waiting_for_tag_choice = State()
    waiting_for_tag = State()
    waiting_for_deletion_confirmation = State()
    waiting_for_tag_selection = State()

bot = Bot(token=config.bot_token.get_secret_value())
dp = Dispatcher(storage=MemoryStorage())

def get_main_keyboard():
    kb = [
        [KeyboardButton(text="Добавить запись")],
        [KeyboardButton(text="Просмотреть записи")],
        [KeyboardButton(text="Поиск по тегу")],
        [KeyboardButton(text="Удалить всё")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    return keyboard

def get_tag_choice_keyboard():
    kb = [
        [KeyboardButton(text="Да")],
        [KeyboardButton(text="Нет")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    return keyboard

def get_cancel_keyboard():
    kb = [
        [KeyboardButton(text="❌ Отменить")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    return keyboard

async def create_tags_keyboard(user_id: int):
    tags = await get_user_tags(user_id)
    if not tags:
        return None
    
    kb = []
    for tag, count in tags:
        kb.append([KeyboardButton(text=f"{tag} ({count})")])
    kb.append([KeyboardButton(text="❌ Отменить")])
    
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

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
        "Привет! Я бот для сохранения заметок. Выберите действие:",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "Добавить запись")
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
    
    await state.update_data(user_text=message.text)
    
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
        # Создаем клавиатуру с существующими тегами и опцией создания нового
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Создать новый тег")],
                [KeyboardButton(text="❌ Отменить")]
            ],
            resize_keyboard=True
        )
        
        # Добавляем существующие теги
        tags = await get_user_tags(message.from_user.id)
        if tags:
            for tag, _ in tags:
                keyboard.keyboard.insert(-1, [KeyboardButton(text=tag)])
        
        await message.answer(
            "Выберите существующий тег или создайте новый:",
            reply_markup=keyboard
        )
        await state.set_state(UserState.waiting_for_tag)
    elif message.text.lower() == "нет":
        data = await state.get_data()
        user_text = data.get("user_text")
        
        save_result = await save_message(message.from_user.id, user_text, "no_tag")
        
        if save_result:
            await message.answer(
                "Сообщение сохранено без тега!",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer(
                "Такая запись уже существует!",
                reply_markup=get_main_keyboard()
            )
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
    
    data = await state.get_data()
    user_text = data.get("user_text")
    creating_new_tag = data.get("creating_new_tag", False)
    
    # Если это не создание нового тега, значит выбран существующий
    if not creating_new_tag:
        save_result = await save_message(message.from_user.id, user_text, message.text)
        
        if save_result:
            await message.answer(
                "Сообщение успешно сохранено с выбранным тегом!",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer(
                "Такая запись уже существует!",
                reply_markup=get_main_keyboard()
            )
        await state.clear()
    else:
        # Сохраняем с новым тегом
        save_result = await save_message(message.from_user.id, user_text, message.text)
        
        if save_result:
            await message.answer(
                "Сообщение успешно сохранено с новым тегом!",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer(
                "Такая запись уже существует!",
                reply_markup=get_main_keyboard()
            )
        await state.clear()

@dp.message(F.text == "Просмотреть записи")
async def view_records(message: types.Message):
    if not await check_access(message):
        return
    
    records = await get_user_messages(message.from_user.id)
    if not records:
        await message.answer(
            "У вас пока нет сохраненных записей.",
            reply_markup=get_main_keyboard()
        )
        return

    response = "Ваши записи:\n\n"
    for i, (text, tag, timestamp) in enumerate(records, 1):
        response += f"{i}. Текст: {text}\nТег: {tag}\nВремя: {timestamp}\n\n"
        
        if len(response) > 3500:
            await message.answer(response)
            response = ""
    
    if response:
        await message.answer(response)
    
    await message.answer(
        "Выберите следующее действие:",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "Поиск по тегу")
async def search_by_tag(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    
    keyboard = await create_tags_keyboard(message.from_user.id)
    if not keyboard:
        await message.answer(
            "У вас пока нет сохраненных тегов.",
            reply_markup=get_main_keyboard()
        )
        return
    
    await message.answer(
        "Выберите тег для поиска:",
        reply_markup=keyboard
    )
    await state.set_state(UserState.waiting_for_tag_selection)

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
    
    # Извлекаем тег из формата "тег (количество)"
    tag = message.text.split(" (")[0]
    
    records = await get_messages_by_tag(message.from_user.id, tag)
    if not records:
        await message.answer(
            f"Записи с тегом '{tag}' не найдены.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return

    response = f"Записи с тегом '{tag}':\n\n"
    for i, (text, tag, timestamp) in enumerate(records, 1):
        response += f"{i}. Текст: {text}\nВремя: {timestamp}\n\n"
        
        if len(response) > 3500:
            await message.answer(response)
            response = ""
    
    if response:
        await message.answer(response)
    
    await message.answer(
        "Выберите следующее действие:",
        reply_markup=get_main_keyboard()
    )
    await state.clear()

@dp.message(F.text == "Удалить всё")
async def confirm_deletion(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    
    await message.answer(
        "Вы хотите удалить все записи?",
        reply_markup=get_tag_choice_keyboard()
    )
    await state.set_state(UserState.waiting_for_deletion_confirmation)

@dp.message(UserState.waiting_for_deletion_confirmation)
async def process_deletion(message: types.Message, state: FSMContext):
    if not await check_access(message):
        return
    
    if message.text.lower() == "да":
        await delete_all_user_messages(message.from_user.id)
        await message.answer(
            "Все записи успешно удалены!",
            reply_markup=get_main_keyboard()
        )
    elif message.text.lower() == "нет":
        await message.answer(
            "Удаление отменено.",
            reply_markup=get_main_keyboard()
        )
    
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
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
