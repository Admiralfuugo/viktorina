from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def channel_kb(bot_username: str, quiz_id: int, text: str) -> InlineKeyboardMarkup:
    url = f"https://t.me/{bot_username}?start=q_{quiz_id}"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, url=url)]])


def reveal_kb(quiz_id: int, text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=f"rv:{quiz_id}")]])


def channel_url(channel) -> str | None:
    if channel["link"]:
        return channel["link"]
    if channel["chat_id"].startswith("@"):
        return f"https://t.me/{channel['chat_id'][1:]}"
    return None


def subscribe_kb(channels, quiz_id: int, check_text: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"➕ {c['title']}", url=channel_url(c))]
            for c in channels if channel_url(c)]
    rows.append([InlineKeyboardButton(text=check_text, callback_data=f"rv:{quiz_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channels_kb(channels, bot_username: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=c["title"], callback_data=f"ch:{c['id']}")] for c in channels]
    # ch:0 — botning o'zi: post faqat adminlarga boradi
    rows.append([InlineKeyboardButton(text=f"🤖 @{bot_username} (faqat adminlar)", callback_data="ch:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quizzes_kb(quizzes) -> InlineKeyboardMarkup:
    rows = []
    for q in quizzes:
        mark = "🟢" if q["status"] == "active" else "🔒"
        title = q["title"][:30]
        rows.append([InlineKeyboardButton(
            text=f"{mark} #{q['id']} {title} ({q['cnt']})", callback_data=f"ql:{q['id']}:0"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def answers_kb(quiz, answers, page: int, total: int, page_size: int) -> InlineKeyboardMarkup:
    rows = []
    if quiz["status"] == "active":
        for i, a in enumerate(answers, start=page * page_size + 1):
            rows.append([InlineKeyboardButton(
                text=f"🏆 №{i} — {a['full_name'][:25]}", callback_data=f"win:{a['id']}"
            )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"ql:{quiz['id']}:{page - 1}"))
    nav.append(InlineKeyboardButton(text="🔄", callback_data=f"ql:{quiz['id']}:{page}"))
    if (page + 1) * page_size < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"ql:{quiz['id']}:{page + 1}"))
    rows.append(nav)
    if quiz["status"] == "active":
        rows.append([InlineKeyboardButton(text="🔒 G'olibsiz yopish", callback_data=f"close:{quiz['id']}")])
    rows.append([InlineKeyboardButton(text="📋 Viktorinalar", callback_data="qlist")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_win_kb(answer_id: int, quiz_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"winok:{answer_id}"),
        InlineKeyboardButton(text="❌ Bekor", callback_data=f"ql:{quiz_id}:0"),
    ]])
