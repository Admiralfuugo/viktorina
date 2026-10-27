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
"""

# Eski bazaga yangi ustunlar qo'shish
MIGRATIONS = [
    "ALTER TABLE quizzes ADD COLUMN channel_chat_id TEXT",
    "ALTER TABLE quizzes ADD COLUMN has_photo INTEGER NOT NULL DEFAULT 0",
    # Telegram update_id — Telegram serveriga kelish tartibi (eng aniq "kim birinchi")
    "ALTER TABLE answers ADD COLUMN update_id INTEGER",
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


async def add_admin(user_id: int, name: str) -> None:
    await _execute(
        "INSERT INTO admins (user_id, name) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET name = excluded.name",
        (user_id, name),
    )


async def remove_admin(user_id: int) -> None:
    await _execute("DELETE FROM admins WHERE user_id = ?", (user_id,))


# --- Kanallar ---

async def list_channels():
    return await _fetchall("SELECT * FROM channels ORDER BY id")


async def get_channel(channel_id: int):
    return await _fetchone("SELECT * FROM channels WHERE id = ?", (channel_id,))


async def add_channel(chat_id: str, title: str) -> None:
    await _execute(
        "INSERT INTO channels (chat_id, title) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title",
        (chat_id, title),
    )


async def remove_channel(channel_id: int) -> None:
    await _execute("DELETE FROM channels WHERE id = ?", (channel_id,))


# --- Viktorinalar ---

async def create_quiz(title: str, channel_chat_id: str, has_photo: bool = False) -> int:
    cur = await _execute(
        "INSERT INTO quizzes (title, channel_chat_id, has_photo) VALUES (?, ?, ?)",
        (title, channel_chat_id, int(has_photo)),
    )
    return cur.lastrowid


async def set_channel_message(quiz_id: int, message_id: int) -> None:
    await _execute("UPDATE quizzes SET channel_message_id = ? WHERE id = ?", (message_id, quiz_id))


async def update_quiz_title(quiz_id: int, title: str) -> None:
    await _execute("UPDATE quizzes SET title = ? WHERE id = ?", (title, quiz_id))


async def delete_quiz(quiz_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM answers WHERE quiz_id = ?", (quiz_id,))
        await conn.execute("DELETE FROM quizzes WHERE id = ?", (quiz_id,))
        await conn.commit()


async def get_quiz(quiz_id: int):
    return await _fetchone("SELECT * FROM quizzes WHERE id = ?", (quiz_id,))


async def list_quizzes(limit: int = 20):
    return await _fetchall(
        "SELECT q.*, (SELECT COUNT(*) FROM answers a WHERE a.quiz_id = q.id) AS cnt "
        "FROM quizzes q ORDER BY q.id DESC LIMIT ?",
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
