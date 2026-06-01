import os
from dotenv import load_dotenv
load_dotenv()
SHEET_URL = os.getenv("SHEET_URL")
MONO_URL = os.getenv("MONO_URL")

from app.data.bot_state import global_state
from aiogram.utils.keyboard import InlineKeyboardBuilder

def create_main_keyboard(state: str= "pending") -> InlineKeyboardBuilder:
    """

    :param state: pending / processing / success
    :return:
    """
    builder = InlineKeyboardBuilder()
    if state == "pending":
        builder.button( text="📝 Зареєструватись", callback_data="registration")
    elif state == "processing":
        builder.button( text="🎟 Оплатити квиток", callback_data="payment")
    elif state == "success":
        builder.button( text="🪪 Профіль", callback_data="profile")

    builder.button( text="❓ Часті Питання", callback_data="handle_questions")

    return builder

def create_main_admin_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Зареєструватись", callback_data="registration")
    builder.button(text="🎟 Оплатити квиток", callback_data="payment")
    builder.button(text="🪪 Профіль", callback_data="profile")
    builder.button(text="❓ Часті Питання", callback_data="handle_questions")

    builder.button(text="💰 Банка", url=MONO_URL, style="primary")
    builder.button(text="📊 Google табличка", url=SHEET_URL, style="primary")
    status = "✅ ВІДКРИТА" if global_state["registration_open"] else "❌ ЗАКРИТА"
    if status == "✅ ВІДКРИТА":
        text = "🔐Закрити реєстрацію"
    else:
        text ="🔓Вікрити реєстрацію"
    builder.button(text=text, callback_data="admin_stop_registration", style="primary")
    builder.button(text="📨Написати учасникам", callback_data="admin_write_participants", style="primary") # зареєустровані/всі учасники
    builder.adjust(1)
    return builder