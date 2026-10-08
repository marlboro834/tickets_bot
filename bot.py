import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8911166219:AAEUep9EMtIZ5IQyixwPBtGdNyycX7A491Y"
ADMIN_CHAT_ID = -1003887358876  # ID вашей группы администрации (со знаком минус)
# ============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# Состояния (FSM)
class TicketState(StatesGroup):
    waiting_for_category = State()
    waiting_for_message = State()
    waiting_for_admin_reply = State()


# 1. Главное меню для игрока (выбор категории тикета)
def get_categories_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛠 Техподдержка", callback_data="ticket_tech"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📺 Заявка на Медиа", callback_data="ticket_media"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💎 Проблемы с донатом",
                    callback_data="ticket_donate",
                )
            ],
        ]
    )
    return keyboard


# Клавиатура действий в админ-чате
def get_admin_action_keyboard(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Начать чат / Ответить",
                    callback_data=f"reply_{user_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Принять", callback_data=f"status_accept_{user_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"status_reject_{user_id}",
                ),
            ],
        ]
    )


# Старт для пользователя
@dp.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 **Добро пожаловать в службу поддержки!**\n\n"
        "Выберите раздел, по которому вы хотите создать обращение:",
        parse_mode="Markdown",
        reply_markup=get_categories_keyboard(),
    )


# Обработка выбора раздела
@dp.callback_query(F.data.startswith("ticket_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    category_map = {
        "ticket_tech": "🛠 Техническая поддержка",
        "ticket_media": "📺 Заявка на Медиа",
        "ticket_donate": "💎 Донат / Покупки",
    }
    category_name = category_map.get(callback.data, "Обращение")

    # Сохраняем выбранную категорию
    await state.update_data(chosen_category=category_name)
    await state.set_state(TicketState.waiting_for_message)

    await callback.message.edit_text(
        f"Вы выбрали раздел: **{category_name}**\n\n"
        f"📝 Напишите ваше сообщение или заявку одним сообщением:",
        parse_mode="Markdown",
    )
    await callback.answer()


# Получение сообщения от пользователя и отправка в чат администрации
@dp.message(TicketState.waiting_for_message, F.chat.type == "private")
async def process_user_ticket(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("chosen_category", "Обращение")

    user_mention = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Отсутствует"
    )
    user_id = message.from_user.id
    user_text = message.text

    # Формируем карточку точь-в-точь как на ваших скриншотах
    if "Медиа" in category:
        header_text = "📺 НОВАЯ ЗАЯВКА НА МЕДИА"
    else:
        header_text = "🛠 НОВОЕ ОБРАЩЕНИЕ В ТЕХПОДДЕРЖКУ"

    admin_card = (
        f"{header_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **Пользователь:** {user_mention}\n"
        f"🆔 **Telegram ID:** `{user_id}`\n\n"
        f"📁 **Раздел:** {category}\n"
        f"📝 **Сообщение клиента:**\n{user_text}"
    )

    # Отправляем карточку в группу администраторов
    await bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=admin_card,
        parse_mode="Markdown",
        reply_markup=get_admin_action_keyboard(user_id),
    )

    await message.answer(
        "✅ **Ваше обращение отправлено администрации!**\n"
        "Ожидайте, ответ поступит прямо в этот чат.",
        parse_mode="Markdown",
    )
    await state.clear()


# ================= КНОПКИ АДМИНИСТРАЦИИ =================


# Кнопка "Начать чат / Ответить"
@dp.callback_query(F.data.startswith("reply_"))
async def admin_start_reply(callback: types.CallbackQuery, state: FSMContext):
    target_user_id = callback.data.split("_")[1]

    await state.update_data(target_user_id=target_user_id)
    await state.set_state(TicketState.waiting_for_admin_reply)

    await callback.message.reply(
        f"✍️ Напишите ответ для пользователя (ID `{target_user_id}`). Следующее ваше сообщение в эту тему отправится ему:"
    )
    await callback.answer()


# Отправка ответа пользователю от лица бота
@dp.message(TicketState.waiting_admin_reply if hasattr(TicketState, 'waiting_admin_reply') else TicketState.waiting_for_admin_reply)
async def admin_send_message_to_user(
    message: types.Message, state: FSMContext
):
    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    if target_user_id:
        try:
            await bot.send_message(
                chat_id=int(target_user_id),
                text=f"👨‍💻 **Ответ от администрации:**\n\n{message.text}",
                parse_mode="Markdown",
            )
            await message.reply("✅ Ответ успешно доставлен игроку!")
        except Exception as e:
            await message.reply(
                f"❌ Не удалось доставить сообщение (возможно, бот заблокирован): {e}"
            )

    await state.clear()


# Кнопки "Принять" / "Отклонить"
@dp.callback_query(F.data.startswith("status_"))
async def admin_status_action(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    action = parts[1]  # accept или reject
    target_user_id = parts[2]

    if action == "accept":
        await bot.send_message(
            chat_id=int(target_user_id),
            text="🎉 **Ваша заявка была одобрена администрацией!**",
            parse_mode="Markdown",
        )
        await callback.message.edit_text(
            callback.message.text + "\n\n🟢 **СТАТУС: ПРИНЯТО**"
        )
    else:
        await bot.send_message(
            chat_id=int(target_user_id),
            text="❌ **Ваша заявка была отклонена администрацией.**",
            parse_mode="Markdown",
        )
        await callback.message.edit_text(
            callback.message.text + "\n\n🔴 **СТАТУС: ОТКЛОНЕНО**"
        )

    await callback.answer()


# Запуск бота
async def main():

    print("Бот успешно запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())