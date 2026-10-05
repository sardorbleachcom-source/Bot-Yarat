import asyncio
import logging

from aiogram import Bot

from app.bot.loader import bot, dp
from app.handlers import menu, start


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


async def main():
    dp.include_router(start.router)
    dp.include_router(menu.router)

    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()

    logging.info(
        "Bot ishga tushdi: @%s",
        me.username,
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
