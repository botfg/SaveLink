from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, 
    InlineKeyboardButton
)

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает основную клавиатуру."""
    kb = [
        [KeyboardButton(text="📋 Просмотреть записи")],
        [KeyboardButton(text="🔍 Поиск по тегу")],
        [KeyboardButton(text="⚙️ Дополнительно")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_extra_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру с дополнительными действиями."""
    kb = [
        [KeyboardButton(text="📤 Создать резервную копию")],
        # (ИЗМЕНЕНИЕ): Новая кнопка для восстановления
        [KeyboardButton(text="📥 Восстановить из бекапа")],
        [KeyboardButton(text="🗑 Удалить всё")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_tag_choice_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для выбора добавления тега."""
    kb = [
        [KeyboardButton(text="Да")],
        [KeyboardButton(text="Нет")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру с кнопкой отмены."""
    kb = [
        [KeyboardButton(text="❌ Отменить")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_skip_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру с кнопками 'Пропустить' и 'Отменить'."""
    kb = [
        [KeyboardButton(text="⏩ Пропустить")],
        [KeyboardButton(text="❌ Отменить")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def create_tags_keyboard(tags: list) -> ReplyKeyboardMarkup | None:
    """Создает клавиатуру с существующими тегами, принимая их как аргумент."""
    if not tags:
        return None

    kb_buttons = []
    for tag, count in tags:
        display_text = "Без тега" if tag == "no_tag" else tag
        kb_buttons.append([KeyboardButton(text=f"{display_text} ({count})")])

    if not kb_buttons:
        return None

    kb_buttons.append([KeyboardButton(text="❌ Отменить")])
    return ReplyKeyboardMarkup(keyboard=kb_buttons, resize_keyboard=True)


def get_delete_confirmation_keyboard(record_id: int) -> InlineKeyboardMarkup:
    """Возвращает inline-клавиатуру для подтверждения удаления записи."""
    kb = [
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_del_{record_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel_del_{record_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
