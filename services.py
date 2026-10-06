# -*- coding: utf-8 -*-
"""Biznes mantiq: foydalanuvchilar, tariflar, Premium, botlarni boshqarish, zaxira, xabar yuborish."""
import asyncio
import json
import logging
import time
import traceback

from . import config, database as db, security
from .i18n import t
from .templates_data import EXTRA_CMDS
from .tg import TG, TGError, poll
from .utils import B, K, esc, fmt_day

log = logging.getLogger("svc")
DAY = 86400


# ---------------------------------------------------------------- foydalanuvchilar
async def touch_user(frm):
    uid = frm["id"]
    un = (frm.get("username") or "").lower() or None
    fn = (frm.get("first_name") or "")[:64]
    row = await db.one("SELECT * FROM users WHERE user_id=?", uid)
    if not row:
        await db.run("INSERT INTO users(user_id,username,first_name) VALUES(?,?,?)", uid, un, fn)
        return await db.one("SELECT * FROM users WHERE user_id=?", uid)
    if row["username"] != un or row["first_name"] != fn:
        await db.upd("users", "user_id", uid, username=un, first_name=fn)
        row.update(username=un, first_name=fn)
    return row


async def role_of(uid):
    if uid in config.SUPER_ADMINS:
        return "super"
    r = await db.one("SELECT role FROM admins WHERE user_id=?", uid)
    return r["role"] if r else None


async def staff_ids(min_roles=("super", "admin")):
    rows = await db.all_("SELECT user_id FROM admins WHERE role IN (%s)" % ",".join("?" * len(min_roles)), *min_roles)
    return sorted({r["user_id"] for r in rows} | (config.SUPER_ADMINS if "super" in min_roles else set()))


async def notify_staff(app, text, kb=None, roles=("super", "admin"), html=True):
    for uid in await staff_ids(roles):
        try:
            await app.tg.send(uid, text, kb, html=html)
        except TGError:
            pass


async def log_error(source, bot_id, exc):
    msg = security.redact(exc if isinstance(exc, str) else "".join(traceback.format_exception_only(type(exc), exc)))
    tb = "" if isinstance(exc, str) else security.redact("".join(traceback.format_tb(exc.__traceback__)[-2:]))
    log.error("[%s] %s", source, msg.strip())
    try:
        await db.run("INSERT INTO error_logs(source,bot_id,message) VALUES(?,?,?)", source, bot_id, (msg + tb)[-900:])
    except Exception:
        pass


# ---------------------------------------------------------------- tariflar / Premium
async def get_plan(key):
    return await db.one("SELECT * FROM plans WHERE key=?", key) or await db.one("SELECT * FROM plans WHERE key='free'")


def effective_key(user):
    if user["plan"] != "free" and user["premium_until"] and user["premium_until"] < time.time():
        return "free"
    return user["plan"]


async def plan_of(user):
    return await get_plan(effective_key(user))


async def grant(app, uid, plan, days, by):
    """Tarif berish. days=None -> muddatsiz. Bir xil faol tarif bo'lsa, muddat ustiga qo'shiladi."""
    user = await db.one("SELECT * FROM users WHERE user_id=?", uid)
    now = int(time.time())
    if plan == "free" or days is None:
        until = None
    elif user["plan"] == plan and user["premium_until"] is None:
        until = None
    else:
        base = user["premium_until"] if (user["plan"] == plan and (user["premium_until"] or 0) > now) else now
        until = base + days * DAY
    await db.upd("users", "user_id", uid, plan=plan, premium_until=until, notified=0)
    await db.run("INSERT INTO subscriptions(user_id,plan,days,started_at,until,granted_by) VALUES(?,?,?,?,?,?)",
                 uid, plan, days, now, until, by)
    await enforce_limits(app, uid)
    lang = user["lang"] or config.DEFAULT_LANG
    pname = t(lang, "plan_" + plan)
    msg = t(lang, "prem_free") if plan == "free" else t(lang, "prem_granted", plan=pname, until=fmt_day(until) if until else t(lang, "forever"))
    try:
        await app.tg.send(uid, msg, html=True)
    except TGError:
        pass
    return until


async def enforce_limits(app, uid):
    user = await db.one("SELECT * FROM users WHERE user_id=?", uid)
    plan = await plan_of(user)
    bots = await db.all_("SELECT id FROM bots WHERE owner_id=? ORDER BY id", uid)
    for b in bots[plan["max_bots"]:]:
        await app.runner.stop(b["id"])


