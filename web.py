"""Veb admin panel (FastAPI). Bot bilan bitta jarayonda ishlaydi."""
import io
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook
from starlette.middleware.sessions import SessionMiddleware

import db
import matcher
import services
import texts
from config import PANEL_PASSWORD, PANEL_SECURE, PANEL_USER, SECRET_KEY

TZ = timezone(timedelta(hours=5))  # Toshkent vaqti

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="strict",
                   https_only=PANEL_SECURE, max_age=7 * 24 * 3600)
templates = Jinja2Templates(directory="templates")


def fmt_time(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(TZ).strftime("%d.%m.%Y %H:%M:%S.%f")[:-3]


templates.env.filters["t"] = fmt_time


class LoginRequired(Exception):
    pass


@app.exception_handler(LoginRequired)
async def _to_login(request: Request, exc: LoginRequired):
    return RedirectResponse("/login", status_code=303)


def auth(request: Request) -> None:
    if not request.session.get("auth"):
        raise LoginRequired()


def get_bot(request: Request) -> Bot:
    return request.app.state.bot


def flash(request: Request, msg: str, kind: str = "ok") -> None:
    request.session["flash"] = [kind, msg]


def render(request: Request, name: str, **ctx) -> HTMLResponse:
    ctx["flash"] = request.session.pop("flash", None)
    return templates.TemplateResponse(request, name, ctx)


def back(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


# --- Kirish ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render(request, "login.html", no_password=not PANEL_PASSWORD)


# Parolni terib topishdan himoya: IP bo'yicha 15 daqiqada 5 ta xato urinish
MAX_FAILS, FAIL_WINDOW = 5, 15 * 60
_fails: dict[str, deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    # Coolify proxy'si haqiqiy IP'ni X-Forwarded-For oxiriga qo'shadi
    # (boshidagi qiymatlarni mijoz o'zi soxtalashtirishi mumkin)
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[-1].strip() if forwarded else request.client.host


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    ip, now = client_ip(request), time.monotonic()
    fails = _fails[ip]
    while fails and now - fails[0] > FAIL_WINDOW:
        fails.popleft()
    if len(fails) >= MAX_FAILS:
        flash(request, "Juda ko'p urinish. 15 daqiqadan keyin qayta urinib ko'ring.", "err")
        return back("/login")
    if PANEL_PASSWORD and secrets.compare_digest(username, PANEL_USER) \
            and secrets.compare_digest(password, PANEL_PASSWORD):
        fails.clear()
        request.session["auth"] = True
        return back("/")
    fails.append(now)
    flash(request, "Login yoki parol noto'g'ri", "err")
    return back("/login")


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return back("/login")


# --- Viktorinalar ---

@app.get("/", response_class=HTMLResponse, dependencies=[Depends(auth)])
async def dashboard(request: Request):
    return render(request, "dashboard.html",
                  quizzes=await db.list_quizzes(100), channels=await db.list_channels())


@app.post("/quiz/new", dependencies=[Depends(auth)])
async def quiz_new(request: Request, channel_id: int = Form(...), text: str = Form(...),
                   photo: UploadFile | None = File(None), bot: Bot = Depends(get_bot)):
    channel = await db.get_channel(channel_id)
    if channel is None:
        flash(request, "Kanal topilmadi", "err")
        return back("/")
    data = await photo.read() if photo and photo.filename else None
    try:
        quiz_id = await services.publish_text(bot, channel["chat_id"], text.strip(), data,
                                              photo.filename if data else "photo.jpg")
    except Exception as e:
        flash(request, f"Kanalga joylab bo'lmadi: {e}. Bot kanalda admin ekanini tekshiring.", "err")
        return back("/")
    flash(request, f"Viktorina #{quiz_id} kanalga joylandi")
    return back(f"/quiz/{quiz_id}")


async def _quiz_or_404(quiz_id: int):
    quiz = await db.get_quiz(quiz_id)
    if quiz is None:
        raise HTTPException(404, "Viktorina topilmadi")
    return quiz


@app.get("/quiz/{quiz_id}", response_class=HTMLResponse, dependencies=[Depends(auth)])
async def quiz_page(request: Request, quiz_id: int):
    quiz = await _quiz_or_404(quiz_id)
    if quiz["mode"] == "auto":
        return back(f"/qa/{quiz_id}")
    winner = await db.get_answer(quiz["winner_answer_id"]) if quiz["winner_answer_id"] else None
    return render(request, "quiz.html", quiz=quiz, winner=winner,
                  answers=await db.list_answers(quiz_id))


@app.get("/quiz/{quiz_id}/rows", response_class=HTMLResponse, dependencies=[Depends(auth)])
async def quiz_rows(request: Request, quiz_id: int):
    quiz = await _quiz_or_404(quiz_id)
    return templates.TemplateResponse(request, "_rows.html",
                                      {"quiz": quiz, "answers": await db.list_answers(quiz_id)})


@app.post("/quiz/{quiz_id}/edit", dependencies=[Depends(auth)])
async def quiz_edit(request: Request, quiz_id: int, text: str = Form(...), bot: Bot = Depends(get_bot)):
    await _quiz_or_404(quiz_id)
    try:
        await services.edit_quiz_text(bot, quiz_id, text.strip())
        flash(request, "Savol yangilandi (kanalda ham)")
    except Exception as e:
        flash(request, f"Tahrirlab bo'lmadi: {e}", "err")
    return back(f"/quiz/{quiz_id}")


@app.post("/quiz/{quiz_id}/close", dependencies=[Depends(auth)])
async def quiz_close(request: Request, quiz_id: int, bot: Bot = Depends(get_bot)):
    await services.close(bot, quiz_id)
    flash(request, "Viktorina yopildi")
    return back(f"/quiz/{quiz_id}")


@app.post("/quiz/{quiz_id}/reopen", dependencies=[Depends(auth)])
async def quiz_reopen(request: Request, quiz_id: int, bot: Bot = Depends(get_bot)):
    await services.reopen(bot, quiz_id)
    flash(request, "Viktorina qayta ochildi (g'olib bekor qilindi)")
    return back(f"/quiz/{quiz_id}")


@app.post("/quiz/{quiz_id}/delete", dependencies=[Depends(auth)])
async def quiz_delete(request: Request, quiz_id: int, from_channel: str | None = Form(None),
                      bot: Bot = Depends(get_bot)):
    quiz = await _quiz_or_404(quiz_id)
    await services.delete(bot, quiz_id, from_channel=bool(from_channel))
    flash(request, f"Viktorina #{quiz_id} o'chirildi")
    return back("/qa" if quiz["mode"] == "auto" else "/")


@app.post("/answer/{answer_id}/win", dependencies=[Depends(auth)])
async def answer_win(request: Request, answer_id: int, bot: Bot = Depends(get_bot)):
    answer = await db.get_answer(answer_id)
    ok, note = await services.choose_winner(bot, answer_id)
    flash(request, ("G'olib tanlandi. " if ok else "") + note, "ok" if ok else "err")
    return back(f"/quiz/{answer['quiz_id']}" if answer else "/")


@app.post("/answer/{answer_id}/delete", dependencies=[Depends(auth)])
async def answer_delete(request: Request, answer_id: int):
    answer = await db.get_answer(answer_id)
    await db.delete_answer(answer_id)
    flash(request, "Javob o'chirildi (foydalanuvchi qayta javob bera oladi)")
    return back(f"/quiz/{answer['quiz_id']}" if answer else "/")


@app.get("/quiz/{quiz_id}/export", dependencies=[Depends(auth)])
async def quiz_export(quiz_id: int):
    quiz = await _quiz_or_404(quiz_id)
    wb = Workbook()
    ws = wb.active
    ws.title = f"Viktorina {quiz_id}"
    ws.append(["№", "Vaqt", "Ism", "Username", "User ID", "Javob", "G'olib"])
    for i, a in enumerate(await db.list_answers(quiz_id), start=1):
        ws.append([i, fmt_time(a["received_at"]), a["full_name"],
                   f"@{a['username']}" if a["username"] else "", a["user_id"], a["text"],
                   "🏆" if a["id"] == quiz["winner_answer_id"] else ""])
    for col, width in zip("ABCDEFG", (5, 24, 25, 18, 14, 50, 8)):
        ws.column_dimensions[col].width = width
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="viktorina_{quiz_id}.xlsx"'},
    )


# --- Savol-javob (avtomatik tekshiruv) ---

MAX_ATTEMPTS = 10


def _attempts_arg(value: int) -> int:
    return max(1, min(MAX_ATTEMPTS, value))


def _qa_summary(attempts) -> list[dict]:
    """Foydalanuvchilar kesimida: urinishlar, to'g'ri topganmi, birinchi to'g'ri javob tartibi."""
    users: dict[int, dict] = {}
    for t in attempts:
        u = users.setdefault(t["user_id"], {
            "user_id": t["user_id"], "full_name": t["full_name"], "username": t["username"],
            "tries": [], "solved_at": None,
        })
        u["tries"].append(t)
        if t["is_correct"] and u["solved_at"] is None:
            u["solved_at"] = t["received_at"]
            u["solved_order"] = sum(1 for x in users.values() if x["solved_at"])
    return sorted(users.values(), key=lambda u: (u["solved_at"] is None, u.get("solved_order", 0)))


@app.get("/qa", response_class=HTMLResponse, dependencies=[Depends(auth)])
async def qa_list(request: Request):
    return render(request, "qa_list.html", quizzes=await db.list_qa_quizzes(),
                  channels=await db.list_channels(), max_attempts=MAX_ATTEMPTS)


@app.post("/qa/new", dependencies=[Depends(auth)])
async def qa_new(request: Request, channel_id: int = Form(...), text: str = Form(...),
                 answers: str = Form(...), max_attempts: int = Form(3),
                 photo: UploadFile | None = File(None), bot: Bot = Depends(get_bot)):
    if not matcher.variants(answers):
        flash(request, "Kamida bitta to'g'ri javob kiriting", "err")
        return back("/qa")
    channel = await db.get_channel(channel_id)
    if channel is None:
        flash(request, "Kanal topilmadi", "err")
        return back("/qa")
    data = await photo.read() if photo and photo.filename else None
    try:
        quiz_id = await services.publish_text(
            bot, channel["chat_id"], text.strip(), data, photo.filename if data else "photo.jpg",
            mode="auto", correct_answers="\n".join(matcher.variants(answers)),
            max_attempts=_attempts_arg(max_attempts),
        )
    except Exception as e:
        flash(request, f"Kanalga joylab bo'lmadi: {e}. Bot kanalda admin ekanini tekshiring.", "err")
        return back("/qa")
    flash(request, f"Savol #{quiz_id} kanalga joylandi")
    return back(f"/qa/{quiz_id}")


async def _qa_or_404(quiz_id: int):
    quiz = await _quiz_or_404(quiz_id)
    if quiz["mode"] != "auto":
        raise HTTPException(404, "Savol-javob topilmadi")
    return quiz


@app.get("/qa/{quiz_id}", response_class=HTMLResponse, dependencies=[Depends(auth)])
async def qa_page(request: Request, quiz_id: int):
    quiz = await _qa_or_404(quiz_id)
    attempts = await db.list_attempts(quiz_id)
    return render(request, "qa_quiz.html", quiz=quiz, attempts=attempts, users=_qa_summary(attempts),
                  max_attempts=MAX_ATTEMPTS, test=request.session.pop("qa_test", None))


@app.get("/qa/{quiz_id}/rows", response_class=HTMLResponse, dependencies=[Depends(auth)])
async def qa_rows(request: Request, quiz_id: int):
    quiz = await _qa_or_404(quiz_id)
    attempts = await db.list_attempts(quiz_id)
    return templates.TemplateResponse(request, "_qa_rows.html",
                                      {"quiz": quiz, "users": _qa_summary(attempts)})


@app.post("/qa/{quiz_id}/answers", dependencies=[Depends(auth)])
async def qa_answers(request: Request, quiz_id: int, answers: str = Form(...), max_attempts: int = Form(...)):
    await _qa_or_404(quiz_id)
    if not matcher.variants(answers):
        flash(request, "Kamida bitta to'g'ri javob kiriting", "err")
        return back(f"/qa/{quiz_id}")
    await db.update_quiz_answers(quiz_id, "\n".join(matcher.variants(answers)), _attempts_arg(max_attempts))
    flash(request, "To'g'ri javoblar va urinishlar soni saqlandi (keyingi javoblarga qo'llanadi)")
    return back(f"/qa/{quiz_id}")


@app.post("/qa/{quiz_id}/test", dependencies=[Depends(auth)])
async def qa_test(request: Request, quiz_id: int, sample: str = Form(...)):
    quiz = await _qa_or_404(quiz_id)
    request.session["qa_test"] = [sample, matcher.is_correct(sample, quiz["correct_answers"])]
    return back(f"/qa/{quiz_id}")


@app.post("/qa/{quiz_id}/reset/{user_id}", dependencies=[Depends(auth)])
async def qa_reset_user(request: Request, quiz_id: int, user_id: int):
    await db.delete_user_attempts(quiz_id, user_id)
    flash(request, "Foydalanuvchi urinishlari o'chirildi — u qaytadan javob bera oladi")
    return back(f"/qa/{quiz_id}")


@app.get("/qa/{quiz_id}/export", dependencies=[Depends(auth)])
async def qa_export(quiz_id: int):
    await _qa_or_404(quiz_id)
    wb = Workbook()
    ws = wb.active
    ws.title = f"Savol {quiz_id}"
    ws.append(["№", "Vaqt", "Ism", "Username", "User ID", "Javob", "Natija"])
    for i, t in enumerate(await db.list_attempts(quiz_id), start=1):
        ws.append([i, fmt_time(t["received_at"]), t["full_name"],
                   f"@{t['username']}" if t["username"] else "", t["user_id"], t["text"],
                   "To'g'ri" if t["is_correct"] else "Noto'g'ri"])
    for col, width in zip("ABCDEFG", (5, 24, 25, 18, 14, 50, 12)):
        ws.column_dimensions[col].width = width
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="savol_javob_{quiz_id}.xlsx"'},
    )


# --- Bot matnlari ---

@app.get("/texts", response_class=HTMLResponse, dependencies=[Depends(auth)])
async def texts_page(request: Request):
    current = await texts.all_texts()
    items = [(k, label, current[k], default) for k, (label, default) in texts.DEFAULTS.items()]
    return render(request, "texts.html", items=items)


@app.post("/texts", dependencies=[Depends(auth)])
async def texts_save(request: Request):
    form = await request.form()
    for key, (_, default) in texts.DEFAULTS.items():
        value = str(form.get(key, "")).strip()
        if not value or value == default:
            await db.delete_setting(key)
        else:
            await db.set_setting(key, value)
    flash(request, "Matnlar saqlandi")
    return back("/texts")


@app.post("/texts/{key}/reset", dependencies=[Depends(auth)])
async def texts_reset(request: Request, key: str):
    await db.delete_setting(key)
    flash(request, "Standart matn tiklandi")
    return back("/texts")


# --- Adminlar ---

@app.get("/admins", response_class=HTMLResponse, dependencies=[Depends(auth)])
async def admins_page(request: Request):
    return render(request, "admins.html", admins=await db.list_admins())


@app.post("/admins/add", dependencies=[Depends(auth)])
async def admins_add(request: Request, user_id: str = Form(...), name: str = Form("")):
    if not user_id.strip().isdigit():
        flash(request, "Telegram ID faqat raqamlardan iborat bo'lishi kerak", "err")
        return back("/admins")
    await db.add_admin(int(user_id), name.strip())
    flash(request, "Admin qo'shildi")
    return back("/admins")


@app.post("/admins/{user_id}/delete", dependencies=[Depends(auth)])
async def admins_delete(request: Request, user_id: int):
    await db.remove_admin(user_id)
    flash(request, "Admin o'chirildi")
    return back("/admins")


# --- Kanallar ---

@app.get("/channels", response_class=HTMLResponse, dependencies=[Depends(auth)])
async def channels_page(request: Request):
    return render(request, "channels.html", channels=await db.list_channels())


@app.post("/channels/add", dependencies=[Depends(auth)])
async def channels_add(request: Request, chat_id: str = Form(...), bot: Bot = Depends(get_bot)):
    chat_id = chat_id.strip()
    try:
        chat = await bot.get_chat(services.chat_ref(chat_id))
        me = await bot.get_me()
        member = await bot.get_chat_member(chat.id, me.id)
    except Exception as e:
        flash(request, f"Kanal topilmadi yoki bot kanalga qo'shilmagan: {e}", "err")
        return back("/channels")
    if member.status not in ("administrator", "creator"):
        flash(request, "Bot bu kanalda admin emas. Avval botni kanalga admin qiling.", "err")
        return back("/channels")
    await db.add_channel(str(chat.id), chat.title or chat_id)
    flash(request, f"Kanal qo'shildi: {chat.title}")
    return back("/channels")


@app.post("/channels/{channel_id}/delete", dependencies=[Depends(auth)])
async def channels_delete(request: Request, channel_id: int):
    await db.remove_channel(channel_id)
    flash(request, "Kanal o'chirildi")
    return back("/channels")
