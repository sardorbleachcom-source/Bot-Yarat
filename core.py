# -*- coding: utf-8 -*-
"""Asosiy bot yadrosi: kontekst, marshrutlash, rate limit, xatolarni ushlash."""
import asyncio
import logging

import aiohttp

from . import config, database as db, i18n, security, services as svc
from .templates_data import TEMPLATES
from .tg import TG, TGError, poll
from .utils import B, K, esc

log = logging.getLogger("core")
CB, STEP, CMD = {}, {}, {}
RANK = {None: 0, "mod": 1, "admin": 2, "super": 3}


def cb(name, role=None):
    def deco(f):
        CB[name] = (f, role)
        return f
    return deco


def step(name, role=None):
    def deco(f):
        STEP[name] = (f, role)
        return f
    return deco


def cmd(name, role=None):
    def deco(f):
        CMD[name] = (f, role)
        return f
    return deco


class Ctx:
    def __init__(self, app, upd):
        self.app, self.tg = app, app.tg
        self.q = upd.get("callback_query")
        self.msg = self.q["message"] if self.q else upd["message"]
        self.frm = (self.q or self.msg)["from"]
        self.uid, self.chat = self.frm["id"], self.msg["chat"]["id"]
        self.mid = self.msg["message_id"] if self.q else None
        self.text = "" if self.q else (self.msg.get("text") or self.msg.get("caption") or "").strip()
        self.user, self.lang, self.role = None, config.DEFAULT_LANG, None
        self.toast, self.alert = None, False

    # ---- matnlar
    def t(self, key, **kw):
        return i18n.t(self.lang, key, **kw)

    def T(self, key, **kw):
        return i18n.T(self.lang, key, **kw)

    def rtl_(self, text):
        return i18n.rtl(self.lang, text)

    # ---- holat (qadamlar)
    @property
    def state(self):
        return self.app.state.get(self.uid)

    def set_step(self, name, **data):
        self.app.state[self.uid] = {"step": name, "d": data}

    def clear(self):
        self.app.state.pop(self.uid, None)

    # ---- chiqish
    async def show(self, text, kb=None):
        """Panel xabarini tahrirlaydi (bo'lmasa yangisini yuboradi)."""
        mid = self.mid or self.app.panel.get(self.uid)
        if mid:
            try:
                await self.tg.edit(self.chat, mid, text, kb, html=True)
                self.app.panel[self.uid] = mid
                return mid
            except TGError as e:
                if "not modified" in e.desc:
                    return mid
        return await self.fresh(text, kb)

    async def fresh(self, text, kb=None):
        r = await self.tg.send(self.chat, text, kb, html=True)
        self.app.panel[self.uid] = r["message_id"]
        return r["message_id"]

    async def send(self, text, kb=None):
        return await self.tg.send(self.chat, text, kb, html=True)

    async def drop_input(self):
        if not self.q:
            await self.tg.delete(self.chat, self.msg["message_id"])

    def home_row(self):
        return [B(self.t("home"), "home")]

    def nav(self, back=None):
        row = [B(self.t("back"), back)] if back else []
        return [row + self.home_row()]


class App:
    def __init__(self):
        self.session = self.tg = self.runner = self.me = None
        self.state, self.panel = {}, {}
        self.limiter = security.Limiter(20, 10)
        self.tok_limiter = security.Limiter(5, 600)
        self.bc_queue = asyncio.Queue()
        self.bg = []

    async def start(self):
        security.fernet()
        await db.init(TEMPLATES)
        self.session = aiohttp.ClientSession()
        self.tg = TG(config.BOT_TOKEN, self.session)
        self.me = await self.tg.call("getMe")
        await self.tg.call("deleteWebhook")
        self.runner = svc.Runner(self)
        await self.runner.start_all()
        self.bg = [asyncio.create_task(svc.expiry_loop(self)), asyncio.create_task(svc.broadcast_worker(self))]

    async def stop(self):
        for t_ in self.bg:
            t_.cancel()
        if self.runner:
            await self.runner.stop_all()
        if self.session:
            await self.session.close()


def lang_kb():
    return K([B(i18n.t("uz", "lang_uz"), "lang:uz"), B(i18n.t("uz", "lang_ru"), "lang:ru")],
             [B(i18n.t("uz", "lang_en"), "lang:en"), B(i18n.t("uz", "lang_ar"), "lang:ar")])


async def send_lang_picker(c):
    await c.fresh(i18n.t("uz", "choose_lang"), lang_kb())


async def handle(app, upd):
    q, m = upd.get("callback_query"), upd.get("message")
    src = q.get("message") if q else m
    if not src or src.get("chat", {}).get("type") != "private":
        return
    c = Ctx(app, upd)
    if c.frm.get("is_bot"):
        return
    c.user = await svc.touch_user(c.frm)
    c.lang = c.user["lang"] or config.DEFAULT_LANG
    c.role = await svc.role_of(c.uid)
    try:
        if c.user["blocked"] and not c.role:
            if q:
                await c.tg.answer(q["id"])
            else:
                await c.send(c.T("blocked"))
            return
        if not app.limiter.hit(c.uid):
            if q:
                await c.tg.answer(q["id"], "⏳")
            return
        if q:
            name, _, arg = (q.get("data") or "").partition(":")
            ent = CB.get(name)
            if not ent:
                return await c.tg.answer(q["id"])
            if not c.user["lang"] and name != "lang":
                await send_lang_picker(c)
                return await c.tg.answer(q["id"])
            fn, role = ent
            if RANK[c.role] < RANK[role]:
                c.toast = "⛔"
            else:
                await fn(c, arg)
            await c.tg.answer(q["id"], c.toast, c.alert)
            return
        text = c.text
        if text.startswith("/"):
            name = text[1:].split()[0].split("@")[0].lower() if len(text) > 1 else ""
            ent = CMD.get(name)
            if ent:
                if name != "start" and not c.user["lang"]:
                    return await send_lang_picker(c)
                if RANK[c.role] >= RANK[ent[1]]:
                    return await ent[0](c)
                return
        if not c.user["lang"]:
            return await send_lang_picker(c)
        st = c.state
        if st and st["step"] in STEP:
            fn, role = STEP[st["step"]]
            if RANK[c.role] >= RANK[role]:
                return await fn(c)
            c.clear()
        await CMD["menu"][0](c)
    except asyncio.CancelledError:
        raise
    except TGError as e:
        await svc.log_error("main", None, f"TGError {e.code} {e.desc}")
    except Exception as e:
        await svc.log_error("main", None, e)
        try:
            await c.send(c.T("err_generic"))
        except Exception:
            pass
