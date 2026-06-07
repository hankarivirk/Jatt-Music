from pyrogram import filters, types
from jatt import app, db, lang, queue
from jatt.helpers import can_manage_vc


@app.on_message(filters.command(["shuffle"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _shuffle(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])
    count = queue.shuffle(m.chat.id)
    if count < 2:
        return await m.reply_text(m.lang["shuffle_empty"])
    await m.reply_text(m.lang["shuffle_done"].format(count))
