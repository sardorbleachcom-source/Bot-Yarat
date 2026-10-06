# -*- coding: utf-8 -*-
"""Mijozlar yaratgan botlarning ish vaqtidagi mantig'i (har bir bot uchun bitta Child)."""
import ast
import asyncio
import operator
import random
import re
import time
from collections import OrderedDict

from . import config, database as db, security, services as svc
from .i18n import t
from .tg import TGError
from .utils import B, K, today_start

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}


def safe_eval(expr):
    """Faqat sonlar va + - * / // % ** ( ). Boshqa hech narsa bajarilmaydi."""
    if len(expr) > 100:
        raise ValueError
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            v = ev(n.operand)
            return v if isinstance(n.op, ast.UAdd) else -v
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and (abs(b) > 100 or abs(a) > 1e6):
                raise ValueError
            return _OPS[type(n.op)](a, b)
        raise ValueError
    return ev(ast.parse(expr.replace("^", "**").replace(",", ".").strip(), mode="eval"))


class Child:
    def __init__(self, app, tg, bot_id, username):
        self.app, self.tg, self.id, self.username = app, tg, bot_id, username
        self.state, self.rmap, self.jobs = {}, OrderedDict(), set()
        self.lim = security.Limiter(15, 10)

    # ------------------------------------------------------------ kirish nuqtasi
    async def handle(self, upd):
        q, m = upd.get("callback_query"), upd.get("message")
        src = q.get("message") if q else m
        if not src or src.get("chat", {}).get("type") != "private":
            return
        frm = (q or m)["from"]
        if frm.get("is_bot") or not self.lim.hit(frm["id"]):
            return
        bot = await db.one("SELECT * FROM bots WHERE id=?", self.id)
        st = await db.one("SELECT * FROM bot_settings WHERE bot_id=?", self.id)
        if not bot or not st:
            return
        owner = await db.one("SELECT * FROM users WHERE user_id=?", bot["owner_id"])
        plan = await svc.plan_of(owner)
        uid, now = frm["id"], int(time.time())
        await db.run(
            "INSERT INTO bot_users(bot_id,user_id,first_name,username,messages,first_seen,last_seen) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(bot_id,user_id) DO UPDATE SET first_name=excluded.first_name, username=excluded.username, "
            "messages=messages+excluded.messages, last_seen=excluded.last_seen, updated_at=excluded.last_seen",
            self.id, uid, (frm.get("first_name") or "")[:64], frm.get("username"), 0 if q else 1, now, now)
        is_admin = uid == bot["owner_id"] or bool(await db.one("SELECT 1 FROM bot_admins WHERE bot_id=? AND user_id=?", self.id, uid))
        x = {"bot": bot, "st": st, "plan": plan, "uid": uid, "frm": frm, "admin": is_admin, "L": st["lang"], "chat": src["chat"]["id"]}
        try:
            if q:
                await self.on_cb(q, x)
            else:
                await self.on_msg(m, x)
        except TGError as e:
            if e.code in (401, 404, 409):
                raise
            await svc.log_error("child", self.id, f"TGError {e.code} {e.desc}")

    # ------------------------------------------------------------ yordamchilar
    async def show(self, chat, mid, text, kb):
        """Xabarni tahrirlaydi; rasmli bo'lsa o'chirib yangisini yuboradi."""
        try:
            await self.tg.edit(chat, mid, text, kb)
        except TGError as e:
            if "not modified" in e.desc:
                return
            await self.tg.delete(chat, mid)
            await self.tg.send(chat, text, kb)

    async def level_kb(self, parent, x, with_channel=False):
        rows, cur = [], []
        for b in await db.all_("SELECT * FROM bot_buttons WHERE bot_id=? AND parent_id IS ? ORDER BY position,id", self.id, parent or None):
            if b["action"] == "url" and security.safe_url(b["value"]):
                btn = B(b["label"], url=b["value"])
            elif b["action"] == "channel" and b["value"]:
                btn = B(b["label"], url=f"https://t.me/{b['value'].lstrip('@')}")
            else:
                btn = B(b["label"], f"c:{b['id']}")
            cur.append(btn)
            if len(cur) == 2:
                rows.append(cur)
                cur = []
        if cur:
            rows.append(cur)
        st = x["st"]
        if with_channel and st["channel"] and x["plan"]["channel"]:
            rows.append([B(t(x["L"], "ch_channel"), url=f"https://t.me/{st['channel'].lstrip('@')}")])
        if parent:
            up = await db.val("SELECT parent_id FROM bot_buttons WHERE id=?", parent)
            rows.append([B(t(x["L"], "ch_back"), f"m:{up or 0}"), B(t(x["L"], "ch_home"), "m:0")])
        return K(*rows)

    def start_text(self, x):
        text = (x["st"]["start_text"] or "👋").strip()
        if not (x["plan"]["nofooter"] and x["st"]["hide_footer"]):
            text += "\n\n" + t(x["L"], "ch_footer", bu=config.BOT_USERNAME)
        return text

    async def send_start(self, x):
        chat, st = x["chat"], x["st"]
        text, kb = self.start_text(x), await self.level_kb(0, x, True)
        if st["banner_main"] and x["plan"]["banner"]:
            cap = text if len(text) <= 1000 else None
            try:
                if st["banner_child"]:
                    await self.tg.call("sendPhoto", chat_id=chat, photo=st["banner_child"], caption=cap, reply_markup=kb if cap else None)
                else:
                    data = await self.app.tg.download(st["banner_main"])
                    r = await self.tg.upload("sendPhoto", "photo", data, "banner.jpg", chat_id=chat, caption=cap,
                                             reply_markup=kb if cap else None)
                    await db.upd("bot_settings", "bot_id", self.id, banner_child=r["photo"][-1]["file_id"])
                if not cap:
                    await self.tg.send(chat, text, kb)
                return
            except TGError as e:
                if e.code in (401, 404, 409):
                    raise
        await self.tg.send(chat, text, kb)

    # ------------------------------------------------------------ xabarlar
    async def on_msg(self, m, x):
        uid, chat, L = x["uid"], x["chat"], x["L"]
        text = (m.get("text") or "").strip()
        if text.startswith("/"):
            name = text[1:].split()[0].split("@")[0].lower() if len(text) > 1 else ""
            if name in ("start", "cancel"):
                self.state.pop(uid, None)
                return await self.send_start(x)
            if name == "stats" and x["admin"]:
                return await self.cmd_stats(x)
            if name == "broadcast" and x["admin"]:
                return await self.cmd_broadcast(x, text.partition(" ")[2].strip())
        stt = self.state.get(uid)
        if stt:
            return await self.on_state(m, x, stt, text)
        if x["admin"] and m.get("reply_to_message"):
            rep = m["reply_to_message"]
            target = self.rmap.get((chat, rep["message_id"]))
            if not target:
                mt = re.search(r"🆔 (\d+)", rep.get("text") or "")
                target = int(mt.group(1)) if mt else None
            if target:
                try:
                    await self.tg.call("copyMessage", chat_id=target, from_chat_id=chat, message_id=m["message_id"])
                    return await self.tg.send(chat, t(L, "ch_reply_sent"))
                except TGError:
                    return await self.tg.send(chat, t(L, "ch_reply_fail"))
        low = text.lower()
        if low:
            for a in await db.all_("SELECT * FROM bot_autoreplies WHERE bot_id=?", self.id):
                if a["keyword"].lower() in low:
                    return await self.tg.send(chat, a["reply"])
        await self.send_start(x)

    async def on_state(self, m, x, stt, text):
        uid, chat, L = x["uid"], x["chat"], x["L"]
        kb = K([B(t(L, "ch_home"), "m:0")])
        kind = stt[0]
        if kind == "contact":
            self.state.pop(uid, None)
            fr = x["frm"]
            head = f"📩 {fr.get('first_name', '')} (@{fr.get('username') or '-'})\n🆔 {uid}"
            rec = {x["bot"]["owner_id"]} | {r["user_id"] for r in await db.all_("SELECT user_id FROM bot_admins WHERE bot_id=?", self.id)}
            sent = 0
            for r in rec:
                try:
                    if m.get("text"):
                        res = await self.tg.send(r, f"{head}\n\n{m['text']}")
                        ids = [res["message_id"]]
                    else:
                        h = await self.tg.send(r, head)
                        c2 = await self.tg.call("copyMessage", chat_id=r, from_chat_id=chat, message_id=m["message_id"])
                        ids = [h["message_id"], c2["message_id"]]
                    for i in ids:
                        self.rmap[(r, i)] = uid
                    sent += 1
                except TGError:
                    pass
            while len(self.rmap) > 5000:
                self.rmap.popitem(last=False)
            return await self.tg.send(chat, t(L, "ch_contact_sent" if sent else "ch_contact_fail"), kb)
        if kind == "calc":
            try:
                v = safe_eval(text)
                v = int(v) if isinstance(v, float) and v.is_integer() and abs(v) < 1e15 else round(v, 8)
                return await self.tg.send(chat, f"= {v}", kb)
            except Exception:
                return await self.tg.send(chat, t(L, "ch_calc_bad"), kb)
        if kind == "random":
            mt = re.match(r"^\s*(-?\d+)\s*[-–]\s*(-?\d+)\s*$", text)
            if mt:
                a, b = sorted((int(mt.group(1)), int(mt.group(2))))
                return await self.tg.send(chat, f"🎲 {random.randint(a, b)}", kb)
            if re.match(r"^\d{1,9}$", text):
                return await self.tg.send(chat, f"🎲 {random.randint(1, max(1, int(text)))}", kb)
            items = [i.strip() for i in text.split(",") if i.strip()]
            if len(items) >= 2:
                return await self.tg.send(chat, f"🎯 {random.choice(items)}", kb)
            return await self.tg.send(chat, t(L, "ch_random_bad"), kb)
        self.state.pop(uid, None)

    # ------------------------------------------------------------ tugmalar
    async def on_cb(self, q, x):
        uid, chat, L = x["uid"], x["chat"], x["L"]
        mid = q["message"]["message_id"]
        data = q.get("data") or ""
        await self.tg.answer(q["id"])
        kind, _, arg = data.partition(":")
        if kind == "m" and arg.lstrip("-").isdigit():
            self.state.pop(uid, None)
            pid = int(arg)
            if pid == 0:
                return await self.show(chat, mid, self.start_text(x), await self.level_kb(0, x, True))
            p = await db.one("SELECT * FROM bot_buttons WHERE id=? AND bot_id=?", pid, self.id)
            if p:
                return await self.show(chat, mid, p["label"], await self.level_kb(pid, x))
            return
        if kind != "c" or not arg.isdigit():
            return
        b = await db.one("SELECT * FROM bot_buttons WHERE id=? AND bot_id=?", int(arg), self.id)
        if not b:
            return
        back = f"m:{b['parent_id'] or 0}"
        nav = [B(t(L, "ch_back"), back), B(t(L, "ch_home"), "m:0")]
        if b["action"] == "text":
            return await self.show(chat, mid, b["value"] or "…", K(nav))
        if b["action"] == "menu":
            return await self.show(chat, mid, b["label"], await self.level_kb(b["id"], x))
        if b["action"] == "command":
            return await self.run_cmd(b["value"], chat, mid, x, nav)

    async def run_cmd(self, name, chat, mid, x, nav):
        uid, L = x["uid"], x["L"]
        if name in ("contact", "calc", "random"):
            self.state[uid] = (name,)
            return await self.show(chat, mid, t(L, "ch_ask_" + name), K(nav))
        if name == "coin":
            return await self.show(chat, mid, t(L, "ch_coin_" + random.choice(("h", "t"))), K(nav))
        if name == "id":
            return await self.show(chat, mid, f"🆔 {uid}", K(nav))

    # ------------------------------------------------------------ bot admini buyruqlari
    async def cmd_stats(self, x):
        r = await db.one("SELECT COUNT(*) n, COALESCE(SUM(messages),0) m, "
                         "SUM(first_seen>=?) today, SUM(last_seen>=?) act FROM bot_users WHERE bot_id=?",
                         today_start(), int(time.time()) - 86400, self.id)
        await self.tg.send(x["chat"], t(x["L"], "ch_stats", n=r["n"], today=r["today"] or 0, act=r["act"] or 0, m=r["m"]))

    async def cmd_broadcast(self, x, text):
        L, chat = x["L"], x["chat"]
        if not text:
            return await self.tg.send(chat, t(L, "ch_bc_usage"))
        if security.is_dangerous(text):
            return await self.tg.send(chat, t(L, "ch_bc_bad"))
        ids = [r["user_id"] for r in await db.all_("SELECT user_id FROM bot_users WHERE bot_id=?", self.id)]
        await self.tg.send(chat, t(L, "ch_bc_start", n=len(ids)))

        async def job():
            ok = fail = 0
            for uid in ids:
                try:
                    await self.tg.send(uid, text)
                    ok += 1
                except TGError as e:
                    if e.code == 429:
                        await asyncio.sleep(int(e.params.get("retry_after", 3)) + 1)
                    fail += 1
                await asyncio.sleep(0.05)
            st = x["st"]
            if st["channel"] and x["plan"]["channel"]:
                try:
                    await self.tg.send("@" + st["channel"].lstrip("@"), text)
                except TGError:
                    pass
            try:
                await self.tg.send(chat, t(L, "ch_bc_done", ok=ok, fail=fail))
            except TGError:
                pass
        tk = asyncio.create_task(job())
        self.jobs.add(tk)
        tk.add_done_callback(self.jobs.discard)
