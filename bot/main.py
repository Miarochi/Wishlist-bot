import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommandScopeChat

from bot.config import BOT_TOKEN, OWNER_ID
from bot.db import init_db
from bot.handlers import friend_flow, owner
from bot.scheduler import setup_scheduler


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(owner.router)
    dp.include_router(friend_flow.router)

    setup_scheduler(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    # Slash commands are hidden from the "/" menu in favor of the reply-keyboard buttons
    # (owner_menu_keyboard) — this clears the ones registered by an earlier version.
    await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=OWNER_ID))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
