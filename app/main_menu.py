from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Bot yaratish",
                    callback_data="create_bot",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🤖 Mening botlarim",
                    callback_data="my_bots",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📚 Bot shablonlari",
                    callback_data="templates",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👑 Premium",
                    callback_data="premium",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💬 Admin bilan bog‘lanish",
                    callback_data="support",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Sozlamalar",
                    callback_data="settings",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📖 Qo‘llanma",
                    callback_data="help",
                ),
            ],
        ]
    )
