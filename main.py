# -*- coding: utf-8 -*-
"""BotYarat24Bot — Telegram bot konstruktori. Ishga tushirish: python main.py"""
import asyncio
import logging

from app import config

config.setup_logging()
log = logging.getLogger("main")

if not config.BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN topilmadi. .env faylini tekshiring.")
if not config.SUPER_ADMINS:
    raise SystemExit("❌ ADMIN_ID topilmadi. .env ga ADMIN_ID=Telegram_ID qo'shing.")

from app import core  # noqa: E402
from app.handlers import admin, mybots, user  # noqa: E402,F401  (handlerlarni ro'yxatdan o'tkazadi)
from app.tg import TGError, poll  # noqa: E402


async def main():
    app = core.App()
    await app.start()
    log.info("✅ @%s ishga tushdi. Botlar ishga tushirildi.", app.me.get("username"))
    try:
        await poll(app.tg, lambda u: core.handle(app, u), name="main")
    except TGError as e:
        log.error("Asosiy bot to'xtadi: %s", e.desc)
        if e.code == 409:
            log.error("Shu token boshqa joyda ham ishlayapti. Faqat bitta nusxa ishlashi kerak.")
    finally:
        await app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
