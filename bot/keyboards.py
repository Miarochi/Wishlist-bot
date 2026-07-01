from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


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
