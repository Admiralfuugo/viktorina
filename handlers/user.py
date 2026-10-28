import html
import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, Update

import db
import keyboards as kb
import matcher
import services
import texts
from config import NOTIFY_ADMINS

router = Router()


class AnswerState(StatesGroup):
    waiting = State()


@router.message(CommandStart(deep_link=True))
async def start_with_quiz(message: Message, command: CommandObject, state: FSMContext):
    arg = command.args or ""
    if not arg.startswith("q_") or not arg[2:].isdigit():
        await message.answer(await texts.get("start"))
        return
    quiz_id = int(arg[2:])
    quiz = await db.get_quiz(quiz_id)
    if quiz is None:
        await message.answer(await texts.get("not_found"))
        return
    if quiz["status"] != "active":
        await message.answer(await texts.get("closed"), reply_markup=await reveal_markup(quiz))
        return
    if quiz["mode"] == "auto":
        used, solved = await db.user_attempt_state(quiz_id, message.from_user.id)
        if solved:
            await message.answer(await texts.get("qa_solved"))
            return
        if used >= quiz["max_attempts"]:
            await message.answer(await texts.get("qa_limit"), reply_markup=await reveal_markup(quiz))
            return
        await state.set_state(AnswerState.waiting)
        await state.update_data(quiz_id=quiz_id)
        await message.answer(await texts.get(
            "qa_ask", title=quiz["title"], left=quiz["max_attempts"] - used
        ))
        return
    if await db.has_answered(quiz_id, message.from_user.id):
        await message.answer(await texts.get("already"))
        return
    await state.set_state(AnswerState.waiting)
    await state.update_data(quiz_id=quiz_id)
    await message.answer(await texts.get("ask_answer", title=quiz["title"]))


@router.message(CommandStart())
async def start_plain(message: Message):
    await message.answer(await texts.get("start"))


@router.message(AnswerState.waiting, F.text)
async def receive_answer(message: Message, state: FSMContext, bot: Bot, event_update: Update):
    # Tartib Telegram update_id bo'yicha: handlerlar parallel ishlasa ham to'g'ri qoladi
    received_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    quiz_id = (await state.get_data())["quiz_id"]

    quiz = await db.get_quiz(quiz_id)
    if quiz is None or quiz["status"] != "active":
        await state.clear()
        await message.answer(await texts.get("closed"),
                             reply_markup=await reveal_markup(quiz) if quiz else None)
        return
    if quiz["mode"] == "auto":
        await check_answer(message, state, quiz, received_at, event_update.update_id)
        return
    await state.clear()

    user = message.from_user
    ok = await db.add_answer(
        quiz_id, user.id, user.username, user.full_name, message.text, received_at,
        event_update.update_id,
    )
    if not ok:
        await message.answer(await texts.get("already"))
        return
    await message.answer(await texts.get("accepted"))

    if NOTIFY_ADMINS:
        uname = f"@{user.username}" if user.username else "—"
        text = (
            f"📩 Yangi javob — viktorina #{quiz_id}\n"
            f"{html.escape(user.full_name)} ({uname})\n"
            f"<i>{html.escape(message.text)}</i>"
        )
        for admin in await db.list_admins():
            try:
                await bot.send_message(admin["user_id"], text)
            except Exception:
                pass


async def check_answer(message: Message, state: FSMContext, quiz, received_at: str, update_id: int):
    """Savol-javob: javobni darhol tekshirib, natijani aytadi."""
    user = message.from_user
    correct = matcher.is_correct(message.text, quiz["correct_answers"])
    result = await db.add_attempt(
        quiz["id"], user.id, user.username, user.full_name, message.text, correct,
        received_at, update_id, quiz["max_attempts"],
    )
    if result != "saved":
        await state.clear()
        if result == "solved":
            await message.answer(await texts.get("qa_solved"))
        else:
            await message.answer(await texts.get("qa_limit"), reply_markup=await reveal_markup(quiz))
        return
    if correct:
        await state.clear()
        await message.answer(await texts.get("qa_correct"))
        return
    used, _ = await db.user_attempt_state(quiz["id"], user.id)
    left = quiz["max_attempts"] - used
    if left > 0:
        # Holat saqlanadi — foydalanuvchi shunchaki yana yozadi
        await message.answer(await texts.get("qa_wrong", left=left))
    else:
        await state.clear()
        await message.answer(await texts.get("qa_wrong_last"), reply_markup=await reveal_markup(quiz))


# --- To'g'ri javobni ochish (majburiy obuna) ---

def reveal_answer(quiz) -> str:
    """Ko'rsatiladigan javob: admin yozgani yoki Savol-javobda birinchi to'g'ri variant."""
    if quiz["reveal_text"].strip():
        return quiz["reveal_text"].strip()
    if quiz["mode"] == "auto":
        found = matcher.variants(quiz["correct_answers"])
        return found[0] if found else ""
    return ""


async def reveal_markup(quiz):
    if not reveal_answer(quiz):
        return None
    return kb.reveal_kb(quiz["id"], await texts.get("reveal_btn"))


async def can_reveal(quiz, user_id: int) -> bool:
    # Ochiq viktorinada javob faqat urinishlarini tugatganlarga ochiladi
    if quiz["status"] != "active":
        return True
    if quiz["mode"] == "auto":
        used, solved = await db.user_attempt_state(quiz["id"], user_id)
        return solved or used >= quiz["max_attempts"]
    return False


async def missing_subscriptions(bot: Bot, user_id: int):
    missing = []
    for channel in await db.required_channels():
        try:
            member = await bot.get_chat_member(services.chat_ref(channel["chat_id"]), user_id)
        except Exception:
            # Bot kanalda admin bo'lmasa tekshirib bo'lmaydi — foydalanuvchini to'smaymiz
            logging.warning("Obunani tekshirib bo'lmadi: %s", channel["chat_id"])
            continue
        subscribed = member.status in ("member", "administrator", "creator") or \
            (member.status == "restricted" and getattr(member, "is_member", False))
        if not subscribed:
            missing.append(channel)
    return missing


@router.callback_query(F.data.startswith("rv:"))
async def reveal(call: CallbackQuery, bot: Bot):
    quiz = await db.get_quiz(int(call.data.split(":")[1]))
    if quiz is None:
        await call.answer(await texts.get("not_found"), show_alert=True)
        return
    answer = reveal_answer(quiz)
    if not answer:
        await call.answer(await texts.get("reveal_none"), show_alert=True)
        return
    if not await can_reveal(quiz, call.from_user.id):
        await call.answer(await texts.get("reveal_wait"), show_alert=True)
        return
    missing = await missing_subscriptions(bot, call.from_user.id)
    if missing:
        markup = kb.subscribe_kb(missing, quiz["id"], await texts.get("check_btn"))
        text = await texts.get("subscribe_need")
        if call.message.text == text:
            # Allaqachon obuna xabari ochiq — faqat ogohlantiramiz
            await call.answer(await texts.get("not_subscribed"), show_alert=True)
            try:
                await call.message.edit_reply_markup(reply_markup=markup)
            except Exception:
                pass
            return
        await call.message.answer(text, reply_markup=markup)
        await call.answer()
        return
    await call.message.answer(await texts.get("reveal", answer=html.escape(answer)))
    await call.answer()


@router.message(AnswerState.waiting)
async def receive_non_text(message: Message):
    await message.answer(await texts.get("text_only"))


@router.message(F.chat.type == "private")
async def no_state(message: Message):
    # Holat yo'q (masalan, bot qayta ishga tushgan) — tugmani qayta bosishni so'raymiz
    await message.answer(await texts.get("start"))
