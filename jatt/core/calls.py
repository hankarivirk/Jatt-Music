# Copyright (c) 2025 JattDevs
# Licensed under the MIT License.
# This file is part of JattMusicBot

import asyncio

from ntgcalls import (ConnectionNotFound, TelegramServerError,
                      RTMPStreamingUnsupported, ConnectionError)
from pyrogram.errors import (ChatSendMediaForbidden, ChatSendPhotosForbidden,
                             MessageIdInvalid)
from pyrogram.types import InputMediaPhoto, Message
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession

from jatt import (app, config, db, lang, logger,
                   queue, thumb, userbot, yt)
from jatt.helpers import Media, Track, buttons


class TgCall(PyTgCalls):
    def __init__(self):
        self.clients = []

    async def pause(self, chat_id: int) -> bool:
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=True)
        return await client.pause(chat_id)

    async def resume(self, chat_id: int) -> bool:
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=False)
        return await client.resume(chat_id)

    async def stop(self, chat_id: int) -> None:
        client = await db.get_assistant(chat_id)
        queue.clear(chat_id)
        await db.remove_call(chat_id)
        await db.set_loop(chat_id, 0)
        try:
            await client.leave_call(chat_id, close=False)
        except Exception:
            pass

    # ── Safe wrapper: prevents update_handler from ever crashing ─────────────
    async def _safe_play_next(self, chat_id: int) -> None:
        """Wraps play_next so any exception is logged and never propagates."""
        try:
            await self.play_next(chat_id)
        except Exception as e:
            logger.error(f"play_next error for chat {chat_id}: {e}", exc_info=True)
            try:
                await self.stop(chat_id)
            except Exception:
                pass

    async def play_media(
        self,
        chat_id: int,
        message: Message,
        media: Media | Track,
        seek_time: int = 0,
    ) -> None:
        client = await db.get_assistant(chat_id)
        _lang = await lang.get_lang(chat_id)
        _thumb = (
            await thumb.generate(media)
            if isinstance(media, Track)
            else config.DEFAULT_THUMB
        ) if config.THUMB_GEN else None

        if not media.file_path:
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            # Use create_task so we don't block and don't recurse
            asyncio.create_task(self._safe_play_next(chat_id))
            return

        stream = types.MediaStream(
            media_path=media.file_path,
            audio_parameters=types.AudioQuality.HIGH,
            video_parameters=types.VideoQuality.HD_720p,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(
                types.MediaStream.Flags.AUTO_DETECT
                if media.video
                else types.MediaStream.Flags.IGNORE
            ),
            ffmpeg_parameters=f"-ss {seek_time}" if seek_time > 1 else None,
        )
        try:
            await client.play(
                chat_id=chat_id,
                stream=stream,
                config=types.GroupCallConfig(auto_start=False),
            )
            if not seek_time:
                media.time = 1
                await db.add_call(chat_id)
                # Save to play history (non-blocking — never stall playback)
                asyncio.create_task(self._save_history(chat_id, media))

                text = _lang["play_media"].format(
                    media.url,
                    media.title,
                    media.duration,
                    media.user,
                )
                keyboard = buttons.controls(chat_id)
                try:
                    if _thumb:
                        await message.edit_media(
                            media=InputMediaPhoto(media=_thumb, caption=text),
                            reply_markup=keyboard,
                        )
                    else:
                        await message.edit_text(text, reply_markup=keyboard)
                except (ChatSendMediaForbidden, ChatSendPhotosForbidden, MessageIdInvalid):
                    try:
                        if _thumb:
                            sent = await app.send_photo(
                                chat_id=chat_id, photo=_thumb,
                                caption=text, reply_markup=keyboard,
                            )
                        else:
                            sent = await app.send_message(
                                chat_id=chat_id, text=text, reply_markup=keyboard,
                            )
                        media.message_id = sent.id
                    except Exception:
                        pass

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
            logger.warning(f"Stream connection error in {chat_id}: {e}")
            await self.stop(chat_id)
            try:
                await message.edit_text(_lang["error_tg_server"])
            except Exception:
                pass
        except RTMPStreamingUnsupported:
            await self.stop(chat_id)
            await message.edit_text(_lang["error_rtmp"])
        except Exception as e:
            logger.error(f"Unexpected play_media error in {chat_id}: {e}", exc_info=True)
            asyncio.create_task(self._safe_play_next(chat_id))

    @staticmethod
    async def _save_history(chat_id: int, media: Media | Track) -> None:
        try:
            await db.add_history(
                chat_id,
                title=media.title or "Unknown",
                url=media.url or "",
                duration=media.duration,
                user=media.user or "Unknown",
            )
        except Exception:
            pass

    async def replay(self, chat_id: int) -> None:
        if not await db.get_call(chat_id):
            return
        media = queue.get_current(chat_id)
        if not media:
            return
        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_again"])
        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)

    async def play_next(self, chat_id: int) -> None:
        if loop := await db.get_loop(chat_id):
            await db.set_loop(chat_id, loop - 1)
            return await self.replay(chat_id)

        media = queue.get_next(chat_id)

        # MUST check None BEFORE touching any attribute (previous crash source)
        if not media:
            return await self.stop(chat_id)

        try:
            if media.message_id:
                await app.delete_messages(
                    chat_id=chat_id,
                    message_ids=media.message_id,
                    revoke=True,
                )
                media.message_id = 0
        except Exception:
            pass

        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_next"])

        if not media.file_path:
            media.file_path = await yt.download(media.id, video=media.video)
            if not media.file_path:
                await msg.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
                # Non-recursive: schedule next track as a fresh task
                asyncio.create_task(self._safe_play_next(chat_id))
                return

        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)

    async def ping(self) -> float:
        pings = [client.ping for client in self.clients]
        return round(sum(pings) / len(pings), 2) if pings else 0.0

    async def decorators(self, client: PyTgCalls) -> None:
        @client.on_update()
        async def update_handler(_, update: types.Update) -> None:
            # ── CRITICAL: ALWAYS use create_task here ────────────────────────
            # If play_next or stop raise any exception the update_handler
            # must NOT crash — that would kill the PyTgCalls event loop and
            # cause the bot to stop responding to stream events (the "auto
            # restart" symptom the user observed).
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
                logger.error(f"update_handler dispatch error: {e}", exc_info=True)

    async def boot(self) -> None:
        PyTgCallsSession.notice_displayed = True
        for ub in userbot.clients:
            client = PyTgCalls(ub, cache_duration=100)
            await client.start()
            self.clients.append(client)
            await self.decorators(client)
        logger.info("PyTgCalls client(s) started.")
