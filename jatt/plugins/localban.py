from pyrogram import filters, types
from jatt import app, db, lang
from jatt.helpers import admin_check

@app.on_message(filters.command(["localban"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def _localban(_, m: types.Message):
    user = None
    if m.reply_to_message and m.reply_to_message.from_user:
        user = m.reply_to_message.from_user
    elif len(m.command) >= 2:
        try:
            user = await app.get_users(int(m.command[1]))
        except Exception:
            return await m.reply_text(m.lang["user_not_found"])
    if not user:
        return await m.reply_text(m.lang["user_not_found"])
    await db.local_ban(m.chat.id, user.id)
    await m.reply_text(m.lang["localban_done"].format(user.mention))

@app.on_message(filters.command(["localunban"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def _localunban(_, m: types.Message):
    user = None
    if m.reply_to_message and m.reply_to_message.from_user:
        user = m.reply_to_message.from_user
    elif len(m.command) >= 2:
        try:
            user = await app.get_users(int(m.command[1]))
        except Exception:
            return await m.reply_text(m.lang["user_not_found"])
    if not user:
        return await m.reply_text(m.lang["user_not_found"])
    await db.local_unban(m.chat.id, user.id)
    await m.reply_text(m.lang["localunban_done"].format(user.mention))

@app.on_message(filters.command(["localbans"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def _localbans(_, m: types.Message):
    bans = await db.get_local_bans(m.chat.id)
    if not bans:
        return await m.reply_text(m.lang["localbans_empty"])
    text = m.lang["localbans_title"]
    for uid in bans:
        try:
            u = await app.get_users(uid)
            text += f"  ◈  {u.mention}  —  <code>{uid}</code>\n"
        except Exception:
            text += f"  ◈  <code>{uid}</code>\n"
    await m.reply_text(text)
