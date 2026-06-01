from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

import os
import asyncio
from dotenv import load_dotenv

from app.db.db_requests import get_user, update_payment_status
from app.utils.google_sheets import update_user_in_sheet

load_dotenv()
router = Router()

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
MONO_URL = os.getenv("MONO_URL")


class PaymentForm(StatesGroup):
    waiting_for_receipt = State()


# ==================== СТОРОНА КОРИСТУВАЧА ====================

@router.callback_query(F.data == "payment")
async def start_payment(callback: types.CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    if not user:
        return await callback.answer("Ти не зареєстрований!", show_alert=True)

    if user.status == "success":
        return await callback.answer("✅ Ти вже оплатив квиток!", show_alert=True)
    elif user.status == "processing":
        return await callback.answer("⏳ Твоя квитанція зараз на перевірці!", show_alert=True)

    text = (
        "🎟 <b>Оплата квитка</b>\n\n"
        "Вартість квитка: <b>150 грн</b>\n\n"
        "1️⃣ Перейди за посиланням на банку:\n"
        f"👉 <a href='{MONO_URL}'>Монобанка</a>\n\n"
        "2️⃣ Зроби переказ на вказану суму.\n"
        "3️⃣ <b>Надішли сюди фотографію (скріншот) квитанції</b> або екрану успішного переказу.\n\n"
        "<i>(Якщо передумав платити зараз, натисни Скасувати)</i>"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="Скасувати", callback_data="cancel_payment", style="danger")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), disable_web_page_preview=True)
    await state.set_state(PaymentForm.waiting_for_receipt)
    await callback.answer()


