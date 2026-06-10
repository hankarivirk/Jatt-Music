from pyrogram import filters, types
from jatt import app, db, jatt, lang, queue, yt


@app.on_message(filters.command(["prev", "previous", "back"]) & filters.group & ~app.bl_users)
@lang.language()
async def _previous(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])
    media = queue.get_previous(m.chat.id)
    if not media:
        return await m.reply_text(m.lang["prev_empty"])
    sent = await m.reply_text(m.lang["prev_loading"].format(media.title or "?"))
    media.message_id = sent.id
    if not media.file_path:
        media.file_path = await yt.download(media.id, video=media.video)
    if not media.file_path:
        return await sent.edit_text(m.lang["error_no_file"].format(""))
    await jatt.play_media(m.chat.id, sent, media)
