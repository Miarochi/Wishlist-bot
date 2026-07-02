from __future__ import annotations

import asyncio
from datetime import date

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.config import OWNER_ID
from bot.db import async_session
from bot.keyboards import (
    BTN_ADD_NOTE,
    BTN_FRIEND_DETAILS,
    BTN_HELP,
    BTN_LIST_FRIENDS,
    BTN_REFRESH_WISHLIST,
    delete_confirm_keyboard,
    edit_cancel_keyboard,
    edit_field_keyboard,
    friend_picker_keyboard,
    links_done_keyboard,
    owner_menu_keyboard,
)
from bot.link_preview import title_for_item
from bot.models import Friend
from bot.utils import esc, format_friend_details, next_birthday, parse_birthday

router = Router()
router.message.filter(F.from_user.id == OWNER_ID)
router.callback_query.filter(F.from_user.id == OWNER_ID)


async def _reply(target: Message, text: str) -> None:
    await target.answer(text, reply_markup=owner_menu_keyboard())


class NoteInput(StatesGroup):
    text = State()


class EditField(StatesGroup):
    name = State()
    birthday = State()
    wishlist = State()
    notes = State()


FIELD_STATES = {
    "name": EditField.name,
    "birthday": EditField.birthday,
    "wishlist": EditField.wishlist,
    "notes": EditField.notes,
}

FIELD_PROMPTS = {
    "name": "✏️ Новое имя (одно слово, без пробелов):",
    "birthday": "🎂 Новая дата рождения. Формат ДД.ММ.ГГГГ, например: 12.04.2005",
    "wishlist": "🎁 Пришли новый вишлист — ссылки или текст, каждый пункт на новой строке. Это заменит текущий список.",
    "notes": "📝 Новый текст заметок (заменит текущие):",
}


@router.message(NoteInput.text)
async def receive_note_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await _reply(message, "Пришли текст заметки:")
        return

    data = await state.get_data()
    async with async_session() as session:
        friend = await session.get(Friend, data["note_friend_id"])
        existing = f"{friend.notes}\n" if friend.notes else ""
        friend.notes = existing + text
        await session.commit()

    await state.clear()
    await _reply(message, f"📝 Заметка про <b>{esc(data['note_friend_name'])}</b> сохранена ✅")


async def _update_edit_card(bot: Bot, chat_id: int, message_id: int, friend_id: int) -> None:
    async with async_session() as session:
        friend = await session.get(Friend, friend_id)
    if friend is None:
        await bot.edit_message_text("Друг не найден.", chat_id=chat_id, message_id=message_id)
        return
    await bot.edit_message_text(
        format_friend_details(friend),
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=edit_field_keyboard(friend.id),
    )


@router.message(EditField.name)
async def receive_edit_name(message: Message, state: FSMContext, bot: Bot) -> None:
    name = (message.text or "").strip()
    if not name or " " in name:
        await message.answer("Имя должно быть одним словом без пробелов. Попробуй ещё раз:")
        return

    data = await state.get_data()
    async with async_session() as session:
        friend = await session.get(Friend, data["edit_friend_id"])
        friend.name = name
        await session.commit()

    await state.clear()
    await _update_edit_card(bot, data["edit_chat_id"], data["edit_message_id"], data["edit_friend_id"])


@router.message(EditField.birthday)
async def receive_edit_birthday(message: Message, state: FSMContext, bot: Bot) -> None:
    parsed = parse_birthday(message.text or "")
    if parsed is None:
        await message.answer("Не понял дату. Нужен формат ДД.ММ.ГГГГ, например: 12.04.2005. Попробуй ещё раз:")
        return
    day, month, year = parsed

    data = await state.get_data()
    async with async_session() as session:
        friend = await session.get(Friend, data["edit_friend_id"])
        friend.birthday_day = day
        friend.birthday_month = month
        friend.birthday_year = year
        friend.last_reminded_year = None
        await session.commit()

    await state.clear()
    await _update_edit_card(bot, data["edit_chat_id"], data["edit_message_id"], data["edit_friend_id"])


