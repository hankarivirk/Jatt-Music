# Copyright (c) 2025 JattDevs
# Licensed under the MIT License.
# This file is part of JattMusicBot

from pyrogram import filters, types

from jatt import app, config, db, lang, queue, thumb
from jatt.helpers import Track, buttons


@app.on_message(
    filters.command(["nowplaying", "np"]) & filters.group & ~app.bl_users
)
@lang.language()
async def _nowplaying(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    media = queue.get_current(m.chat.id)
    if not media:
        return await m.reply_text(m.lang["not_playing"])

    sent = await m.reply_text(m.lang["processing"])

    # Build the "now playing" caption
    if media.url:
        title_link = f'<a href="{media.url}">{media.title}</a>'
    else:
        title_link = media.title or "Unknown"

    text = m.lang["nowplaying_card"].format(
        title_link,
        media.duration,
        media.user or "Unknown",
    )

    _thumb = (
        await thumb.generate(media)
        if isinstance(media, Track)
        else config.DEFAULT_THUMB
    ) if config.THUMB_GEN else None

    keyboard = buttons.controls(m.chat.id)

    try:
        if _thumb:
            await sent.edit_media(
                media=types.InputMediaPhoto(media=_thumb, caption=text),
                reply_markup=keyboard,
            )
        else:
            await sent.edit_text(text, reply_markup=keyboard)
    except Exception:
        await sent.edit_text(text, reply_markup=keyboard)
