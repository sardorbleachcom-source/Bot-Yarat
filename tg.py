# -*- coding: utf-8 -*-
"""Telegram Bot API uchun yengil asinxron klient (faqat aiohttp)."""
import asyncio
import json
import logging
from collections import defaultdict

import aiohttp

API = "https://api.telegram.org"
log = logging.getLogger("tg")


class TGError(Exception):
    def __init__(self, code=0, desc="", params=None):
        super().__init__(f"{code} {desc}")
        self.code, self.desc, self.params = code, desc or "", params or {}


class TG:
    def __init__(self, token, session):
        self.token, self.s = token, session

    async def _req(self, method, _timeout=35, **kw):
        try:
            async with self.s.post(f"{API}/bot{self.token}/{method}",
                                   timeout=aiohttp.ClientTimeout(total=_timeout), **kw) as r:
                data = await r.json(content_type=None)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # xato matnida token bo'lishi mumkin, shuning uchun faqat tur nomi
            raise TGError(0, "network " + type(e).__name__) from None
        if not data.get("ok"):
            raise TGError(data.get("error_code", 0), data.get("description", ""), data.get("parameters"))
        return data["result"]

    async def call(self, method, _timeout=35, **p):
        return await self._req(method, _timeout=_timeout, json={k: v for k, v in p.items() if v is not None})

    async def upload(self, method, field, data, filename, **p):
        fd = aiohttp.FormData()
        for k, v in p.items():
            if v is None:
                continue
            fd.add_field(k, v if isinstance(v, str) else json.dumps(v) if isinstance(v, (dict, list)) else str(v))
        fd.add_field(field, data, filename=filename)
        return await self._req(method, _timeout=120, data=fd)

    async def download(self, file_id):
        f = await self.call("getFile", file_id=file_id)
        try:
            async with self.s.get(f"{API}/file/bot{self.token}/{f['file_path']}",
                                  timeout=aiohttp.ClientTimeout(total=60)) as r:
                return await r.read()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            raise TGError(0, "network " + type(e).__name__) from None

    async def send(self, chat, text, kb=None, html=False):
        return await self.call("sendMessage", chat_id=chat, text=text, reply_markup=kb,
                               parse_mode="HTML" if html else None, disable_web_page_preview=True)

    async def edit(self, chat, mid, text, kb=None, html=False):
        return await self.call("editMessageText", chat_id=chat, message_id=mid, text=text, reply_markup=kb,
                               parse_mode="HTML" if html else None, disable_web_page_preview=True)

    async def delete(self, chat, mid):
        try:
            await self.call("deleteMessage", chat_id=chat, message_id=mid)
        except TGError:
            pass

    async def answer(self, cb_id, text=None, alert=False):
        try:
            await self.call("answerCallbackQuery", callback_query_id=cb_id, text=text, show_alert=alert or None)
        except TGError:
            pass


_locks = defaultdict(asyncio.Lock)


def _chat_of(u):
    m = u.get("message") or (u.get("callback_query") or {}).get("message") or {}
    return m.get("chat", {}).get("id", 0)


async def poll(tg, on_update, name="main"):
    """Long polling. Bir foydalanuvchining xabarlari ketma-ket, turli foydalanuvchilar parallel ishlanadi."""
    offset, backoff, tasks = None, 1, set()

    async def run(u):
        async with _locks[(name, _chat_of(u))]:
            try:
                await on_update(u)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Update xatosi [%s]", name)
        if len(_locks) > 5000:
            for k in [k for k, l in _locks.items() if not l.locked()]:
                _locks.pop(k, None)

    try:
        while True:
            try:
                ups = await tg.call("getUpdates", _timeout=45, offset=offset, timeout=25,
                                    allowed_updates=["message", "callback_query"])
                backoff = 1
            except TGError as e:
                if e.code in (401, 404, 409):
                    raise
                await asyncio.sleep(min(backoff, 30))
                backoff *= 2
                continue
            for u in ups:
                offset = u["update_id"] + 1
                t = asyncio.create_task(run(u))
                tasks.add(t)
                t.add_done_callback(tasks.discard)
    finally:
        for t in tasks:
            t.cancel()
