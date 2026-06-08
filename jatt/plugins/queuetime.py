from pyrogram import filters, types
from jatt import app, db, lang, queue
from jatt.helpers import utils

@app.on_message(filters.command(["queuetime", "qt"]) & filters.group & ~app.bl_users)
@lang.language()
async def _queuetime(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])
    items = queue.get_queue(m.chat.id)
    if not items:
        return await m.reply_text(m.lang["not_playing"])
    total = sum(getattr(i, "duration_sec", 0) or 0 for i in items)
    h, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    fmt = (f"{h}h " if h else "") + f"{mins}m {secs}s"
    await m.reply_text(m.lang["queuetime_text"].format(len(items) - 1, fmt))
