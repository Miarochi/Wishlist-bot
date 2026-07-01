from datetime import date

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from bot.config import OWNER_ID, REMINDER_DAYS_BEFORE, REMINDER_HOUR, TIMEZONE
from bot.db import async_session
from bot.keyboards import reminder_keyboard
from bot.models import Friend
from bot.utils import next_birthday


async def check_birthdays(bot: Bot) -> None:
    today = date.today()
    async with async_session() as session:
        result = await session.execute(select(Friend))
        friends = result.scalars().all()

        for friend in friends:
            if friend.birthday_day is None or friend.birthday_month is None:
                continue
            next_bday = next_birthday(friend, today)
            days_left = (next_bday - today).days
            if days_left != REMINDER_DAYS_BEFORE:
                continue
            if friend.last_reminded_year == next_bday.year:
                continue

            links = friend.wishlist_links
            lines = [
                f"🎂 Через {REMINDER_DAYS_BEFORE} дн. день рождения у {friend.name} ({next_bday.strftime('%d.%m')})",
                "Вишлист:\n" + ("\n".join(links) if links else "(ещё не прислал)"),
            ]
            if friend.notes:
                lines.append(f"Заметки: {friend.notes}")

            await bot.send_message(
                OWNER_ID,
                "\n\n".join(lines),
                reply_markup=reminder_keyboard(friend.id),
            )

            friend.last_reminded_year = next_bday.year

        await session.commit()


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        check_birthdays,
        trigger=CronTrigger(hour=REMINDER_HOUR, minute=0),
        args=[bot],
        id="check_birthdays",
    )
    scheduler.start()
    return scheduler
