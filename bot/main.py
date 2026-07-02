import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat

from bot.config import BOT_TOKEN, OWNER_ID
from bot.db import init_db
from bot.handlers import friend_flow, owner
from bot.scheduler import setup_scheduler

OWNER_COMMANDS = [
    BotCommand(command="friends", description="📋 Статус анкет"),
    BotCommand(command="friend", description="👤 Подробности о друге"),
    BotCommand(command="ask", description="🔄 Попросить обновить вишлист"),
    BotCommand(command="notes", description="📝 Добавить заметку"),
    BotCommand(command="birthday", description="🎂 Изменить дату рождения"),
    BotCommand(command="help", description="❓ Помощь"),
]


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(owner.router)
    dp.include_router(friend_flow.router)

    setup_scheduler(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    # Both interfaces are offered: the "/" command menu and the reply-keyboard buttons
    # (owner_menu_keyboard) sent on /start.
    await bot.set_my_commands(OWNER_COMMANDS, scope=BotCommandScopeChat(chat_id=OWNER_ID))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
