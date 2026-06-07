from pyrogram import filters, types
from jatt import app, db, lang


@app.on_message(filters.command(["top"]) & filters.group & ~app.bl_users)
@lang.language()
async def _top(_, m: types.Message):
    sent = await m.reply_text(m.lang["processing"])
    tracks = await db.get_top_tracks(m.chat.id, limit=10)
    if not tracks:
        return await sent.edit_text(m.lang["top_empty"])

    text = m.lang["top_title"].format(m.chat.title or "this chat")
    for i, item in enumerate(tracks, start=1):
        title = (item.get("title") or "Unknown")[:42]
        url   = item.get("url", "")
        count = item.get("count", 1)
        t = f'<a href="{url}">{title}</a>' if url else title
        text += f"  <b>{i}.</b>  {t}  —  {count}x\n\n"

    await sent.edit_text(text, disable_web_page_preview=True)
