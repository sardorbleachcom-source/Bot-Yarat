# -*- coding: utf-8 -*-
"""SQLite baza. Barcha so'rovlar parametrli (SQL injectiondan himoya)."""
import asyncio
import re
import sqlite3
import threading

from . import config

_conn = None
_lock = threading.Lock()
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, lang TEXT,
  plan TEXT NOT NULL DEFAULT 'free', premium_until INTEGER, notified INTEGER NOT NULL DEFAULT 0,
  blocked INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);
CREATE TABLE IF NOT EXISTS admins(
  user_id INTEGER PRIMARY KEY, role TEXT NOT NULL,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
CREATE TABLE IF NOT EXISTS plans(
  key TEXT PRIMARY KEY, price INTEGER NOT NULL DEFAULT 0, max_bots INTEGER NOT NULL, max_buttons INTEGER NOT NULL,
  max_admins INTEGER NOT NULL, max_autoreplies INTEGER NOT NULL, banner INTEGER NOT NULL DEFAULT 0,
  channel INTEGER NOT NULL DEFAULT 0, backup INTEGER NOT NULL DEFAULT 0, nofooter INTEGER NOT NULL DEFAULT 0,
  adv_stats INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
CREATE TABLE IF NOT EXISTS bot_templates(
  key TEXT PRIMARY KEY, grp TEXT NOT NULL, name_uz TEXT, name_ru TEXT, name_en TEXT, name_ar TEXT,
  start_text TEXT, premium INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
CREATE TABLE IF NOT EXISTS bots(
  id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER NOT NULL REFERENCES users(user_id),
  template TEXT, name TEXT, username TEXT, token_enc TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'stopped', error_text TEXT,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
CREATE INDEX IF NOT EXISTS ix_bots_owner ON bots(owner_id);
CREATE TABLE IF NOT EXISTS bot_settings(
  bot_id INTEGER PRIMARY KEY REFERENCES bots(id) ON DELETE CASCADE, lang TEXT NOT NULL DEFAULT 'uz',
  description TEXT, start_text TEXT, banner_main TEXT, banner_child TEXT, channel TEXT,
  hide_footer INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
CREATE TABLE IF NOT EXISTS bot_buttons(
  id INTEGER PRIMARY KEY AUTOINCREMENT, bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
  parent_id INTEGER REFERENCES bot_buttons(id) ON DELETE CASCADE, label TEXT NOT NULL, action TEXT NOT NULL,
  value TEXT, position INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
CREATE INDEX IF NOT EXISTS ix_btn ON bot_buttons(bot_id, parent_id, position);
CREATE TABLE IF NOT EXISTS bot_autoreplies(
  id INTEGER PRIMARY KEY AUTOINCREMENT, bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
  keyword TEXT NOT NULL, reply TEXT NOT NULL,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
CREATE TABLE IF NOT EXISTS bot_users(
  bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE, user_id INTEGER NOT NULL,
  first_name TEXT, username TEXT, messages INTEGER NOT NULL DEFAULT 0,
  first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
  PRIMARY KEY(bot_id, user_id));
CREATE TABLE IF NOT EXISTS bot_admins(
  bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE, user_id INTEGER NOT NULL,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
  PRIMARY KEY(bot_id, user_id));
CREATE TABLE IF NOT EXISTS subscriptions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, plan TEXT NOT NULL, days INTEGER,
  started_at INTEGER, until INTEGER, granted_by INTEGER,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
CREATE TABLE IF NOT EXISTS payments(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, plan TEXT NOT NULL, days INTEGER NOT NULL,
  amount INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', reviewed_by INTEGER,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
CREATE TABLE IF NOT EXISTS support_messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, text TEXT NOT NULL,
  answered INTEGER NOT NULL DEFAULT 0, reply_text TEXT, answered_by INTEGER,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
CREATE TABLE IF NOT EXISTS backups(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, bot_id INTEGER, owner_id INTEGER, data TEXT, path TEXT,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
CREATE TABLE IF NOT EXISTS error_logs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, bot_id INTEGER, message TEXT,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY, value TEXT,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
"""

DEFAULT_PLANS = [  # key, price, bots, buttons, admins, autoreplies, banner, channel, backup, nofooter, adv_stats
    ("free", 0, 1, 6, 0, 3, 0, 0, 0, 0, 0),
    ("premium", 30000, 5, 30, 3, 20, 1, 1, 1, 1, 1),
    ("premium_plus", 60000, 20, 100, 10, 100, 1, 1, 1, 1, 1),
]


def _connect():
    global _conn
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False, isolation_level=None)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    _conn.executescript(SCHEMA)
    return _conn


def _run(sql, args, mode):
    with _lock:
        conn = _conn or _connect()
        cur = conn.execute(sql, args)
        if mode == "one":
            r = cur.fetchone()
            return dict(r) if r else None
        if mode == "all":
            return [dict(r) for r in cur.fetchall()]
        return cur.lastrowid


async def one(sql, *args):
    return await asyncio.to_thread(_run, sql, args, "one")


async def all_(sql, *args):
    return await asyncio.to_thread(_run, sql, args, "all")


async def run(sql, *args):
    return await asyncio.to_thread(_run, sql, args, "exec")


async def val(sql, *args):
    r = await one(sql, *args)
    return next(iter(r.values())) if r else None


async def upd(table, keycol, keyval, **fields):
    """UPDATE ... SET maydon=? (nomlar tekshiriladi), updated_at avtomatik yangilanadi."""
    if not fields:
        return
    for name in (table, keycol, *fields):
        if not _IDENT.match(name):
            raise ValueError("noto'g'ri identifikator")
    sets = ", ".join(f"{k}=?" for k in fields)
    await run(f"UPDATE {table} SET {sets}, updated_at=strftime('%s','now') WHERE {keycol}=?",
              *fields.values(), keyval)


async def init(templates):
    """Sxemani yaratadi va boshlang'ich ma'lumotlarni (tariflar, shablonlar) joylaydi."""
    await asyncio.to_thread(_run, "SELECT 1", (), "one")
    for p in DEFAULT_PLANS:
        await run("INSERT OR IGNORE INTO plans(key,price,max_bots,max_buttons,max_admins,max_autoreplies,banner,"
                  "channel,backup,nofooter,adv_stats) VALUES(?,?,?,?,?,?,?,?,?,?,?)", *p)
    for key, grp, names, premium in templates:
        await run("INSERT OR IGNORE INTO bot_templates(key,grp,name_uz,name_ru,name_en,name_ar,premium) "
                  "VALUES(?,?,?,?,?,?,?)", key, grp, *names, premium)
    await run("INSERT OR IGNORE INTO settings(key,value) VALUES('payment_info', "
              "'💳 To‘lov rekvizitlari uchun admin bilan bog‘laning.')")
    for uid in config.SUPER_ADMINS:
        await run("INSERT OR IGNORE INTO users(user_id) VALUES(?)", uid)
        await run("INSERT OR REPLACE INTO admins(user_id, role) VALUES(?, 'super')", uid)


def backup_to(path):
    """Bazaning to'liq nusxasi (SQLite backup API)."""
    with _lock:
        conn = _conn or _connect()
        dst = sqlite3.connect(str(path))
        try:
            conn.backup(dst)
        finally:
            dst.close()
