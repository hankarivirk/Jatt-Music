# Copyright (c) 2025 JattDevs
# Licensed under the MIT License.
# This file is part of JattMusicBot

from pyrogram import filters, types

from jatt import app, db, lang, queue
from jatt.helpers import can_manage_vc


@app.on_message(
    filters.command(["remove", "rm"]) & filters.group & ~app.bl_users
)
@lang.language()
@can_manage_vc
async def _remove(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    if len(m.command) != 2:
        return await m.reply_text(m.lang["remove_usage"])

    try:
        pos = int(m.command[1])
    except ValueError:
        return await m.reply_text(m.lang["remove_usage"])

    q_list = list(queue.queues[m.chat.id])
    queued_count = len(q_list) - 1  # excludes currently playing

    if queued_count < 1:
        return await m.reply_text(m.lang["clearqueue_empty"])

    removed = queue.remove_item(m.chat.id, pos)
    if removed is None:
        return await m.reply_text(
            m.lang["remove_invalid"].format(queued_count)
        )

    title = (removed.title[:40] if removed.title else "Unknown")
    await m.reply_text(m.lang["remove_done"].format(title, pos))
