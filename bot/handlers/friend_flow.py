from __future__ import annotations

import asyncio
import re

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.config import OWNER_ID
from bot.db import async_session
from bot.keyboards import links_done_keyboard, owner_menu_keyboard
from bot.link_preview import fetch_link_title
from bot.models import Friend
from bot.utils import format_friend_details, parse_birthday

router = Router()

NO_CHANGE_PHRASES = {"без изменений", "нет изменений", "не изменился", "не поменялся"}
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


async def _title_for_item(item: str) -> str | None:
    return await fetch_link_title(item) if _URL_RE.match(item) else None


class KnownFriendFilter(BaseFilter):
    """Matches a message from a friend who is currently mid-onboarding/refresh, injecting `friend` into the handler."""

    def __init__(self, stages: set[str]):
        self.stages = stages

    async def __call__(self, message: Message) -> bool | dict:
        async with async_session() as session:
            result = await session.execute(select(Friend).where(Friend.telegram_id == message.from_user.id))
            friend = result.scalars().first()
        if friend is None or friend.stage not in self.stages:
            return False
        return {"friend": friend}


async def notify_owner_filled(bot: Bot, friend: Friend) -> None:
    await bot.send_message(OWNER_ID, f"🎉 Новая анкета готова!\n\n{format_friend_details(friend)}")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user.id == OWNER_ID:
        await message.answer(
            "Это твой бот для сбора вишлистов друзей. Пришли ссылку на бота друзьям — "
            "они заполнят анкету сами, а я пришлю тебе уведомление.",
            reply_markup=owner_menu_keyboard(),
        )
        return

    async with async_session() as session:
        result = await session.execute(select(Friend).where(Friend.telegram_id == message.from_user.id))
        existing = result.scalars().first()

        if existing is not None:
            existing.username = message.from_user.username
            await session.commit()
            if existing.onboarded:
                await message.answer("Привет! Уже всё записал, спасибо 🙂")
                return
            returning_stage = existing.stage
            candidate_name = None
        else:
            returning_stage = None
            # Telegram даёт имя из профиля, но не даёт дату рождения — её бот в любом случае не узнает сам.
            candidate_name = (message.from_user.first_name or "").strip().split(" ")[0] or None

            stage = "awaiting_birthday" if candidate_name else "awaiting_name"
            session.add(
                Friend(
                    telegram_id=message.from_user.id,
                    name=candidate_name,
                    username=message.from_user.username,
                    stage=stage,
                )
            )
            await session.commit()

    if returning_stage is not None:
        await message.answer("С возвращением! Продолжим 🙂")
        await _prompt_for_stage(message, returning_stage)
        return

    if candidate_name:
        await message.answer(f"Привет, {candidate_name}! 👋 Меня попросили собрать твой вишлист к дню рождения.")
    else:
        await message.answer("Привет! 👋 Меня попросили собрать твой вишлист к дню рождения.")
    await _prompt_for_stage(message, stage)


async def _prompt_for_stage(message: Message, stage: str) -> None:
    if stage == "awaiting_name":
        await message.answer("Как тебя зовут? (одно слово, без пробелов)")
    elif stage == "awaiting_birthday":
        await message.answer("Когда у тебя день рождения? Формат ДД.ММ.ГГГГ, например: 12.04.2005")
    elif stage == "awaiting_wishlist":
        await message.answer(
            "Пришли ссылку(и) на вишлист (Wildberries/Ozon/Kaspi) или просто опиши словами, что хочешь получить в подарок — "
            "можно несколько сообщений подряд, а когда закончишь, нажми «Готово».",
            reply_markup=links_done_keyboard(),
        )


@router.message(KnownFriendFilter({"awaiting_name"}))
async def receive_name(message: Message, friend: Friend) -> None:
    name = (message.text or "").strip()
    if not name or " " in name:
        await message.answer("Имя должно быть одним словом без пробелов. Как тебя зовут?")
        return

    async with async_session() as session:
        db_friend = await session.get(Friend, friend.id)
        db_friend.name = name
        db_friend.stage = "awaiting_birthday"
        await session.commit()

    await _prompt_for_stage(message, "awaiting_birthday")


@router.message(KnownFriendFilter({"awaiting_birthday"}))
async def receive_birthday(message: Message, friend: Friend) -> None:
    parsed = parse_birthday(message.text or "")
    if parsed is None:
        await message.answer("Не понял дату. Нужен формат ДД.ММ.ГГГГ, например: 12.04.2005. Попробуй ещё раз:")
        return
    day, month, year = parsed

    async with async_session() as session:
        db_friend = await session.get(Friend, friend.id)
        db_friend.birthday_day = day
        db_friend.birthday_month = month
        db_friend.birthday_year = year
        db_friend.stage = "awaiting_wishlist"
        await session.commit()

    await _prompt_for_stage(message, "awaiting_wishlist")


@router.message(KnownFriendFilter({"awaiting_wishlist"}))
async def receive_wishlist_item(message: Message, friend: Friend) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пришли ссылку или текст, пожалуйста, или нажми «Готово».", reply_markup=links_done_keyboard())
        return

    # A pasted batch of links (or "не изменился") lands as one message — split it into
    # separate wishlist entries per line instead of storing it as a single blob.
    items = [line.strip() for line in text.splitlines() if line.strip()]
    if len(items) == 1 and items[0].lower() in NO_CHANGE_PHRASES:
        items = []

    titles = await asyncio.gather(*(_title_for_item(item) for item in items))

    async with async_session() as session:
        db_friend = await session.get(Friend, friend.id)
        for item, title in zip(items, titles):
            db_friend.add_wishlist_link(item, title)
        await session.commit()

    reply = f"Записал ({len(items)}) ✅" if len(items) > 1 else "Записал ✅"
    await message.answer(f"{reply} Пришли ещё или нажми «Готово».", reply_markup=links_done_keyboard())


@router.callback_query(F.data == "links_done")
async def cb_links_done(callback: CallbackQuery, bot: Bot) -> None:
    async with async_session() as session:
        result = await session.execute(select(Friend).where(Friend.telegram_id == callback.from_user.id))
        friend = result.scalars().first()
        if friend is None:
            await callback.answer()
            return
        friend.stage = "done"
        await session.commit()

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Спасибо! Всё сохранил 🎉")
    await notify_owner_filled(bot, friend)
