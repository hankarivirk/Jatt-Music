from py_yt import VideosSearch
from pyrogram import filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from jatt import app, db, jatt, lang, queue
from jatt.helpers._play import checkUB

_results: dict[int, list] = {}

@app.on_message(filters.command(["search"]) & filters.group & ~app.bl_users)
@lang.language()
@checkUB
async def _search(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text(m.lang["search_usage"])
    query = " ".join(m.command[1:])
    sent  = await m.reply_text(m.lang["play_searching"])
    try:
        s = VideosSearch(query, limit=5)
        data = (await s.next()).get("result", [])
    except Exception:
        return await sent.edit_text(m.lang["play_not_found"].format(""))
    if not data:
        return await sent.edit_text(m.lang["search_empty"])

    _results[m.from_user.id] = [
        {"id": r["id"], "title": r.get("title","?")[:45],
         "duration": r.get("duration","?")}
        for r in data[:5]
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{i+1}.  {r['title']}  ({r['duration']})",
            callback_data=f"search {m.from_user.id} {i}"
        )] for i, r in enumerate(_results[m.from_user.id])
    ] + [[InlineKeyboardButton("✗  Cancel", callback_data="search_cancel")]])
    await sent.edit_text(m.lang["search_results"], reply_markup=kb)

@app.on_callback_query(filters.regex(r"^search"))
@lang.language()
async def _search_cb(_, q: types.CallbackQuery):
    data = q.data.split()
    if data[0] == "search_cancel":
        return await q.message.delete()
    uid, idx = int(data[1]), int(data[2])
    if q.from_user.id != uid:
        return await q.answer("Not your search.", show_alert=True)
    items = _results.pop(uid, [])
    if not items or idx >= len(items):
        return await q.message.delete()

    item = items[idx]
    from jatt import yt
    from jatt.helpers import Track, utils
    track = await yt.search(item["id"], q.message.id)
    if not track:
        return await q.message.edit_text(q.lang["play_not_found"].format(""))

    track.user = q.from_user.mention
    pos = queue.add(q.message.chat.id, track)
    _lang = await lang.get_lang(q.message.chat.id)

    if pos != 0 or await db.get_call(q.message.chat.id):
        await q.message.edit_text(_lang["play_queued"].format(
            pos, track.url, track.title, track.duration, track.user))
        return

    track.file_path = await yt.download(track.id, video=track.video)
    await jatt.play_media(q.message.chat.id, q.message, track)
