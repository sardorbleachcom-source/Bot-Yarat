# -*- coding: utf-8 -*-
"""Admin panel (o'zbek tilida). Darajalar: super > admin > mod."""
import time

from .. import config, database as db, security, services as svc
from ..core import cb, cmd, step, RANK
from ..i18n import t
from ..templates_data import GROUPS
from ..tg import TGError
from ..utils import B, K, esc, fmt_day, paged, today_start

PLANS = ("free", "premium", "premium_plus")
PN = lambda k: t("uz", "plan_" + k)
ROLE_NAME = {"super": "👑 Super Admin", "admin": "🛡 Admin", "mod": "🔧 Moderator"}
BACK = [B("⬅️ Admin panel", "adm")]


def until_text(u):
    if u["plan"] == "free":
        return "—"
    return fmt_day(u["premium_until"]) if u["premium_until"] else "muddatsiz"


async def find_user(text):
    text = text.strip().lstrip("@")
    if text.isdigit():
        return await db.one("SELECT * FROM users WHERE user_id=?", int(text))
    return await db.one("SELECT * FROM users WHERE username=?", text.lower())


# ------------------------------------------------------------ bosh panel
@cmd("admin", "mod")
async def c_admin(c):
    c.clear()
    await panel(c, fresh=True)


@cb("adm", "mod")
async def cb_adm(c, a):
    c.clear()
    await panel(c)


async def panel(c, fresh=False):
    R = RANK[c.role]
    rows = [[B("👥 Foydalanuvchilar", "au"), B("💬 Murojaatlar", "asup")]]
    if R >= 2:
        rows += [[B("🤖 Botlar", "ab:0"), B("👑 Premium", "ap")], [B("💳 To‘lovlar", "apay"), B("📚 Shablonlar", "atpl:0")]]
    rows.append([B("📊 Statistika", "ast")] + ([B("📢 Xabar yuborish", "abc")] if R >= 2 else []))
    if R >= 2:
        rows.append([B("💾 Zaxira", "abk")])
    if R >= 3:
        rows.append([B("⚙️ Tizim sozlamalari", "asys")])
    rows.append([B("🚨 Xatoliklar", "aerr"), B("🏠 Bosh menyu", "home")])
    pend = await db.val("SELECT COUNT(*) FROM payments WHERE status='pending'")
    uns = await db.val("SELECT COUNT(*) FROM support_messages WHERE answered=0")
    text = f"🛠 <b>Admin panel</b> — {ROLE_NAME[c.role]}\n\n💳 Kutilayotgan to‘lovlar: <b>{pend}</b>\n💬 Javobsiz murojaatlar: <b>{uns}</b>"
    await (c.fresh if fresh else c.show)(text, K(*rows))


# ------------------------------------------------------------ foydalanuvchilar
@cb("au", "mod")
async def cb_au(c, a):
    c.clear()
    await c.show("👥 <b>Foydalanuvchilar</b>", K([B("🔎 Qidirish (ID / @username)", "auf")], [B("🆕 So‘nggilar", "aul:r:0"), B("🚫 Bloklanganlar", "aul:b:0")], BACK))


@cb("auf", "mod")
async def cb_auf(c, a):
    c.set_step("au_find")
    await c.show("🔎 Foydalanuvchi <b>ID</b> yoki <b>@username</b> ni yuboring:", K([B("❌ Bekor", "au")]))


@step("au_find", "mod")
async def s_au_find(c):
    await c.drop_input()
    u = await find_user(c.text)
    if not u:
        return await c.show("❌ Topilmadi (foydalanuvchi botga /start bosgan bo‘lishi kerak).", K([B("❌ Bekor", "au")]))
    c.clear()
    await card(c, u)


@cb("aul", "mod")
async def cb_aul(c, a):
    mode, p = a.split(":")
    where = "WHERE blocked=1" if mode == "b" else ""
    rows_all = await db.all_(f"SELECT user_id,username,first_name FROM users {where} ORDER BY created_at DESC LIMIT 200")
    chunk, page, pages = paged(rows_all, int(p), 10)
    rows = [[B(f"{u['first_name'] or '-'} @{u['username'] or '-'} · {u['user_id']}"[:60], f"auc:{u['user_id']}")] for u in chunk]
    nav = ([B("⬅️", f"aul:{mode}:{page - 1}")] if page > 0 else []) + ([B("➡️", f"aul:{mode}:{page + 1}")] if page < pages - 1 else [])
    await c.show("👥 Ro‘yxat" + (" (bloklanganlar)" if mode == "b" else " (so‘nggilar)"), K(*rows, nav, [B("⬅️ Orqaga", "au")]))


