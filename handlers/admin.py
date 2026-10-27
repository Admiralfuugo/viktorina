import html
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, TelegramObject

import db
import keyboards as kb
import services
from config import PANEL_URL


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        return event.from_user is not None and await db.is_admin(event.from_user.id)


router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

PAGE_SIZE = 10
TZ = timezone(timedelta(hours=5))  # Toshkent vaqti


class NewQuiz(StatesGroup):
    choosing_channel = State()
    waiting_post = State()


@router.message(Command("admin"))
async def admin_help(message: Message):
    await message.answer(
        "Admin buyruqlari:\n"
        "/new — yangi viktorina joylash\n"
        "/quizzes — viktorinalar va javoblar ro'yxati\n"
        "/cancel — bekor qilish\n\n"
        f"Veb-panel: {PANEL_URL}"
    )


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.")


@router.message(Command("new"))
async def new_quiz(message: Message, state: FSMContext):
    channels = await db.list_channels()
    if not channels:
        await message.answer("Avval veb-panelda kanal qo'shing.")
        return
    if len(channels) == 1:
        await state.set_state(NewQuiz.waiting_post)
        await state.update_data(chat_id=channels[0]["chat_id"])
        await message.answer(f"Kanal: {html.escape(channels[0]['title'])}\nViktorina savolini yuboring (matn yoki rasm + izoh).")
        return
    await state.set_state(NewQuiz.choosing_channel)
    await message.answer("Qaysi kanalga joylaymiz?", reply_markup=kb.channels_kb(channels))


@router.callback_query(NewQuiz.choosing_channel, F.data.startswith("ch:"))
async def pick_channel(call: CallbackQuery, state: FSMContext):
    channel = await db.get_channel(int(call.data.split(":")[1]))
    if channel is None:
        await call.answer("Kanal topilmadi", show_alert=True)
        return
    await state.set_state(NewQuiz.waiting_post)
    await state.update_data(chat_id=channel["chat_id"])
    await call.message.edit_text(f"Kanal: {html.escape(channel['title'])}\nViktorina savolini yuboring (matn yoki rasm + izoh).")
    await call.answer()


@router.message(NewQuiz.waiting_post)
async def publish_quiz(message: Message, state: FSMContext, bot: Bot):
    if not (message.text or message.caption):
        await message.answer("Savol matni kerak (matn yoki rasm izohi).")
        return
    chat_id = (await state.get_data())["chat_id"]
    await state.clear()
    try:
        quiz_id = await services.publish_copy(bot, chat_id, message)
    except Exception as e:
        await message.answer(f"Kanalga joylab bo'lmadi: {html.escape(str(e))}\nBot kanalda admin ekanini tekshiring.")
        return
    await message.answer(f"✅ Viktorina #{quiz_id} kanalga joylandi. Javoblar: /quizzes")


async def _show_quizzes(target: Message, edit: bool):
    quizzes = await db.list_quizzes()
    if not quizzes:
        await target.answer("Hali viktorina yo'q. /new")
        return
    text = "Viktorinalar (🟢 faol, 🔒 yopilgan, qavsda javoblar soni):"
    if edit:
        await target.edit_text(text, reply_markup=kb.quizzes_kb(quizzes))
    else:
        await target.answer(text, reply_markup=kb.quizzes_kb(quizzes))


@router.message(Command("quizzes"))
async def quizzes_cmd(message: Message):
    await _show_quizzes(message, edit=False)


@router.callback_query(F.data == "qlist")
async def quizzes_cb(call: CallbackQuery):
    await _show_quizzes(call.message, edit=True)
    await call.answer()


def _fmt_time(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(TZ).strftime("%d.%m %H:%M:%S.%f")[:-3]


@router.callback_query(F.data.startswith("ql:"))
async def answers_page(call: CallbackQuery):
    _, quiz_id, page = call.data.split(":")
    quiz_id, page = int(quiz_id), int(page)
    quiz = await db.get_quiz(quiz_id)
    if quiz is None:
        await call.answer("Topilmadi", show_alert=True)
        return
    total = await db.count_answers(quiz_id)
    answers = await db.list_answers(quiz_id, page * PAGE_SIZE, PAGE_SIZE)

    status = "🟢 faol" if quiz["status"] == "active" else "🔒 yopilgan"
    lines = [
        f"<b>#{quiz_id}</b> — {status}, javoblar: {total}",
        f"<i>{html.escape(quiz['title'][:200])}</i>",
        "",
    ]
    if quiz["winner_answer_id"]:
        w = await db.get_answer(quiz["winner_answer_id"])
        if w:
            lines.append(f"🏆 G'olib: {html.escape(w['full_name'])} — «{html.escape(w['text'])}»\n")
    for i, a in enumerate(answers, start=page * PAGE_SIZE + 1):
        uname = f"@{a['username']}" if a["username"] else f"id{a['user_id']}"
        lines.append(
            f"<b>№{i}</b> {_fmt_time(a['received_at'])} | {html.escape(a['full_name'])} ({uname})\n"
            f"    ➜ {html.escape(a['text'][:300])}"
        )
    if not answers:
        lines.append("Hali javob yo'q.")
    try:
        await call.message.edit_text(
            "\n".join(lines), reply_markup=kb.answers_kb(quiz, answers, page, total, PAGE_SIZE)
        )
    except Exception:
        pass  # matn o'zgarmagan bo'lsa
    await call.answer()


@router.callback_query(F.data.startswith("win:"))
async def ask_winner(call: CallbackQuery):
    answer = await db.get_answer(int(call.data.split(":")[1]))
    if answer is None:
        await call.answer("Topilmadi", show_alert=True)
        return
    await call.message.edit_text(
        f"G'olib sifatida tasdiqlaysizmi?\n\n{html.escape(answer['full_name'])}: «{html.escape(answer['text'])}»",
        reply_markup=kb.confirm_win_kb(answer["id"], answer["quiz_id"]),
    )
    await call.answer()


@router.callback_query(F.data.startswith("winok:"))
async def confirm_winner(call: CallbackQuery, bot: Bot):
    ok, note = await services.choose_winner(bot, int(call.data.split(":")[1]))
    if not ok:
        await call.answer(note, show_alert=True)
        return
    await call.message.edit_text(f"🏆 G'olib tanlandi, viktorina yakunlandi.\n{note}")
    await call.answer()


@router.callback_query(F.data.startswith("close:"))
async def close_without_winner(call: CallbackQuery, bot: Bot):
    quiz_id = int(call.data.split(":")[1])
    if not await services.close(bot, quiz_id):
        await call.answer("Allaqachon yopilgan.", show_alert=True)
        return
    await call.message.edit_text(f"🔒 Viktorina #{quiz_id} g'olibsiz yopildi.")
    await call.answer()
