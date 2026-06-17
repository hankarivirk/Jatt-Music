from pyrogram import filters, types

from jatt import app, db, lang
from jatt.helpers._admins import is_admin


@app.on_message(filters.command(["history", "recent"]) & filters.group & ~app.bl_users)
@lang.language()
async def _history(_, m: types.Message):
    sent = await m.reply_text(m.lang["processing"])
    tracks = await db.get_history(m.chat.id)
    if not tracks:
        return await sent.edit_text(m.lang["history_empty"])

    text = m.lang["history_title"].format(m.chat.title or "this chat")
    for i, item in enumerate(tracks, start=1):
        title = item.get("title", "Unknown")[:45]
        url   = item.get("url", "")
        dur   = item.get("duration", "--:--")
        user  = item.get("user", "Unknown")
        title_text = f'<a href="{url}">{title}</a>' if url else title
        text += f"<b>{i}.</b> {title_text}\n     ⏱ {dur}  ·  👤 {user}\n\n"

    await sent.edit_text(text, disable_web_page_preview=True)


@app.on_message(filters.command(["clearhistory", "clrhistory"]) & filters.group & ~app.bl_users)
@lang.language()
async def _clearhistory(_, m: types.Message):
    if not await is_admin(m.chat.id, m.from_user.id) and m.from_user.id not in app.sudoers:
        return await m.reply_text(m.lang["user_not_admin"])
    await db.clear_history(m.chat.id)
    await m.reply_text("🗑  <b>Play history cleared</b>  for this chat.")