async def card(c, u):
    plan = svc.effective_key(u)
    n = await db.val("SELECT COUNT(*) FROM bots WHERE owner_id=?", u["user_id"])
    text = (f"👤 <b>{esc(u['first_name'] or '-')}</b> @{esc(u['username'] or '-')}\n🆔 <code>{u['user_id']}</code>\n"
            f"⭐ Tarif: <b>{PN(plan)}</b> ({until_text(u)})\n🤖 Botlar: {n}\n🚫 Bloklangan: {'ha' if u['blocked'] else 'yo‘q'}\n📅 Qo‘shilgan: {fmt_day(u['created_at'])}")
    uid = u["user_id"]
    rows = []
    if RANK[c.role] >= 2:
        rows += [[B("👑 Tarif berish", f"apg:{uid}"), B("❌ Premiumni bekor qilish", f"apx:{uid}")], [B("📅 Muddatni o‘zgartirish", f"apd:{uid}")]]
    rows.append([B("✅ Blokdan chiqarish" if u["blocked"] else "🚫 Bloklash", f"abl:{uid}")])
    rows.append([B("⬅️ Orqaga", "au")])
    await c.show(text, K(*rows))


@cb("auc", "mod")
async def cb_auc(c, a):
    u = await db.one("SELECT * FROM users WHERE user_id=?", int(a))
    if u:
        await card(c, u)


@cb("abl", "mod")
async def cb_abl(c, a):
    uid = int(a)
    if await svc.role_of(uid):
        c.toast, c.alert = "Xodimni bloklab bo‘lmaydi", True
        return
    u = await db.one("SELECT * FROM users WHERE user_id=?", uid)
    await db.upd("users", "user_id", uid, blocked=0 if u["blocked"] else 1)
    if not u["blocked"]:
        for b in await db.all_("SELECT id FROM bots WHERE owner_id=?", uid):
            await c.app.runner.stop(b["id"])
    await card(c, await db.one("SELECT * FROM users WHERE user_id=?", uid))


# ------------------------------------------------------------ Premium berish
@cb("ap", "admin")
async def cb_ap(c, a):
    c.clear()
    await c.show("👑 <b>Premium</b>", K([B("👑 Premium berish", "apf")], [B("📋 Premium foydalanuvchilar", "apl:0")], [B("💰 Tariflar va narxlar", "apt")], BACK))


@cb("apf", "admin")
async def cb_apf(c, a):
    c.set_step("ap_find")
    await c.show("👑 Foydalanuvchi <b>@username</b> yoki <b>ID</b> sini yuboring:\n(Asosiy identifikator Telegram ID, username faqat qidirish uchun)", K([B("❌ Bekor", "ap")]))


@step("ap_find", "admin")
async def s_ap_find(c):
    await c.drop_input()
    u = await find_user(c.text)
    if not u:
        return await c.show("❌ Foydalanuvchi topilmadi.", K([B("❌ Bekor", "ap")]))
    c.clear()
    await cb_apg(c, str(u["user_id"]))


@cb("apg", "admin")
async def cb_apg(c, a):
    u = await db.one("SELECT * FROM users WHERE user_id=?", int(a))
    if not u:
        return
    rows = [[B(PN(p), f"apg2:{a}:{p}")] for p in PLANS]
    await c.show(f"👤 @{esc(u['username'] or '-')} (<code>{a}</code>)\nHozirgi tarif: <b>{PN(svc.effective_key(u))}</b>\n\nTarifni tanlang:", K(*rows, [B("⬅️ Orqaga", "ap")]))


@cb("apg2", "admin")
async def cb_apg2(c, a):
    uid, plan = a.split(":")
    if plan == "free":
        return await cb_apg3(c, f"{uid}:free:0")
    rows = [[B("7 kun", f"apg3:{uid}:{plan}:7"), B("30 kun", f"apg3:{uid}:{plan}:30")],
            [B("90 kun", f"apg3:{uid}:{plan}:90"), B("Muddatsiz", f"apg3:{uid}:{plan}:inf")]]
    await c.show(f"⭐ {PN(plan)}\nMuddatni tanlang:", K(*rows, [B("⬅️ Orqaga", f"apg:{uid}")]))


