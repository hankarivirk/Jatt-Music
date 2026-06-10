from pyrogram import filters, types
from jatt import app, db, lang
from jatt.helpers import admin_check

@app.on_message(filters.command(["mystats"]) & filters.group & ~app.bl_users)
@lang.language()
async def _mystats(_, m: types.Message):
    count = await db.get_user_plays(m.chat.id, m.from_user.id)
    top   = await db.get_top_tracks(m.chat.id, limit=1)
    fav   = top[0].get("title","—")[:35] if top else "—"
    await m.reply_text(m.lang["mystats_text"].format(m.from_user.first_name, count, fav))

@app.on_message(filters.command(["userstats"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def _userstats(_, m: types.Message):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await m.reply_text(m.lang["user_not_found"])
    u     = m.reply_to_message.from_user
    count = await db.get_user_plays(m.chat.id, u.id)
    await m.reply_text(m.lang["userstats_text"].format(u.first_name, count))

@app.on_message(filters.command(["chatstats"]) & filters.group & ~app.bl_users)
@lang.language()
async def _chatstats(_, m: types.Message):
    sent = await m.reply_text(m.lang["processing"])
    top  = await db.get_chat_top_requesters(m.chat.id, limit=5)
    all_stats = await db.get_chat_play_count(m.chat.id)
    text = m.lang["chatstats_title"].format(m.chat.title or "Group")
    for i, r in enumerate(top, 1):
        uid   = r.get("user_id", 0)
        count = r.get("count", 0)
        try:
            u    = await app.get_users(uid)
            name = u.first_name[:20]
        except Exception:
            name = str(uid)
        text += f"  <b>{i}.</b>  {name}  —  {count} tracks\n"
    text += m.lang["chatstats_total"].format(all_stats)
    await sent.edit_text(text)

@app.on_message(filters.command(["botstats"]) & app.sudoers)
@lang.language()
async def _botstats(_, m: types.Message):
    sent  = await m.reply_text(m.lang["processing"])
    total = await db.get_global_play_count()
    chats = len(await db.get_chats())
    users = len(await db.get_users())
    await sent.edit_text(m.lang["botstats_text"].format(total, chats, users))
