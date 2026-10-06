# -*- coding: utf-8 -*-
"""Sozlamalar (.env), yo'llar, logging. Tokenlar loglarda yashiriladi."""
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
for _n in (".env", "env.txt"):
    if (ROOT / _n).exists():
        ENV_FILE = ROOT / _n
        load_dotenv(ENV_FILE)
        break

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "BotYarat24Bot").strip().lstrip("@") or "BotYarat24Bot"
SUPER_ADMINS = {int(x) for x in re.split(r"[,\s]+", os.getenv("ADMIN_ID", "")) if x.isdigit()}
DATA_DIR = Path(os.getenv("DATA_DIR", "").strip() or str(ROOT / "data"))
BACKUP_DIR = DATA_DIR / "backups"
DB_PATH = DATA_DIR / "botyarat24.db"
LOCALES_DIR = ROOT / "locales"
TZ_OFFSET = int(os.getenv("TZ_OFFSET", "5") or 5)

LANGS = ("uz", "ru", "en", "ar")
DEFAULT_LANG = "uz"
TOKEN_FIND = re.compile(r"\d{6,12}:[A-Za-z0-9_-]{30,}")


class RedactFormatter(logging.Formatter):
    """Log qatoridagi har qanday bot tokenini *** ga almashtiradi."""

    def format(self, record):
        return TOKEN_FIND.sub("***", super().format(record))


def setup_logging():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    fmt = RedactFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    handlers = [logging.FileHandler(DATA_DIR / "bot.log", encoding="utf-8"), logging.StreamHandler()]
    for h in handlers:
        h.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
