# -*- coding: utf-8 -*-
"""Mening botlarim: sozlash, menyu (tugma konstruktori), xabarlar, adminlar, statistika, zaxira, o'chirish."""
import re
import time

from .. import database as db, security, services as svc
from ..core import cb, step
from ..templates_data import COMMANDS
from ..tg import TG, TGError
from ..utils import B, K, esc, fmt_day, paged, today_start


async def own(c, a):
    """(bot, qolgan_argumentlar). Faqat egasi kira oladi."""
    parts = a.split(":")
    bot = await db.one("SELECT * FROM bots WHERE id=? AND owner_id=?", int(parts[0]), c.uid) if parts[0].isdigit() else None
    if not bot:
        await c.show(c.T("not_found"), K(c.home_row()))
    return bot, parts[1:]


def status_of(c, bot):
    if bot["status"] == "running":
        return c.t("st_running") if c.app.runner.alive(bot["id"]) else c.t("st_down")
    return c.t("st_error") if bot["status"] == "error" else c.t("st_stopped")


async def tgc(c, bot):
    return TG(security.decrypt(bot["token_enc"]), c.app.session)


def lock(c):
    return c.T("locked"), K([B(c.t("m_prem"), "prem")], c.home_row())


# ------------------------------------------------------------ ro'yxat va kartochka
@cb("mb")
async def cb_mb(c, a):
    c.clear()
    bots = await db.all_("SELECT * FROM bots WHERE owner_id=? ORDER BY id", c.uid)
    if not bots:
        return await c.show(c.T("mb_empty"), K([B(c.t("m_create"), "new")], c.home_row()))
    chunk, page, pages = paged(bots, int(a or 0), 8)
    rows = [[B(f"{status_of(c, b).split()[0]} {b['name']} · @{b['username']}"[:60], f"bot:{b['id']}")] for b in chunk]
    nav = ([B("⬅️", f"mb:{page - 1}")] if page > 0 else []) + ([B("➡️", f"mb:{page + 1}")] if page < pages - 1 else [])
    await c.show(c.T("mb_title"), K(*rows, nav, c.home_row()))


@cb("bot")
async def cb_bot(c, a):
    c.clear()
    bot, _ = await own(c, a)
    if not bot:
        return
    i = bot["id"]
    st = await db.one("SELECT COUNT(*) n FROM bot_users WHERE bot_id=?", i)
    text = c.T("bot_card", name=esc(bot["name"]), user=esc(bot["username"]), status=status_of(c, bot), n=st["n"])
    rows = [[B(c.t("b_set"), f"bset:{i}"), B(c.t("b_menu"), f"bbtn:{i}:0")],
            [B(c.t("b_start"), f"bst:{i}:start"), B(c.t("b_stop"), f"bst:{i}:stop")],
            [B(c.t("b_msgs"), f"bmsg:{i}"), B(c.t("b_admins"), f"badm:{i}")],
            [B(c.t("b_stats"), f"bstat:{i}"), B(c.t("b_backup"), f"bbak:{i}")],
            [B(c.t("b_delete"), f"bdel:{i}")], [B(c.t("back"), "mb:0")] + c.home_row()]
    await c.show(text, K(*rows))


@cb("bst")
async def cb_bst(c, a):
    bot, rest = await own(c, a)
    if not bot:
        return
    if rest[0] == "start":
        plan = await svc.plan_of(c.user)
        ids = [r["id"] for r in await db.all_("SELECT id FROM bots WHERE owner_id=? ORDER BY id", c.uid)]
        if bot["id"] not in ids[:plan["max_bots"]]:
            c.toast, c.alert = c.t("limit_bots", n=plan["max_bots"]), True
            return
        res = await c.app.runner.start(bot["id"])
        c.toast, c.alert = (c.t("started"), False) if res is True else (c.t("start_fail"), True)
    else:
        await c.app.runner.stop(bot["id"])
        c.toast = c.t("stopped")
    await cb_bot(c, str(bot["id"]))


@cb("bdel")
async def cb_bdel(c, a):
    bot, rest = await own(c, a)
    if not bot:
        return
    if rest and rest[0] == "y":
        await svc.delete_bot(c.app, bot["id"])
        c.toast = c.t("deleted")
        return await cb_mb(c, "0")
    await c.show(c.T("del_confirm", user=esc(bot["username"])),
                 K([B(c.t("yes"), f"bdel:{bot['id']}:y"), B(c.t("cancel"), f"bot:{bot['id']}")]))


