import asyncio
from datetime import datetime, timedelta, timezone
from pyrogram import filters, types
from jatt import app, db, jatt, lang, queue


@app.on_message(filters.command(["schedule"]) & filters.group & ~app.bl_users)
@lang.language()
async def _schedule(_, m: types.Message):
    if len(m.command) < 3:
        return await m.reply_text(m.lang["schedule_usage"])
    try:
        hh, mm = map(int, m.command[1].split(":"))
        assert 0 <= hh <= 23 and 0 <= mm <= 59
    except Exception:
        return await m.reply_text(m.lang["schedule_usage"])

    query = " ".join(m.command[2:])
    now = datetime.now(timezone.utc)
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)

    delay = (target - now).total_seconds()
    mention = m.from_user.mention
    await m.reply_text(m.lang["schedule_set"].format(query[:35], m.command[1]))

    async def _run():
        await asyncio.sleep(delay)
        from jatt import yt
        track = await yt.search(query, 0)
        if not track:
            try: await app.send_message(m.chat.id, m.lang["schedule_failed"].format(query[:35]))
            except Exception: pass
            return
        track.user = mention
        pos = queue.add(m.chat.id, track)
        if pos == 0 and not await db.get_call(m.chat.id):
            track.file_path = await yt.download(track.id, video=track.video)
            msg = await app.send_message(m.chat.id, m.lang["schedule_playing"].format(track.title))
            track.message_id = msg.id
            await jatt.play_media(m.chat.id, msg, track)
        else:
            await app.send_message(m.chat.id, m.lang["schedule_queued"].format(track.title, pos))

    asyncio.create_task(_run())
