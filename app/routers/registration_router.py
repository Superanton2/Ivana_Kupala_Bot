from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardRemove

from app.data.bot_state import global_state
from app.utils.google_sheets import add_user_to_sheet
from app.db.db_requests import add_user, get_user
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()
router = Router()


class RegisterForm(StatesGroup):
    entering_name = State()
    entering_mail = State()
    choosing_education = State()

    # Гілка КПІ
    choosing_faculty_kpi = State()
    entering_faculty_text_kpi = State()
    entering_group_kpi = State()

    # Гілка KSE
    entering_program_kse = State()
    choosing_grad_year_kse = State()

    # Спільні кроки
    agreeing_to_rules = State()
    choosing_quest = State()
    waiting_confirmation = State()


@router.callback_query(F.data == "registration")
async def start_registration(callback: types.CallbackQuery, state: FSMContext):
    if not global_state.get("registration_open", True):
        await callback.answer("На жаль, реєстрація вже закрита ❌", show_alert=True)
        return

    existing_user = await get_user(callback.from_user.id)

    if existing_user:
        builder = InlineKeyboardBuilder()
        builder.button(text="🪪 Перейти в профіль", callback_data="profile")
        builder.button(text="Головне меню", callback_data="controller_hub", style="primary")

        await callback.message.edit_text(
            "❌ <b>Ти вже зареєстрований на цей захід!</b>\n\n"
            "Якщо ти хочеш змінити свої дані, перейди у свій Профіль.",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    new_msg = await callback.message.answer(
        "[1/6] 👤 Введи твоє ПІБ\nПриклад: Корнага Ярослав Ігорович\n\n"
        "<i>*після підтвердження реєстрації дані можна змінити в профілі</i>",
        reply_markup=ReplyKeyboardRemove()
    )

    await state.update_data(main_message_id=new_msg.message_id)
    await state.set_state(RegisterForm.entering_name)
    await callback.answer()


@router.message(RegisterForm.entering_name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    data = await state.get_data()
    main_msg_id = data.get("main_message_id")

    try:
        await message.delete()
    except Exception:
        pass
    if main_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=main_msg_id)
        except Exception:
            pass

    new_msg = await message.answer(
        "[2/6] ✉️ Введи твою електронну пошту\nПриклад: email@example.com"
    )

    await state.update_data(main_message_id=new_msg.message_id)
    await state.set_state(RegisterForm.entering_mail)


@router.message(RegisterForm.entering_mail, F.text)
async def process_mail(message: types.Message, state: FSMContext):
    mail_input = message.text.strip()

    if "@" not in mail_input or len(mail_input) < 5:
        await message.answer("❌ Некоректна пошта! Спробуй ще раз:")
        return

    await state.update_data(mail=mail_input)
    data = await state.get_data()
    main_msg_id = data.get("main_message_id")

    try:
        await message.delete()
    except Exception:
        pass
    if main_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=main_msg_id)
        except Exception:
            pass

    builder = InlineKeyboardBuilder()
    builder.button(text="🎓 КПІ ім. Ігоря Сікорського", callback_data="edu_kpi")
    builder.button(text="🏫 KSE (Київська школа економіки)", callback_data="edu_kse")
    builder.adjust(1)

    new_msg = await message.answer(
        "[3/6] Обери свій навчальний заклад:",
        reply_markup=builder.as_markup()
    )

    await state.update_data(main_message_id=new_msg.message_id)
    await state.set_state(RegisterForm.choosing_education)


# ==================== РОЗГАЛУЖЕННЯ НАВЧАЛЬНИХ ЗАКЛАДІВ ====================

