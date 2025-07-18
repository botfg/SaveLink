from aiogram.fsm.state import State, StatesGroup

class UserState(StatesGroup):
    # Существующие состояния
    waiting_for_text = State()
    waiting_for_name = State()
    waiting_for_tag_choice = State()
    waiting_for_tag = State()
    waiting_for_deletion_confirmation = State()
    waiting_for_final_confirmation = State()
    waiting_for_tag_selection = State()
    waiting_for_restore_confirmation = State()
    editing_record_name = State()
    editing_record_link = State()
    editing_record_tag = State()