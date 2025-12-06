#!/usr/bin/env python3
"""
Manager + Worker single-file (Python 3.9 compatible)
Combined version — build_manager_app is defined before start_all.
"""

import asyncio
import json
import os
import time
import logging
from typing import Dict, List, Optional, Set

from telegram import Update, Bot as TgBot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)

# ---------------------------
# CONFIG – EDIT LOCALLY
# ---------------------------
MANAGER_TOKEN = "8516170208:AAGgAZ33jrmxkRaDxKmE6A64wVKphC30qp4"   # <-- Replace locally
OWNER_ID = 6940098775                       # owner id

# Persistence files
USERS_FILE = "users.json"     # user_id -> [API tokens]
TOKENS_FILE = "tokens.json"   # flat list of all tokens
INVITE_FILE = "invites.json"  # users allowed to /addapi

# ---------------------------
# Persistence helpers
# ---------------------------
def load_json(name, default):
    if os.path.exists(name):
        try:
            with open(name, "r") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(name, data):
    with open(name, "w") as f:
        json.dump(data, f)

USERS: Dict[str, List[str]] = load_json(USERS_FILE, {})
TOKENS: List[str] = load_json(TOKENS_FILE, [])
INVITED: Set[int] = set(int(x) for x in load_json(INVITE_FILE, [OWNER_ID]))

def save_all():
    save_json(USERS_FILE, USERS)
    save_json(TOKENS_FILE, TOKENS)
    save_json(INVITE_FILE, list(INVITED))

# ---------------------------
# Runtime state
# ---------------------------
manager_app: Optional[Application] = None
worker_apps: List[Application] = []
worker_bots: List[TgBot] = []
awaiting_token_users: Set[int] = set()

# ---------------------------
# Worker helpers & builders (ensure defined before manager uses them)
# ---------------------------

RAID_TEXTS = [
    "Try ben ci भोसड़ी beta 😝",
    "😂😂😂😂 Try ma randy 😂😂😂😂",
    "Teri mom ko i love u ree 😆💔🖕🏽",
    "Tmkc pe chppl hi chppl marunga !! 🔥😂🩴",
    "😉😈🔥 هههههههههههههه Teri maa रंडी",
    "𝐂ʜʟ 𝐇ᴀʀᴍᴢᴀ𝐝𝐈 𝐊ᴇ लड़के 💛🤍🩵",
    "hlw hlw mja aarha cudne me? 🤔",
    "bina ruke thukai hogi teri 😶",
    "kr na fyt 💪",
    "sort nhi krunga cud tu bina ruke 😎",
    "काले Doraemon रोता reh 😭",
    "teri bkc me bigboss 👑",
    "Awaz neeche rndy k bacche 🔊",
    "Sawal mt puch tery ma k bosda baap mhu ⚠️",
    "TMKC LADLE 🤙 "
]

NCEMO_EMOJIS = [
    "😋","😝","😜","🤪","😑","🤫","🤭","🥱","🤗","😡","😠","😤",
    "😮‍💨","🙄","😒","🥶","🥵","🤢","😎","🥸",
    "😹","💫","😼","😽","🙀","😿","😾",
    "🙈","🙉","🙊",
    "⭐","🌟","✨","⚡","💥","💨",
    "💛","💙","💜","🤎","🤍","💘","💝",
    "🧡","❤️","💚","🩵","🩶","🖤","💕","💓","💗","💖",
    "💟","💞","💯","🔥","🌈","🌙","☀️","🌤️","⛅","🌥️",
    "🌧️","🌦️","🌩️","❄️","☃️","🌊","🍀","🍃","🌸","🌺",
    "🌼","🌻","🌹","🍁","🍂","🌵","🌴","🌳","🌲","🌱",
    "🐶","🐱","🐰","🐻","🐼","🐯","🐸","🐵","🦊","🐮",
    "🐷","🐔","🐣"
]

def sudo_filename(token: str) -> str:
    return f"sudo_{token[:12].replace(':','_')}.json"

