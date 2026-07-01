from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

BTN_LIST_FRIENDS = "📋 Список друзей"
BTN_FRIEND_DETAILS = "👤 Подробности о друге"
BTN_REFRESH_WISHLIST = "🔄 Обновить вишлист"
BTN_ADD_NOTE = "📝 Добавить заметку"
BTN_HELP = "❓ Помощь"


def owner_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_LIST_FRIENDS), KeyboardButton(text=BTN_FRIEND_DETAILS)],
            [KeyboardButton(text=BTN_REFRESH_WISHLIST), KeyboardButton(text=BTN_ADD_NOTE)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def friend_picker_keyboard(action: str, friends: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f.name or f"id {f.telegram_id}", callback_data=f"{action}:{f.id}")]
            for f in friends
        ]
    )


def reminder_keyboard(friend_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔔 Спросить у друга об обновлении", callback_data=f"ask_update:{friend_id}"
                )
            ],
            [InlineKeyboardButton(text="⏭ Не сейчас", callback_data=f"skip_update:{friend_id}")],
        ]
    )


def links_done_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="links_done")]]
    )