@router.message(EditField.wishlist)
async def receive_edit_wishlist(message: Message, state: FSMContext, bot: Bot) -> None:
    text = (message.text or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    titles = await asyncio.gather(*(title_for_item(line) for line in lines))
    items = [{"text": line, "title": title} for line, title in zip(lines, titles)]

    data = await state.get_data()
    async with async_session() as session:
        friend = await session.get(Friend, data["edit_friend_id"])
        friend.set_wishlist(items)
        await session.commit()

    await state.clear()
    await _update_edit_card(bot, data["edit_chat_id"], data["edit_message_id"], data["edit_friend_id"])


@router.message(EditField.notes)
async def receive_edit_notes(message: Message, state: FSMContext, bot: Bot) -> None:
    text = (message.text or "").strip()

    data = await state.get_data()
    async with async_session() as session:
        friend = await session.get(Friend, data["edit_friend_id"])
        friend.notes = text or None
        await session.commit()

    await state.clear()
    await _update_edit_card(bot, data["edit_chat_id"], data["edit_message_id"], data["edit_friend_id"])


async def _find_friend_by_name(session, name: str) -> Friend | None:
    result = await session.execute(select(Friend).where(Friend.name.ilike(name.strip())))
    return result.scalars().first()


async def _all_friends(session) -> list[Friend]:
    result = await session.execute(select(Friend).order_by(Friend.name))
    return list(result.scalars().all())


async def send_refresh_request(bot: Bot, telegram_id: int) -> None:
    await bot.send_message(
        telegram_id,
        "Привет! Хотят уточнить, не изменились ли твои пожелания к подаркам 🙂\n"
        "Пришли ссылку(и) на вишлист или опиши словами, а когда закончишь — нажми «Готово». "
        "Если ничего не поменялось, просто нажми «Готово» сразу.",
        reply_markup=links_done_keyboard(),
    )


async def _send_help(message: Message, bot: Bot) -> None:
    me = await bot.get_me()
    await _reply(
        message,
        "🎁 <b>Wishlist Bot</b>\n"
        "Собирает вишлисты твоих друзей. Пришли им ссылку на бота "
        f"(<code>https://t.me/{esc(me.username)}</code>) — они заполнят анкету сами, а я пришлю тебе "
        "уведомление и напомню перед днём рождения.\n\n"
        "<b>Кнопки внизу:</b>\n"
        f"{BTN_LIST_FRIENDS} — список друзей и статус анкеты\n"
        f"{BTN_FRIEND_DETAILS} — вишлист, заметки и статус конкретного друга\n"
        f"{BTN_REFRESH_WISHLIST} — попросить друга обновить вишлист прямо сейчас\n"
        f"{BTN_ADD_NOTE} — дописать заметку о друге вручную (добавляет к старым)\n\n"
        "<b>Только в меню слэш-команд:</b>\n"
        "/edit — редактировать анкету друга целиком (имя, дата рождения, вишлист, заметки — заменяет, а не дописывает)\n"
        "/delete — удалить друга насовсем (с подтверждением)",
    )


@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot) -> None:
    await _send_help(message, bot)


@router.message(F.text == BTN_HELP)
async def btn_help(message: Message, bot: Bot) -> None:
    await _send_help(message, bot)


def _fmt_friend_line(friend: Friend, today: date) -> str:
    name = esc(friend.name or f"(id {friend.telegram_id})")
    if not friend.onboarded:
        return f"⏳ {name} — анкета не закончена"
    next_bday = next_birthday(friend, today)
    days_left = (next_bday - today).days
    return f"✅ <b>{name}</b> — через {days_left} дн. ({next_bday.strftime('%d.%m')})"


async def _send_friends_list(message: Message) -> None:
    async with async_session() as session:
        friends = await _all_friends(session)

    if not friends:
        me = await message.bot.get_me()
        await _reply(
            message, f"Пока никто не заполнил анкету. Пришли друзьям ссылку на бота: <code>https://t.me/{esc(me.username)}</code>"
        )
        return

    today = date.today()
    lines = [_fmt_friend_line(f, today) for f in friends]
    await _reply(message, "📋 <b>Твои друзья</b>\n\n" + "\n".join(lines))


@router.message(Command("friends"))
async def cmd_friends(message: Message) -> None:
    await _send_friends_list(message)


@router.message(F.text == BTN_LIST_FRIENDS)
async def btn_friends(message: Message) -> None:
    await _send_friends_list(message)


@router.message(Command("friend"))
async def cmd_friend(message: Message, command: CommandObject) -> None:
    if not command.args:
        await _prompt_friend_picker(message, "pick_details", "Кого показать?")
        return

    async with async_session() as session:
        friend = await _find_friend_by_name(session, command.args)
        if friend is None:
            await _reply(message, "Не нашёл такого друга. Проверь /friends")
            return

        await _reply(message, format_friend_details(friend))


