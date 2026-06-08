from pyrogram import filters, types
from jatt import app, db, lang
from jatt.helpers import admin_check

@app.on_message(filters.command(["setlimit"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def _setlimit(_, m: types.Message):
    if len(m.command) < 2:
        cur = await db.get_setlimit(m.chat.id)
        return await m.reply_text(m.lang["setlimit_current"].format(cur or "None"))
    try:
        mins = int(m.command[1])
        assert 0 < mins <= 360
    except Exception:
        return await m.reply_text(m.lang["setlimit_usage"])
    await db.set_chat_limit(m.chat.id, mins)
    await m.reply_text(m.lang["setlimit_done"].format(mins))

@app.on_message(filters.command(["setqueue"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def _setqueue(_, m: types.Message):
    if len(m.command) < 2:
        cur = await db.get_queue_max(m.chat.id)
        return await m.reply_text(m.lang["setqueue_current"].format(cur))
    try:
        n = int(m.command[1])
        assert 1 <= n <= 100
    except Exception:
        return await m.reply_text(m.lang["setqueue_usage"])
    await db.set_queue_max(m.chat.id, n)
    await m.reply_text(m.lang["setqueue_done"].format(n))

@app.on_message(filters.command(["queuelock"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def _queuelock(_, m: types.Message):
    cur = await db.get_queuelock(m.chat.id)
    await db.set_queuelock(m.chat.id, not cur)
    key = "queuelock_on" if not cur else "queuelock_off"
    await m.reply_text(m.lang[key])

@app.on_message(filters.command(["autoplay"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def _autoplay(_, m: types.Message):
    cur = await db.get_autoplay(m.chat.id)
    await db.set_autoplay(m.chat.id, not cur)
    key = "autoplay_on" if not cur else "autoplay_off"
    await m.reply_text(m.lang[key])
