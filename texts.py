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