@router.message(Command("ask"))
async def cmd_refresh(message: Message, command: CommandObject, bot: Bot) -> None:
    if not command.args:
        await _prompt_friend_picker(message, "pick_refresh", "Кого попросить обновить вишлист?")
        return
    async with async_session() as session:
        friend = await _find_friend_by_name(session, command.args)
        if friend is None:
            await _reply(message, "Не нашёл такого друга. Проверь /friends")
            return
        friend.stage = "awaiting_wishlist"
        await session.commit()
        friend_name, telegram_id = friend.name, friend.telegram_id

    await send_refresh_request(bot, telegram_id)
    await _reply(message, f"🔄 Спросил у <b>{esc(friend_name)}</b> про обновление вишлиста ✅")


@router.message(Command("notes"))
async def cmd_notes(message: Message, command: CommandObject) -> None:
    if not command.args:
        await _prompt_friend_picker(message, "pick_notes", "Кому добавить заметку?")
        return
    if " " not in command.args:
        await _reply(message, "Использование: /notes Имя текст заметки")
        return
    name, _, text = command.args.partition(" ")
    async with async_session() as session:
        friend = await _find_friend_by_name(session, name)
        if friend is None:
            await _reply(message, "Не нашёл такого друга. Проверь /friends")
            return
        existing = f"{friend.notes}\n" if friend.notes else ""
        friend.notes = existing + text.strip()
        await session.commit()
    await _reply(message, "📝 Заметка сохранена ✅")


@router.message(Command("edit"))
async def cmd_edit(message: Message, command: CommandObject) -> None:
    if not command.args:
        await _prompt_friend_picker(message, "pick_edit", "Кого редактировать?")
        return
    async with async_session() as session:
        friend = await _find_friend_by_name(session, command.args)
    if friend is None:
        await _reply(message, "Не нашёл такого друга. Проверь /friends")
        return
    await message.answer(format_friend_details(friend), reply_markup=edit_field_keyboard(friend.id))


@router.message(Command("delete"))
async def cmd_delete(message: Message, command: CommandObject) -> None:
    if not command.args:
        await _prompt_friend_picker(message, "pick_delete", "Кого удалить?")
        return
    async with async_session() as session:
        friend = await _find_friend_by_name(session, command.args)
    if friend is None:
        await _reply(message, "Не нашёл такого друга. Проверь /friends")
        return
    await message.answer(
        f"❗ Удалить <b>{esc(friend.name or f'id {friend.telegram_id}')}</b> вместе со всеми данными? "
        "Это нельзя отменить.",
        reply_markup=delete_confirm_keyboard(friend.id),
    )


async def _prompt_friend_picker(message: Message, action: str, prompt: str) -> None:
    async with async_session() as session:
        friends = await _all_friends(session)
    if not friends:
        await _reply(message, "Пока нет ни одного друга.")
        return
    await message.answer(prompt, reply_markup=friend_picker_keyboard(action, friends))


@router.message(F.text == BTN_FRIEND_DETAILS)
async def btn_friend_details(message: Message) -> None:
    await _prompt_friend_picker(message, "pick_details", "Кого показать?")


@router.callback_query(F.data.startswith("pick_details:"))
async def cb_pick_details(callback: CallbackQuery) -> None:
    friend_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        friend = await session.get(Friend, friend_id)

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    if friend is None:
        await _reply(callback.message, "Друг не найден.")
        return
    await _reply(callback.message, format_friend_details(friend))


@router.message(F.text == BTN_REFRESH_WISHLIST)
async def btn_refresh(message: Message) -> None:
    await _prompt_friend_picker(message, "pick_refresh", "Кого попросить обновить вишлист?")


@router.callback_query(F.data.startswith("pick_refresh:"))
async def cb_pick_refresh(callback: CallbackQuery, bot: Bot) -> None:
    friend_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        friend = await session.get(Friend, friend_id)
        if friend is None:
            await callback.answer("Друг не найден", show_alert=True)
            return
        friend.stage = "awaiting_wishlist"
        await session.commit()
        friend_name, telegram_id = friend.name, friend.telegram_id

    await send_refresh_request(bot, telegram_id)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _reply(callback.message, f"🔄 Спросил у <b>{esc(friend_name)}</b> про обновление вишлиста ✅")


@router.message(F.text == BTN_ADD_NOTE)
async def btn_notes(message: Message) -> None:
    await _prompt_friend_picker(message, "pick_notes", "Кому добавить заметку?")


