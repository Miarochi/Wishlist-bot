import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set. Copy .env.example to .env and fill it in.")
    return value


BOT_TOKEN = _require("BOT_TOKEN")
OWNER_ID = int(_require("OWNER_ID"))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "10"))
REMINDER_DAYS_BEFORE = int(os.getenv("REMINDER_DAYS_BEFORE", "7"))
DB_PATH = os.getenv("DB_PATH", "wishlist_bot.db")
