"""Botga yozgan har bir foydalanuvchini eslab qolish (adminni @username bilan qo'shish uchun)."""
import logging

from aiogram import BaseMiddleware

import db

# Ma'lumot o'zgarmagan bo'lsa bazaga qayta yozmaslik uchun
_seen: dict[int, tuple[str | None, str]] = {}


class RememberUser(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is not None and not user.is_bot:
            info = (user.username, user.full_name)
            if _seen.get(user.id) != info:
                try:
                    await db.save_user(user.id, user.username, user.full_name)
                    _seen[user.id] = info
                except Exception:
                    logging.exception("Foydalanuvchini saqlab bo'lmadi: %s", user.id)
        return await handler(event, data)