@router.callback_query(F.data.startswith("pick_notes:"))
async def cb_pick_notes(callback: CallbackQuery, state: FSMContext) -> None:
    friend_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        friend = await session.get(Friend, friend_id)

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    if friend is None:
        await _reply(callback.message, "Друг не найден.")
        return

    await state.update_data(note_friend_id=friend.id, note_friend_name=friend.name)
    await state.set_state(NoteInput.text)
    await _reply(callback.message, f"📝 Напиши заметку про <b>{esc(friend.name)}</b>:")


@router.callback_query(F.data.startswith("pick_edit:"))
async def cb_pick_edit(callback: CallbackQuery) -> None:
    friend_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        friend = await session.get(Friend, friend_id)

    await callback.answer()
    if friend is None:
        await callback.message.edit_text("Друг не найден.")
        return
    await callback.message.edit_text(format_friend_details(friend), reply_markup=edit_field_keyboard(friend.id))


@router.callback_query(F.data.startswith("edit_field:"))
async def cb_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    _, field, friend_id_s = callback.data.split(":", 2)
    friend_id = int(friend_id_s)

    await callback.answer()
    await state.update_data(
        edit_friend_id=friend_id,
        edit_chat_id=callback.message.chat.id,
        edit_message_id=callback.message.message_id,
    )
    await state.set_state(FIELD_STATES[field])
    await callback.message.edit_text(FIELD_PROMPTS[field], reply_markup=edit_cancel_keyboard(friend_id))


@router.callback_query(F.data.startswith("edit_cancel:"))
async def cb_edit_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    friend_id = int(callback.data.split(":", 1)[1])
    await state.clear()

    async with async_session() as session:
        friend = await session.get(Friend, friend_id)

    await callback.answer("Отменено")
    if friend is None:
        await callback.message.edit_text("Друг не найден.")
        return
    await callback.message.edit_text(format_friend_details(friend), reply_markup=edit_field_keyboard(friend.id))


@router.callback_query(F.data.startswith("edit_done:"))
async def cb_edit_done(callback: CallbackQuery) -> None:
    friend_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        friend = await session.get(Friend, friend_id)

    await callback.answer()
    if friend is None:
        await callback.message.edit_text("Друг не найден.")
        return
    await callback.message.edit_text(format_friend_details(friend))


@router.callback_query(F.data.startswith("pick_delete:"))
async def cb_pick_delete(callback: CallbackQuery) -> None:
    friend_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        friend = await session.get(Friend, friend_id)

    await callback.answer()
    if friend is None:
        await callback.message.edit_text("Друг не найден.")
        return
    await callback.message.edit_text(
        f"❗ Удалить <b>{esc(friend.name or f'id {friend.telegram_id}')}</b> вместе со всеми данными? "
        "Это нельзя отменить.",
        reply_markup=delete_confirm_keyboard(friend.id),
    )


@router.callback_query(F.data.startswith("confirm_delete:"))
async def cb_confirm_delete(callback: CallbackQuery) -> None:
    friend_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        friend = await session.get(Friend, friend_id)
        if friend is None:
            await callback.answer("Друг не найден", show_alert=True)
            return
        name = friend.name or f"id {friend.telegram_id}"
        await session.delete(friend)
        await session.commit()

    await callback.answer("Удалено")
    await callback.message.edit_text(f"🗑 <b>{esc(name)}</b> удалён(а).")


@router.callback_query(F.data == "cancel_delete")
async def cb_cancel_delete(callback: CallbackQuery) -> None:
    await callback.answer("Отменено")
    await callback.message.edit_text("Отменено, друг не удалён.")


@router.callback_query(F.data.startswith("ask_update:"))
async def cb_ask_update(callback: CallbackQuery, bot: Bot) -> None:
    friend_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        friend = await session.get(Friend, friend_id)
        if friend is None:
            await callback.answer("Друг не найден", show_alert=True)
            return
        friend.stage = "awaiting_wishlist"
        await session.commit()
        friend_name, telegram_id = friend.name, friend.telegram_id

    await send_refresh_request(bot, telegram_id)
    await callback.answer()
    await callback.message.edit_text(callback.message.html_text + f"\n\n🔄 Спросил у <b>{esc(friend_name)}</b> ✅")


@router.callback_query(F.data.startswith("skip_update:"))
async def cb_skip_update(callback: CallbackQuery) -> None:
    await callback.answer("Ок")
    await callback.message.edit_text(callback.message.html_text + "\n\n⏭ Ок, не спрашиваю.")
