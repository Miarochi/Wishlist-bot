from __future__ import annotations

import re
from datetime import date

from bot.models import Friend

_DATE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")

STAGE_LABELS = {
    "awaiting_name": "ещё не назвал(а) имя",
    "awaiting_birthday": "не указал(а) дату рождения",
    "awaiting_wishlist": "не написал(а), что хочет в подарок",
}


def parse_birthday(text: str) -> tuple[int, int, int] | None:
    match = _DATE_RE.match(text.strip())
    if match is None:
        return None
    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    try:
        date(year, month, day)
    except ValueError:
        return None
    return day, month, year


def next_birthday(friend: Friend, today: date) -> date:
    year = today.year
    try:
        bday = date(year, friend.birthday_month, friend.birthday_day)
    except ValueError:
        bday = date(year, 3, 1)  # Feb 29 on a non-leap year
    if bday < today:
        year += 1
        try:
            bday = date(year, friend.birthday_month, friend.birthday_day)
        except ValueError:
            bday = date(year, 3, 1)
    return bday


def format_wishlist(links: list[dict]) -> str:
    if not links:
        return "(пусто)"
    items = []
    for item in links:
        text, title = item.get("text", ""), item.get("title")
        items.append(f"🎁 {title}\n{text}" if title else text)
    return "\n\n".join(items)


def format_friend_details(friend: Friend) -> str:
    name = friend.name or f"Без имени (id {friend.telegram_id})"
    if friend.username:
        name = f"{name} (@{friend.username})"
    lines = [name]

    if friend.birthday_day and friend.birthday_month:
        if friend.birthday_year:
            lines.append(f"ДР: {friend.birthday_day:02d}.{friend.birthday_month:02d}.{friend.birthday_year}")
        else:
            lines.append(f"ДР: {friend.birthday_day:02d}.{friend.birthday_month:02d}")

    if friend.onboarded:
        lines.append("Вишлист:\n" + format_wishlist(friend.wishlist_links))
        lines.append(f"Заметки: {friend.notes or '(нет)'}")
    else:
        lines.append(f"Анкета не закончена: {STAGE_LABELS.get(friend.stage, friend.stage)}")

    return "\n\n".join(lines)