@router.callback_query(PaymentForm.waiting_for_receipt, F.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.button(text="Головне меню", callback_data="controller_hub_new", style="primary")
    await callback.message.edit_text("❌ Оплату скасовано. Ти можеш повернутися до неї пізніше.",
                                     reply_markup=builder.as_markup())
    await callback.answer()


@router.message(PaymentForm.waiting_for_receipt, F.photo | F.document)
async def receive_receipt(message: types.Message, state: FSMContext):
    tg_id = message.from_user.id
    user = await get_user(tg_id)

    await update_payment_status(tg_id, "processing")
    asyncio.create_task(update_user_in_sheet(tg_id, "status", "processing"))


    builder = InlineKeyboardBuilder()
    builder.button(text="Головне меню", callback_data="controller_hub_new")
    await message.answer(
        "✅ <b>Квитанцію отримано!</b>\n\n"
        "Вона відправлена на перевірку адміністраторам. Це може зайняти деякий час. "
        "Ми повідомимо тебе про результат (перевірка відбувається вручну).",
        reply_markup=builder.as_markup()
    )
    await state.clear()

    if not ADMIN_CHAT_ID:
        print("ПОМИЛКА: Не вказано ADMIN_CHAT_ID у .env")
        return

    username_display = user.username if user.username != "немає" else "Без юзернейму"

    caption = (
        f"💰 <b>Нова заявка на оплату</b>\n\n"
        f"👤 <b>ПІБ:</b> {user.name} ({username_display})\n"
        f"🎓 <b>Навчання:</b> {user.education}\n"
        f"🏛 <b>Фак/Програма:</b> {user.faculty}\n"
        f"👥 <b>Група/Рік:</b> {user.group}\n\n"
        f"Очікує перевірки."
    )

    admin_kb = InlineKeyboardBuilder()
    admin_kb.button(text="Підтвердити", callback_data=f"appr_pay_{tg_id}", style="success")
    admin_kb.button(text="Відхилити", callback_data=f"rej_pay_{tg_id}", style="danger")

    try:
        if message.photo:
            await message.bot.send_photo(
                chat_id=int(ADMIN_CHAT_ID),
                photo=message.photo[-1].file_id, # Беремо найкращу якість
                caption=caption,
                reply_markup=admin_kb.as_markup()
            )
        elif message.document:
            await message.bot.send_document(
                chat_id=int(ADMIN_CHAT_ID),
                document=message.document.file_id,
                caption=caption,
                reply_markup=admin_kb.as_markup()
            )
    except Exception as e:
        print(f"Помилка відправки квитанції в адмін-чат: {e}")


@router.message(PaymentForm.waiting_for_receipt)
async def receive_receipt_invalid(message: types.Message):
    # текст, стікер, кружечок тощо
    await message.answer("❌ Будь ласка, надішли <b>фотографію</b> або <b>файл (PDF/зображення)</b> з квитанцією.")



# ==================== СТОРОНА АДМІНІСТРАТОРІВ ====================

@router.callback_query(F.data.startswith("appr_pay_") | F.data.startswith("rej_pay_"))
async def admin_first_click(callback: types.CallbackQuery):
    """Перший клік: Блокування заявки іншим адмінам і запит підтвердження"""

    if callback.message.caption and "⏳" in callback.message.caption:
        return await callback.answer("Цю заявку вже обробляє інший адміністратор!", show_alert=True)

    action = "appr" if callback.data.startswith("appr") else "rej"
    tg_id = callback.data.split("_")[2]

    admin_username = callback.from_user.username or callback.from_user.first_name
    new_caption = callback.message.caption + f"\n\n⏳ <i>Заявку перевіряє @{admin_username}...</i>"

    builder = InlineKeyboardBuilder()
    if action == "appr":
        builder.button(text="⚠️ Точно підтвердити?", callback_data=f"conf_appr_{tg_id}")
    else:
        builder.button(text="⚠️ Точно відхилити?", callback_data=f"conf_rej_{tg_id}")

    builder.button(text="⬅️ Скасувати мою дію", callback_data=f"cancel_act_{tg_id}")
    builder.adjust(1)

    try:
        await callback.message.edit_caption(caption=new_caption, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        pass

    await callback.answer()


@router.callback_query(F.data.startswith("cancel_act_"))
async def admin_cancel_action(callback: types.CallbackQuery):
    """Якщо адмін передумав — повертаємо повідомлення у початковий стан"""
    tg_id = callback.data.split("_")[2]

    # Відрізаємо доданий рядок "⏳ Заявку перевіряє..."
    old_caption = callback.message.caption.split("\n\n⏳")[0]

    builder = InlineKeyboardBuilder()
    builder.button(text="Підтвердити", callback_data=f"appr_pay_{tg_id}", style="success")
    builder.button(text="Відхилити", callback_data=f"rej_pay_{tg_id}", style="danger")

    try:
        await callback.message.edit_caption(caption=old_caption, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        pass

    await callback.answer("Твою дію скасовано. Заявка знову відкрита.")


@router.callback_query(F.data.startswith("conf_appr_") | F.data.startswith("conf_rej_"))
async def admin_confirm_action(callback: types.CallbackQuery):
    """Фінальне рішення: Оновлення БД, відправка логу та повідомлення юзеру"""
    action = "appr" if callback.data.startswith("conf_appr") else "rej"
    tg_id = int(callback.data.split("_")[2])

    user = await get_user(tg_id)
    if not user:
        return await callback.answer("Помилка: Користувача не знайдено в базі!", show_alert=True)

    admin_username = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.first_name

    try:
        if action == "appr":
            # 1. Оновлюємо БД
            await update_payment_status(tg_id, "success")
            asyncio.create_task(update_user_in_sheet(tg_id, "status", "success"))

            # 2. Сповіщаємо юзера
            await callback.bot.send_message(
                chat_id=tg_id,
                text=(
                    "🎉 <b>Твою оплату підтверджено!</b> Ти в списках учасників.\n\n"
                    "Чекаємо на тебе 21 червня на святкуванні Івана Купала!\n"
                    "📍 <b>Місце:</b> Вулиця Миколи Шпака, 3\n"
                    "⏰ <b>Час:</b> Буде повідомлено згодом"
                )
            )

            # 3. Формуємо лог для адмін чату
            log_text = f"🟢 <b>ОПЛАЧЕНО:</b> {user.name}.\nПідтвердив(ла): {admin_username}"

        else:
            # 1. Оновлюємо БД назад до pending
            await update_payment_status(tg_id, "pending")
            asyncio.create_task(update_user_in_sheet(tg_id, "status", "pending"))

            # 2. Сповіщаємо юзера
            await callback.bot.send_message(
                chat_id=tg_id,
                text=(
                    "❌ <b>Оплату не підтверджено.</b>\n\n"
                    "Адміністратори не змогли знайти твій платіж або сума/реквізити некоректні. "
                    "Будь ласка, перевір дані або спробуй надіслати квитанцію ще раз через меню."
                )
            )

            # 3. Формуємо лог для адмін чату
            log_text = f"🔴 <b>ВІДХИЛЕНО:</b> {user.name}.\nВідхилив(ла): {admin_username}"

        # Видаляємо громіздке повідомлення з фото
        await callback.message.delete()
        # Надсилаємо акуратний текстовий лог
        await callback.message.answer(log_text)

    except Exception as e:
        print(f"Помилка при обробці фінального рішення: {e}")
        await callback.answer("Виникла помилка. Перевір консоль (логи).", show_alert=True)

    await callback.answer()