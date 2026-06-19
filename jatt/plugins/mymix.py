from pyrogram import filters, types
from jatt import app, config, db, jatt, lang, queue, yt
from jatt.helpers import buttons
from jatt.helpers._play import checkUB


@app.on_message(filters.command(["mymix", "mix"]) & filters.group & ~app.bl_users)
@lang.language()
@checkUB
async def _mymix(_, m: types.Message):
    sent    = await m.reply_text(m.lang["play_searching"])
    mention = m.from_user.mention

    seed_id  = None
    seed_url = None
    current  = queue.get_current(m.chat.id)

    if current and getattr(current, "id", None) and yt.is_youtube_id(current.id):
        seed_id  = current.id
        seed_url = current.url or f"https://www.youtube.com/watch?v={seed_id}"
    elif len(m.command) >= 2:
        query = " ".join(m.command[1:])
        track = await yt.search(query, sent.id)
        if track and yt.is_youtube_id(track.id):
            seed_id  = track.id
            seed_url = track.url or f"https://www.youtube.com/watch?v={seed_id}"

    if not seed_id:
        return await sent.edit_text(m.lang["mymix_no_seed"])

    await sent.edit_text(m.lang["mymix_loading"])

    if await db.is_local_banned(m.chat.id, m.from_user.id):
        return await sent.edit_text(m.lang["localban_blocked"])

    tracks = await yt.mix(seed_id, mention, False, limit=config.PLAYLIST_LIMIT)

    if not tracks:
        return await sent.edit_text(m.lang["mymix_failed"])

    file        = tracks[0]
    file.message_id = sent.id
    rest        = tracks[1:]

    pos = queue.add(m.chat.id, file)
    if pos != 0 or await db.get_call(m.chat.id):
        for t in rest:
            queue.add(m.chat.id, t)
        return await sent.edit_text(
            m.lang["mymix_queued"].format(len(tracks), file.title),
            reply_markup=buttons.play_queued(m.chat.id, file.id, m.lang["play_now"]),
        )

    for t in rest:
        queue.add(m.chat.id, t)

    if not file.file_path:
        file.file_path = await yt.download(file.id, video=False)
    if not file.file_path:
        return await sent.edit_text(m.lang["error_no_file"].format(config.SUPPORT_CHAT))

    await jatt.play_media(m.chat.id, sent, file)
