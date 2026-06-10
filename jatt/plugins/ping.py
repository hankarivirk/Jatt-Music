import time
import psutil

from pyrogram import filters, types
from jatt import app, jatt, boot, config, lang
from jatt.helpers import buttons


@app.on_message(filters.command(["alive", "ping"]) & ~app.bl_users)
@lang.language()
async def _ping(_, m: types.Message):
    start = time.time()
    sent = await m.reply_text(m.lang["pinging"])

    def _fmt_uptime(s: int) -> str:
        parts = []
        days = s // 86400
        hrs  = (s % 86400) // 3600
        mins = (s % 3600) // 60
        secs = s % 60
        if days: parts.append(f"{days}d")
        if hrs:  parts.append(f"{hrs}h")
        if mins: parts.append(f"{mins}m")
        parts.append(f"{secs}s")
        return " ".join(parts)

    uptime  = _fmt_uptime(int(time.time() - boot))
    latency = round((time.time() - start) * 1000, 2)
    vc_ping = await jatt.ping()

    cpu   = psutil.cpu_percent(interval=0)
    ram   = psutil.virtual_memory().percent
    disk  = psutil.disk_usage("/").percent

    await sent.edit_media(
        media=types.InputMediaPhoto(
            media=config.PING_IMG,
            caption=m.lang["ping_pong"].format(
                latency, uptime, cpu, ram, disk, vc_ping,
            )
        ),
        reply_markup=buttons.ping_markup(m.lang["support"]),
    )