@cb("apg3", "admin")
async def cb_apg3(c, a):
    uid, plan, days = a.split(":")
    d = "muddatsiz" if days == "inf" else ("—" if plan == "free" else f"{days} kun")
    await c.show(f"❓ Tasdiqlaysizmi?\n\n🆔 <code>{uid}</code>\n⭐ {PN(plan)}\n📅 {d}",
                 K([B("✅ Tasdiqlash", f"apg4:{a}"), B("❌ Bekor", "ap")]))


@cb("apg4", "admin")
async def cb_apg4(c, a):
    uid, plan, days = a.split(":")
    await svc.grant(c.app, int(uid), plan, None if days in ("inf", "0") else int(days), c.uid)
    c.toast = "✅ Bajarildi"
    await card(c, await db.one("SELECT * FROM users WHERE user_id=?", int(uid)))


@cb("apx", "admin")
async def cb_apx(c, a):
    await svc.grant(c.app, int(a), "free", None, c.uid)
    c.toast = "✅ Premium bekor qilindi"
    await card(c, await db.one("SELECT * FROM users WHERE user_id=?", int(a)))


@cb("apd", "admin")
async def cb_apd(c, a):
    c.set_step("ap_days", uid=int(a))
    await c.show("📅 Yangi muddatni <b>bugundan boshlab kunlarda</b> yuboring (0 = muddatsiz):", K([B("❌ Bekor", f"auc:{a}")]))


@step("ap_days", "admin")
async def s_ap_days(c):
    await c.drop_input()
    uid = c.state["d"]["uid"]
    u = await db.one("SELECT * FROM users WHERE user_id=?", uid)
    if not c.text.isdigit() or int(c.text) > 3650 or u["plan"] == "free":
        return await c.show("❌ Son kiriting (0–3650). Avval foydalanuvchiga Premium tarif bering.", K([B("❌ Bekor", f"auc:{uid}")]))
    days = int(c.text)
    await db.upd("users", "user_id", uid, premium_until=int(time.time()) + days * 86400 if days else None, notified=0)
    c.clear()
    await card(c, await db.one("SELECT * FROM users WHERE user_id=?", uid))


@cb("apl", "admin")
async def cb_apl(c, a):
    us = await db.all_("SELECT * FROM users WHERE plan!='free' ORDER BY premium_until IS NULL, premium_until LIMIT 200")
    us = [u for u in us if svc.effective_key(u) != "free"]
    chunk, page, pages = paged(us, int(a), 10)
    rows = [[B(f"{PN(u['plan'])} · @{u['username'] or u['user_id']} · {until_text(u)}"[:60], f"auc:{u['user_id']}")] for u in chunk]
    nav = ([B("⬅️", f"apl:{page - 1}")] if page > 0 else []) + ([B("➡️", f"apl:{page + 1}")] if page < pages - 1 else [])
    await c.show(f"📋 Premium foydalanuvchilar: {len(us)}", K(*rows, nav, [B("⬅️ Orqaga", "ap")]))


FIELDS = {"price": "💰 Narx (so‘m/30 kun)", "max_bots": "🤖 Botlar soni", "max_buttons": "🔘 Tugmalar", "max_admins": "👥 Bot adminlari",
          "max_autoreplies": "💬 Avto-javoblar", "banner": "🖼 Banner (0/1)", "channel": "📢 Kanal (0/1)", "backup": "💾 Zaxira (0/1)",
          "nofooter": "🏷 Belgisiz (0/1)", "adv_stats": "📊 Kengaytirilgan stat. (0/1)"}


@cb("apt", "admin")
async def cb_apt(c, a):
    c.clear()
    rows = []
    for k in PLANS:
        p = await svc.get_plan(k)
        rows.append([B(f"{PN(k)} — {p['price']} so‘m", f"apte:{k}")])
    await c.show("💰 <b>Tariflar</b>\nO‘zgartirish uchun tanlang:", K(*rows, [B("⬅️ Orqaga", "ap")]))


