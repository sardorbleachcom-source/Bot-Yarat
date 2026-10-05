from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.keyboards.main_menu import main_menu


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "👋 Assalomu alaykum!\n\n"
        "🤖 BotYarat24Bot — Telegram bot-konstruktor.\n\n"
        "Kod yozmasdan o‘z Telegram botingizni yarating, "
        "sozlang va boshqaring.",
        reply_markup=main_menu(),
    )
