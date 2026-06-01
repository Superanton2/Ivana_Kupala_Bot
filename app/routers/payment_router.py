from aiogram import Router, F, types

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data.csv_handler import CSVHandler

router = Router()
handler = CSVHandler()


# [key: id -> question,answer]
@router.callback_query(F.data == "payment")
async def show_faq(callback: types.CallbackQuery):
    questions = handler.get_questions()
    if not questions:
        await callback.answer("Помилка: Файл питань порожній або не знайдений", show_alert=True)
        return

    builder = InlineKeyboardBuilder()

    builder.button(text="")

    await callback.message.answer("payment:\n", reply_markup=builder.as_markup())
    await callback.answer()