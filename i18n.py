# -*- coding: utf-8 -*-
"""Tillar: locales/*.json. Arab tilida matn o'ngdan chapga yo'naltiriladi."""
import json

from . import config

_data = {}
RLM = "\u200f"


def load():
    for lang in config.LANGS:
        with open(config.LOCALES_DIR / f"{lang}.json", encoding="utf-8") as f:
            _data[lang] = json.load(f)


load()


def t(lang, key, **kw):
    s = _data.get(lang, {}).get(key)
    if s is None:
        s = _data[config.DEFAULT_LANG].get(key, key)
    return s.format(**kw) if kw else s


def rtl(lang, text):
    if lang != "ar":
        return text
    return "\n".join((RLM + ln) if ln.strip() else ln for ln in text.split("\n"))


def T(lang, key, **kw):
    return rtl(lang, t(lang, key, **kw))
