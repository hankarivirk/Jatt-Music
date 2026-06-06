# Copyright (c) 2025 JattDevs
# Licensed under the MIT License.
# This file is part of JattMusicBot

import asyncio
import gc
import ctypes
import os
import signal
import sys
import time
import importlib
from contextlib import suppress

from jatt import (jatt, app, config, db, logger,
                   stop, thumb, userbot, yt)
from jatt.plugins import all_modules


async def idle():
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()


async def _memory_trim() -> None:
    """
    Every 5 minutes: force a Python GC cycle then ask the OS allocator
    (glibc malloc) to release free arenas back to the OS.
    This prevents RSS from climbing indefinitely on Railway's container.
    """
    while True:
        await asyncio.sleep(300)
        gc.collect()
        try:
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:
            pass


async def main():
    await db.connect()
    await app.boot()
    await userbot.boot()
    await jatt.boot()
    await thumb.start()

    for module in all_modules:
        importlib.import_module(f"jatt.plugins.{module}")
    logger.info(f"Loaded {len(all_modules)} modules.")

    if config.COOKIES_URL:
        await yt.save_cookies(config.COOKIES_URL)

    sudoers = await db.get_sudoers()
    app.sudoers.update(sudoers)
    app.bl_users.update(await db.get_blacklisted())
    logger.info(f"Loaded {len(app.sudoers)} sudo users.")

    # Background memory manager (prevents Railway OOM)
    asyncio.create_task(_memory_trim())

    await idle()
    asyncio.create_task(stop())


# ── Auto-restart on crash ─────────────────────────────────────────────────────
# If the bot dies from an unexpected exception it relaunches itself using
# os.execve (replaces the current process — clean memory, same PID slot).
# A counter in the environment prevents infinite restart loops.

_MAX_RESTARTS = 10
_RESTART_DELAY = 5   # seconds before relaunching


if __name__ == "__main__":
    _boot_count = int(os.environ.get("_JATT_BOOT", "0"))
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested by KeyboardInterrupt.")
    except SystemExit as e:
        # Config errors, missing env vars — don't retry
        sys.exit(e.code)
    except Exception as e:
        logger.critical(
            f"Fatal crash (boot #{_boot_count}): {e}", exc_info=True
        )
        if _boot_count < _MAX_RESTARTS:
            logger.info(
                f"Auto-restarting in {_RESTART_DELAY}s "
                f"(attempt {_boot_count + 1}/{_MAX_RESTARTS})..."
            )
            time.sleep(_RESTART_DELAY)
            env = os.environ.copy()
            env["_JATT_BOOT"] = str(_boot_count + 1)
            # Replace this process entirely — fresh Python interpreter
            os.execve(sys.executable, [sys.executable, "-m", "jatt"], env)
        else:
            logger.critical(
                f"Reached maximum restart limit ({_MAX_RESTARTS}). "
                "Check your config and logs."
            )