# ------------------------------------------------------------ sozlamalar
@cb("bset")
async def cb_bset(c, a):
    c.clear()
    bot, _ = await own(c, a)
    if not bot:
        return
    i = bot["id"]
    st = await db.one("SELECT * FROM bot_settings WHERE bot_id=?", i)
    foot = c.t("on") if st["hide_footer"] else c.t("off")
    rows = [[B(c.t("bs_name"), f"bsf:{i}:name"), B(c.t("bs_desc"), f"bsf:{i}:desc")],
            [B(c.t("bs_banner"), f"bsf:{i}:banner"), B(c.t("bs_channel"), f"bsf:{i}:channel")],
            [B(c.t("bs_footer", s=foot), f"bsf:{i}:footer")], [B(c.t("back"), f"bot:{i}")] + c.home_row()]
    await c.show(c.T("bs_title", name=esc(bot["name"]), desc=esc(st["description"] or "—"), ch=esc(st["channel"] or "—")), K(*rows))


@cb("bsf")
async def cb_bsf(c, a):
    bot, rest = await own(c, a)
    if not bot:
        return
    field, plan = rest[0], await svc.plan_of(c.user)
    need = {"banner": "banner", "channel": "channel", "footer": "nofooter"}.get(field)
    if need and not plan[need]:
        return await c.show(*lock(c))
    if field == "footer":
        st = await db.one("SELECT hide_footer FROM bot_settings WHERE bot_id=?", bot["id"])
        await db.upd("bot_settings", "bot_id", bot["id"], hide_footer=0 if st["hide_footer"] else 1)
        return await cb_bset(c, str(bot["id"]))
    c.set_step("set_" + field, bot=bot["id"])
    await c.show(c.T("ask_" + field), K([B(c.t("cancel"), f"bset:{bot['id']}")]))


async def _bot_from_state(c):
    bid = c.state["d"]["bot"]
    return await db.one("SELECT * FROM bots WHERE id=? AND owner_id=?", bid, c.uid)


async def _saved(c, bid):
    c.clear()
    c.toast = c.t("saved")
    await cb_bset(c, str(bid))


@step("set_name")
async def s_set_name(c):
    await c.drop_input()
    bot = await _bot_from_state(c)
    if not bot or not 2 <= len(c.text) <= 40 or security.is_dangerous(c.text):
        return await c.show(c.T("bad_name"), K(c.home_row()))
    await db.upd("bots", "id", bot["id"], name=c.text)
    try:
        await (await tgc(c, bot)).call("setMyName", name=c.text)
    except TGError:
        pass
    await _saved(c, bot["id"])


@step("set_desc")
async def s_set_desc(c):
    await c.drop_input()
    bot = await _bot_from_state(c)
    if not bot or not c.text or security.is_dangerous(c.text):
        return await c.show(c.T("bad_text"), K(c.home_row()))
    text = c.text[:500]
    await db.upd("bot_settings", "bot_id", bot["id"], description=text)
    tg = await tgc(c, bot)
    for m, p in (("setMyDescription", {"description": text}), ("setMyShortDescription", {"short_description": text[:120]})):
        try:
            await tg.call(m, **p)
        except TGError:
            pass
    await _saved(c, bot["id"])


@step("set_channel")
async def s_set_channel(c):
    await c.drop_input()
    bot = await _bot_from_state(c)
    raw = re.sub(r"^(https?://)?(t\.me/)?@?", "", c.text.strip())
    if not bot or not (raw == "-" or re.match(r"^[A-Za-z][A-Za-z0-9_]{4,31}$", raw)):
        return await c.show(c.T("bad_channel"), K(c.home_row()))
    await db.upd("bot_settings", "bot_id", bot["id"], channel=None if raw == "-" else "@" + raw)
    await _saved(c, bot["id"])


@step("set_banner")
async def s_set_banner(c):
    bot = await _bot_from_state(c)
    if not bot:
        return
    if c.msg.get("photo"):
        await db.upd("bot_settings", "bot_id", bot["id"], banner_main=c.msg["photo"][-1]["file_id"], banner_child=None)
    elif c.text == "-":
        await db.upd("bot_settings", "bot_id", bot["id"], banner_main=None, banner_child=None)
    else:
        return await c.show(c.T("bad_photo"), K(c.home_row()))
    await c.drop_input()
    await _saved(c, bot["id"])


