import json
from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Friend(Base):
    __tablename__ = "friends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)

    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    birthday_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    birthday_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    birthday_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # onboarding / update state machine:
    # "awaiting_name" -> "awaiting_birthday" -> "awaiting_wishlist" -> "done"
    stage: Mapped[str] = mapped_column(String(32), default="awaiting_name")

    wishlist_links_json: Mapped[str] = mapped_column(Text, default="[]")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    last_reminded_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    @property
    def wishlist_links(self) -> list[dict]:
        raw = json.loads(self.wishlist_links_json or "[]")
        # Older records stored plain strings before titles were added.
        return [item if isinstance(item, dict) else {"text": item, "title": None} for item in raw]

    def add_wishlist_link(self, link: str, title: Optional[str] = None) -> None:
        links = self.wishlist_links
        links.append({"text": link, "title": title})
        self.wishlist_links_json = json.dumps(links, ensure_ascii=False)

    def set_wishlist(self, items: list[dict]) -> None:
        self.wishlist_links_json = json.dumps(items, ensure_ascii=False)

    @property
    def onboarded(self) -> bool:
        return self.stage == "done"