@cb("apte", "admin")
async def cb_apte(c, a):
    p = await svc.get_plan(a)
    lines = "\n".join(f"{v}: <b>{p[k]}</b>" for k, v in FIELDS.items())
    rows = [[B(v, f"aptf:{a}:{k}")] for k, v in FIELDS.items()]
    await c.show(f"⭐ <b>{PN(a)}</b>\n\n{lines}", K(*rows, [B("⬅️ Orqaga", "apt")]))


@cb("aptf", "admin")
async def cb_aptf(c, a):
    plan, field = a.split(":")
    if field not in FIELDS:
        return
    c.set_step("plan_edit", plan=plan, field=field)
    await c.show(f"✍️ <b>{FIELDS[field]}</b> uchun yangi qiymat (son):", K([B("❌ Bekor", f"apte:{plan}")]))


@step("plan_edit", "admin")
async def s_plan_edit(c):
    await c.drop_input()
    d = c.state["d"]
    if not c.text.isdigit() or int(c.text) > 10_000_000_000:
        return await c.show("❌ Faqat son kiriting.", K([B("❌ Bekor", f"apte:{d['plan']}")]))
    await db.upd("plans", "key", d["plan"], **{d["field"]: int(c.text)})
    c.clear()
    await cb_apte(c, d["plan"])


# ------------------------------------------------------------ to'lovlar
@cb("apay", "admin")
async def cb_apay(c, a):
    items = await db.all_("SELECT * FROM payments WHERE status='pending' ORDER BY id")
    rows = [[B(f"#{p['id']} · {PN(p['plan'])} · {p['amount']} · {p['user_id']}", f"apayc:{p['id']}")] for p in items[:20]]
    await c.show(f"💳 <b>To‘lovlar</b>\nKutilayotgan: {len(items)}", K(*rows, BACK))


async def pay_text(p):
    u = await db.one("SELECT * FROM users WHERE user_id=?", p["user_id"])
    return (f"💳 <b>To‘lov #{p['id']}</b> ({p['status']})\n👤 {esc(u['first_name'] or '-')} @{esc(u['username'] or '-')}\n"
            f"🆔 <code>{p['user_id']}</code>\n⭐ Tarif: {PN(p['plan'])}\n💰 Narx: {p['amount']}\n📅 Muddat: {p['days']} kun")


@cb("apayc", "admin")
async def cb_apayc(c, a):
    p = await db.one("SELECT * FROM payments WHERE id=?", int(a))
    if p:
        rows = [[B("✅ To‘lov tasdiqlandi", f"apayr:{a}:ok"), B("❌ To‘lov rad etildi", f"apayr:{a}:no")]] if p["status"] == "pending" else []
        await c.show(await pay_text(p), K(*rows, [B("⬅️ Orqaga", "apay")]))


@cb("apayr", "admin")
async def cb_apayr(c, a):
    pid, res = a.split(":")
    p = await db.one("SELECT * FROM payments WHERE id=?", int(pid))
    if not p or p["status"] != "pending":
        c.toast = "Allaqachon ko‘rib chiqilgan"
        return
    await db.upd("payments", "id", p["id"], status="approved" if res == "ok" else "rejected", reviewed_by=c.uid)
    u = await db.one("SELECT * FROM users WHERE user_id=?", p["user_id"])
    if res == "ok":
        await svc.grant(c.app, p["user_id"], p["plan"], p["days"], c.uid)
    else:
        try:
            await c.tg.send(p["user_id"], t(u["lang"] or "uz", "pay_rejected"), html=True)
        except TGError:
            pass
    await c.show(await pay_text(await db.one("SELECT * FROM payments WHERE id=?", p["id"])) + f"\n\n{'✅ Tasdiqlandi' if res == 'ok' else '❌ Rad etildi'}", K([B("⬅️ To‘lovlar", "apay")]))


# ------------------------------------------------------------ murojaatlar
@cb("asup", "mod")
async def cb_asup(c, a):
    items = await db.all_("SELECT * FROM support_messages WHERE answered=0 ORDER BY id LIMIT 20")
    rows = [[B(f"#{m['id']} · {m['user_id']} · {m['text'][:30]}", f"asc:{m['id']}")] for m in items]
    await c.show(f"💬 <b>Murojaatlar</b>\nJavobsiz: {len(items)}", K(*rows, BACK))


