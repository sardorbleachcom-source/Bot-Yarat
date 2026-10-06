# -*- coding: utf-8 -*-
"""Foydalanuvchi oqimlari: til, menyu, bot yaratish, shablonlar, Premium, murojaat, sozlamalar, qo'llanma."""
import re

from .. import config, database as db, security, services as svc
from ..core import cb, cmd, step, send_lang_picker, lang_kb
from ..templates_data import GROUPS
from ..tg import TG, TGError
from ..utils import B, K, esc, fmt_day, paged

TPL_PER_PAGE = 8


def pname(c, tpl):
    return tpl.get("name_" + c.lang) or tpl["name_uz"]


async def menu(c, fresh=False):
    rows = [[B(c.t("m_create"), "new"), B(c.t("m_bots"), "mb:0")],
            [B(c.t("m_tpl"), "tpl:"), B(c.t("m_prem"), "prem")],
            [B(c.t("m_support"), "sup"), B(c.t("m_cfg"), "cfg")],
            [B(c.t("m_help"), "help")]]
    if c.role:
        rows.append([B("🛠 Admin", "adm")])
    text = c.T("menu", name=esc(c.frm.get("first_name", "")))
    await (c.fresh if fresh or not (c.mid or c.app.panel.get(c.uid)) else c.show)(text, K(*rows))


@cmd("start")
async def c_start(c):
    c.clear()
    if not c.user["lang"]:
        return await send_lang_picker(c)
    await menu(c, fresh=True)


@cmd("menu")
async def c_menu(c):
    c.clear()
    await menu(c, fresh=not c.q)


@cmd("cancel")
async def c_cancel(c):
    c.clear()
    await menu(c, fresh=True)


@cb("home")
async def cb_home(c, a):
    c.clear()
    await menu(c)


@cb("lang")
async def cb_lang(c, a):
    if a not in config.LANGS:
        return
    await db.upd("users", "user_id", c.uid, lang=a)
    c.lang = a
    c.clear()
    c.toast = c.t("lang_saved")
    await menu(c)


# ------------------------------------------------------------ shablonlar va bot yaratish
async def groups_screen(c, title_key):
    rows = [B(c.t("g_" + g), f"tpl:{g}:0") for g in GROUPS]
    kb = [rows[i:i + 2] for i in range(0, len(rows), 2)] + [c.home_row()]
    await c.show(c.T(title_key), K(*kb))


@cb("new")
async def cb_new(c, a):
    c.clear()
    plan = await svc.plan_of(c.user)
    n = await db.val("SELECT COUNT(*) FROM bots WHERE owner_id=?", c.uid)
    if n >= plan["max_bots"]:
        return await c.show(c.T("limit_bots", n=plan["max_bots"]), K([B(c.t("m_prem"), "prem")], c.home_row()))
    await groups_screen(c, "step_type")


@cb("tpl")
async def cb_tpl(c, a):
    if not a:
        return await groups_screen(c, "tpl_title")
    grp, _, p = a.partition(":")
    items = await db.all_("SELECT * FROM bot_templates WHERE grp=? AND enabled=1 ORDER BY rowid", grp)
    chunk, page, pages = paged(items, int(p or 0), TPL_PER_PAGE)
    rows = [[B(("🔒 " if t_["premium"] else "") + pname(c, t_), f"tpc:{t_['key']}")] for t_ in chunk]
    nav = ([B("⬅️", f"tpl:{grp}:{page - 1}")] if page > 0 else []) + ([B("➡️", f"tpl:{grp}:{page + 1}")] if page < pages - 1 else [])
    rows.append(nav)
    rows.append([B(c.t("back"), "tpl:")] + c.home_row())
    await c.show(c.T("tpl_group", g=c.t("g_" + grp), d=c.t("gd_" + grp)), K(*rows))


@cb("tpc")
async def cb_tpc(c, a):
    t_ = await db.one("SELECT * FROM bot_templates WHERE key=? AND enabled=1", a)
    if not t_:
        return await c.show(c.T("not_found"), K(c.home_row()))
    plan = await svc.plan_of(c.user)
    locked = bool(t_["premium"]) and plan["key"] == "free"
    text = c.T("tpl_card", name=esc(pname(c, t_)), d=c.t("gd_" + t_["grp"])) + (("\n\n" + c.t("tpl_locked")) if locked else "")
    rows = [[B(c.t("m_prem"), "prem")] if locked else [B(c.t("pick_btn"), f"pick:{a}")],
            [B(c.t("back"), f"tpl:{t_['grp']}:0")] + c.home_row()]
    await c.show(text, K(*rows))


