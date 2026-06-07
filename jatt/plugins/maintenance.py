from pyrogram import filters, StopPropagation, types
from jatt import app, db, lang


@app.on_message(filters.command(["maintenance"]) & app.sudoers)
@lang.language()
async def _maintenance(_, m: types.Message):
    current = await db.get_maintenance()
    await db.set_maintenance(not current)
    status = "ON" if not current else "OFF"
    await m.reply_text(m.lang["maintenance_set"].format(status))


@app.on_message(filters.group & filters.text, group=-3)
async def _maintenance_gate(_, m: types.Message):
    if not m.text or not m.command:
        return
    if not await db.get_maintenance():
        return
    if m.from_user and m.from_user.id in app.sudoers:
        return
    try:
        await m.reply_text("▲  Bot is under maintenance. Please wait.")
    except Exception:
        pass
    raise StopPropagation
