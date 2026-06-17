import io
import os
import re
import sys
import uuid
import traceback
from html import escape

from pyrogram import filters, types

from jatt import jatt, app, config, db, lang, userbot
from jatt.helpers import format_exception, meval


@app.on_message(filters.command(["eval", "exec"]) & filters.user(app.owner))
@app.on_edited_message(filters.command(["eval", "exec"]) & filters.user(app.owner))
@lang.language()
async def eval_handler(_, message: types.Message):
    if len(message.command) < 2:
        return await message.reply_text(message.lang["eval_inp"])

    code = message.text.split(None, 1)[1]
    out_buf = io.StringIO()

    async def _eval():
        async def send(*a, **kw): return await message.reply_text(*a, **kw)
        def _print(*a, **kw): kw.setdefault("file", out_buf); print(*a, **kw)
        try:
            result = await meval(code, globals(), **{
                "m": message, "r": message.reply_to_message,
                "chat": message.chat, "user": message.from_user,
                "app": app, "db": db, "client": app, "ub": userbot,
                "ikb": types.InlineKeyboardButton, "ikm": types.InlineKeyboardMarkup,
                "send": send, "config": config, "print": _print,
                "os": os, "re": re, "sys": sys, "tb": traceback,
            })
            return "", result
        except Exception as e:
            tb = traceback.extract_tb(e.__traceback__)
            i = next((i for i, f in enumerate(tb) if f.filename == "<string>"), -1)
            return message.lang["eval_error"], format_exception(e, tb[i:] if i != -1 else tb)

    _, result = await _eval()
    if result is not None or not out_buf.getvalue():
        print(result, file=out_buf)
    output = out_buf.getvalue().strip()
    response = message.lang["eval_out"].format(escape(output))
    if len(response) > 4096:
        with io.BytesIO(output.encode()) as f:
            f.name = f"{uuid.uuid4().hex[:8]}.txt"
            return await message.reply_document(document=f, disable_notification=True)
    await message.reply_text(response)
