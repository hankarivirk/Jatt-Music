# Copyright (c) 2025 JattDevs
# Licensed under the MIT License.
# This file is part of JattMusicBot

from pyrogram import filters, types

from jatt import app, db, lang, queue
from jatt.helpers import can_manage_vc


@app.on_message(
    filters.command(["move"]) & filters.group & ~app.bl_users
)
@lang.language()
@can_manage_vc
async def _move(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    # Need exactly two integer arguments
    if len(m.command) != 3:
        return await m.reply_text(m.lang["move_usage"])

    try:
        from_pos = int(m.command[1])
        to_pos   = int(m.command[2])
    except ValueError:
        return await m.reply_text(m.lang["move_usage"])

    if from_pos == to_pos:
        return await m.reply_text(m.lang["move_same"])

    # Queue size (includes currently playing at index 0)
    q = queue.get_queue(m.chat.id)
    queued_count = len(q) - 1  # excludes currently playing

    if queued_count < 1:
        return await m.reply_text(m.lang["clearqueue_empty"])

    track = None
    # Peek at the item before moving to show its title
    q_list = list(queue.queues[m.chat.id])
    if 1 <= from_pos < len(q_list):
        track = q_list[from_pos]

    success = queue.move(m.chat.id, from_pos, to_pos)
    if not success:
        return await m.reply_text(
            m.lang["move_invalid"].format(queued_count)
        )

    title = (track.title[:40] if track else "Unknown")
    await m.reply_text(
        m.lang["move_done"].format(title, from_pos, to_pos)
    )
