from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="back",
                ),
                InlineKeyboardButton(
                    text="🏠 Bosh menyu",
                    callback_data="home",
                ),
            ]
        ]
    )
