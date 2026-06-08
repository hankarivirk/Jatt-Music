from pyrogram import filters, types
from jatt import app, db, jatt, lang, queue
from jatt.helpers import can_manage_vc

@app.on_message(filters.command(["skipto"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _skipto(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])
    if len(m.command) < 2:
        return await m.reply_text(m.lang["skipto_usage"])
    try:
        pos = int(m.command[1])
    except ValueError:
        return await m.reply_text(m.lang["skipto_usage"])

    media = queue.skipto(m.chat.id, pos)
    if not media:
        total = len(queue.get_queue(m.chat.id)) - 1
        return await m.reply_text(m.lang["skipto_invalid"].format(total))

    sent = await m.reply_text(m.lang["skipto_jumping"].format(pos, media.title or "?"))
    if not media.file_path:
        from jatt import yt
        media.file_path = await yt.download(media.id, video=media.video)
    media.message_id = sent.id
    await jatt.play_media(m.chat.id, sent, media)