@cb("asc", "mod")
async def cb_asc(c, a):
    m = await db.one("SELECT * FROM support_messages WHERE id=?", int(a))
    if m:
        u = await db.one("SELECT * FROM users WHERE user_id=?", m["user_id"])
        await c.show(f"🔔 <b>Murojaat #{m['id']}</b>\n👤 @{esc(u['username'] or '-')}\n🆔 <code>{m['user_id']}</code>\n💬 {esc(m['text'])}"
                     + (f"\n\n↩️ Javob: {esc(m['reply_text'])}" if m["answered"] else ""),
                     K([B("💬 Javob berish", f"asr:{a}")], [B("⬅️ Orqaga", "asup")]))


@cb("asr", "mod")
async def cb_asr(c, a):
    c.set_step("sup_reply", id=int(a))
    await c.show("✍️ Foydalanuvchiga javobingizni yozing:", K([B("❌ Bekor", "asup")]))


@step("sup_reply", "mod")
async def s_sup_reply(c):
    await c.drop_input()
    sid = c.state["d"]["id"]
    m = await db.one("SELECT * FROM support_messages WHERE id=?", sid)
    if not m or not c.text:
        return
    u = await db.one("SELECT lang FROM users WHERE user_id=?", m["user_id"])
    try:
        await c.tg.send(m["user_id"], t(u["lang"] or "uz", "sup_reply", text=esc(c.text)), html=True)
        ok = "✅ Javob yuborildi."
    except TGError:
        ok = "⚠️ Foydalanuvchiga yuborib bo‘lmadi (bot bloklangan bo‘lishi mumkin)."
    await db.upd("support_messages", "id", sid, answered=1, reply_text=c.text, answered_by=c.uid)
    c.clear()
    await c.show(ok, K([B("⬅️ Murojaatlar", "asup")]))


# ------------------------------------------------------------ botlar
@cb("ab", "admin")
async def cb_ab(c, a):
    bots = await db.all_("SELECT * FROM bots ORDER BY id DESC")
    chunk, page, pages = paged(bots, int(a or 0), 10)
    icon = {"running": "🟢", "stopped": "⏸", "error": "⚠️"}
    rows = [[B(f"{icon.get(b['status'], '🔴')} @{b['username']} · {b['owner_id']}"[:60], f"abc2:{b['id']}")] for b in chunk]
    nav = ([B("⬅️", f"ab:{page - 1}")] if page > 0 else []) + ([B("➡️", f"ab:{page + 1}")] if page < pages - 1 else [])
    await c.show(f"🤖 <b>Botlar</b>: {len(bots)}", K(*rows, nav, BACK))


@cb("abc2", "admin")
async def cb_abc2(c, a):
    b = await db.one("SELECT * FROM bots WHERE id=?", int(a))
    if not b:
        return
    n = await db.val("SELECT COUNT(*) FROM bot_users WHERE bot_id=?", b["id"])
    live = "🟢 ishlayapti" if c.app.runner.alive(b["id"]) else "⏸/🔴 ishlamayapti"
    err = f"\n⚠️ {esc(b['error_text'])}" if b["error_text"] else ""
    await c.show(f"🤖 <b>{esc(b['name'])}</b> @{esc(b['username'])}\n🆔 Bot ID: {b['id']}\n👤 Egasi: <code>{b['owner_id']}</code>\n"
                 f"📦 Shablon: {b['template']}\n🔐 Token: yashirin\n📊 Holat: {b['status']} ({live})\n👥 Obunachilar: {n}{err}",
                 K([B("▶️ Ishga tushirish", f"abx:{a}:start"), B("⏸ To‘xtatish", f"abx:{a}:stop")],
                   [B("🗑 O‘chirish", f"abx:{a}:del")], [B("⬅️ Orqaga", "ab:0")]))


@cb("abx", "admin")
async def cb_abx(c, a):
    bid, act = a.split(":")
    if act == "start":
        res = await c.app.runner.start(int(bid))
        c.toast = "✅ Ishga tushdi" if res is True else "❌ Ishga tushmadi"
    elif act == "stop":
        await c.app.runner.stop(int(bid))
        c.toast = "⏸ To‘xtatildi"
    else:
        await svc.delete_bot(c.app, int(bid))
        c.toast = "🗑 O‘chirildi"
        return await cb_ab(c, "0")
    await cb_abc2(c, bid)