# ------------------------------------------------------------ xabarlar va avto-javoblar
@cb("bmsg")
async def cb_bmsg(c, a):
    c.clear()
    bot, _ = await own(c, a)
    if not bot:
        return
    i = bot["id"]
    await c.show(c.T("bm_title"), K([B(c.t("bm_start"), f"bmf:{i}")], [B(c.t("bm_auto"), f"bar:{i}")],
                                    [B(c.t("back"), f"bot:{i}")] + c.home_row()))


@cb("bmf")
async def cb_bmf(c, a):
    bot, _ = await own(c, a)
    if not bot:
        return
    c.set_step("set_start", bot=bot["id"])
    st = await db.one("SELECT start_text FROM bot_settings WHERE bot_id=?", bot["id"])
    await c.show(c.T("ask_start", cur=esc((st["start_text"] or "—")[:300])), K([B(c.t("cancel"), f"bmsg:{bot['id']}")]))


@step("set_start")
async def s_set_start(c):
    await c.drop_input()
    bot = await _bot_from_state(c)
    if not bot or not c.text or len(c.text) > 3500 or security.is_dangerous(c.text):
        return await c.show(c.T("bad_text"), K(c.home_row()))
    await db.upd("bot_settings", "bot_id", bot["id"], start_text=c.text)
    c.clear()
    c.toast = c.t("saved")
    await c.show(c.T("saved"), K([B(c.t("back"), f"bmsg:{bot['id']}")] + c.home_row()))


@cb("bar")
async def cb_bar(c, a):
    c.clear()
    bot, _ = await own(c, a)
    if not bot:
        return
    items = await db.all_("SELECT * FROM bot_autoreplies WHERE bot_id=? ORDER BY id", bot["id"])
    rows = [[B(f"🗑 {x['keyword']}"[:40], f"bard:{bot['id']}:{x['id']}")] for x in items]
    rows.append([B(c.t("ar_add"), f"bara:{bot['id']}")])
    rows.append([B(c.t("back"), f"bmsg:{bot['id']}")] + c.home_row())
    await c.show(c.T("ar_title", n=len(items)) + ("" if items else "\n\n" + c.t("ar_empty")), K(*rows))


@cb("bard")
async def cb_bard(c, a):
    bot, rest = await own(c, a)
    if not bot:
        return
    await db.run("DELETE FROM bot_autoreplies WHERE id=? AND bot_id=?", int(rest[0]), bot["id"])
    await cb_bar(c, str(bot["id"]))


@cb("bara")
async def cb_bara(c, a):
    bot, _ = await own(c, a)
    if not bot:
        return
    plan = await svc.plan_of(c.user)
    if await db.val("SELECT COUNT(*) FROM bot_autoreplies WHERE bot_id=?", bot["id"]) >= plan["max_autoreplies"]:
        return await c.show(c.T("ar_limit", n=plan["max_autoreplies"]), K([B(c.t("m_prem"), "prem")], [B(c.t("back"), f"bar:{bot['id']}")]))
    c.set_step("ar_kw", bot=bot["id"])
    await c.show(c.T("ask_kw"), K([B(c.t("cancel"), f"bar:{bot['id']}")]))


@step("ar_kw")
async def s_ar_kw(c):
    await c.drop_input()
    if not c.text or len(c.text) > 60 or security.is_dangerous(c.text) or c.text.startswith("/"):
        return await c.show(c.T("bad_text"), K(c.home_row()))
    c.state["d"]["kw"] = c.text
    c.state["step"] = "ar_reply"
    await c.show(c.T("ask_reply"), K(c.home_row()))


@step("ar_reply")
async def s_ar_reply(c):
    await c.drop_input()
    bot = await _bot_from_state(c)
    if not bot or not c.text or len(c.text) > 3500 or security.is_dangerous(c.text):
        return await c.show(c.T("bad_text"), K(c.home_row()))
    await db.run("INSERT INTO bot_autoreplies(bot_id,keyword,reply) VALUES(?,?,?)", bot["id"], c.state["d"]["kw"], c.text)
    c.clear()
    await cb_bar(c, str(bot["id"]))


