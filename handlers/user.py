import html
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, Update

import db
import matcher
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
        await message.answer(await texts.get("closed"))
        return
    if quiz["mode"] == "auto":
        used, solved = await db.user_attempt_state(quiz_id, message.from_user.id)
        if solved:
            await message.answer(await texts.get("qa_solved"))
            return
        if used >= quiz["max_attempts"]:
            await message.answer(await texts.get("qa_limit"))
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
        await message.answer(await texts.get("closed"))
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
        await message.answer(await texts.get("qa_solved" if result == "solved" else "qa_limit"))
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
        await message.answer(await texts.get("qa_wrong_last"))


@router.message(AnswerState.waiting)
async def receive_non_text(message: Message):
    await message.answer(await texts.get("text_only"))


@router.message(F.chat.type == "private")
async def no_state(message: Message):
    # Holat yo'q (masalan, bot qayta ishga tushgan) — tugmani qayta bosishni so'raymiz
    await message.answer(await texts.get("start"))
