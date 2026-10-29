"""Bot matnlari: standart qiymatlar + paneldan o'zgartirilganlari (settings jadvali)."""
import db

# key: (panel uchun tavsif, standart matn)
DEFAULTS: dict[str, tuple[str, str]] = {
    "start": ("/start (oddiy)", "Assalomu alaykum! Viktorinada qatnaşiş uchun kanaldagi «Javob beriş» tugmasini bosing."),
    "ask_answer": ("Javob sörash ({title} — savol)", "<b>{title}</b>\n\nJavobingizni bitta xabarda yozing:"),
    "accepted": ("Javob qabul qilindi", "✅ Javobingiz qabul qilindi! Natijalarni kuting."),
    "already": ("Takroriy javob", "Siz bu viktorinaga allaqachon javob yuborgansiz."),
    "closed": ("Viktorina yopiq", "Bu viktorina yakunlangan."),
    "not_found": ("Viktorina topilmadi", "Bunday viktorina topilmadi."),
    "text_only": ("Matn bölmagan xabar", "Iltimos, javobni matn körinishida yuboring."),
    "winner": ("Ğolibga tabrik", "🎉 Tabriklaymiz! Siz javobni birinchi bo'lib topdingiz va viktorina Ğolibiga aylandingiz!"),
    "button": ("Kanaldagi tugma", "✍️ Javob beriş"),
    # Savol-javob (avtomatik tekshiruv)
    "qa_ask": ("Savol-javob: javob sörash ({title} — savol, {left} — qolgan urinish)",
               "<b>{title}</b>\n\nJavobingizni yozing. Urinishlar soni: {left}"),
    "qa_correct": ("Savol-javob: töğri javob", "✅ Töğri javob topdingiz!"),
    "qa_wrong": ("Savol-javob: notöğri, urinish qoldi ({left} — qolgan)",
                 "❌ Notöğri javob. Yana urinib köring. Qolgan urinishlar: {left}"),
    "qa_wrong_last": ("Savol-javob: notöğri, urinish tugadi", "❌ Notöğri javob. Urinishlaringiz tugadi."),
    "qa_solved": ("Savol-javob: oldin topgan", "Siz bu savolga allaqachon töğri javob bergansiz ✅"),
    "qa_limit": ("Savol-javob: urinish tugagan", "Bu savol uchun urinishlaringiz tugagan."),
    # To'g'ri javobni ochish (majburiy obuna)
    "reveal_btn": ("Tugma: töğri javobni körish", "🔑 Töğri javobni körish"),
    "subscribe_need": ("Obuna bölish talabi",
                       "Töğri javobni körish uchun quyidagi kanallarga obuna böling, söng «Tekşiriş» tugmasini bosing:"),
    "check_btn": ("Tugma: obunani tekşiriş", "✅ Tekşiriş"),
    "not_subscribed": ("Hali obuna bölmagan (qisqa ogohlantiriş)", "Siz hali barcha kanallarga obuna bölmagansiz"),
    "reveal": ("Töğri javob ({answer} — javob)", "🔑 Töğri javob: <b>{answer}</b>"),
    "reveal_wait": ("Javob hali ochilmaydi", "Töğri javob viktorina yakunlangach ochiladi."),
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
