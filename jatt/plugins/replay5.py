from pyrogram import filters, types
from jatt import app, db, jatt, lang, queue

@app.on_message(filters.command(["replay5", "rewind"]) & filters.group & ~app.bl_users)
@lang.language()
async def _replay5(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])
    media = queue.get_current(m.chat.id)
    if not media:
        return await m.reply_text(m.lang["not_playing"])
    seek = max(0, (media.time or 0) - 5)
    sent = await m.reply_text(m.lang["play_seeking"])
    media.message_id = sent.id
    await jatt.play_media(m.chat.id, sent, media, seek_time=seek)
