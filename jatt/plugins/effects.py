import asyncio
from pyrogram import filters, types
from jatt import app, db, jatt, lang, queue
from jatt.helpers import can_manage_vc

async def _apply_filter(m, filter_str, label):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])
    media = queue.get_current(m.chat.id)
    if not media or not media.file_path:
        return await m.reply_text(m.lang["not_playing"])
    jatt.set_filter(m.chat.id, filter_str)
    sent = await m.reply_text(m.lang["effect_applying"].format(label))
    media.message_id = sent.id
    await jatt.play_media(m.chat.id, sent, media, seek_time=max(0, (media.time or 1) - 1))

@app.on_message(filters.command(["speed"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _speed(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text(m.lang["speed_usage"])
    try:
        val = float(m.command[1])
        assert 0.5 <= val <= 2.0
    except Exception:
        return await m.reply_text(m.lang["speed_usage"])
    await _apply_filter(m, f"atempo={val}", f"Speed {val}x")

@app.on_message(filters.command(["bass"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _bass(_, m: types.Message):
    lvl = int(m.command[1]) if len(m.command) > 1 and m.command[1].isdigit() else 5
    lvl = max(1, min(10, lvl))
    await _apply_filter(m, f"bass=g={lvl}", f"Bass +{lvl}")

@app.on_message(filters.command(["nightcore"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _nightcore(_, m: types.Message):
    await _apply_filter(m, "asetrate=55125,aresample=44100,atempo=1.0", "Nightcore")

@app.on_message(filters.command(["mono"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _mono(_, m: types.Message):
    await _apply_filter(m, "pan=mono|c0=0.5*c0+0.5*c1", "Mono")

@app.on_message(filters.command(["3d"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _3d(_, m: types.Message):
    await _apply_filter(m, "apulsator=hz=0.08", "3D Audio")

@app.on_message(filters.command(["reverb"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _reverb(_, m: types.Message):
    await _apply_filter(m, "aecho=0.8:0.9:500:0.3", "Reverb")

@app.on_message(filters.command(["cleareffects", "ce", "normalise"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _clearfx(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])
    jatt.clear_filter(m.chat.id)
    media = queue.get_current(m.chat.id)
    if not media or not media.file_path:
        return await m.reply_text(m.lang["effect_cleared"])
    sent = await m.reply_text(m.lang["effect_cleared"])
    media.message_id = sent.id
    await jatt.play_media(m.chat.id, sent, media, seek_time=max(0, (media.time or 1) - 1))
