from __future__ import annotations

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
    friend_picker_keyboard,
    links_done_keyboard,
    owner_menu_keyboard,
)
from bot.models import Friend
from bot.utils import format_friend_details, next_birthday

router = Router()
router.message.filter(F.from_user.id == OWNER_ID)
router.callback_query.filter(F.from_user.id == OWNER_ID)


class NoteInput(StatesGroup):
    text = State()


@router.message(NoteInput.text)
async def receive_note_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пришли текст заметки:")
        return

    data = await state.get_data()
    async with async_session() as session:
        friend = await session.get(Friend, data["note_friend_id"])
        existing = f"{friend.notes}\n" if friend.notes else ""
        friend.notes = existing + text
        await session.commit()

    await state.clear()
    await message.answer(f"Заметка про {data['note_friend_name']} сохранена ✅")


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
    await message.answer(
        "Этот бот собирает вишлисты твоих друзей. Пришли им ссылку на бота "
        f"(https://t.me/{me.username}) — они заполнят анкету сами, а я пришлю тебе уведомление и "
        "напомню перед днём рождения.\n\n"
        "Используй кнопки внизу:\n"
        f"{BTN_LIST_FRIENDS} — список друзей и статус анкеты\n"
        f"{BTN_FRIEND_DETAILS} — вишлист, заметки и статус конкретного друга\n"
        f"{BTN_REFRESH_WISHLIST} — попросить друга обновить вишлист прямо сейчас\n"
        f"{BTN_ADD_NOTE} — дописать заметку о друге вручную",
        reply_markup=owner_menu_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot) -> None:
    await _send_help(message, bot)


@router.message(F.text == BTN_HELP)
async def btn_help(message: Message, bot: Bot) -> None:
    await _send_help(message, bot)


def _fmt_friend_line(friend: Friend, today: date) -> str:
    if not friend.onboarded:
        return f"⏳ {friend.name or f'(id {friend.telegram_id})'} — анкета не закончена"
    status = "✅"
    next_bday = next_birthday(friend, today)
    days_left = (next_bday - today).days
    return f"{status} {friend.name} — через {days_left} дн. ({next_bday.strftime('%d.%m')})"


async def _send_friends_list(message: Message) -> None:
    async with async_session() as session:
        friends = await _all_friends(session)

    if not friends:
        me = await message.bot.get_me()
        await message.answer(
            f"Пока никто не заполнил анкету. Пришли друзьям ссылку на бота: https://t.me/{me.username}"
        )
        return

    today = date.today()
    lines = [_fmt_friend_line(f, today) for f in friends]
    await message.answer("\n".join(lines))


@router.message(Command("friends"))
async def cmd_friends(message: Message) -> None:
    await _send_friends_list(message)


@router.message(F.text == BTN_LIST_FRIENDS)
async def btn_friends(message: Message) -> None:
    await _send_friends_list(message)


@router.message(Command("friend"))
async def cmd_friend(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.answer("Использование: /friend Имя")
        return

    async with async_session() as session:
        friend = await _find_friend_by_name(session, command.args)
        if friend is None:
            await message.answer("Не нашёл такого друга. Проверь /friends")
            return

        await message.answer(format_friend_details(friend))


@router.message(Command("refresh"))
async def cmd_refresh(message: Message, command: CommandObject, bot: Bot) -> None:
    if not command.args:
        await message.answer("Использование: /refresh Имя")
        return
    async with async_session() as session:
        friend = await _find_friend_by_name(session, command.args)
        if friend is None:
            await message.answer("Не нашёл такого друга. Проверь /friends")
            return
        friend.stage = "awaiting_wishlist"
        await session.commit()
        friend_name, telegram_id = friend.name, friend.telegram_id

    await send_refresh_request(bot, telegram_id)
    await message.answer(f"Спросил у {friend_name} про обновление вишлиста ✅")


@router.message(Command("notes"))
async def cmd_notes(message: Message, command: CommandObject) -> None:
    if not command.args or " " not in command.args:
        await message.answer("Использование: /notes Имя текст заметки")
        return
    name, _, text = command.args.partition(" ")
    async with async_session() as session:
        friend = await _find_friend_by_name(session, name)
        if friend is None:
            await message.answer("Не нашёл такого друга. Проверь /friends")
            return
        existing = f"{friend.notes}\n" if friend.notes else ""
        friend.notes = existing + text.strip()
        await session.commit()
    await message.answer("Заметка сохранена ✅")


async def _prompt_friend_picker(message: Message, action: str, prompt: str) -> None:
    async with async_session() as session:
        friends = await _all_friends(session)
    if not friends:
        await message.answer("Пока нет ни одного друга.")
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
        await callback.message.answer("Друг не найден.")
        return
    await callback.message.answer(format_friend_details(friend))


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
    await callback.message.answer(f"Спросил у {friend_name} про обновление вишлиста ✅")


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
        await callback.message.answer("Друг не найден.")
        return

    await state.update_data(note_friend_id=friend.id, note_friend_name=friend.name)
    await state.set_state(NoteInput.text)
    await callback.message.answer(f"Напиши заметку про {friend.name}:")


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
    await callback.message.edit_text(callback.message.text + f"\n\nСпросил у {friend_name} ✅")


@router.callback_query(F.data.startswith("skip_update:"))
async def cb_skip_update(callback: CallbackQuery) -> None:
    await callback.answer("Ок")
    await callback.message.edit_text(callback.message.text + "\n\nОк, не спрашиваю.")
