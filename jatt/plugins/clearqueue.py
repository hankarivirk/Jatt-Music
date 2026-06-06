# Copyright (c) 2025 JattDevs
# Licensed under the MIT License.
# This file is part of JattMusicBot

from pyrogram import filters, types

from jatt import app, db, lang, queue
from jatt.helpers import can_manage_vc


@app.on_message(
    filters.command(["clearqueue", "cq"]) & filters.group & ~app.bl_users
)
@lang.language()
@can_manage_vc
async def _clearqueue(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    removed = queue.clear_keep_current(m.chat.id)

    if removed == 0:
        return await m.reply_text(m.lang["clearqueue_empty"])

    await m.reply_text(m.lang["clearqueue_done"].format(removed))