async def expiry_loop(app):
    last_backup = 0
    while True:
        try:
            now = int(time.time())
            for u in await db.all_("SELECT * FROM users WHERE plan!='free' AND premium_until IS NOT NULL AND premium_until<?", now):
                await db.upd("users", "user_id", u["user_id"], plan="free", premium_until=None, notified=0)
                await enforce_limits(app, u["user_id"])
                try:
                    await app.tg.send(u["user_id"], t(u["lang"] or "uz", "prem_expired"), html=True)
                except TGError:
                    pass
            for u in await db.all_("SELECT * FROM users WHERE plan!='free' AND premium_until BETWEEN ? AND ? AND notified=0",
                                   now, now + 3 * DAY):
                await db.upd("users", "user_id", u["user_id"], notified=1)
                try:
                    await app.tg.send(u["user_id"], t(u["lang"] or "uz", "prem_soon", until=fmt_day(u["premium_until"])), html=True)
                except TGError:
                    pass
            if now - last_backup > DAY:
                if last_backup:
                    await system_backup(app)
                last_backup = now
        except asyncio.CancelledError:
            raise
        except Exception as e:
            await log_error("expiry", None, e)
        await asyncio.sleep(600)


# ---------------------------------------------------------------- zaxira
async def system_backup(app):
    BK = config.BACKUP_DIR
    BK.mkdir(parents=True, exist_ok=True)
    path = BK / f"botyarat24_{time.strftime('%Y%m%d_%H%M%S')}.db"
    await asyncio.to_thread(db.backup_to, path)
    await db.run("INSERT INTO backups(kind,path) VALUES('system',?)", str(path))
    old = await db.all_("SELECT id,path FROM backups WHERE kind='system' ORDER BY id DESC LIMIT -1 OFFSET 7")
    for o in old:
        try:
            import os
            os.remove(o["path"])
        except OSError:
            pass
        await db.run("DELETE FROM backups WHERE id=?", o["id"])
    return path


async def snapshot(bot_id):
    """Bot sozlamalari JSON (token kirmaydi)."""
    st = await db.one("SELECT * FROM bot_settings WHERE bot_id=?", bot_id)
    btns = await db.all_("SELECT id,parent_id,label,action,value,position FROM bot_buttons WHERE bot_id=? ORDER BY id", bot_id)
    ars = await db.all_("SELECT keyword,reply FROM bot_autoreplies WHERE bot_id=?", bot_id)
    keep = {k: st[k] for k in ("lang", "description", "start_text", "banner_main", "channel", "hide_footer")}
    return json.dumps({"settings": keep, "buttons": btns, "autoreplies": ars}, ensure_ascii=False)


async def restore(bot_id, data):
    d = json.loads(data)
    s = d["settings"]
    await db.upd("bot_settings", "bot_id", bot_id, lang=s["lang"], description=s["description"], start_text=s["start_text"],
                 banner_main=s["banner_main"], banner_child=None, channel=s["channel"], hide_footer=s["hide_footer"])
    await db.run("DELETE FROM bot_buttons WHERE bot_id=?", bot_id)
    await db.run("DELETE FROM bot_autoreplies WHERE bot_id=?", bot_id)
    idmap = {}
    pending = list(d["buttons"])
    while pending:  # ota tugmalar avval
        rest = []
        for b in pending:
            if b["parent_id"] is None or b["parent_id"] in idmap:
                idmap[b["id"]] = await db.run(
                    "INSERT INTO bot_buttons(bot_id,parent_id,label,action,value,position) VALUES(?,?,?,?,?,?)",
                    bot_id, idmap.get(b["parent_id"]), b["label"], b["action"], b["value"], b["position"])
            else:
                rest.append(b)
        if len(rest) == len(pending):
            break
        pending = rest
    for a in d["autoreplies"]:
        await db.run("INSERT INTO bot_autoreplies(bot_id,keyword,reply) VALUES(?,?,?)", bot_id, a["keyword"], a["reply"])


# ---------------------------------------------------------------- bot yaratish
async def add_button(bot_id, parent, label, action, value=None):
    pos = await db.val("SELECT COALESCE(MAX(position),0)+1 FROM bot_buttons WHERE bot_id=? AND parent_id IS ?", bot_id, parent)
    return await db.run("INSERT INTO bot_buttons(bot_id,parent_id,label,action,value,position) VALUES(?,?,?,?,?,?)",
                        bot_id, parent, label[:40], action, value, pos)