# ------------------------------------------------------------ tugma konstruktori
async def level(c, bot, parent):
    items = await db.all_("SELECT * FROM bot_buttons WHERE bot_id=? AND parent_id IS ? ORDER BY position,id", bot["id"], parent)
    rows = [[B(f"{x['label']}"[:50], f"bbi:{x['id']}")] for x in items]
    rows.append([B(c.t("bb_add"), f"bba:{bot['id']}:{parent}")])
    if parent:
        up = await db.val("SELECT parent_id FROM bot_buttons WHERE id=?", parent)
        back = f"bbtn:{bot['id']}:{up or 0}"
    else:
        back = f"bot:{bot['id']}"
    rows.append([B(c.t("back"), back)] + c.home_row())
    head = c.T("bb_title", n=len(items))
    await c.show(head + ("" if items else "\n\n" + c.t("bb_empty")), K(*rows))


@cb("bbtn")
async def cb_bbtn(c, a):
    c.clear()
    bot, rest = await own(c, a)
    if bot:
        await level(c, bot, int(rest[0]) or None)


async def btn_of(c, bid):
    b = await db.one("SELECT b.*, o.owner_id FROM bot_buttons b JOIN bots o ON o.id=b.bot_id WHERE b.id=?", int(bid)) if str(bid).isdigit() else None
    if not b or b["owner_id"] != c.uid:
        await c.show(c.T("not_found"), K(c.home_row()))
        return None
    return b


@cb("bbi")
async def cb_bbi(c, a):
    c.clear()
    b = await btn_of(c, a)
    if not b:
        return
    i = b["id"]
    val = esc((b["value"] or "—")[:200])
    rows = [[B("⬆️", f"bbm:{i}:u"), B("⬇️", f"bbm:{i}:d")],
            [B(c.t("bb_edit_label"), f"bbe:{i}:label")]]
    if b["action"] in ("text", "url", "channel"):
        rows[1].append(B(c.t("bb_edit_value"), f"bbe:{i}:value"))
    if b["action"] == "menu":
        rows.append([B(c.t("bb_open"), f"bbtn:{b['bot_id']}:{i}")])
    rows.append([B(c.t("bb_delete"), f"bbd:{i}")])
    rows.append([B(c.t("back"), f"bbtn:{b['bot_id']}:{b['parent_id'] or 0}")] + c.home_row())
    await c.show(c.T("btn_card", label=esc(b["label"]), act=c.t("act_" + b["action"]), val=val), K(*rows))


@cb("bbm")
async def cb_bbm(c, a):
    bid, _, d = a.partition(":")
    b = await btn_of(c, bid)
    if not b:
        return
    sib = await db.all_("SELECT id,position FROM bot_buttons WHERE bot_id=? AND parent_id IS ? ORDER BY position,id", b["bot_id"], b["parent_id"])
    idx = next(i for i, x in enumerate(sib) if x["id"] == b["id"])
    j = idx - 1 if d == "u" else idx + 1
    if 0 <= j < len(sib):
        sib[idx], sib[j] = sib[j], sib[idx]
        for pos, x in enumerate(sib):
            await db.upd("bot_buttons", "id", x["id"], position=pos)
    bot = await db.one("SELECT * FROM bots WHERE id=?", b["bot_id"])
    await level(c, bot, b["parent_id"])


@cb("bbd")
async def cb_bbd(c, a):
    b = await btn_of(c, a)
    if not b:
        return
    await db.run("DELETE FROM bot_buttons WHERE id=?", b["id"])
    bot = await db.one("SELECT * FROM bots WHERE id=?", b["bot_id"])
    await level(c, bot, b["parent_id"])


@cb("bbe")
async def cb_bbe(c, a):
    bid, _, field = a.partition(":")
    b = await btn_of(c, bid)
    if not b or field not in ("label", "value"):
        return
    c.set_step("btn_edit", id=b["id"], field=field)
    await c.show(c.T("ask_btn_label" if field == "label" else "ask_btn_" + b["action"]), K([B(c.t("cancel"), f"bbi:{b['id']}")]))


def valid_value(action, text):
    """(ok, qiymat). Havola/kanal/matn xavfsizligi."""
    text = text.strip()
    if action == "url":
        u = security.safe_url(text)
        return (bool(u), u)
    if action == "channel":
        raw = re.sub(r"^(https?://)?(t\.me/)?@?", "", text)
        return (bool(re.match(r"^[A-Za-z][A-Za-z0-9_]{4,31}$", raw)), "@" + raw)
    return (bool(text) and len(text) <= 3500 and not security.is_dangerous(text), text)


