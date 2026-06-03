# 🎵 Jatt Music Bot
# Built with ❤️ for the Jatt community

import time
import asyncio
import logging
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    format="[%(asctime)s - %(levelname)s] - %(name)s: %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("log.txt", maxBytes=10485760, backupCount=5),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("ntgcalls").setLevel(logging.CRITICAL)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


__version__ = "1.0.0"
__botname__ = "Jatt Music Bot"

from config import Config

config = Config()
config.check()
tasks = []
boot = time.time()

from jatt.core.bot import Bot
app = Bot()

from jatt.core.dir import ensure_dirs
ensure_dirs()

from jatt.core.userbot import Userbot
userbot = Userbot()

from jatt.core.mongo import MongoDB
db = MongoDB()

from jatt.core.lang import Language
lang = Language()

from jatt.core.telegram import Telegram
from jatt.core.youtube import YouTube
tg = Telegram()
yt = YouTube()

from jatt.helpers import Queue, Thumbnail
queue = Queue()
thumb = Thumbnail()

from jatt.core.calls import TgCall
jatt = TgCall()


async def stop() -> None:
    logger.info("Stopping Jatt Music Bot...")
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.exceptions.CancelledError:
            pass

    await app.exit()
    await userbot.exit()
    await db.close()
    await thumb.close()

    logger.info("Jatt Music Bot stopped.\n")
