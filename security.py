# -*- coding: utf-8 -*-
"""Shifrlash, token tekshiruvi, rate limit, xavfli matn filtri."""
import hashlib
import logging
import os
import re
import time
from collections import defaultdict, deque

from cryptography.fernet import Fernet

from . import config

TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,50}$")
_BAD = re.compile(r"(\d{6,12}:[A-Za-z0-9_-]{30,})|javascript:|data:text/html|<\s*script", re.I)
_fernet = None


def fernet():
    """SECRET_KEY .env dan olinadi; bo'lmasa bir marta yaratilib .env ga yoziladi."""
    global _fernet
    if _fernet:
        return _fernet
    key = os.getenv("SECRET_KEY", "").strip()
    if not key:
        key = Fernet.generate_key().decode()
        try:
            with open(config.ENV_FILE, "a", encoding="utf-8") as f:
                f.write(f"\nSECRET_KEY={key}\n")
        except OSError:
            raise SystemExit("SECRET_KEY topilmadi va uni .env ga yozib bo'lmadi. "
                             "Fernet kalitini yarating va SECRET_KEY sifatida kiriting.")
        os.environ["SECRET_KEY"] = key
        logging.getLogger("security").warning("SECRET_KEY yaratildi va .env ga yozildi. Uni zaxirada saqlang!")
    _fernet = Fernet(key.encode())
    return _fernet


def encrypt(token):
    return fernet().encrypt(token.encode()).decode()


def decrypt(enc):
    return fernet().decrypt(enc.encode()).decode()


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def redact(text):
    return config.TOKEN_FIND.sub("***", str(text))


def is_dangerous(text):
    return bool(_BAD.search(text or ""))


def safe_url(u):
    u = (u or "").strip()
    return u if re.match(r"^(https?|tg)://[^\s]+$", u, re.I) else None


class Limiter:
    """Sirpanuvchi oyna: `per` soniyada ko'pi bilan `n` ta hodisa."""

    def __init__(self, n, per):
        self.n, self.per, self.h = n, per, defaultdict(deque)

    def _clean(self, key):
        d, now = self.h[key], time.monotonic()
        while d and now - d[0] > self.per:
            d.popleft()
        if not d:
            self.h.pop(key, None)
        return self.h[key]

    def ok(self, key):
        return len(self._clean(key)) < self.n

    def add(self, key):
        self._clean(key).append(time.monotonic())

    def hit(self, key):
        if not self.ok(key):
            return False
        self.add(key)
        return True