@step("btn_edit")
async def s_btn_edit(c):
    await c.drop_input()
    d = c.state["d"]
    b = await btn_of(c, d["id"])
    if not b:
        return
    if d["field"] == "label":
        ok, val = bool(c.text) and len(c.text) <= 40 and not security.is_dangerous(c.text), c.text
    else:
        ok, val = valid_value(b["action"], c.text)
    if not ok:
        return await c.show(c.T("bad_url" if b["action"] in ("url", "channel") and d["field"] == "value" else "bad_text"), K(c.home_row()))
    await db.upd("bot_buttons", "id", b["id"], **{d["field"]: val})
    c.clear()
    await cb_bbi(c, str(b["id"]))


@cb("bba")
async def cb_bba(c, a):
    bot, rest = await own(c, a)
    if not bot:
        return
    plan = await svc.plan_of(c.user)
    if await db.val("SELECT COUNT(*) FROM bot_buttons WHERE bot_id=?", bot["id"]) >= plan["max_buttons"]:
        return await c.show(c.T("btn_limit", n=plan["max_buttons"]), K([B(c.t("m_prem"), "prem")], [B(c.t("back"), f"bbtn:{bot['id']}:{rest[0]}")]))
    c.set_step("btn_label", bot=bot["id"], parent=int(rest[0]) or None)
    await c.show(c.T("ask_btn_label"), K([B(c.t("cancel"), f"bbtn:{bot['id']}:{rest[0]}")]))


@step("btn_label")
async def s_btn_label(c):
    await c.drop_input()
    if not c.text or len(c.text) > 40 or security.is_dangerous(c.text) or c.text.startswith("/"):
        return await c.show(c.T("bad_text"), K(c.home_row()))
    d = c.state["d"]
    d["label"] = c.text
    c.state["step"] = "btn_type"
    rows = [[B(c.t("ty_text"), "bty:text"), B(c.t("ty_url"), "bty:url")],
            [B(c.t("ty_menu"), "bty:menu"), B(c.t("ty_channel"), "bty:channel")], [B(c.t("ty_command"), "bty:command")]]
    await c.show(c.T("ask_btn_type"), K(*rows, [B(c.t("cancel"), f"bbtn:{d['bot']}:{d['parent'] or 0}")]))


async def _create_btn(c, action, value):
    d = c.state["d"]
    bot = await db.one("SELECT * FROM bots WHERE id=? AND owner_id=?", d["bot"], c.uid)
    if not bot:
        return
    bid = await svc.add_button(bot["id"], d["parent"], d["label"], action, value)
    c.clear()
    c.toast = c.t("btn_created")
    await level(c, bot, d["parent"])
    return bid


@cb("bty")
async def cb_bty(c, a):
    st = c.state
    if not st or st["step"] != "btn_type":
        return
    plan = await svc.plan_of(c.user)
    if a == "channel" and not plan["channel"]:
        return await c.show(*lock(c))
    if a == "menu":
        return await _create_btn(c, "menu", None)
    if a == "command":
        rows = [[B(c.t("cmd_" + x), f"btc:{x}")] for x in COMMANDS]
        return await c.show(c.T("ask_btn_command"), K(*rows, c.home_row()))
    st["step"] = "btn_value"
    st["d"]["action"] = a
    await c.show(c.T("ask_btn_" + a), K(c.home_row()))


@cb("btc")
async def cb_btc(c, a):
    st = c.state
    if st and st["step"] == "btn_type" and a in COMMANDS:
        await _create_btn(c, "command", a)


@step("btn_value")
async def s_btn_value(c):
    await c.drop_input()
    d = c.state["d"]
    ok, val = valid_value(d["action"], c.text)
    if not ok:
        return await c.show(c.T("bad_url" if d["action"] in ("url", "channel") else "bad_text"), K(c.home_row()))
    await _create_btn(c, d["action"], val)


# ------------------------------------------------------------ bot adminlari
@cb("badm")
async def cb_badm(c, a):
    c.clear()
    bot, _ = await own(c, a)
    if not bot:
        return
    ids = [r["user_id"] for r in await db.all_("SELECT user_id FROM bot_admins WHERE bot_id=? ORDER BY created_at", bot["id"])]
    rows = [[B(f"🗑 {u}", f"badmd:{bot['id']}:{u}")] for u in ids]
    rows.append([B(c.t("ba_add"), f"badma:{bot['id']}")])
    rows.append([B(c.t("back"), f"bot:{bot['id']}")] + c.home_row())
    await c.show(c.T("ba_title", owner=bot["owner_id"]) + ("" if ids else "\n\n" + c.t("ba_none")), K(*rows))


