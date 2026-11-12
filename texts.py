"""Bot matnlari: standart qiymatlar + paneldan o'zgartirilganlari (settings jadvali)."""
import db

# key: (panel uchun tavsif, standart matn)
DEFAULTS: dict[str, tuple[str, str]] = {
    "start": ("/start (oddiy)", "Assalomu alaykum! Viktorinada qatnaşiş uçun kanaldagi «Javob beriş» tugmasini bosing."),
    "ask_answer": ("Javob söraş ({title} — savol)", "<b>{title}</b>\n\nJavobingizni bitta xabarda yozing:"),
    "accepted": ("Javob qabul qilindi", "✅ Javobingiz qabul qilindi! Natijalarni kuting."),
    "already": ("Takroriy javob", "Siz bu viktorinaga allaqaçon javob yuborgansiz."),
    "closed": ("Viktorina yopiq", "Bu viktorina yakunlangan."),
    "not_found": ("Viktorina topilmadi", "Bunday viktorina topilmadi."),
    "text_only": ("Matn bölmagan xabar", "Iltimos, javobni matn körinişida yuboring."),
    "winner": ("Çolibga tabrik", "🎉 Tabriklaymiz! Siz javobni birinçi bölib topdingiz va viktorina ğolibiga aylandingiz!"),
    "button": ("Kanaldagi tugma", "✍️ Javob beriş"),
    # Savol-javob (avtomatik tekshiruv)
    "qa_ask": ("Savol-javob: javob söraş ({title} — savol, {left} — qolgan uriniş)",
               "<b>{title}</b>\n\nJavobingizni yozing. Urinişlar soni: {left}"),
    "qa_correct": ("Savol-javob: töğri javob", "✅ Töğri javob topdingiz!"),
    "qa_wrong": ("Savol-javob: notöğri, uriniş qoldi ({left} — qolgan)",
                 "❌ Notöğri javob. Yana urinib köring. Qolgan urinişlar: {left}"),
    "qa_wrong_last": ("Savol-javob: notöğri, uriniş tugadi", "❌ Notöğri javob. Urinişlaringiz tugadi."),
    "qa_solved": ("Savol-javob: oldin topgan", "Siz bu savolga allaqaçon töğri javob bergansiz ✅"),
    "qa_limit": ("Savol-javob: uriniş tugagan", "Bu savol uchun urinişlaringiz tugagan."),
    # To'g'ri javobni ochish (majburiy obuna)
    "reveal_btn": ("Tugma: töğri javobni köriş", "🔑 Töğri javobni köriş"),
    "subscribe_need": ("Obuna bo'liş talabi",
                       "Töğri javobni köriş uchun quyidagi kanallarga obuna böling, söng «Tekşiriş» tugmasini bosing:"),
    "check_btn": ("Tugma: obunani tekşiriş", "✅ Tekşiriş"),
    "not_subscribed": ("Hali obuna bölmagan (qisqa ogohlantiriş)", "Siz hali barcha kanallarga obuna bölmagansiz"),
    "reveal": ("Töğri javob ({answer} — javob)", "🔑 Töğri javob: <b>{answer}</b>"),
    "reveal_wait": ("Javob hali oçilmaydi", "Töğri javob viktorina yakunlangaç oçiladi."),
    "reveal_none": ("Töğri javob kiritilmagan", "Bu savol uchun töğri javob hali e'lon qilinmagan."),
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
