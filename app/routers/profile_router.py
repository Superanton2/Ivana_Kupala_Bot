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
    waiting_for_new_mail = State()
    waiting_for_new_education = State()
    waiting_for_new_faculty = State()
    waiting_for_new_group = State()


@router.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    tg_id = callback.from_user.id

    user = await get_user(tg_id)
    if not user:
        await callback.message.answer("Профіль не знайдено. Спочатку зареєструйся.")
        await callback.answer()
        return

    status_map = {
        "pending": "Очікує оплати ⏳",
        "processing": "На перевірці адміністратором ⏳",
        "success": "Оплачено ✅"
    }
    payment_status = status_map.get(user.status, "Невідомо")
    quest_text = "Так 🗺" if user.quest_participation else "Ні ❌"

    text = (
        f"👤 <b>ТВІЙ ПРОФІЛЬ</b>\n"
        f"───────────────\n"
        f"<b>ПІБ:</b> {user.name}\n"
        f"<b>Пошта:</b> {user.mail}\n"
        f"<b>Навчання:</b> {user.education}\n"
    )

    # Динамічне відображення залежно від університету
    if user.education == "KSE":
        if user.faculty: text += f"<b>Програма:</b> {user.faculty}\n"
        if user.group: text += f"<b>Рік випуску:</b> {user.group}\n"
    elif user.education == "КПІ ім. Ігоря Сікорського":
        if user.faculty and user.faculty != "не навчаюсь":
            text += f"<b>Факультет:</b> {user.faculty}\n"
        if user.group:
            text += f"<b>Група:</b> {user.group}\n"
    else:
        if user.faculty and user.faculty != "не навчаюсь":
            text += f"<b>Факультет/Напрям:</b> {user.faculty}\n"

    text += (
        f"<b>Участь у квесті:</b> {quest_text}\n"
        f"───────────────\n"
        f"🎟 <b>Статус квитка:</b> {payment_status}"
    )

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
    builder.button(text="✏️ Пошта", callback_data="edit_prof_mail")
    builder.button(text="✏️ Навчальний заклад", callback_data="edit_prof_education")

    if user.education == "KSE":
        builder.button(text="✏️ Програма", callback_data="edit_prof_faculty")
        builder.button(text="✏️ Рік випуску", callback_data="edit_prof_group")
    else:
        builder.button(text="✏️ Факультет", callback_data="edit_prof_faculty")
        builder.button(text="✏️ Група", callback_data="edit_prof_group")

    quest_btn_text = "❌ Скасувати участь у квесті" if user.quest_participation else "🗺 Додати участь у квесті"
    builder.button(text=quest_btn_text, callback_data="toggle_quest_prof")

    builder.button(text="Назад до профілю", callback_data="profile")

    builder.adjust(2, 1, 2, 1, 1)

    await callback.message.edit_text(
        "⚙️ <b>Що саме ти хочеш змінити?</b>\n\n"
        "<i>*Якщо ти змінюєш університет, не забудь також змінити факультет/програму та групу/рік!</i>",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_quest_prof")
async def toggle_quest_in_profile(callback: types.CallbackQuery, state: FSMContext):
    """Миттєво змінює статус участі у квесті на протилежний"""
    tg_id = callback.from_user.id
    user = await get_user(tg_id)

    new_val = not user.quest_participation

    await update_user_field(tg_id, "quest_participation", new_val)
    asyncio.create_task(update_user_in_sheet(tg_id, "quest_participation", new_val))

    await callback.answer("✅ Статус квесту оновлено!")
    await show_profile(callback, state)


@router.callback_query(F.data.startswith("edit_prof_"))
async def start_edit_text_field(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_prof_", "")

    prompts = {
        "name": "Введи нове ПІБ:",
        "mail": "Введи нову електронну пошту:",
        "education": "Введи назву твого нового навчального закладу (наприклад: KSE, КПІ ім. Ігоря Сікорського):",
        "faculty": "Введи нову програму або факультет:",
        "group": "Введи нову групу або рік випуску:"
    }

    states = {
        "name": ProfileForm.waiting_for_new_name,
        "mail": ProfileForm.waiting_for_new_mail,
        "education": ProfileForm.waiting_for_new_education,
        "faculty": ProfileForm.waiting_for_new_faculty,
        "group": ProfileForm.waiting_for_new_group
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
@router.message(ProfileForm.waiting_for_new_mail, F.text)
@router.message(ProfileForm.waiting_for_new_education, F.text)
@router.message(ProfileForm.waiting_for_new_faculty, F.text)
@router.message(ProfileForm.waiting_for_new_group, F.text)
async def save_text_field(message: types.Message, state: FSMContext):
    current_state = await state.get_state()

    state_to_field = {
        ProfileForm.waiting_for_new_name.state: "name",
        ProfileForm.waiting_for_new_mail.state: "mail",
        ProfileForm.waiting_for_new_education.state: "education",
        ProfileForm.waiting_for_new_faculty.state: "faculty",
        ProfileForm.waiting_for_new_group.state: "group"
    }
    field_to_update = state_to_field.get(current_state)
    input_text = message.text.strip()

    if field_to_update == "mail":
        if "@" not in input_text or len(input_text) < 5:
            await message.answer(
                "❌ Некоректна пошта. Вона має містити символ @. Спробуй ще раз:")
            return

    if field_to_update in ["faculty", "group"]:
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