from dotenv import load_dotenv

from aiogram import F
from aiogram.filters import Command
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import app.utils.keyboards as kb
from app.db.db_requests import is_admin, get_user

from app.routers.admin_router import router as admin_router
from app.routers.registration_router import router as registration_router
from app.routers.profile_router import router as profile_router
from app.routers.faq_router import router as faq_router
from app.routers.payment_router import router as payment_router

load_dotenv()
router = Router()
router.include_routers(
    admin_router,
    registration_router,
    profile_router,
    faq_router,
    payment_router,
)

async def safe_reply(message: types.Message, text: str, reply_markup=None):
    try:
        return await message.edit_text(text=text, reply_markup=reply_markup,
                                        parse_mode="HTML", disable_web_page_preview=True)
    except TelegramBadRequest:
        return await message.answer(text=text, reply_markup=reply_markup, parse_mode="HTML",
                                    disable_web_page_preview=True)



@router.message(Command("start"))
async def cmd_start(message: types.Message):

    is_user_admin = await is_admin(message.from_user.id)
    existing_user = await get_user(message.from_user.id)

    text = "👋 Вітаю! Я бот для реєстрації на Івана Купала. "
    if is_user_admin:
        keyboard = kb.create_main_admin_keyboard()
        text += ("\n\n───────────────\n"
                "Ти маєш права Адміна\nОбери дію:\n")
    elif existing_user:
        keyboard = kb.create_main_keyboard(is_existing_user=existing_user)
        text = "Ти вже зареєстрований. Дата події 21 червня!\n"
    else:
        text += "Ти не зареєстрований, для того щоб потрапити на захід треба зареєструватись."
        keyboard = kb.create_main_keyboard(is_existing_user=existing_user)

    await message.reply(
        text= text,
        reply_markup= keyboard.as_markup()
    )

@router.callback_query(F.data.in_(["controller_hub", "controller_hub_new"]))
async def cmd_back_hub(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.clear()

    is_user_admin = await is_admin(callback.from_user.id)
    existing_user = await get_user(callback.from_user.id)

    text = "👋 Вітаю! Я бот для реєстрації на Івана Купала. "
    if is_user_admin:
        keyboard = kb.create_main_admin_keyboard()
        text += ("\n\n───────────────\n"
                "Ти маєш права Адміна\nОбери дію:\n")
    elif existing_user:
        keyboard = kb.create_main_keyboard(is_existing_user=existing_user)
        text = "Ти вже зареєстрований. Дата події 21 червня!\n"
    else:
        text += "Ти не зареєстрований, для того щоб потрапити на захід треба зареєструватись."
        keyboard = kb.create_main_keyboard(is_existing_user=existing_user)


    if callback.data == "controller_hub_new":
        await safe_reply(
            message=callback.message,
            text=text,
            reply_markup=keyboard.as_markup()
        )
    else:
        await callback.message.answer(
            text=text,
            reply_markup=keyboard.as_markup()
        )

    await callback.answer()