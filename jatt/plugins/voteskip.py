import asyncio
from pyrogram import filters, types
from jatt import app, db, jatt, lang

_votes: dict[int, set[int]] = {}
_timers: dict[int, asyncio.Task] = {}
VOTE_TIMEOUT = 60


async def _expire(chat_id: int):
    await asyncio.sleep(VOTE_TIMEOUT)
    _votes.pop(chat_id, None)
    _timers.pop(chat_id, None)


@app.on_message(filters.command(["voteskip", "vs"]) & filters.group & ~app.bl_users)
@lang.language()
async def _voteskip(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    chat_id = m.chat.id
    user_id = m.from_user.id

    if chat_id not in _votes:
        _votes[chat_id] = set()

    if user_id in _votes[chat_id]:
        return await m.reply_text(m.lang["voteskip_already"])

    _votes[chat_id].add(user_id)

    try:
        client = await db.get_assistant(chat_id)
        participants = await client.get_participants(chat_id)
        vc_count = max(len(participants) - 1, 1)
    except Exception:
        vc_count = 3

    needed = max(2, (vc_count + 1) // 2)
    have = len(_votes[chat_id])

    if have >= needed:
        _votes.pop(chat_id, None)
        if chat_id in _timers:
            _timers.pop(chat_id).cancel()
        asyncio.create_task(jatt._safe_play_next(chat_id))
        return await m.reply_text(m.lang["voteskip_passed"])

    if chat_id not in _timers:
        _timers[chat_id] = asyncio.create_task(_expire(chat_id))

    await m.reply_text(m.lang["voteskip_vote"].format(have, needed))
