from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.keyboards.common import back_home_keyboard


router = Router()


@router.callback_query(F.data == "home")
async def home_callback(callback: CallbackQuery):
    from app.keyboards.main_menu import main_menu

    await callback.message.edit_text(
        "🏠 Bosh menyu",
        reply_markup=main_menu(),
    )

    await callback.answer()


@router.callback_query(F.data == "back")
async def back_callback(callback: CallbackQuery):
    from app.keyboards.main_menu import main_menu

    await callback.message.edit_text(
        "🏠 Bosh menyu",
        reply_markup=main_menu(),
    )

    await callback.answer()


@router.callback_query(F.data == "create_bot")
async def create_bot_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "➕ Bot yaratish\n\n"
        "Bu bo‘lim keyingi bosqichda ishga tushiriladi.",
        reply_markup=back_home_keyboard(),
    )

    await callback.answer()


@router.callback_query(F.data == "my_bots")
async def my_bots_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "🤖 Mening botlarim\n\n"
        "Hozircha yaratilgan botlar mavjud emas.",
        reply_markup=back_home_keyboard(),
    )

    await callback.answer()


@router.callback_query(F.data == "templates")
async def templates_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "📚 Bot shablonlari\n\n"
        "Shablonlar keyingi bosqichda qo‘shiladi.",
        reply_markup=back_home_keyboard(),
    )

    await callback.answer()


@router.callback_query(F.data == "premium")
async def premium_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "👑 Premium\n\n"
        "Tariflar keyingi bosqichda qo‘shiladi.",
        reply_markup=back_home_keyboard(),
    )

    await callback.answer()


@router.callback_query(F.data == "support")
async def support_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "💬 Admin bilan bog‘lanish\n\n"
        "Murojaat tizimi keyingi bosqichda qo‘shiladi.",
        reply_markup=back_home_keyboard(),
    )

    await callback.answer()


@router.callback_query(F.data == "settings")
async def settings_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚙️ Sozlamalar\n\n"
        "Sozlamalar keyingi bosqichda qo‘shiladi.",
        reply_markup=back_home_keyboard(),
    )

    await callback.answer()


@router.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "📖 Qo‘llanma\n\n"
        "Botdan foydalanish qo‘llanmasi keyingi bosqichda qo‘shiladi.",
        reply_markup=back_home_keyboard(),
    )

    await callback.answer()