@router.callback_query(RegisterForm.choosing_education, F.data.startswith("edu_"))
async def process_education_choice(callback: types.CallbackQuery, state: FSMContext):
    choice = callback.data

    if choice == "edu_kpi":
        await state.update_data(education="КПІ ім. Ігоря Сікорського")
        builder = InlineKeyboardBuilder()
        builder.button(text="ФІОТ", callback_data="fac_fiot")
        builder.button(text="🏫 Інший", callback_data="fac_other")
        builder.adjust(1)

        await callback.message.edit_text(
            "[4/6] 🏛 Обери або твого факультету:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(RegisterForm.choosing_faculty_kpi)

    elif choice == "edu_kse":
        await state.update_data(education="KSE")
        await callback.message.edit_text(
            "[4/6] 📚 На якій програмі ти навчаєшся?\nПриклад: AI"
        )
        await state.set_state(RegisterForm.entering_program_kse)

    await callback.answer()


# ----------------- ГІЛКА КПІ -----------------

@router.callback_query(RegisterForm.choosing_faculty_kpi, F.data.startswith("fac_"))
async def process_kpi_faculty_choice(callback: types.CallbackQuery, state: FSMContext):
    choice = callback.data

    if choice == "fac_fiot":
        await state.update_data(faculty="ФІОТ")
        await callback.message.edit_text("[5/6] 👥 Введи групу в якій ти вчишся\nПриклад: ІА-11:")
        await state.set_state(RegisterForm.entering_group_kpi)
    else:
        await callback.message.edit_text("[4/6] 🏛 Введи назву твого факультету текстом:")
        await state.set_state(RegisterForm.entering_faculty_text_kpi)

    await callback.answer()


@router.message(RegisterForm.entering_faculty_text_kpi, F.text)
async def process_kpi_faculty_text(message: types.Message, state: FSMContext):
    await state.update_data(faculty=message.text.strip().upper())

    data = await state.get_data()
    main_msg_id = data.get("main_message_id")
    try:
        await message.delete()
        await message.bot.edit_message_text(chat_id=message.chat.id, message_id=main_msg_id,
                                            text="[5/6] 👥 Введи групу в якій ти вчишся\nПриклад: ІА-11:")
    except Exception:
        new_msg = await message.answer("[5/6] 👥 Введи групу в якій ти вчишся\nПриклад: ІА-11:")
        await state.update_data(main_message_id=new_msg.message_id)

    await state.set_state(RegisterForm.entering_group_kpi)


@router.message(RegisterForm.entering_group_kpi, F.text)
async def process_kpi_group(message: types.Message, state: FSMContext):
    await state.update_data(group=message.text.strip().upper())
    try:
        await message.delete()
    except Exception:
        pass
    await ask_for_rules(message, state)


# ----------------- ГІЛКА KSE -----------------

@router.message(RegisterForm.entering_program_kse, F.text)
async def process_kse_program(message: types.Message, state: FSMContext):
    await state.update_data(faculty=message.text.strip())  # Програму записуємо в faculty

    builder = InlineKeyboardBuilder()
    builder.button(text="2026", callback_data="year_2026")
    builder.button(text="2027", callback_data="year_2027")
    builder.button(text="2028", callback_data="year_2028")
    builder.button(text="2029", callback_data="year_2029")
    builder.adjust(1)

    data = await state.get_data()
    main_msg_id = data.get("main_message_id")
    text = "[5/6] 🎓 Обери рік в якому ти випускаєшся:"

    try:
        await message.delete()
        await message.bot.edit_message_text(chat_id=message.chat.id, message_id=main_msg_id,
                                            text=text, reply_markup=builder.as_markup())
    except Exception:
        new_msg = await message.answer(text, reply_markup=builder.as_markup())
        await state.update_data(main_message_id=new_msg.message_id)

    await state.set_state(RegisterForm.choosing_grad_year_kse)


@router.callback_query(RegisterForm.choosing_grad_year_kse, F.data.startswith("year_"))
async def process_kse_grad_year(callback: types.CallbackQuery, state: FSMContext):
    year = callback.data.split("_")[1]
    await state.update_data(group=year)  # Рік записуємо в group
    await callback.answer()
    await ask_for_rules(callback, state)


# ==================== СПІЛЬНЕ ЗАВЕРШЕННЯ ====================

async def ask_for_rules(event: types.Message | types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    main_msg_id = data.get("main_message_id")
    bot = event.bot
    chat_id = event.message.chat.id if isinstance(event, types.CallbackQuery) else event.chat.id

    rules_url = os.getenv("RULES_URL", "https://t.me")

    text = (
        f"[6/6] 📜 <b>Правила заходу</b>\n\n"
        f"Будь ласка, ознайомся із правилами нашого заходу за посиланням нижче:\n"
        f"👉 <a href='{rules_url}'>Читати правила</a>\n\n"
        f"Чи згоден ти їх дотримуватися?"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="Погоджуюсь", callback_data="agree_rules")

    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text=text, reply_markup=builder.as_markup(), disable_web_page_preview=True)
    else:
        if main_msg_id:
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=main_msg_id, text=text,
                                            reply_markup=builder.as_markup(), disable_web_page_preview=True)
            except Exception:
                new_msg = await event.answer(text=text, reply_markup=builder.as_markup(), disable_web_page_preview=True)
                await state.update_data(main_message_id=new_msg.message_id)

    await state.set_state(RegisterForm.agreeing_to_rules)


