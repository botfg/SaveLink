from aiogram.fsm.state import State, StatesGroup

class UserState(StatesGroup):
    waiting_for_text = State()
    waiting_for_name = State()
    waiting_for_tag_choice = State()
    waiting_for_tag = State()
    waiting_for_deletion_confirmation = State()
    waiting_for_final_confirmation = State()
    waiting_for_tag_selection = State()