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

## Serverga joylash (Coolify)
1. Coolify → **New Resource** → GitHub repozitoriy (`viktorina`), branch `main`.
2. **Build Pack:** `Dockerfile`.
3. **Ports Exposes:** `8000`. **Domains:** `https://panel.sizningdomen.uz` (DNS'da A-yozuv server IP'siga).
4. **Environment Variables:** `BOT_TOKEN`, `ADMIN_IDS`, `CHANNEL_ID`, `PANEL_USER`, `PANEL_PASSWORD`, `SECRET_KEY`, `PANEL_URL=https://panel.sizningdomen.uz`.
5. **Storages:** volume qo'shing, Destination Path: `/data` (baza shu yerda saqlanadi, aks holda har deployda o'chadi).
6. **Deploy**. Keyin GitHub'ga har push qilinganda avtomatik yangilanadi (Coolify GitHub App yoki webhook orqali).

Muhim: bot faqat bitta joyda ishlashi kerak. Serverda ishga tushgach, kompyuterdagi `python bot.py` ni to'xtating.
