from aiogram import Bot, Dispatcher

from app.settings import Settings


settings = Settings()

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()
