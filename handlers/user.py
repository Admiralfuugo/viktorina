import html
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

import db
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
async def receive_answer(message: Message, state: FSMContext, bot: Bot):
    # Aniq tartib uchun bot qabul qilgan vaqt (mikrosekund bilan) saqlanadi
    received_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    quiz_id = (await state.get_data())["quiz_id"]
    await state.clear()

    quiz = await db.get_quiz(quiz_id)
    if quiz is None or quiz["status"] != "active":
        await message.answer(await texts.get("closed"))
        return

    user = message.from_user
    ok = await db.add_answer(
        quiz_id, user.id, user.username, user.full_name, message.text, received_at
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


@router.message(AnswerState.waiting)
async def receive_non_text(message: Message):
    await message.answer(await texts.get("text_only"))
