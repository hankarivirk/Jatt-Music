from pyrogram import filters, types
from jatt import app, db, jatt, lang
from jatt.helpers import can_manage_vc


@app.on_message(filters.command(["volume", "vol"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _volume(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    if len(m.command) < 2:
        vol = await db.get_volume(m.chat.id)
        return await m.reply_text(m.lang["volume_current"].format(vol))

    try:
        vol = int(m.command[1])
    except ValueError:
        return await m.reply_text(m.lang["volume_usage"])

    if not 1 <= vol <= 200:
        return await m.reply_text(m.lang["volume_range"])

    try:
        await jatt.set_volume(m.chat.id, vol)
    except Exception:
        return await m.reply_text(m.lang["volume_error"])

    await m.reply_text(m.lang["volume_set"].format(vol))
