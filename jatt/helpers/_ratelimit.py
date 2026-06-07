import time
from collections import defaultdict
from functools import wraps

from pyrogram import types

# {user_id: {cmd_key: last_used_ts}}
_cd: dict[int, dict[str, float]] = defaultdict(dict)


def ratelimit(seconds: int = 3, key: str = ""):
    """Per-user cooldown decorator. Blocks repeated invocations within `seconds`."""
    def decorator(func):
        cmd_key = key or func.__name__

        @wraps(func)
        async def wrapper(_, m: types.Message):
            if not m.from_user:
                return await func(_, m)
            uid = m.from_user.id
            now = time.time()
            diff = now - _cd[uid].get(cmd_key, 0.0)
            if diff < seconds:
                wait = round(seconds - diff, 1)
                return await m.reply_text(
                    f"⏳  Slow down. Retry in  <b>{wait}s</b>", quote=True
                )
            _cd[uid][cmd_key] = now
            return await func(_, m)

        return wrapper
    return decorator