# ------------------------------------------------------------ shablonlar
@cb("atpl", "admin")
async def cb_atpl(c, a):
    c.clear()
    items = await db.all_("SELECT * FROM bot_templates ORDER BY rowid")
    chunk, page, pages = paged(items, int(a or 0), 10)
    rows = [[B(f"{'✅' if x['enabled'] else '⛔'}{'⭐' if x['premium'] else ''} {x['name_uz']}"[:60], f"atc:{x['key']}")] for x in chunk]
    nav = ([B("⬅️", f"atpl:{page - 1}")] if page > 0 else []) + ([B("➡️", f"atpl:{page + 1}")] if page < pages - 1 else [])
    await c.show(f"📚 <b>Shablonlar</b>: {len(items)}", K(*rows, nav, [B("➕ Yangi shablon", "ata")], BACK))


@cb("atc", "admin")
async def cb_atc(c, a):
    x = await db.one("SELECT * FROM bot_templates WHERE key=?", a)
    if x:
        await c.show(f"📚 <b>{esc(x['name_uz'])}</b>\nGuruh: {x['grp']}\nKalit: {x['key']}\nFaol: {'ha' if x['enabled'] else 'yo‘q'}\nPremium: {'ha' if x['premium'] else 'yo‘q'}",
                     K([B("🔁 Faol/o‘chiq", f"att:{a}:enabled"), B("⭐ Premium/oddiy", f"att:{a}:premium")], [B("⬅️ Orqaga", "atpl:0")]))


@cb("att", "admin")
async def cb_att(c, a):
    key, field = a.split(":")
    if field in ("enabled", "premium"):
        x = await db.one("SELECT * FROM bot_templates WHERE key=?", key)
        await db.upd("bot_templates", "key", key, **{field: 0 if x[field] else 1})
    await cb_atc(c, key)


@cb("ata", "admin")
async def cb_ata(c, a):
    rows = [[B(t("uz", "g_" + g), f"atag:{g}")] for g in GROUPS]
    await c.show("➕ Yangi shablon: guruhni tanlang", K(*rows, [B("❌ Bekor", "atpl:0")]))


@cb("atag", "admin")
async def cb_atag(c, a):
    c.set_step("ata_uz", grp=a)
    await c.show("✍️ Shablon nomi (🇺🇿 O‘zbekcha), emoji bilan:", K([B("❌ Bekor", "atpl:0")]))


@step("ata_uz", "admin")
async def s_ata_uz(c):
    await _ata(c, "ata_ru", "ru", "🇷🇺 Ruscha")


@step("ata_ru", "admin")
async def s_ata_ru(c):
    await _ata(c, "ata_en", "en", "🇬🇧 Inglizcha")


@step("ata_en", "admin")
async def s_ata_en(c):
    await _ata(c, "ata_ar", "ar", "🇸🇦 Arabcha")


@step("ata_ar", "admin")
async def s_ata_ar(c):
    await _ata(c, "ata_start", None, "/start matni (hamma tillar uchun; guruh standarti uchun «-»)")


async def _ata(c, nxt, nxt_lang, label):
    await c.drop_input()
    cur = c.state["step"]
    if not c.text or len(c.text) > 60 and cur != "ata_start" or security.is_dangerous(c.text):
        return await c.show("❌ Noto‘g‘ri matn, qayta yuboring.", K([B("❌ Bekor", "atpl:0")]))
    c.state["d"][cur[-2:]] = c.text
    c.state["step"] = nxt
    await c.show(f"✍️ {label}:", K([B("❌ Bekor", "atpl:0")]))


@step("ata_start", "admin")
async def s_ata_start(c):
    await c.drop_input()
    d = c.state["d"]
    if security.is_dangerous(c.text):
        return
    key = "t" + str(int(time.time()))
    await db.run("INSERT INTO bot_templates(key,grp,name_uz,name_ru,name_en,name_ar,start_text) VALUES(?,?,?,?,?,?,?)",
                 key, d["grp"], d["uz"], d["ru"], d["en"], d["ar"], None if c.text == "-" else c.text[:3500])
    c.clear()
    await c.show("✅ Shablon qo‘shildi.", K([B("⬅️ Shablonlar", "atpl:0")]))


