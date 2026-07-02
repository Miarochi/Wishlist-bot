from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

BTN_LIST_FRIENDS = "📋 Статус анкет"
BTN_FRIEND_DETAILS = "👤 Подробности"
BTN_REFRESH_WISHLIST = "🔄 Попросить"


def owner_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_LIST_FRIENDS), KeyboardButton(text=BTN_FRIEND_DETAILS)],
            [KeyboardButton(text=BTN_REFRESH_WISHLIST)],
        ],
        resize_keyboard=True,
    )


def _picker_label(friend) -> str:
    label = friend.name or f"id {friend.telegram_id}"
    if friend.username:
        label = f"{label} (@{friend.username})"
    return label


def friend_picker_keyboard(action: str, friends: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_picker_label(f), callback_data=f"{action}:{f.id}")] for f in friends
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


def edit_field_keyboard(friend) -> InlineKeyboardMarkup:
    notes_label = "📝 Заметки" if friend.notes else "📝 Добавить заметку"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Имя", callback_data=f"edit_field:name:{friend.id}"),
                InlineKeyboardButton(text="🎂 Дата рождения", callback_data=f"edit_field:birthday:{friend.id}"),
            ],
            [
                InlineKeyboardButton(text="🎁 Вишлист", callback_data=f"edit_field:wishlist:{friend.id}"),
                InlineKeyboardButton(text=notes_label, callback_data=f"edit_field:notes:{friend.id}"),
            ],
            [InlineKeyboardButton(text="✅ Готово", callback_data=f"edit_done:{friend.id}")],
        ]
    )


def edit_cancel_keyboard(friend_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_cancel:{friend_id}")]]
    )


def delete_confirm_keyboard(friend_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Да, удалить", callback_data=f"confirm_delete:{friend_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")],
        ]
    )
