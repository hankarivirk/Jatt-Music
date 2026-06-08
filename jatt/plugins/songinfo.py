from pyrogram import filters, types
from jatt import app, db, lang, queue

@app.on_message(filters.command(["songinfo", "si", "track"]) & filters.group & ~app.bl_users)
@lang.language()
async def _songinfo(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])
    media = queue.get_current(m.chat.id)
    if not media:
        return await m.reply_text(m.lang["not_playing"])

    url   = getattr(media, "url", "") or ""
    ch    = getattr(media, "channel_name", "") or ""
    views = getattr(media, "view_count", "") or ""
    title = media.title or "Unknown"
    t_link = f'<a href="{url}">{title}</a>' if url else f"<b>{title}</b>"

    text = m.lang["songinfo_text"].format(
        t_link, ch or "—", views or "—",
        media.duration, media.user or "—",
        "Video" if media.video else "Audio",
        url or "—",
    )
    await m.reply_text(text, disable_web_page_preview=True)
