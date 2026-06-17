import asyncio
from ntgcalls import (ConnectionNotFound, TelegramServerError,
                      RTMPStreamingUnsupported, ConnectionError)
from pyrogram.errors import (ChatSendMediaForbidden, ChatSendPhotosForbidden,
                             MessageIdInvalid)
from pyrogram.types import InputMediaPhoto, Message
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession
from jatt import (app, config, db, lang, logger, queue, thumb, userbot, yt)
from jatt.helpers import Media, Track, buttons


class TgCall(PyTgCalls):
    def __init__(self):
        self.clients  = []
        self._filters: dict[int, str] = {}   # active audio filters per chat
        self._pinned:  dict[int, int] = {}    # pinned now-playing msg per chat

    async def pause(self, chat_id):
        await db.playing(chat_id, paused=True)
        return await (await db.get_assistant(chat_id)).pause(chat_id)

    async def resume(self, chat_id):
        await db.playing(chat_id, paused=False)
        return await (await db.get_assistant(chat_id)).resume(chat_id)

    async def stop(self, chat_id):
        client = await db.get_assistant(chat_id)
        queue.clear(chat_id)
        self._filters.pop(chat_id, None)
        await self._delete_pinned(chat_id)
        await db.remove_call(chat_id)
        await db.set_loop(chat_id, 0)
        try: await client.leave_call(chat_id, close=False)
        except Exception: pass

    async def set_volume(self, chat_id, volume):
        await (await db.get_assistant(chat_id)).change_volume_call(chat_id, volume)
        await db.set_volume(chat_id, volume)

    def set_filter(self, chat_id, f): self._filters[chat_id] = f
    def clear_filter(self, chat_id):  self._filters.pop(chat_id, None)
    def get_filter(self, chat_id):    return self._filters.get(chat_id)

    async def _delete_pinned(self, chat_id):
        msg_id = self._pinned.pop(chat_id, None)
        if msg_id:
            try: await app.delete_messages(chat_id, msg_id, revoke=True)
            except Exception: pass

    async def _safe_play_next(self, chat_id):
        try: await self.play_next(chat_id)
        except Exception as e:
            logger.error(f"play_next {chat_id}: {e}", exc_info=True)
            try: await self.stop(chat_id)
            except Exception: pass

    @staticmethod
    async def _send_thumb(message, _thumb, text, keyboard, chat_id, media):
        try:
            await message.edit_media(
                media=InputMediaPhoto(media=_thumb, caption=text),
                reply_markup=keyboard,
            )
        except (ChatSendMediaForbidden, ChatSendPhotosForbidden, MessageIdInvalid):
            try:
                s = await app.send_photo(chat_id=chat_id, photo=_thumb,
                                         caption=text, reply_markup=keyboard)
                media.message_id = s.id
            except Exception: pass
        except Exception: pass

    async def play_media(self, chat_id, message: Message,
                         media: "Media | Track", seek_time: int = 0):
        client = await db.get_assistant(chat_id)
        _lang  = await lang.get_lang(chat_id)

        if not media.file_path:
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            asyncio.create_task(self._safe_play_next(chat_id))
            return

        parts = []
        if seek_time > 1:    parts.append(f"-ss {seek_time}")
        af = self._filters.get(chat_id)
        if af:               parts.append(f"-af {af}")

        stream = types.MediaStream(
            media_path=media.file_path,
            audio_parameters=types.AudioQuality.HIGH,
            video_parameters=types.VideoQuality.HD_720p,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(types.MediaStream.Flags.AUTO_DETECT if media.video
                         else types.MediaStream.Flags.IGNORE),
            ffmpeg_parameters=" ".join(parts) or None,
        )
        try:
            await client.play(chat_id=chat_id, stream=stream,
                              config=types.GroupCallConfig(auto_start=False))
            if not seek_time:
                if not getattr(media, "_replaying", False):
                    media.time = 1
                await db.add_call(chat_id)
                asyncio.create_task(self._save_history(chat_id, media))
                asyncio.create_task(self._prefetch_next(chat_id))

            text     = _lang["play_media"].format(media.url, media.title,
                                                   media.duration, media.user)
            keyboard = buttons.controls(chat_id)

            # Text-first: respond instantly, thumbnail follows in background
            try: await message.edit_text(text, reply_markup=keyboard)
            except Exception: pass

            # Auto-pin now-playing card
            if not seek_time:
                try:
                    await app.pin_chat_message(chat_id, message.id,
                                               disable_notification=True)
                    self._pinned[chat_id] = message.id
                except Exception: pass

            # Background thumbnail
            if config.THUMB_GEN and isinstance(media, Track):
                async def _t():
                    try:
                        t = await thumb.generate(media)
                        if t: await self._send_thumb(message, t, text,
                                                      keyboard, chat_id, media)
                    except Exception: pass
                asyncio.create_task(_t())

        except FileNotFoundError:
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            asyncio.create_task(self._safe_play_next(chat_id))
        except exceptions.NoActiveGroupCall:
            await self.stop(chat_id)
            await message.edit_text(_lang["error_no_call"])
        except exceptions.NoAudioSourceFound:
            await message.edit_text(_lang["error_no_audio"])
            asyncio.create_task(self._safe_play_next(chat_id))
        except (ConnectionError, ConnectionNotFound, TelegramServerError) as e:
            logger.warning(f"Stream error {chat_id}: {e}")
            await self.stop(chat_id)
            try: await message.edit_text(_lang["error_tg_server"])
            except Exception: pass
        except RTMPStreamingUnsupported:
            await self.stop(chat_id)
            await message.edit_text(_lang["error_rtmp"])
        except Exception as e:
            logger.error(f"play_media {chat_id}: {e}", exc_info=True)
            asyncio.create_task(self._safe_play_next(chat_id))

    @staticmethod
    async def _save_history(chat_id, media: "Media | Track"):
        try:
            await db.add_history(chat_id, title=media.title or "Unknown",
                                 url=media.url or "", duration=media.duration,
                                 user=media.user or "Unknown")
            if media.url:
                await db.increment_track(chat_id, media.title or "Unknown", media.url)
            # Track per-user play count
            import re
            uid_match = re.search(r"tg://user\?id=(\d+)", media.user or "")
            if uid_match:
                await db.add_user_play(chat_id, int(uid_match.group(1)))
        except Exception: pass

    async def _prefetch_next(self, chat_id):
        try:
            q = list(queue.queues.get(chat_id, []))
            if len(q) < 2: return
            nxt = q[1]
            if getattr(nxt, "file_path", None): return
            if not getattr(nxt, "id", None): return
            path = await yt.download(nxt.id, video=nxt.video)
            if path: nxt.file_path = path
        except Exception: pass

    async def _autoplay(self, chat_id):
        """Search for a related track when queue empties."""
        try:
            history = await db.get_history(chat_id)
            if not history: return await self.stop(chat_id)
            last_title = history[0].get("title", "")
            if not last_title: return await self.stop(chat_id)
            track = await yt.search(last_title, 0)
            if not track: return await self.stop(chat_id)
            track.user = "Autoplay"
            queue.add(chat_id, track)
            _lang = await lang.get_lang(chat_id)
            msg = await app.send_message(chat_id, _lang["autoplay_found"].format(track.title))
            track.message_id = msg.id
            if not track.file_path:
                track.file_path = await yt.download(track.id, video=track.video)
            if not track.file_path:
                return await self.stop(chat_id)
            await self.play_media(chat_id, msg, track)
        except Exception as e:
            logger.error(f"autoplay {chat_id}: {e}")
            await self.stop(chat_id)

    async def replay(self, chat_id):
        if not await db.get_call(chat_id): return
        media = queue.get_current(chat_id)
        if not media: return
        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_again"])
        media.message_id = msg.id
        media._replaying = True
        await self.play_media(chat_id, msg, media)
        media._replaying = False

    async def play_next(self, chat_id):
        if loop := await db.get_loop(chat_id):
            await db.set_loop(chat_id, loop - 1)
            return await self.replay(chat_id)

        media = queue.get_next(chat_id)
        if not media:
            if await db.get_autoplay(chat_id):
                asyncio.create_task(self._autoplay(chat_id))
                return
            return await self.stop(chat_id)

        # Delete old now-playing pinned card
        await self._delete_pinned(chat_id)

        try:
            if media.message_id:
                await app.delete_messages(chat_id=chat_id,
                                          message_ids=media.message_id, revoke=True)
                media.message_id = 0
        except Exception: pass

        _lang = await lang.get_lang(chat_id)
        msg   = await app.send_message(chat_id=chat_id, text=_lang["play_next"])

        if not media.file_path:
            media.file_path = await yt.download(media.id, video=media.video)
            if not media.file_path:
                await msg.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
                asyncio.create_task(self._safe_play_next(chat_id))
                return

        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)

    async def ping(self):
        p = [c.ping for c in self.clients]
        return round(sum(p) / len(p), 2) if p else 0.0

    async def decorators(self, client: PyTgCalls):
        @client.on_update()
        async def update_handler(_, update: types.Update):
            try:
                if isinstance(update, types.StreamEnded):
                    if update.stream_type == types.StreamEnded.Type.AUDIO:
                        asyncio.create_task(self._safe_play_next(update.chat_id))
                elif isinstance(update, types.ChatUpdate):
                    if update.status in [
                        types.ChatUpdate.Status.KICKED,
                        types.ChatUpdate.Status.LEFT_GROUP,
                        types.ChatUpdate.Status.CLOSED_VOICE_CHAT,
                    ]:
                        asyncio.create_task(self.stop(update.chat_id))
            except Exception as e:
                logger.error(f"update_handler: {e}", exc_info=True)

    async def boot(self):
        PyTgCallsSession.notice_displayed = True
        for ub in userbot.clients:
            client = PyTgCalls(ub, cache_duration=100)
            await client.start()
            self.clients.append(client)
            await self.decorators(client)
        logger.info("PyTgCalls started.")