@cb("pick")
async def cb_pick(c, a):
    t_ = await db.one("SELECT * FROM bot_templates WHERE key=? AND enabled=1", a)
    plan = await svc.plan_of(c.user)
    n = await db.val("SELECT COUNT(*) FROM bots WHERE owner_id=?", c.uid)
    if not t_ or n >= plan["max_bots"] or (t_["premium"] and plan["key"] == "free"):
        return await cb_new(c, "")
    c.set_step("name", tpl=a)
    await c.show(c.T("step_name"), K(c.home_row()))


@step("name")
async def s_name(c):
    await c.drop_input()
    name = c.text
    if not 2 <= len(name) <= 40 or security.is_dangerous(name) or name.startswith("/"):
        return await c.show(c.T("bad_name"), K(c.home_row()))
    c.state["d"]["name"] = name
    c.state["step"] = "uname"
    await c.show(c.T("step_user"), K(c.home_row()))


@step("uname")
async def s_uname(c):
    await c.drop_input()
    u = c.text.lstrip("@")
    if not re.match(r"^[A-Za-z][A-Za-z0-9_]{3,30}[Bb][Oo][Tt]$", u):
        return await c.show(c.T("bad_user"), K(c.home_row()))
    c.state["d"]["uname"] = u
    c.state["step"] = "token"
    await c.show(c.T("step_token"), K(c.home_row()))


@step("token")
async def s_token(c):
    await c.drop_input()  # token xabari darhol o'chiriladi
    token = c.text.strip()
    kb = K(c.home_row())
    if not c.app.tok_limiter.ok(c.uid):
        return await c.show(c.T("token_locked"), kb)
    if not security.TOKEN_RE.match(token):
        c.app.tok_limiter.add(c.uid)
        return await c.show(c.T("token_bad"), kb)
    if await db.one("SELECT id FROM bots WHERE token_hash=?", security.token_hash(token)):
        return await c.show(c.T("token_used"), kb)
    tmp = TG(token, c.app.session)
    try:
        me = await tmp.call("getMe")
    except TGError:
        c.app.tok_limiter.add(c.uid)
        return await c.show(c.T("token_bad"), kb)
    d = c.state["d"]
    plan = await svc.plan_of(c.user)
    n = await db.val("SELECT COUNT(*) FROM bots WHERE owner_id=?", c.uid)
    tpl = await db.one("SELECT * FROM bot_templates WHERE key=?", d["tpl"])
    if n >= plan["max_bots"] or not tpl:
        c.clear()
        return await c.show(c.T("limit_bots", n=plan["max_bots"]), K(c.home_row()))
    username = me.get("username") or d["uname"]
    bot_id = await svc.create_bot(c.app, c.lang, c.uid, tpl, d["name"], username, token)
    try:
        await tmp.call("setMyName", name=d["name"])
    except TGError:
        pass
    ok = await c.app.runner.start(bot_id)
    c.clear()
    note = "" if ok is True else "\n\n" + c.t("start_fail")
    await c.show(c.T("created", name=esc(d["name"]), user=esc(username)) + note,
                 K([B(f"🤖 @{username}", url=f"https://t.me/{username}")],
                   [B(c.t("m_bots"), "mb:0")], c.home_row()))


# ------------------------------------------------------------ Premium
def money(n):
    return f"{n:,}".replace(",", " ")


def plan_text(c, p):
    yes = lambda v: "✅" if v else "❌"
    head = f"<b>{c.t('plan_' + p['key'])}</b> — " + (c.t("price_line", price=money(p["price"])) if p["price"] else c.t("free_word"))
    return "\n".join([head, c.t("pf_bots", n=p["max_bots"]), c.t("pf_buttons", n=p["max_buttons"]),
                      c.t("pf_admins", n=p["max_admins"]), c.t("pf_auto", n=p["max_autoreplies"]),
                      f"{yes(p['banner'])} {c.t('pf_banner')}", f"{yes(p['channel'])} {c.t('pf_channel')}",
                      f"{yes(p['backup'])} {c.t('pf_backup')}", f"{yes(p['nofooter'])} {c.t('pf_nofooter')}",
                      f"{yes(p['adv_stats'])} {c.t('pf_stats')}"])


