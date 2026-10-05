import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "")

    ADMIN_IDS = {
        int(user_id.strip())
        for user_id in os.getenv("ADMIN_IDS", "").split(",")
        if user_id.strip().isdigit()
    }

    TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY", "")


settings = Settings()