# ------------------------------------------------------------ statistika
@cb("ast", "mod")
async def cb_ast(c, a):
    now, ts = int(time.time()), today_start()
    runner = c.app.runner
    bots = await db.all_("SELECT id,status FROM bots")
    active = sum(1 for b in bots if b["status"] == "running" and runner.alive(b["id"]))
    stopped = sum(1 for b in bots if b["status"] == "stopped")
    prem = sum(1 for u in await db.all_("SELECT * FROM users WHERE plan!='free'") if svc.effective_key(u) != "free")
    today_pay = await db.one("SELECT COUNT(*) n, COALESCE(SUM(amount),0) s FROM payments WHERE status='approved' AND updated_at>=?", ts)
    total = await db.val("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='approved'")
    await c.show("📊 <b>Umumiy statistika</b>\n\n"
                 f"👥 Jami foydalanuvchilar: <b>{await db.val('SELECT COUNT(*) FROM users')}</b>\n"
                 f"🆕 Bugungi foydalanuvchilar: <b>{await db.val('SELECT COUNT(*) FROM users WHERE created_at>=?', ts)}</b>\n"
                 f"🤖 Jami botlar: <b>{len(bots)}</b>\n🟢 Faol botlar: <b>{active}</b>\n⏸ To‘xtatilgan: <b>{stopped}</b>\n"
                 f"👑 Premium foydalanuvchilar: <b>{prem}</b>\n💳 Bugungi to‘lovlar: <b>{today_pay['n']}</b> ({today_pay['s']} so‘m)\n💰 Umumiy tushum: <b>{total}</b> so‘m",
                 K(BACK))


# ------------------------------------------------------------ xabar yuborish
@cb("abc", "admin")
async def cb_abc(c, a):
    c.set_step("bc_content")
    await c.show("📢 Barcha foydalanuvchilarga yuboriladigan xabarni yuboring.\n📝 matn, 🖼 rasm yoki 🎥 video (izoh bilan) bo‘lishi mumkin.", K([B("❌ Bekor", "adm")]))


@step("bc_content", "admin")
async def s_bc_content(c):
    c.state["d"].update(chat=c.chat, mid=c.msg["message_id"])
    c.state["step"] = "bc_btn"
    await c.show("🔗 Tugmalar kerak bo‘lsa, har qatorga <code>Matn | https://havola</code> yozing.\nTugmasiz yuborish uchun <code>-</code>", K([B("❌ Bekor", "adm")]))


@step("bc_btn", "admin")
async def s_bc_btn(c):
    await c.drop_input()
    d, rows = c.state["d"], []
    if c.text != "-":
        for line in c.text.splitlines():
            label, _, url = line.partition("|")
            u = security.safe_url(url)
            if not label.strip() or not u:
                return await c.show("❌ Format: <code>Matn | https://havola</code>. Qayta yuboring yoki <code>-</code>.", K([B("❌ Bekor", "adm")]))
            rows.append([B(label.strip()[:40], url=u)])
    d["kb"] = K(*rows) if rows else None
    try:
        await c.tg.call("copyMessage", chat_id=c.chat, from_chat_id=d["chat"], message_id=d["mid"], reply_markup=d["kb"])
    except TGError:
        pass
    n = await db.val("SELECT COUNT(*) FROM users WHERE blocked=0 AND lang IS NOT NULL")
    c.state["step"] = "bc_confirm"
    await c.show(f"👆 Yuqorida xabar ko‘rinishi.\n\n📢 <b>{n}</b> ta foydalanuvchiga yuborilsinmi?", K([B("✅ Yuborish", "abcgo"), B("❌ Bekor", "adm")]))


@cb("abcgo", "admin")
async def cb_abcgo(c, a):
    st = c.state
    if not st or st["step"] != "bc_confirm":
        return
    d = st["d"]
    await c.app.bc_queue.put({"admin": c.uid, "chat": d["chat"], "mid": d["mid"], "kb": d["kb"]})
    c.clear()
    await c.show(f"⏳ Navbatga qo‘yildi (navbatda: {c.app.bc_queue.qsize()}). Tugagach hisobot keladi.", K(BACK))