@cb("prem")
async def cb_prem(c, a):
    c.clear()
    plan = await svc.plan_of(c.user)
    until = c.user["premium_until"]
    cur = c.t("plan_" + plan["key"])
    if plan["key"] != "free":
        cur += f" ({c.t('until')} {fmt_day(until)})" if until else f" ({c.t('forever')})"
    rows = [[B(c.t("plan_" + k), f"pp:{k}")] for k in ("free", "premium", "premium_plus")]
    await c.show(c.T("prem_title", cur=cur), K(*rows, c.home_row()))


@cb("pp")
async def cb_pp(c, a):
    p = await db.one("SELECT * FROM plans WHERE key=?", a)
    if not p:
        return
    rows = []
    if a != "free":
        rows = [[B(c.t("days_n", n=d) + " — " + money(p["price"] * d // 30), f"pd:{a}:{d}")] for d in (30, 90)]
    await c.show(c.rtl_(plan_text(c, p)), K(*rows, [B(c.t("back"), "prem")] + c.home_row()))


@cb("pd")
async def cb_pd(c, a):
    plan, _, days = a.partition(":")
    p = await db.one("SELECT * FROM plans WHERE key=?", plan)
    if not p or plan == "free" or days not in ("30", "90"):
        return
    amount = p["price"] * int(days) // 30
    info = await db.val("SELECT value FROM settings WHERE key='payment_info'")
    text = c.T("pay_title", plan=c.t("plan_" + plan), days=days, amount=money(amount), info=esc(info))
    await c.show(text, K([B(c.t("pay_btn"), f"pay:{plan}:{days}")], [B(c.t("m_support"), "sup")],
                         [B(c.t("back"), f"pp:{plan}")] + c.home_row()))


@cb("pay")
async def cb_pay(c, a):
    plan, _, days = a.partition(":")
    p = await db.one("SELECT * FROM plans WHERE key=?", plan)
    if not p or plan == "free" or days not in ("30", "90"):
        return
    if await db.one("SELECT id FROM payments WHERE user_id=? AND status='pending'", c.uid):
        c.toast, c.alert = c.t("pay_pending"), True
        return
    amount = p["price"] * int(days) // 30
    pid = await db.run("INSERT INTO payments(user_id,plan,days,amount) VALUES(?,?,?,?)", c.uid, plan, int(days), amount)
    await svc.notify_staff(c.app, f"💳 <b>Yangi to‘lov so‘rovi #{pid}</b>\n👤 {esc(c.frm.get('first_name', ''))} @{esc(c.user['username'] or '-')}\n"
                                  f"🆔 <code>{c.uid}</code>\n⭐ {plan}\n💰 {amount}\n📅 {days} kun",
                           K([B("✅ To‘lov tasdiqlandi", f"apayr:{pid}:ok"), B("❌ To‘lov rad etildi", f"apayr:{pid}:no")]))
    await c.show(c.T("pay_sent"), K(c.home_row()))


# ------------------------------------------------------------ admin bilan aloqa
@cb("sup")
async def cb_sup(c, a):
    c.set_step("support")
    await c.show(c.T("sup_ask"), K(c.home_row()))


@step("support")
async def s_support(c):
    text = c.text[:1500]
    if not text or text.startswith("/"):
        return
    await c.drop_input()
    sid = await db.run("INSERT INTO support_messages(user_id,text) VALUES(?,?)", c.uid, text)
    c.clear()
    await svc.notify_staff(c.app, f"🔔 <b>Yangi murojaat #{sid}</b>\n👤 @{esc(c.user['username'] or '-')}\n🆔 <code>{c.uid}</code>\n💬 {esc(text)}",
                           K([B("💬 Javob berish", f"asr:{sid}")]), roles=("super", "admin", "mod"))
    await c.show(c.T("sup_sent"), K(c.home_row()))


# ------------------------------------------------------------ sozlamalar va qo'llanma
@cb("cfg")
async def cb_cfg(c, a):
    plan = await svc.plan_of(c.user)
    n = await db.val("SELECT COUNT(*) FROM bots WHERE owner_id=?", c.uid)
    await c.show(c.T("cfg", id=c.uid, lang=c.t("lang_" + c.lang), plan=c.t("plan_" + plan["key"]), n=n),
                 K([B(c.t("change_lang"), "chlang")], c.home_row()))


@cb("chlang")
async def cb_chlang(c, a):
    await c.show(c.t("choose_lang"), lang_kb())


@cb("help")
async def cb_help(c, a):
    await c.show(c.T("help"), K(c.home_row()))
