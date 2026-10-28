"""Bot va panel uchun umumiy amallar."""
from aiogram import Bot
from aiogram.types import BufferedInputFile, Message

import db
import keyboards as kb
import texts


def chat_ref(chat_id: str) -> int | str:
    return int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id


async def _markup(bot: Bot, quiz_id: int):
    me = await bot.get_me()
    return kb.channel_kb(me.username, quiz_id, await texts.get("button"))


async def publish_text(bot: Bot, chat_id: str, text: str, photo: bytes | None = None,
                       photo_name: str = "photo.jpg", mode: str = "manual",
                       correct_answers: str = "", max_attempts: int = 1, reveal_text: str = "") -> int:
    """Paneldan viktorina joylash. Xato bo'lsa exception ko'taradi."""
    quiz_id = await db.create_quiz(text, chat_id, has_photo=photo is not None, mode=mode,
                                   correct_answers=correct_answers, max_attempts=max_attempts,
                                   reveal_text=reveal_text)
    try:
        markup = await _markup(bot, quiz_id)
        if photo:
            sent = await bot.send_photo(
                chat_ref(chat_id), BufferedInputFile(photo, photo_name), caption=text, reply_markup=markup
            )
        else:
            sent = await bot.send_message(chat_ref(chat_id), text, reply_markup=markup)
    except Exception:
        await db.delete_quiz(quiz_id)
        raise
    await db.set_channel_message(quiz_id, sent.message_id)
    return quiz_id


async def publish_copy(bot: Bot, chat_id: str, message: Message) -> int:
    """Botdagi xabarni kanalga nusxalash (bot ichidagi /new)."""
    text = message.text or message.caption or ""
    quiz_id = await db.create_quiz(text, chat_id, has_photo=bool(message.photo))
    try:
        sent = await message.copy_to(chat_ref(chat_id), reply_markup=await _markup(bot, quiz_id))
    except Exception:
        await db.delete_quiz(quiz_id)
        raise
    await db.set_channel_message(quiz_id, sent.message_id)
    return quiz_id


async def edit_quiz_text(bot: Bot, quiz_id: int, text: str) -> None:
    quiz = await db.get_quiz(quiz_id)
    if quiz["channel_message_id"]:
        markup = await _markup(bot, quiz_id) if quiz["status"] == "active" else None
        chat = chat_ref(quiz["channel_chat_id"])
        if quiz["has_photo"]:
            await bot.edit_message_caption(chat_id=chat, message_id=quiz["channel_message_id"],
                                           caption=text, reply_markup=markup)
        else:
            await bot.edit_message_text(text, chat_id=chat, message_id=quiz["channel_message_id"],
                                        reply_markup=markup)
    await db.update_quiz_title(quiz_id, text)


async def _set_button(bot: Bot, quiz, show: bool) -> None:
    if not quiz["channel_message_id"] or not quiz["channel_chat_id"]:
        return
    try:
        await bot.edit_message_reply_markup(
            chat_id=chat_ref(quiz["channel_chat_id"]), message_id=quiz["channel_message_id"],
            reply_markup=await _markup(bot, quiz["id"]) if show else None,
        )
    except Exception:
        pass


async def choose_winner(bot: Bot, answer_id: int) -> tuple[bool, str]:
    """(muvaffaqiyat, izoh) qaytaradi."""
    answer = await db.get_answer(answer_id)
    if answer is None:
        return False, "Javob topilmadi."
    if not await db.close_quiz(answer["quiz_id"], answer["id"]):
        return False, "Viktorina allaqachon yopilgan."
    try:
        await bot.send_message(answer["user_id"], await texts.get("winner"))
        note = "G'olibga xabar yuborildi ✅"
    except Exception:
        note = "⚠️ G'olibga xabar yuborib bo'lmadi (botni bloklagan bo'lishi mumkin)."
    await _set_button(bot, await db.get_quiz(answer["quiz_id"]), show=False)
    return True, note


async def close(bot: Bot, quiz_id: int) -> bool:
    if not await db.close_quiz(quiz_id):
        return False
    await _set_button(bot, await db.get_quiz(quiz_id), show=False)
    return True


async def reopen(bot: Bot, quiz_id: int) -> None:
    await db.reopen_quiz(quiz_id)
    await _set_button(bot, await db.get_quiz(quiz_id), show=True)


async def delete(bot: Bot, quiz_id: int, from_channel: bool) -> None:
    quiz = await db.get_quiz(quiz_id)
    if from_channel and quiz and quiz["channel_message_id"]:
        try:
            await bot.delete_message(chat_ref(quiz["channel_chat_id"]), quiz["channel_message_id"])
        except Exception:
            pass
    await db.delete_quiz(quiz_id)