@cb("badmd")
async def cb_badmd(c, a):
    bot, rest = await own(c, a)
    if bot:
        await db.run("DELETE FROM bot_admins WHERE bot_id=? AND user_id=?", bot["id"], int(rest[0]))
        await cb_badm(c, str(bot["id"]))


@cb("badma")
async def cb_badma(c, a):
    bot, _ = await own(c, a)
    if not bot:
        return
    plan = await svc.plan_of(c.user)
    if await db.val("SELECT COUNT(*) FROM bot_admins WHERE bot_id=?", bot["id"]) >= plan["max_admins"]:
        return await c.show(c.T("ba_limit", n=plan["max_admins"]), K([B(c.t("m_prem"), "prem")], [B(c.t("back"), f"badm:{bot['id']}")]))
    c.set_step("badm_add", bot=bot["id"])
    await c.show(c.T("ask_admin_id"), K([B(c.t("cancel"), f"badm:{bot['id']}")]))


@step("badm_add")
async def s_badm_add(c):
    await c.drop_input()
    bot = await _bot_from_state(c)
    if not bot or not re.match(r"^\d{5,15}$", c.text):
        return await c.show(c.T("bad_id"), K(c.home_row()))
    await db.run("INSERT OR IGNORE INTO bot_admins(bot_id,user_id) VALUES(?,?)", bot["id"], int(c.text))
    c.clear()
    await cb_badm(c, str(bot["id"]))


# ------------------------------------------------------------ statistika
@cb("bstat")
async def cb_bstat(c, a):
    bot, _ = await own(c, a)
    if not bot:
        return
    plan, now = await svc.plan_of(c.user), int(time.time())
    r = await db.one("SELECT COUNT(*) n, COALESCE(SUM(messages),0) m, COALESCE(SUM(first_seen>=?),0) today, COALESCE(SUM(last_seen>=?),0) act, "
                     "COALESCE(SUM(first_seen>=?),0) w7, COALESCE(SUM(first_seen>=?),0) d30 FROM bot_users WHERE bot_id=?",
                     today_start(), now - 86400, now - 7 * 86400, now - 30 * 86400, bot["id"])
    text = c.T("bstat", name=esc(bot["name"]), **r)
    text += ("\n" + c.t("bstat_adv", w7=r["w7"], d30=r["d30"])) if plan["adv_stats"] else "\n\n" + c.t("bstat_lock")
    await c.show(text, K([B(c.t("back"), f"bot:{bot['id']}")] + c.home_row()))


# ------------------------------------------------------------ zaxira
@cb("bbak")
async def cb_bbak(c, a):
    c.clear()
    bot, rest = await own(c, a)
    if not bot:
        return
    plan = await svc.plan_of(c.user)
    if not plan["backup"]:
        return await c.show(*lock(c))
    if rest and rest[0] == "new":
        await db.run("INSERT INTO backups(kind,bot_id,owner_id,data) VALUES('user',?,?,?)", bot["id"], c.uid, await svc.snapshot(bot["id"]))
        await db.run("DELETE FROM backups WHERE kind='user' AND bot_id=? AND id NOT IN (SELECT id FROM backups WHERE kind='user' AND bot_id=? ORDER BY id DESC LIMIT 5)",
                     bot["id"], bot["id"])
        c.toast = c.t("bk_done")
    if rest and rest[0] == "res":
        last = await db.one("SELECT data FROM backups WHERE kind='user' AND bot_id=? ORDER BY id DESC LIMIT 1", bot["id"])
        if last:
            await svc.restore(bot["id"], last["data"])
            c.toast = c.t("bk_restored")
    items = await db.all_("SELECT created_at FROM backups WHERE kind='user' AND bot_id=? ORDER BY id DESC", bot["id"])
    lst = "\n".join(f"• {fmt_day(x['created_at'])}" for x in items) or c.t("bk_none")
    await c.show(c.T("bk_title", list=lst), K([B(c.t("bk_create"), f"bbak:{bot['id']}:new")],
                                              [B(c.t("bk_restore"), f"bbak:{bot['id']}:res")] if items else [],
                                              [B(c.t("back"), f"bot:{bot['id']}")] + c.home_row()))
