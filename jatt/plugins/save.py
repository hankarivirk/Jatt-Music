from pyrogram import filters, types
from jatt import app, db, lang, queue


@app.on_message(filters.command(["save"]) & filters.group & ~app.bl_users)
@lang.language()
async def _save(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    media = queue.get_current(m.chat.id)
    if not media:
        return await m.reply_text(m.lang["not_playing"])

    title = media.title or "Unknown"
    url   = media.url or ""
    t     = f'<a href="{url}">{title}</a>' if url else f"<b>{title}</b>"

    text = m.lang["save_text"].format(
        t,
        media.duration,
        m.chat.title or "Group",
    )
    try:
        await app.send_message(m.from_user.id, text)
        await m.reply_text(m.lang["save_done"])
    except Exception:
        await m.reply_text(m.lang["save_error"])
