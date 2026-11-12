"""Bosh sahifa uchun analitika: barcha hisob-kitob shu yerda (baza kichik — Python'da sanaymiz)."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

import db

TZ = timezone(timedelta(hours=5))  # Toshkent vaqti
DAYS = 30


def _local(iso: str) -> datetime:
    return datetime.fromisoformat(iso).astimezone(TZ)


def _created(value: str) -> datetime:
    # created_at — SQLite datetime('now'), UTC, zona belgisisiz
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).astimezone(TZ)


async def build() -> dict:
    quizzes = await db._fetchall("SELECT * FROM quizzes ORDER BY id")
    answers = await db._fetchall(
        "SELECT quiz_id, user_id, username, full_name, received_at FROM answers")
    attempts = await db._fetchall(
        "SELECT quiz_id, user_id, username, full_name, is_correct, received_at FROM attempts "
        "ORDER BY update_id IS NULL, update_id, received_at, id")
    bot_users = (await db._fetchone("SELECT COUNT(*) AS c FROM users"))["c"]

    by_id = {q["id"]: q for q in quizzes}
    today = datetime.now(TZ).date()
    days = [today - timedelta(days=i) for i in range(DAYS - 1, -1, -1)]

    # --- Kunlik va soatlik faollik ---
    daily_manual: Counter[date] = Counter()
    daily_auto: Counter[date] = Counter()
    hourly = [0] * 24
    for a in answers:
        t = _local(a["received_at"])
        daily_manual[t.date()] += 1
        hourly[t.hour] += 1
    for t_ in attempts:
        t = _local(t_["received_at"])
        daily_auto[t.date()] += 1
        hourly[t.hour] += 1

    def period(start: int, end: int) -> int:
        span = [today - timedelta(days=i) for i in range(start, end)]
        return sum(daily_manual[d] + daily_auto[d] for d in span)

    # --- Ishtirokchilar ---
    people: dict[int, dict] = {}

    def person(row) -> dict:
        p = people.setdefault(row["user_id"], {
            "user_id": row["user_id"], "name": row["full_name"] or "", "username": row["username"],
            "quizzes": set(), "responses": 0, "correct": 0, "wins": 0,
        })
        p["name"] = row["full_name"] or p["name"]
        p["username"] = row["username"] or p["username"]
        return p

    winners = {q["winner_answer_id"] for q in quizzes if q["winner_answer_id"]}
    win_rows = await db._fetchall("SELECT id, user_id FROM answers WHERE id IN (%s)" %
                                  ",".join("?" * len(winners)), tuple(winners)) if winners else []
    win_users = Counter(r["user_id"] for r in win_rows)

    for a in answers:
        p = person(a)
        p["quizzes"].add(a["quiz_id"])
        p["responses"] += 1

    # Savol-javob: har bir (savol, foydalanuvchi) juftligi uchun urinishlar va natija
    pairs: dict[tuple[int, int], dict] = defaultdict(lambda: {"tries": 0, "solved_on": None})
    for t in attempts:
        p = person(t)
        p["quizzes"].add(t["quiz_id"])
        p["responses"] += 1
        pair = pairs[(t["quiz_id"], t["user_id"])]
        if pair["solved_on"] is None:
            pair["tries"] += 1
            if t["is_correct"]:
                pair["solved_on"] = pair["tries"]
                p["correct"] += 1
    for uid, n in win_users.items():
        if uid in people:
            people[uid]["wins"] = n

    top_people = sorted(people.values(),
                        key=lambda p: (-(p["correct"] + p["wins"]), -len(p["quizzes"]), -p["responses"]))[:10]

    # --- Viktorinalar kesimida ---
    participants: dict[int, set] = defaultdict(set)
    for a in answers:
        participants[a["quiz_id"]].add(a["user_id"])
    for t in attempts:
        participants[t["quiz_id"]].add(t["user_id"])

    top_quizzes = sorted(
        ({"id": q["id"], "title": q["title"], "mode": q["mode"], "count": len(participants[q["id"]])}
         for q in quizzes if participants[q["id"]]),
        key=lambda x: -x["count"],
    )[:8]

    # Savol-javob natijalari: so'nggi 8 ta savol
    outcomes = []
    for q in [q for q in quizzes if q["mode"] == "auto"][-8:][::-1]:
        solved = failed = trying = 0
        for (qid, _), pair in pairs.items():
            if qid != q["id"]:
                continue
            if pair["solved_on"]:
                solved += 1
            elif pair["tries"] >= q["max_attempts"]:
                failed += 1
            else:
                trying += 1
        outcomes.append({"id": q["id"], "title": q["title"], "solved": solved, "failed": failed,
                         "trying": trying, "status": q["status"]})

    solved_on = Counter(p["solved_on"] for p in pairs.values() if p["solved_on"])
    max_try = max(solved_on, default=0)
    auto_pairs = len(pairs)
    auto_solved = sum(1 for p in pairs.values() if p["solved_on"])

    # So'nggi viktorinalar (holat bilan)
    recent = [{"id": q["id"], "title": q["title"], "mode": q["mode"], "status": q["status"],
               "count": len(participants[q["id"]]), "created": _created(q["created_at"]).strftime("%d.%m %H:%M"),
               "bot": q["channel_chat_id"] == "bot"}
              for q in quizzes[-6:][::-1]]

    week, prev_week = period(0, 7), period(7, 14)
    return {
        "kpi": {
            "participants": len(people),
            "bot_users": bot_users,
            "quizzes": len(quizzes),
            "quizzes_manual": sum(1 for q in quizzes if q["mode"] != "auto"),
            "quizzes_auto": sum(1 for q in quizzes if q["mode"] == "auto"),
            "active": sum(1 for q in quizzes if q["status"] == "active"),
            "responses": len(answers) + len(attempts),
            "today": daily_manual[today] + daily_auto[today],
            "week": week,
            "week_delta": (round((week - prev_week) * 100 / prev_week) if prev_week else None),
            "success_rate": round(auto_solved * 100 / auto_pairs) if auto_pairs else None,
            "winners": len(winners),
        },
        "daily": {
            "labels": [d.strftime("%d.%m") for d in days],
            "manual": [daily_manual[d] for d in days],
            "auto": [daily_auto[d] for d in days],
        },
        "hourly": hourly,
        "top_quizzes": top_quizzes,
        "outcomes": outcomes,
        "solved_on": [solved_on[i] for i in range(1, max_try + 1)],
        "top_people": [{"name": p["name"], "username": p["username"], "quizzes": len(p["quizzes"]),
                        "responses": p["responses"], "correct": p["correct"], "wins": p["wins"]}
                       for p in top_people],
        "recent": recent,
    }
