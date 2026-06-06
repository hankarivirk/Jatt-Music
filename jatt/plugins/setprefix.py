# Copyright (c) 2025 JattDevs
# Licensed under the MIT License.
# This file is part of JattMusicBot

from pyrogram import filters, types

from jatt import app, db, lang
from jatt.helpers import admin_check

# ── Prefix router ─────────────────────────────────────────────────────────────
# Runs at handler group -1 (before all command handlers).
# When a group has set a custom prefix (e.g. "!"), this replaces it with "/"
# in message.text so that Pyrogram's filters.command() works transparently.

@app.on_message(filters.group & filters.text, group=-1)
async def _prefix_router(_, m: types.Message):
    """Transparently translate custom-prefix commands to /commands."""
    if not m.text or not m.from_user:
        return

    try:
        prefix = await db.get_prefix(m.chat.id)
    except Exception:
        return

    if not prefix or prefix == "/":
        return  # default prefix; nothing to do

    text = m.text.strip()
    if not text.startswith(prefix):
        return

    rest = text[len(prefix):]
    # Only route if the character right after the prefix is a letter (a real command)
    if not rest or not rest[0].isalpha():
        return

    # Replace custom prefix with "/" so filters.command() matches normally
    m.text = "/" + rest


# ── /setprefix command ────────────────────────────────────────────────────────

@app.on_message(
    filters.command(["setprefix"]) & filters.group & ~app.bl_users
)
@lang.language()
@admin_check
async def _setprefix(_, m: types.Message):
    if len(m.command) < 2:
        current = await db.get_prefix(m.chat.id)
        return await m.reply_text(
            m.lang["setprefix_usage"] + f"\n\n" + m.lang["setprefix_current"].format(current)
        )

    new_prefix = m.command[1]

    # Reset to default
    if new_prefix == "/":
        await db.set_prefix(m.chat.id, "/")
        return await m.reply_text(m.lang["setprefix_reset"])

    # Validate: 1–3 non-space characters only
    if len(new_prefix) > 3 or " " in new_prefix:
        return await m.reply_text(m.lang["setprefix_invalid"])

    await db.set_prefix(m.chat.id, new_prefix)
    await m.reply_text(m.lang["setprefix_done"].format(new_prefix))