# ------------------------------------------------------------ zaxira
@cb("abk", "admin")
async def cb_abk(c, a):
    if a == "new":
        path = await svc.system_backup(c.app)
        try:
            with open(path, "rb") as f:
                await c.tg.upload("sendDocument", "document", f.read(), path.name, chat_id=c.chat, caption="💾 Zaxira nusxa")
        except TGError:
            pass
    items = await db.all_("SELECT created_at, path FROM backups WHERE kind='system' ORDER BY id DESC LIMIT 7")
    lst = "\n".join(f"• {time.strftime('%Y-%m-%d %H:%M', time.gmtime(x['created_at'] + config.TZ_OFFSET * 3600))}" for x in items) or "hali yo‘q"
    await c.show(f"💾 <b>Zaxira</b>\nAvtomatik: har kuni (oxirgi 7 ta saqlanadi)\n\n{lst}\n\n⚠️ SECRET_KEY zaxiraga kirmaydi, uni alohida saqlang.",
                 K([B("💾 Zaxira yaratish va yuklab olish", "abk:new")], BACK))


# ------------------------------------------------------------ xatoliklar
@cb("aerr", "mod")
async def cb_aerr(c, a):
    if a == "clr" and RANK[c.role] >= 2:
        await db.run("DELETE FROM error_logs")
    items = await db.all_("SELECT * FROM error_logs ORDER BY id DESC LIMIT 8")
    body = "\n\n".join(f"#{e['id']} {e['source']}{' b' + str(e['bot_id']) if e['bot_id'] else ''} · {fmt_day(e['created_at'])}\n{esc(e['message'][-250:])}" for e in items)
    await c.show("🚨 <b>Xatoliklar</b>\n\n" + (body or "Xatolik yo‘q ✅"), K([B("🗑 Tozalash", "aerr:clr")] if RANK[c.role] >= 2 else [], BACK))


# ------------------------------------------------------------ tizim sozlamalari (faqat Super Admin)
@cb("asys", "super")
async def cb_asys(c, a):
    c.clear()
    await c.show("⚙️ <b>Tizim sozlamalari</b>", K([B("💳 To‘lov ma’lumoti", "asyp")], [B("👥 Adminlar", "asya")], BACK))


@cb("asyp", "super")
async def cb_asyp(c, a):
    c.set_step("sys_pay")
    cur = await db.val("SELECT value FROM settings WHERE key='payment_info'")
    await c.show(f"💳 Hozirgi:\n{esc(cur)}\n\n✍️ Yangi to‘lov ma’lumotini yuboring (foydalanuvchiga ko‘rsatiladi):", K([B("❌ Bekor", "asys")]))


@step("sys_pay", "super")
async def s_sys_pay(c):
    await c.drop_input()
    if not c.text or len(c.text) > 1000:
        return
    await db.run("INSERT OR REPLACE INTO settings(key,value) VALUES('payment_info',?)", c.text)
    c.clear()
    await c.show("✅ Saqlandi.", K([B("⬅️ Orqaga", "asys")]))


@cb("asya", "super")
async def cb_asya(c, a):
    c.clear()
    items = await db.all_("SELECT * FROM admins WHERE role!='super' ORDER BY created_at")
    rows = [[B(f"🗑 {ROLE_NAME[x['role']]} · {x['user_id']}", f"asyrm:{x['user_id']}")] for x in items]
    sup = ", ".join(map(str, sorted(config.SUPER_ADMINS)))
    await c.show(f"👥 <b>Adminlar</b>\n👑 Super Admin (.env): <code>{sup}</code>", K(*rows, [B("➕ Admin", "asyad:admin"), B("➕ Moderator", "asyad:mod")], [B("⬅️ Orqaga", "asys")]))


@cb("asyad", "super")
async def cb_asyad(c, a):
    c.set_step("sys_admin", role=a)
    await c.show(f"✍️ {ROLE_NAME[a]} qilinadigan foydalanuvchi Telegram ID sini yuboring:", K([B("❌ Bekor", "asya")]))


@step("sys_admin", "super")
async def s_sys_admin(c):
    await c.drop_input()
    if not c.text.isdigit():
        return await c.show("❌ ID raqam bo‘lishi kerak.", K([B("❌ Bekor", "asya")]))
    uid = int(c.text)
    await db.run("INSERT OR IGNORE INTO users(user_id) VALUES(?)", uid)
    await db.run("INSERT OR REPLACE INTO admins(user_id, role) VALUES(?,?)", uid, c.state["d"]["role"])
    await cb_asya(c, "")


@cb("asyrm", "super")
async def cb_asyrm(c, a):
    if int(a) not in config.SUPER_ADMINS:
        await db.run("DELETE FROM admins WHERE user_id=?", int(a))
    await cb_asya(c, "")