@router.callback_query(RegisterForm.agreeing_to_rules, F.data == "agree_rules")
async def process_agree_rules(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="Так, буду!", callback_data="quest_yes")
    builder.button(text="Ні, пропускаю", callback_data="quest_no")
    builder.adjust(2)

    await callback.message.edit_text(
        "🗺 <b>Квест</b>\n\n"
        "Чи плануєш ти приймати участь у тематичному квесті під час заходу?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(RegisterForm.choosing_quest)
    await callback.answer()


@router.callback_query(RegisterForm.choosing_quest, F.data.startswith("quest_"))
async def process_quest_choice(callback: types.CallbackQuery, state: FSMContext):
    quest_part = True if callback.data == "quest_yes" else False
    await state.update_data(quest_participation=quest_part)

    await show_confirmation_screen(callback, state)
    await callback.answer()


async def show_confirmation_screen(event: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    name = data.get('name')
    mail = data.get('mail')
    education = data.get('education')
    faculty = data.get('faculty')
    group = data.get('group')
    quest_part = data.get('quest_participation')

    quest_text = "Так" if quest_part else "Ні"

    confirmation_text = (
        f"📋 <b>Перевір твої дані перед підтвердженням:</b>\n\n"
        f"👤 <b>ПІБ:</b> {name}\n"
        f"✉️ <b>Пошта:</b> {mail}\n"
        f"🎓 <b>Навчання:</b> {education}\n"
    )

    if education == "KSE":
        confirmation_text += f"📚 <b>Програма:</b> {faculty}\n"
        confirmation_text += f"🎓 <b>Рік випуску:</b> {group}\n"
    else:
        confirmation_text += f"🏛 <b>Факультет:</b> {faculty}\n"
        confirmation_text += f"👥 <b>Група:</b> {group}\n"

    confirmation_text += f"🗺 <b>Участь у квесті:</b> {quest_text}\n\n"
    confirmation_text += "Усе правильно? Натисни підтвердити для завершення або скасуй реєстрацію."

    builder = InlineKeyboardBuilder()
    builder.button(text="Підтвердити реєстрацію", callback_data="confirm_registration", style="success")
    builder.button(text="Скасувати", callback_data="cancel_registration", style="danger")
    builder.adjust(1)

    await event.message.edit_text(text=confirmation_text, reply_markup=builder.as_markup())
    await state.set_state(RegisterForm.waiting_confirmation)


@router.callback_query(RegisterForm.waiting_confirmation, F.data == "confirm_registration")
async def confirm_registration(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    name = data.get('name')
    mail = data.get('mail')
    education = data.get('education')
    faculty = data.get('faculty')
    group = data.get('group')
    quest_part = data.get('quest_participation')

    tg_username = callback.from_user.username
    username_field = f"@{tg_username}" if tg_username else "немає"

    try:
        await add_user(
            tg_id=callback.from_user.id,
            username=username_field,
            name=name,
            mail=mail,
            education=education,
            faculty=faculty,
            group=group,
            quest_participation=quest_part
        )

        asyncio.create_task(add_user_to_sheet(
            tg_id=callback.from_user.id,
            username=username_field,
            name=name,
            mail=mail,
            education=education,
            faculty=faculty,
            group=group,
            quest_participation=quest_part
        ))

        builder = InlineKeyboardBuilder()
        builder.button(text="Головне меню", callback_data="controller_hub")

        await callback.message.edit_text(
            text=f"🎉 <b>Реєстрація успішна!</b>\n\nДані збережено. Очікуй на інформацію про час та місце проведення заходу.",
            reply_markup=builder.as_markup()
        )
        await state.clear()

    except Exception as e:
        logging.error(f"\033[31mПомилка БД під час реєстрації: {e}\033[0m")
        builder = InlineKeyboardBuilder()
        builder.button(text="Спробувати ще раз", callback_data="registration")

        await callback.message.edit_text(
            text="Виникла помилка під час збереження даних. Спробуй ще раз.",
            reply_markup=builder.as_markup()
        )
        await state.clear()

    await callback.answer()


@router.callback_query(RegisterForm.waiting_confirmation, F.data == "cancel_registration")
async def cancel_registration(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="Повернутись в меню", callback_data="controller_hub")

    await callback.message.edit_text(
        text="❌ <b>Реєстрацію скасовано.</b> Твої дані не було збережено в системі.",
        reply_markup=builder.as_markup()
    )
    await state.clear()
    await callback.answer()