def load_sudo(token: str, owner_id: int):
    fn = sudo_filename(token)
    if os.path.exists(fn):
        try:
            with open(fn, "r") as f:
                arr = json.load(f)
                return set(int(x) for x in arr)
        except Exception:
            return {owner_id}
    else:
        s = {owner_id}
        try:
            with open(fn, "w") as f:
                json.dump(list(s), f)
        except Exception:
            pass
        return s

def save_sudo(token: str, sudo_set):
    fn = sudo_filename(token)
    try:
        with open(fn, "w") as f:
            json.dump(list(sudo_set), f)
    except Exception as e:
        logging.warning("Failed saving sudo file %s: %s", fn, e)

def build_worker_app(token: str, owner_id: int) -> Application:
    app = Application.builder().token(token).build()

    SUDO_USERS = load_sudo(token, owner_id)
    group_tasks = {}
    slide_targets = set()
    slidespam_targets = set()
    swipe_mode = {}
    delay = 1.0

    def only_sudo(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_user is None:
                return
            uid = update.effective_user.id
            if uid not in SUDO_USERS:
                return await update.message.reply_text("❌ You are not a sudo for this bot.")
            return await func(update, context)
        return wrapper

    def only_owner(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_user is None:
                return
            uid = update.effective_user.id
            if uid != owner_id:
                return await update.message.reply_text("⛔ Owner-only command.")
            return await func(update, context)
        return wrapper

    async def bot_loop(bot, chat_id, base, mode):
        i = 0
        while True:
            try:
                if mode == "raid":
                    text = f"{base} {RAID_TEXTS[i % len(RAID_TEXTS)]}"
                else:
                    text = f"{base} {NCEMO_EMOJIS[i % len(NCEMO_EMOJIS)]}"
                await bot.set_chat_title(chat_id, text)
                i += 1
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                logging.info("Loop cancelled for chat %s", chat_id)
                break
            except Exception as e:
                logging.warning("Worker loop error in %s: %s", chat_id, e)
                await asyncio.sleep(2)

    async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🤖 Worker ready — use /help to see commands. ✨")

    async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🧭 *Worker Commands* 🧭\n\n"
            "/gcnc <text> — Start GC name raid loop 🔁\n"
            "/ncemo <text> — Start emoji loop 😜\n"
            "/stopgcnc — Stop loops in this chat ⏹️\n"
            "/stopall — Stop all loops for this worker ⛔\n"
            "/delay <sec> — Set loop delay ⏱️\n"
            "/status — Show active loops 📊\n\n"
            "/targetslide (reply) — Add user as slide target 🎯\n"
            "/stopslide (reply) — Stop slide target 🛑\n"
            "/slidespam (reply) — Start slide spam 💥\n"
            "/stopslidespam (reply) — Stop slide spam 🧯\n\n"
            "/swipe <name> — Enable swipe mode ⚡\n"
            "/stopswipe — Disable swipe mode 🛑\n\n"
            "/addsudo (reply) — Add sudo (owner only) 👑\n"
            "/delsudo (reply) — Remove sudo 🗑️\n"
            "/listsudo — List sudo users 👥\n\n"
            "/myid — Show your id 🆔\n"
            "/ping — Latency check 🏓",
            parse_mode="Markdown"
        )

    async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        start_time = time.time()
        msg = await update.message.reply_text("🏓 Pinging...")
        end_time = time.time()
        latency = int((end_time - start_time) * 1000)
        await msg.edit_text(f"🏓 Pong! {latency} ms ✅")

    async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f"🆔 Your ID: {update.effective_user.id}")

    @only_sudo
    async def gcnc(update: Update, context: ContextTypes.DEFAULT_TYPE):
        nonlocal group_tasks
        if not context.args:
            return await update.message.reply_text("⚠️ Usage: /gcnc <text>")
        base = " ".join(context.args)
        chat_id = update.message.chat_id
        group_tasks.setdefault(chat_id, {})
        bot = update.app.bot
        if bot.id not in group_tasks[chat_id]:
            task = asyncio.create_task(bot_loop(bot, chat_id, base, "raid"))
            group_tasks[chat_id][bot.id] = task
            await update.message.reply_text("🔄 GC name loop started with raid texts. 🔥")
        else:
            await update.message.reply_text("ℹ️ Loop already running in this chat for this bot.")

    @only_sudo
    async def ncemo(update: Update, context: ContextTypes.DEFAULT_TYPE):
        nonlocal group_tasks
        if not context.args:
            return await update.message.reply_text("⚠️ Usage: /ncemo <text>")
        base = " ".join(context.args)
        chat_id = update.message.chat_id
        group_tasks.setdefault(chat_id, {})
        bot = update.app.bot
        if bot.id not in group_tasks[chat_id]:
            task = asyncio.create_task(bot_loop(bot, chat_id, base, "emoji"))
            group_tasks[chat_id][bot.id] = task
            await update.message.reply_text("🔄 Emoji loop started — enjoy the vibes! 🌈")
        else:
            await update.message.reply_text("ℹ️ Loop already running in this chat for this bot.")

    @only_sudo
    async def stopgcnc(update: Update, context: ContextTypes.DEFAULT_TYPE):
        nonlocal group_tasks
        chat_id = update.message.chat_id
        if chat_id in group_tasks and group_tasks[chat_id]:
            for task in list(group_tasks[chat_id].values()):
                task.cancel()
            group_tasks[chat_id] = {}
            await update.message.reply_text("⏹️ Loop(s) stopped in this chat.")
        else:
            await update.message.reply_text("ℹ️ No active loops in this chat.")

    @only_sudo
    async def stopall(update: Update, context: ContextTypes.DEFAULT_TYPE):
        nonlocal group_tasks
        stopped = 0
        for cid in list(group_tasks.keys()):
            for task in list(group_tasks[cid].values()):
                task.cancel()
                stopped += 1
            group_tasks[cid] = {}
        await update.message.reply_text(f"⏹️ All loops stopped (worker). Stopped: {stopped}")

    @only_sudo
    async def delay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        nonlocal delay
        if not context.args:
            return await update.message.reply_text(f"⏱ Current delay: {delay}s")
        try:
            delay = max(0.1, float(context.args[0]))
            await update.message.reply_text(f"✅ Delay set to {delay}s")
        except Exception:
            await update.message.reply_text("⚠️ Invalid number. Provide seconds like `1.5`")

    @only_sudo
    async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = "📊 *Active Loops (this worker)*\n"
        for chat_id, tasks in group_tasks.items():
            msg += f"• Chat `{chat_id}`: {len(tasks)} bots running\n"
        if not group_tasks:
            msg += "No active loops."
        await update.message.reply_text(msg, parse_mode="Markdown")

    @only_owner
    async def addsudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.reply_to_message:
            uid = update.message.reply_to_message.from_user.id
            SUDO_USERS.add(uid)
            save_sudo(token, SUDO_USERS)
            await update.message.reply_text(f"✅ {uid} added as sudo. 👑")
        else:
            await update.message.reply_text("Reply to a user with /addsudo ➕")

    @only_owner
    async def delsudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.reply_to_message:
            uid = update.message.reply_to_message.from_user.id
            if uid in SUDO_USERS:
                SUDO_USERS.discard(uid)
                save_sudo(token, SUDO_USERS)
                await update.message.reply_text(f"🗑️ {uid} removed from sudo.")
            else:
                await update.message.reply_text("ℹ️ That user wasn't a sudo.")
        else:
            await update.message.reply_text("Reply to a user with /delsudo 🗑️")

    @only_sudo
    async def listsudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("👥 *SUDO USERS:*\n" + "\n".join(map(str, SUDO_USERS)), parse_mode="Markdown")

    @only_sudo
    async def targetslide(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.reply_to_message:
            slide_targets.add(update.message.reply_to_message.from_user.id)
            await update.message.reply_text("🎯 Target slide added.")
        else:
            await update.message.reply_text("Reply to a message with /targetslide ➡️")

    @only_sudo
    async def stopslide(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.reply_to_message:
            uid = update.message.reply_to_message.from_user.id
            slide_targets.discard(uid)
            await update.message.reply_text("🛑 Target slide stopped.")
        else:
            await update.message.reply_text("Reply to a message with /stopslide ➡️")

    @only_sudo
    async def slidespam(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.reply_to_message:
            slidespam_targets.add(update.message.reply_to_message.from_user.id)
            await update.message.reply_text("💥 Slide spam target added.")
        else:
            await update.message.reply_text("Reply to a message with /slidespam ➡️")

    @only_sudo
    async def stopslidespam(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.reply_to_message:
            slidespam_targets.discard(update.message.reply_to_message.from_user.id)
            await update.message.reply_text("🛑 Slide spam stopped.")
        else:
            await update.message.reply_text("Reply to a message with /stopslidespam ➡️")

    @only_sudo
    async def swipe(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            return await update.message.reply_text("⚠️ Usage: /swipe <name>")
        swipe_mode[update.message.chat_id] = " ".join(context.args)
        await update.message.reply_text(f"⚡ Swipe mode ON — prefix: `{swipe_mode[update.message.chat_id]}`", parse_mode="Markdown")

    @only_sudo
    async def stopswipe(update: Update, context: ContextTypes.DEFAULT_TYPE):
        swipe_mode.pop(update.message.chat_id, None)
        await update.message.reply_text("🛑 Swipe mode stopped.")

    async def auto_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            uid = update.message.from_user.id
            chat_id = update.message.chat_id
        except Exception:
            return
        if uid in slide_targets:
            for text in RAID_TEXTS[:5]:
                await update.message.reply_text(text)
        if uid in slidespam_targets:
            for text in RAID_TEXTS:
                await update.message.reply_text(text)
        if chat_id in swipe_mode:
            for text in RAID_TEXTS[:3]:
                await update.message.reply_text(f"{swipe_mode[chat_id]} {text}")

    # register handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ping", ping_cmd))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("gcnc", gcnc))
    app.add_handler(CommandHandler("ncemo", ncemo))
    app.add_handler(CommandHandler("stopgcnc", stopgcnc))
    app.add_handler(CommandHandler("stopall", stopall))
    app.add_handler(CommandHandler("delay", delay_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("addsudo", addsudo))
    app.add_handler(CommandHandler("delsudo", delsudo))
    app.add_handler(CommandHandler("listsudo", listsudo))
    app.add_handler(CommandHandler("targetslide", targetslide))
    app.add_handler(CommandHandler("stopslide", stopslide))
    app.add_handler(CommandHandler("slidespam", slidespam))
    app.add_handler(CommandHandler("stopslidespam", stopslidespam))
    app.add_handler(CommandHandler("swipe", swipe))
    app.add_handler(CommandHandler("stopswipe", stopswipe))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_replies))

    return app

# ---------------------------
# Manager builders & handlers
# ---------------------------

def only_owner(func):
    async def wrapper(update, context):
        if update.effective_user.id != OWNER_ID:
            return await update.message.reply_text("❌ Only the owner can use this command.")
        return await func(update, context)
    return wrapper

def invited_only(func):
    async def wrapper(update, context):
        uid = update.effective_user.id
        if uid != OWNER_ID and uid not in INVITED:
            return await update.message.reply_text("⛔ You are not allowed to add APIs. Ask the owner.")
        return await func(update, context)
    return wrapper

async def m_start(update, context):
    await update.message.reply_text("🟢 Manager active — ready to manage worker bots. Use /help ❓")

async def m_help(update, context):
    await update.message.reply_text(
        "🛠️ *Manager Commands* 🛠️\n\n"
        "/adduser (reply/id) — Owner only 👑\n"
        "/deluser (reply/id) — Owner only 🗑️\n"
        "/listusers — Owner only 📋\n"
        "/addapi — Allowed users add bot token 🔑\n"
        "/stat — Owner only 📊\n\n"
        "How to add a token: /addapi → send token as plain message (123456:ABC...) 🔐",
        parse_mode="Markdown"
    )

@only_owner
async def m_adduser(update, context):
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user.id
    elif context.args:
        try:
            target = int(context.args[0])
        except Exception:
            return await update.message.reply_text("⚠️ Invalid id.")
    else:
        return await update.message.reply_text("Reply to a user or use `/adduser <id>` ✍️")
    INVITED.add(target)
    USERS.setdefault(str(target), [])
    save_all()
    await update.message.reply_text(f"✅ User {target} can now add APIs. 🎉")

@only_owner
async def m_deluser(update, context):
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user.id
    elif context.args:
        try:
            target = int(context.args[0])
        except Exception:
            return await update.message.reply_text("⚠️ Invalid id.")
    else:
        return await update.message.reply_text("Reply to a user or use `/deluser <id>` ✍️")
    INVITED.discard(target)
    USERS.pop(str(target), None)
    save_all()
    await update.message.reply_text(f"🗑️ User {target} removed.")

@only_owner
async def m_listusers(update, context):
    if not USERS:
        return await update.message.reply_text("Nobody added yet. ➖")
    out = "👥 *Users and API counts:*\n"
    for uid_str, toks in USERS.items():
        out += f"• `{uid_str}` — {len(toks)} APIs\n"
    await update.message.reply_text(out, parse_mode="Markdown")

@invited_only
async def m_addapi(update, context):
    uid = update.effective_user.id
    awaiting_token_users.add(uid)
    await update.message.reply_text("🔐 Send your bot token now (format: `123456:ABC...`) — I'll validate it.", parse_mode="Markdown")

@only_owner
async def m_stat(update, context):
    total_users = len(USERS)
    total_tokens = sum(len(v) for v in USERS.values())
    out = f"📊 *Manager Stats*\n\nUsers: {total_users}\nAPIs: {total_tokens}\n\n"
    for uid_str, toks in USERS.items():
        out += f"• `{uid_str}`: {len(toks)} APIs\n"
    await update.message.reply_text(out, parse_mode="Markdown")

async def m_handle_token(update, context):
    uid = update.effective_user.id
    if uid not in awaiting_token_users:
        return
    awaiting_token_users.discard(uid)

    token = update.message.text.strip()
    if ":" not in token:
        return await update.message.reply_text("❌ Invalid token format. Make sure it looks like `123456:ABC...`", parse_mode="Markdown")

    try:
        bot = TgBot(token)
        me = await bot.get_me()
    except Exception as e:
        return await update.message.reply_text(f"❌ Token invalid: {e}")

    USERS.setdefault(str(uid), []).append(token)
    TOKENS.append(token)
    save_all()

    try:
        app = build_worker_app(token, owner_id=uid)
        worker_apps.append(app)
        asyncio.create_task(run_worker_app(app))
        try:
            worker_bots.append(app.bot)
        except Exception:
            pass
        await update.message.reply_text(f"✅ Worker started as @{me.username} — good to go! 🚀")
    except Exception as e:
        USERS[str(uid)].remove(token)
        TOKENS.remove(token)
        save_all()
        return await update.message.reply_text(f"❌ Failed to start worker: {e}")

def build_manager_app(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", m_start))
    app.add_handler(CommandHandler("help", m_help))
    app.add_handler(CommandHandler("adduser", m_adduser))
    app.add_handler(CommandHandler("deluser", m_deluser))
    app.add_handler(CommandHandler("listusers", m_listusers))
    app.add_handler(CommandHandler("addapi", m_addapi))
    app.add_handler(CommandHandler("stat", m_stat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, m_handle_token), 1)
    return app

# ---------------------------
# Worker run helper & startup
# ---------------------------

async def run_worker_app(app: Application):
    try:
        await app.initialize()
        await app.start()
        try:
            await app.updater.start_polling()
        except Exception:
            pass
        logging.info("Worker started: %s", getattr(app.bot, "username", "unknown"))
    except Exception as e:
        logging.exception("Failed to start worker: %s", e)

async def start_all():
    global manager_app
    manager_app = build_manager_app(MANAGER_TOKEN)

    for token in TOKENS:
        try:
            app = build_worker_app(token, owner_id=OWNER_ID)
            worker_apps.append(app)
            asyncio.create_task(run_worker_app(app))
        except Exception as e:
            logging.exception("Failed to create worker for saved token: %s", e)

    try:
        manager_app.run_polling()
    except Exception:
        try:
            await manager_app.initialize()
            await manager_app.start()
            try:
                await manager_app.updater.start_polling()
            except Exception:
                pass
            await asyncio.Event().wait()
        except Exception as e:
            logging.exception("Failed to start manager app: %s", e)

if __name__ == "__main__":
    try:
        asyncio.run(start_all())
    except KeyboardInterrupt:
        logging.info("Shutting down...")