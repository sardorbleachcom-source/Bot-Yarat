# BotYarat24Bot

Telegram ichida kod yozmasdan bot yaratish konstruktori (🇺🇿 🇷🇺 🇬🇧 🇸🇦).

## Ishga tushirish
```
pip install -r requirements.txt
cp .env.example .env      # BOT_TOKEN va ADMIN_ID ni yozing
python main.py
```
- `BOT_TOKEN` — @BotYarat24Bot tokeni (@BotFather)
- `ADMIN_ID` — Super Admin Telegram ID (bir nechta bo'lsa vergul bilan)
- `SECRET_KEY` — bo'sh qolsa, birinchi ishga tushishda o'zi yaratilib `.env` ga yoziladi. **Uni zaxirada saqlang**: yo'qolsa, bazadagi tokenlarni ochib bo'lmaydi.
- Railway: Variables ga `BOT_TOKEN`, `ADMIN_ID`, `SECRET_KEY`, `DATA_DIR=/data` qo'shing va Volume ni `/data` ga ulang.

## Tuzilma
```
main.py            ishga tushirish
app/config.py      sozlamalar, logging (tokenlar yashiriladi)
app/core.py        marshrutlash, rate limit, xatolarni ushlash
app/tg.py          Telegram API klienti (aiohttp)
app/database.py    SQLite sxema va so'rovlar
app/security.py    shifrlash, token tekshiruvi, filtrlar
app/services.py    Premium, botlarni ishga tushirish, zaxira, xabar yuborish
app/child.py       yaratilgan botlarning ish mantig'i
app/templates_data.py  tayyor shablonlar
app/handlers/      user.py, mybots.py, admin.py
locales/           uz.json ru.json en.json ar.json
```
