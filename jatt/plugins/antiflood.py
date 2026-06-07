import time
from pyrogram import filters, StopPropagation, types
from jatt import app

_cache: dict[tuple[int, int], list[float]] = {}
WINDOW  = 5.0   # seconds
MAX_OPS = 4     # max commands per window per user

WATCHED = [
    "play","vplay","playforce","vplayforce",
    "skip","pause","resume","stop","seek","seekback",
    "queue","nowplaying","voteskip","volume","shuffle",
    "move","remove","clearqueue","loop","history","top","save",
]


@app.on_message(filters.group & filters.command(WATCHED), group=-2)
async def _antiflood(_, m: types.Message):
    if not m.from_user:
        return
    key = (m.chat.id, m.from_user.id)
    now = time.time()
    hits = [t for t in _cache.get(key, []) if now - t < WINDOW]
    if len(hits) >= MAX_OPS:
        try:
            await m.delete()
        except Exception:
            pass
        raise StopPropagation
    hits.append(now)
    _cache[key] = hits
