# Viktorina bot

Kanalda viktorina savoli joylanadi, foydalanuvchilar «Javob berish» tugmasi orqali botga javob yuboradi. Admin javoblarni kelgan vaqt tartibida ko'radi, birinchi to'g'ri javobni g'olib qilib belgilaydi — bot g'olibga tabrik xabarini yuboradi.

## O'rnatish
1. @BotFather'da bot yarating, tokenni oling.
2. Botni kanalga **admin** qilib qo'shing (xabar joylash va tahrirlash huquqi bilan).
3. O'z Telegram ID'ingizni bilib oling (masalan @userinfobot).
4. `.env.example` dan nusxa olib `.env` yarating va to'ldiring.
5. Ishga tushirish:
   ```bash
   pip install -r requirements.txt
   python bot.py
   ```

## Foydalanish (admin)
- `/new` — savolni yuboring (matn yoki rasm+izoh), bot kanalga tugma bilan joylaydi.
- `/quizzes` — viktorinani tanlang → javoblar vaqt tartibida (millisekundgacha). To'g'ri javob yonidagi 🏆 tugmasini bosing va tasdiqlang.
- G'olib tanlangach viktorina yopiladi, kanal postidagi tugma olib tashlanadi.

Har bir foydalanuvchi bitta viktorinaga faqat bir marta javob bera oladi.
