from aiogram import Bot, Dispatcher

from app.config.settings import settings


bot = Bot(token=settings.BOT_TOKEN)

dp = Dispatcher()
