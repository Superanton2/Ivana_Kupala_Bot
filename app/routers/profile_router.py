from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.db_requests import get_user, update_user_field
from app.utils.google_sheets import update_user_in_sheet

import asyncio

router = Router()


class ProfileForm(StatesGroup):
    waiting_for_new_name = State()
    waiting_for_new_phone = State()
    waiting_for_new_mail = State()
    waiting_for_new_education = State()
    waiting_for_new_faculty = State()


@router.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    tg_id = callback.from_user.id

    user = await get_user(tg_id)
    if not user:
        await callback.message.answer("Профіль не знайдено. Спочатку зареєструйся.")
        await callback.answer()
        return

    text = (
        f"👤 <b>ТВІЙ ПРОФІЛЬ</b>\n"
        f"───────────────\n"
        f"<b>ПІБ:</b> {user.name}\n"
        f"<b>Телефон:</b> {user.phone}\n"
        f"<b>Пошта:</b> {user.mail}\n"
        f"<b>Навчання:</b> {user.education}\n"
    )

    if user.faculty != "не навчаюсь":
        text += f"<b>Факультет:</b> {user.faculty}\n"

    text += f"───────────────\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="⚙️ Змінити дані", callback_data="prof_edit_menu")
    builder.button(text="Назад", callback_data="controller_hub_new")
    builder.adjust(1)

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup())

    await callback.answer()


@router.callback_query(F.data == "prof_edit_menu")
async def edit_profile_menu(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    user = await get_user(tg_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ ПІБ", callback_data="edit_prof_name")
    builder.button(text="✏️ Телефон", callback_data="edit_prof_phone")
    builder.button(text="✏️ Пошта", callback_data="edit_prof_mail")
    builder.button(text="✏️ Навчальний заклад", callback_data="edit_prof_education")

    if user and user.faculty != "не навчаюсь":
        builder.button(text="✏️ Факультет", callback_data="edit_prof_faculty")
        builder.adjust(2, 2, 1, 1)
    else:
        builder.adjust(2, 2, 1)

    builder.button(text="Назад до профілю", callback_data="profile")

    await callback.message.edit_text("⚙️ <b>Що саме ти хочеш змінити?</b>", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_prof_"))
async def start_edit_text_field(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_prof_", "")

    prompts = {
        "name": "Введіть нове ПІБ:",
        "phone": "Введи новий номер телефону (наприклад, 095027...):",
        "mail": "Введи нову електронну пошту:",
        "education": "Введи назву твого нового навчального закладу (або 'не навчаюсь'):",
        "faculty": "Введи назву твого нового факультету:"
    }

    states = {
        "name": ProfileForm.waiting_for_new_name,
        "phone": ProfileForm.waiting_for_new_phone,
        "mail": ProfileForm.waiting_for_new_mail,
        "education": ProfileForm.waiting_for_new_education,
        "faculty": ProfileForm.waiting_for_new_faculty
    }

    prompt = prompts.get(field)
    target_state = states.get(field)

    await state.set_state(target_state)

    builder = InlineKeyboardBuilder()
    builder.button(text="Скасувати", callback_data="prof_edit_menu")

    new_msg = await callback.message.edit_text(prompt, reply_markup=builder.as_markup())
    await state.update_data(main_message_id=new_msg.message_id)
    await callback.answer()


@router.message(ProfileForm.waiting_for_new_name, F.text)
@router.message(ProfileForm.waiting_for_new_phone, F.text)
@router.message(ProfileForm.waiting_for_new_mail, F.text)
@router.message(ProfileForm.waiting_for_new_education, F.text)
@router.message(ProfileForm.waiting_for_new_faculty, F.text)
async def save_text_field(message: types.Message, state: FSMContext):
    current_state = await state.get_state()

    state_to_field = {
        ProfileForm.waiting_for_new_name.state: "name",
        ProfileForm.waiting_for_new_phone.state: "phone",
        ProfileForm.waiting_for_new_mail.state: "mail",
        ProfileForm.waiting_for_new_education.state: "education",
        ProfileForm.waiting_for_new_faculty.state: "faculty"
    }
    field_to_update = state_to_field.get(current_state)
    input_text = message.text.strip()

    if field_to_update == "phone":
        input_text = input_text.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace("+", "")
        if input_text.startswith("380"):
            input_text = input_text[2:]

        if not input_text.isdigit() or len(input_text) != 10:
            await message.answer(
                "❌ Некоректний номер телефону. Він має містити лише 10 цифр (наприклад, 0123456789). Спробуй ще раз:")
            return

    if field_to_update == "mail":
        if "@" not in input_text or input_text.lower() == "email@example.com":
            await message.answer(
                "❌ Некоректна пошта. Вона має містити символ @ і не бути email@example.com. Спробуй ще раз:")
            return

    if field_to_update == "education" and input_text.lower() == "не навчаюсь":
        await update_user_field(message.from_user.id, "faculty", "не навчаюсь")
        asyncio.create_task(update_user_in_sheet(tg_id=message.from_user.id, field="faculty", new_value="не навчаюсь"))

    if field_to_update == "faculty":
        input_text = input_text.upper()

    await update_user_field(message.from_user.id, field_to_update, input_text)

    asyncio.create_task(update_user_in_sheet(
        tg_id=message.from_user.id,
        field=field_to_update,
        new_value=input_text
    ))

    data = await state.get_data()

    try:
        await message.delete()
    except Exception:
        pass
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=data.get("main_message_id"))
    except Exception:
        pass

    builder = InlineKeyboardBuilder()
    builder.button(text="Повернутися в профіль", callback_data="profile", style="primary")
    await message.answer("✅ Дані успішно оновлено!", reply_markup=builder.as_markup())
    await state.clear()