async def create_bot(app, lang, owner, tpl, name, username, token):
    bot_id = await db.run("INSERT INTO bots(owner_id,template,name,username,token_enc,token_hash,status) VALUES(?,?,?,?,?,?,'stopped')",
                          owner, tpl["key"], name, username, security.encrypt(token), security.token_hash(token))
    grp = tpl["grp"]
    start = tpl["start_text"] or t(lang, "p_start_" + grp, bot=name)
    await db.run("INSERT INTO bot_settings(bot_id,lang,start_text) VALUES(?,?,?)", bot_id, lang, start)
    if tpl["key"] != "empty":
        if grp != "universal":
            await add_button(bot_id, None, t(lang, "p_main_" + grp), "text", t(lang, "p_main_text_" + grp))
        await add_button(bot_id, None, t(lang, "p_about_btn"), "text", t(lang, "p_about_text", bot=name))
        if grp != "universal":
            for c in EXTRA_CMDS.get(tpl["key"], ["contact"]):
                await add_button(bot_id, None, t(lang, "cmd_" + c), "command", c)
    return bot_id


async def delete_bot(app, bot_id):
    await app.runner.stop(bot_id)
    await db.run("DELETE FROM bots WHERE id=?", bot_id)


# ---------------------------------------------------------------- ishlayotgan botlar
class Runner:
    def __init__(self, app):
        self.app, self.tasks = app, {}

    def alive(self, bot_id):
        t_ = self.tasks.get(bot_id)
        return bool(t_ and not t_.done())

    async def start(self, bot_id):
        """True yoki (False, sabab)."""
        from .child import Child
        if self.alive(bot_id):
            return True
        bot = await db.one("SELECT * FROM bots WHERE id=?", bot_id)
        if not bot:
            return False, "yo'q"
        tg = TG(security.decrypt(bot["token_enc"]), self.app.session)
        try:
            me = await tg.call("getMe")
            await tg.call("deleteWebhook")
        except TGError as e:
            await self._fail(bot, f"{e.code} {e.desc}", notify=False)
            return False, f"{e.code} {e.desc}"
        child = Child(self.app, tg, bot_id, me.get("username", ""))
        self.tasks[bot_id] = asyncio.create_task(self._run(bot, tg, child))
        await db.upd("bots", "id", bot_id, status="running", error_text=None)
        return True

    async def _run(self, bot, tg, child):
        try:
            await poll(tg, child.handle, name=f"b{bot['id']}")
        except asyncio.CancelledError:
            raise
        except TGError as e:
            await self._fail(bot, f"{e.code} {e.desc}")
        except Exception as e:
            await self._fail(bot, f"{type(e).__name__}")

    async def _fail(self, bot, reason, notify=True):
        reason = security.redact(reason)[:200]
        await db.upd("bots", "id", bot["id"], status="error", error_text=reason)
        await log_error("bot", bot["id"], reason)
        if notify:
            owner = await db.one("SELECT lang FROM users WHERE user_id=?", bot["owner_id"])
            try:
                await self.app.tg.send(bot["owner_id"], t((owner or {}).get("lang") or "uz", "bot_crashed", user=bot["username"]), html=True)
            except TGError:
                pass
            await notify_staff(self.app, f"🚨 Bot xatosi: @{esc(bot['username'])} (ID {bot['id']})\n{esc(reason)}")

    async def stop(self, bot_id, status="stopped"):
        tk = self.tasks.pop(bot_id, None)
        if tk and not tk.done():
            tk.cancel()
            await asyncio.gather(tk, return_exceptions=True)
        await db.upd("bots", "id", bot_id, status=status)

    async def start_all(self):
        for b in await db.all_("SELECT id FROM bots WHERE status='running'"):
            await self.start(b["id"])
            await asyncio.sleep(0.2)

    async def stop_all(self):
        for bid in list(self.tasks):
            tk = self.tasks.pop(bid)
            tk.cancel()
            await asyncio.gather(tk, return_exceptions=True)


# ---------------------------------------------------------------- admin xabar yuborish (navbat)
async def broadcast_worker(app):
    """Bir vaqtda bitta ish; sekundiga ~25 ta xabar (Telegram chegarasidan past)."""
    while True:
        job = await app.bc_queue.get()
        ok = fail = 0
        try:
            ids = [r["user_id"] for r in await db.all_("SELECT user_id FROM users WHERE blocked=0 AND lang IS NOT NULL")]
            for uid in ids:
                for _ in range(3):
                    try:
                        await app.tg.call("copyMessage", chat_id=uid, from_chat_id=job["chat"], message_id=job["mid"],
                                          reply_markup=job["kb"])
                        ok += 1
                        break
                    except TGError as e:
                        if e.code == 429:
                            await asyncio.sleep(int(e.params.get("retry_after", 3)) + 1)
                            continue
                        fail += 1
                        break
                await asyncio.sleep(0.04)
            await app.tg.send(job["admin"], f"✅ Yuborildi: {ok}\n❌ Yuborilmadi: {fail}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            await log_error("broadcast", None, e)
        finally:
            app.bc_queue.task_done()
