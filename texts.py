"""Bot matnlari: standart qiymatlar + paneldan o'zgartirilganlari (settings jadvali)."""
import db

# key: (panel uchun tavsif, standart matn)
DEFAULTS: dict[str, tuple[str, str]] = {
    "start": ("/start (oddiy)", "Assalomu alaykum! Viktorinada qatnashish uchun kanaldagi «Javob berish» tugmasini bosing."),
    "ask_answer": ("Javob so'rash ({title} — savol)", "<b>{title}</b>\n\nJavobingizni bitta xabarda yozing:"),
    "accepted": ("Javob qabul qilindi", "✅ Javobingiz qabul qilindi! Natijalarni kuting."),
    "already": ("Takroriy javob", "Siz bu viktorinaga allaqachon javob yuborgansiz."),
    "closed": ("Viktorina yopiq", "Bu viktorina yakunlangan."),
    "not_found": ("Viktorina topilmadi", "Bunday viktorina topilmadi."),
    "text_only": ("Matn bo'lmagan xabar", "Iltimos, javobni matn ko'rinishida yuboring."),
    "winner": ("G'olibga tabrik", "🎉 Tabriklaymiz! Siz javobni birinchi bo'lib topdingiz va viktorina g'olibiga aylandingiz!"),
    "button": ("Kanaldagi tugma", "✍️ Javob berish"),
    # Savol-javob (avtomatik tekshiruv)
    "qa_ask": ("Savol-javob: javob so'rash ({title} — savol, {left} — qolgan urinish)",
               "<b>{title}</b>\n\nJavobingizni yozing. Urinishlar soni: {left}"),
    "qa_correct": ("Savol-javob: to'g'ri javob", "✅ To'g'ri javob topdingiz!"),
    "qa_wrong": ("Savol-javob: noto'g'ri, urinish qoldi ({left} — qolgan)",
                 "❌ Noto'g'ri javob. Yana urinib ko'ring. Qolgan urinishlar: {left}"),
    "qa_wrong_last": ("Savol-javob: noto'g'ri, urinish tugadi", "❌ Noto'g'ri javob. Urinishlaringiz tugadi."),
    "qa_solved": ("Savol-javob: oldin topgan", "Siz bu savolga allaqachon to'g'ri javob bergansiz ✅"),
    "qa_limit": ("Savol-javob: urinish tugagan", "Bu savol uchun urinishlaringiz tugagan."),
}


async def all_texts() -> dict[str, str]:
    saved = await db.get_settings()
    return {k: saved.get(k, default) for k, (_, default) in DEFAULTS.items()}


async def get(key: str, **fmt) -> str:
    saved = await db.get_settings()
    text = saved.get(key, DEFAULTS[key][1])
    try:
        return text.format(**fmt) if fmt else text
    except (KeyError, IndexError, ValueError):
        return text
