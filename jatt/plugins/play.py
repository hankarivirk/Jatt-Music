import asyncio
from pathlib import Path

from pyrogram import filters, types

from jatt import jatt, app, config, db, lang, queue, tg, yt
from jatt.helpers import buttons, utils
from jatt.helpers._admins import is_admin
from jatt.helpers._play import checkUB


def _add_to_queue(chat_id: int, tracks: list) -> str:
    text = "<blockquote expandable>"
    for track in tracks:
        pos = queue.add(chat_id, track)
        if pos > 0:
            text += f"<b>{pos}.</b> {track.title}\n"
    return text[:1948] + "</blockquote>"


async def _bg_load(chat_id: int, tracks: list) -> None:
    for track in tracks:
        queue.add(chat_id, track)
        await asyncio.sleep(0.1)


@app.on_message(
    filters.command(["play", "playforce", "vplay", "vplayforce",
                     "yplay", "yplayforce", "vyplay", "vyplayforce"])
    & filters.group & ~app.bl_users
)
@lang.language()
@checkUB
async def play_hndlr(
    _,
    m: types.Message,
    force: bool = False,
    m3u8: bool = False,
    video: bool = False,
    url: str = None,
) -> None:
    sent     = await m.reply_text(m.lang["play_searching"])
    mention  = m.from_user.mention
    cmd      = m.command[0].lower()
    use_ytm  = cmd.startswith("y") or cmd.startswith("vy")
    file     = None
    tracks   = []
    media    = tg.get_media(m.reply_to_message) if m.reply_to_message else None

    if media:
        setattr(sent, "lang", m.lang)
        file = await tg.download(m.reply_to_message, sent)

    elif m3u8:
        file = await tg.process_m3u8(url, sent.id, video)

    elif url:
        if yt.is_playlist_url(url):
            await sent.edit_text(m.lang["playlist_fetch"])
            loaded = 0

            async def _progress(done: int, total: int):
                nonlocal loaded
                loaded = done
                try:
                    await sent.edit_text(
                        m.lang["playlist_loading"].format(done, total or "?")
                    )
                except Exception:
                    pass

            tracks = await yt.playlist(config.PLAYLIST_LIMIT, mention, url, video, _progress)
            if not tracks:
                return await sent.edit_text(m.lang["playlist_error"])
            file        = tracks[0]
            tracks      = tracks[1:]
            file.message_id = sent.id

        else:
            if use_ytm:
                file = await yt.ytmusic_search(url, sent.id, video=video)
            else:
                file = await yt.search(url, sent.id, video=video)

        if not file:
            return await sent.edit_text(m.lang["play_not_found"].format(config.SUPPORT_CHAT))

    elif len(m.command) >= 2:
        query = " ".join(m.command[1:])
        if use_ytm:
            file = await yt.ytmusic_search(query, sent.id, video=video)
        else:
            file = await yt.search(query, sent.id, video=video)
        if not file:
            return await sent.edit_text(m.lang["play_not_found"].format(config.SUPPORT_CHAT))

    if not file:
        return await sent.edit_text(m.lang["play_usage"])

    if file.duration_sec and file.duration_sec > config.DURATION_LIMIT:
        return await sent.edit_text(m.lang["play_duration_limit"].format(config.DURATION_LIMIT // 60))

    chat_limit = await db.get_setlimit(m.chat.id)
    if chat_limit and file.duration_sec and file.duration_sec > chat_limit * 60:
        return await sent.edit_text(m.lang["play_duration_limit"].format(chat_limit))

    if await db.is_local_banned(m.chat.id, m.from_user.id):
        return await sent.edit_text(m.lang["localban_blocked"])

    if not force and await db.get_queuelock(m.chat.id):
        if not (await is_admin(m.chat.id, m.from_user.id)
                or m.from_user.id in app.sudoers
                or await db.is_auth(m.chat.id, m.from_user.id)):
            return await sent.edit_text(m.lang["queuelock_blocked"])

    q_max = await db.get_queue_max(m.chat.id)
    if not force and len(queue.get_queue(m.chat.id)) >= q_max:
        return await sent.edit_text(m.lang["play_queue_full"].format(q_max))

    if await db.is_logger():
        await utils.play_log(m, sent.link, file.title, file.duration)

    file.user = mention

    if force:
        queue.force_add(m.chat.id, file)
    else:
        position = queue.add(m.chat.id, file)
        if position != 0 or await db.get_call(m.chat.id):
            await sent.edit_text(
                m.lang["play_queued"].format(position, file.url, file.title, file.duration, mention),
                reply_markup=buttons.play_queued(m.chat.id, file.id, m.lang["play_now"]),
            )
            if tracks:
                added = _add_to_queue(m.chat.id, tracks[:5])
                await app.send_message(m.chat.id, m.lang["playlist_queued"].format(len(tracks)) + added)
                if len(tracks) > 5:
                    asyncio.create_task(_bg_load(m.chat.id, tracks[5:]))
            return

    if not file.file_path:
        if video:
            _check = (f"downloads/{file.id}.mp4",)
        else:
            _check = tuple(f"downloads/{file.id}.{ext}" for ext in ("webm", "opus", "m4a"))
        file.file_path = next((p for p in _check if Path(p).exists()), None)

        if not file.file_path:
            await sent.edit_text(m.lang["play_downloading"])
            file.file_path, _ = (
                await asyncio.gather(
                    yt.download(file.id, video=video),
                    db.get_assistant(m.chat.id),
                    return_exceptions=True,
                )
            )[:2]
            if isinstance(file.file_path, Exception):
                file.file_path = None

    await jatt.play_media(chat_id=m.chat.id, message=sent, media=file)
    if not tracks:
        return
    added = _add_to_queue(m.chat.id, tracks[:5])
    await app.send_message(m.chat.id, m.lang["playlist_queued"].format(len(tracks)) + added)
    if len(tracks) > 5:
        asyncio.create_task(_bg_load(m.chat.id, tracks[5:]))
