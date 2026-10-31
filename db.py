import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    channel_message_id INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    winner_answer_id INTEGER
);
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
    user_id INTEGER NOT NULL,
    username TEXT,
    full_name TEXT,
    text TEXT NOT NULL,
    received_at TEXT NOT NULL,
    UNIQUE (quiz_id, user_id)
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
    user_id INTEGER NOT NULL,
    username TEXT,
    full_name TEXT,
    text TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    received_at TEXT NOT NULL,
    update_id INTEGER
);
CREATE INDEX IF NOT EXISTS attempts_quiz_user ON attempts (quiz_id, user_id);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    name TEXT
);
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL
);
-- Botga yozgan foydalanuvchilar: adminni @username bilan qo'shish uchun
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT
);
CREATE INDEX IF NOT EXISTS users_username ON users (username COLLATE NOCASE);
-- Botga joylangan viktorinaning adminlarga yuborilgan nusxalari (tahrir/o'chirish uchun)
CREATE TABLE IF NOT EXISTS quiz_messages (
    quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
    chat_id TEXT NOT NULL,
    message_id INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS quiz_messages_quiz ON quiz_messages (quiz_id);
"""

# Eski bazaga yangi ustunlar qo'shish
MIGRATIONS = [
    "ALTER TABLE quizzes ADD COLUMN channel_chat_id TEXT",
    "ALTER TABLE quizzes ADD COLUMN has_photo INTEGER NOT NULL DEFAULT 0",
    # Telegram update_id — Telegram serveriga kelish tartibi (eng aniq "kim birinchi")
    "ALTER TABLE answers ADD COLUMN update_id INTEGER",
    # Savol-javob (avtomatik tekshiruv) rejimi
    "ALTER TABLE quizzes ADD COLUMN mode TEXT NOT NULL DEFAULT 'manual'",
    "ALTER TABLE quizzes ADD COLUMN correct_answers TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE quizzes ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 1",
    # Majburiy obuna va to'g'ri javobni ochish
    "ALTER TABLE quizzes ADD COLUMN reveal_text TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE channels ADD COLUMN required INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE channels ADD COLUMN link TEXT",
    "ALTER TABLE admins ADD COLUMN username TEXT",
    # Joriy rasm (panelda ko'rsatish va almashtirish uchun)
    "ALTER TABLE quizzes ADD COLUMN photo_file_id TEXT",
]


async def _fetchall(sql: str, params=()):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(sql, params)
        return await cur.fetchall()


async def _fetchone(sql: str, params=()):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(sql, params)
        return await cur.fetchone()


async def _execute(sql: str, params=()) -> aiosqlite.Cursor:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(sql, params)
        await conn.commit()
        return cur


async def init_db(seed_admins: set[int], seed_channel: int | str | None) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.executescript(SCHEMA)
        for sql in MIGRATIONS:
            try:
                await conn.execute(sql)
            except aiosqlite.OperationalError:
                pass  # ustun allaqachon bor
        # Oldin javob yuborganlar ham @username bo'yicha topilsin
        for table in ("answers", "attempts"):
            await conn.execute(
                f"INSERT OR IGNORE INTO users (user_id, username, full_name) "
                f"SELECT user_id, username, full_name FROM {table} GROUP BY user_id"
            )
        for admin_id in seed_admins:
            await conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
        if seed_channel:
            await conn.execute(
                "INSERT OR IGNORE INTO channels (chat_id, title) VALUES (?, ?)",
                (str(seed_channel), str(seed_channel)),
            )
            await conn.execute(
                "UPDATE quizzes SET channel_chat_id = ? WHERE channel_chat_id IS NULL",
                (str(seed_channel),),
            )
        await conn.commit()


# --- Sozlamalar (bot matnlari) ---

async def get_settings() -> dict[str, str]:
    rows = await _fetchall("SELECT key, value FROM settings")
    return {r["key"]: r["value"] for r in rows}


async def set_setting(key: str, value: str) -> None:
    await _execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


async def delete_setting(key: str) -> None:
    await _execute("DELETE FROM settings WHERE key = ?", (key,))


# --- Adminlar ---

async def list_admins():
    return await _fetchall("SELECT * FROM admins ORDER BY user_id")


async def is_admin(user_id: int) -> bool:
    return await _fetchone("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) is not None


async def add_admin(user_id: int, name: str, username: str | None = None) -> None:
    await _execute(
        "INSERT INTO admins (user_id, name, username) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET name = excluded.name, "
        "username = COALESCE(excluded.username, admins.username)",
        (user_id, name, username),
    )


async def remove_admin(user_id: int) -> None:
    await _execute("DELETE FROM admins WHERE user_id = ?", (user_id,))


# --- Botga yozgan foydalanuvchilar ---

async def save_user(user_id: int, username: str | None, full_name: str) -> None:
    await _execute(
        "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET username = excluded.username, full_name = excluded.full_name",
        (user_id, username, full_name),
    )


async def find_user_by_username(username: str):
    return await _fetchone(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username.lstrip("@"),)
    )


# --- Kanallar ---

async def list_channels():
    return await _fetchall("SELECT * FROM channels ORDER BY id")


async def get_channel(channel_id: int):
    return await _fetchone("SELECT * FROM channels WHERE id = ?", (channel_id,))


async def add_channel(chat_id: str, title: str, link: str | None = None) -> None:
    await _execute(
        "INSERT INTO channels (chat_id, title, link) VALUES (?, ?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title, link = excluded.link",
        (chat_id, title, link),
    )


async def update_channel(channel_id: int, required: bool, link: str | None) -> None:
    await _execute(
        "UPDATE channels SET required = ?, link = ? WHERE id = ?", (int(required), link, channel_id)
    )


async def required_channels():
    return await _fetchall("SELECT * FROM channels WHERE required = 1 ORDER BY id")


async def remove_channel(channel_id: int) -> None:
    await _execute("DELETE FROM channels WHERE id = ?", (channel_id,))


# --- Viktorinalar ---

async def create_quiz(title: str, channel_chat_id: str, has_photo: bool = False,
                      mode: str = "manual", correct_answers: str = "", max_attempts: int = 1,
                      reveal_text: str = "") -> int:
    cur = await _execute(
        "INSERT INTO quizzes (title, channel_chat_id, has_photo, mode, correct_answers, max_attempts, reveal_text) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, channel_chat_id, int(has_photo), mode, correct_answers, max_attempts, reveal_text),
    )
    return cur.lastrowid


async def update_reveal_text(quiz_id: int, reveal_text: str) -> None:
    await _execute("UPDATE quizzes SET reveal_text = ? WHERE id = ?", (reveal_text, quiz_id))


async def update_quiz_answers(quiz_id: int, correct_answers: str, max_attempts: int) -> None:
    await _execute(
        "UPDATE quizzes SET correct_answers = ?, max_attempts = ? WHERE id = ?",
        (correct_answers, max_attempts, quiz_id),
    )


async def set_channel_message(quiz_id: int, message_id: int) -> None:
    await _execute("UPDATE quizzes SET channel_message_id = ? WHERE id = ?", (message_id, quiz_id))


async def update_quiz_title(quiz_id: int, title: str) -> None:
    await _execute("UPDATE quizzes SET title = ? WHERE id = ?", (title, quiz_id))


async def set_quiz_photo(quiz_id: int, file_id: str) -> None:
    await _execute("UPDATE quizzes SET photo_file_id = ? WHERE id = ?", (file_id, quiz_id))


async def delete_quiz(quiz_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM answers WHERE quiz_id = ?", (quiz_id,))
        await conn.execute("DELETE FROM attempts WHERE quiz_id = ?", (quiz_id,))
        await conn.execute("DELETE FROM quiz_messages WHERE quiz_id = ?", (quiz_id,))
        await conn.execute("DELETE FROM quizzes WHERE id = ?", (quiz_id,))
        await conn.commit()


async def add_quiz_message(quiz_id: int, chat_id: int | str, message_id: int) -> None:
    await _execute(
        "INSERT INTO quiz_messages (quiz_id, chat_id, message_id) VALUES (?, ?, ?)",
        (quiz_id, str(chat_id), message_id),
    )


async def list_quiz_messages(quiz_id: int):
    return await _fetchall("SELECT * FROM quiz_messages WHERE quiz_id = ?", (quiz_id,))


async def get_quiz(quiz_id: int):
    return await _fetchone("SELECT * FROM quizzes WHERE id = ?", (quiz_id,))


async def list_quizzes(limit: int = 20, mode: str = "manual"):
    return await _fetchall(
        "SELECT q.*, (SELECT COUNT(*) FROM answers a WHERE a.quiz_id = q.id) AS cnt "
        "FROM quizzes q WHERE q.mode = ? ORDER BY q.id DESC LIMIT ?",
        (mode, limit),
    )


async def list_qa_quizzes(limit: int = 100):
    return await _fetchall(
        "SELECT q.*, "
        "(SELECT COUNT(DISTINCT user_id) FROM attempts t WHERE t.quiz_id = q.id) AS users, "
        "(SELECT COUNT(DISTINCT user_id) FROM attempts t WHERE t.quiz_id = q.id AND t.is_correct) AS solved "
        "FROM quizzes q WHERE q.mode = 'auto' ORDER BY q.id DESC LIMIT ?",
        (limit,),
    )


async def reopen_quiz(quiz_id: int) -> None:
    await _execute(
        "UPDATE quizzes SET status = 'active', winner_answer_id = NULL WHERE id = ?", (quiz_id,)
    )


async def close_quiz(quiz_id: int, winner_answer_id: int | None = None) -> bool:
    """Viktorinani yopadi. Allaqachon yopilgan bo'lsa False."""
    cur = await _execute(
        "UPDATE quizzes SET status = 'closed', winner_answer_id = ? "
        "WHERE id = ? AND status = 'active'",
        (winner_answer_id, quiz_id),
    )
    return cur.rowcount > 0


# --- Javoblar ---

async def add_answer(quiz_id: int, user_id: int, username: str | None,
                     full_name: str, text: str, received_at: str,
                     update_id: int | None = None) -> bool:
    """Javobni saqlaydi. Foydalanuvchi oldin javob bergan bo'lsa False."""
    try:
        await _execute(
            "INSERT INTO answers (quiz_id, user_id, username, full_name, text, received_at, update_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (quiz_id, user_id, username, full_name, text, received_at, update_id),
        )
    except aiosqlite.IntegrityError:
        return False
    return True


async def has_answered(quiz_id: int, user_id: int) -> bool:
    row = await _fetchone(
        "SELECT 1 FROM answers WHERE quiz_id = ? AND user_id = ?", (quiz_id, user_id)
    )
    return row is not None


async def list_answers(quiz_id: int, offset: int = 0, limit: int = -1):
    # Telegram'ga kelish tartibi (update_id); eski yozuvlarda — bot qabul qilgan vaqt
    return await _fetchall(
        "SELECT * FROM answers WHERE quiz_id = ? "
        "ORDER BY update_id IS NULL, update_id, received_at, id LIMIT ? OFFSET ?",
        (quiz_id, limit, offset),
    )


async def count_answers(quiz_id: int) -> int:
    row = await _fetchone("SELECT COUNT(*) AS c FROM answers WHERE quiz_id = ?", (quiz_id,))
    return row["c"]


async def get_answer(answer_id: int):
    return await _fetchone("SELECT * FROM answers WHERE id = ?", (answer_id,))


async def delete_answer(answer_id: int) -> None:
    await _execute("DELETE FROM answers WHERE id = ?", (answer_id,))


# --- Savol-javob urinishlari ---

async def user_attempt_state(quiz_id: int, user_id: int) -> tuple[int, bool]:
    """(urinishlar soni, to'g'ri topganmi)."""
    row = await _fetchone(
        "SELECT COUNT(*) AS n, COALESCE(MAX(is_correct), 0) AS ok FROM attempts "
        "WHERE quiz_id = ? AND user_id = ?",
        (quiz_id, user_id),
    )
    return row["n"], bool(row["ok"])


async def add_attempt(quiz_id: int, user_id: int, username: str | None, full_name: str,
                      text: str, is_correct: bool, received_at: str, update_id: int | None,
                      max_attempts: int) -> str:
    """Urinishni limit doirasida atomar saqlaydi.

    Qaytaradi: 'saved', 'limit' (urinish tugagan) yoki 'solved' (oldin topgan).
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        cur = await conn.execute(
            "SELECT COUNT(*), COALESCE(MAX(is_correct), 0) FROM attempts WHERE quiz_id = ? AND user_id = ?",
            (quiz_id, user_id),
        )
        used, solved = await cur.fetchone()
        if solved:
            await conn.rollback()
            return "solved"
        if used >= max_attempts:
            await conn.rollback()
            return "limit"
        await conn.execute(
            "INSERT INTO attempts (quiz_id, user_id, username, full_name, text, is_correct, received_at, update_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (quiz_id, user_id, username, full_name, text, int(is_correct), received_at, update_id),
        )
        await conn.commit()
        return "saved"


async def list_attempts(quiz_id: int):
    return await _fetchall(
        "SELECT * FROM attempts WHERE quiz_id = ? "
        "ORDER BY update_id IS NULL, update_id, received_at, id",
        (quiz_id,),
    )


async def get_attempt(attempt_id: int):
    return await _fetchone("SELECT * FROM attempts WHERE id = ?", (attempt_id,))


async def delete_user_attempts(quiz_id: int, user_id: int) -> None:
    """Foydalanuvchi urinishlarini o'chirish — u qaytadan javob bera oladi."""
    await _execute("DELETE FROM attempts WHERE quiz_id = ? AND user_id = ?", (quiz_id, user_id))
