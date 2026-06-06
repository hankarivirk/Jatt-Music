# Copyright (c) 2025 JattDevs
# Licensed under the MIT License.
# This file is part of JattMusicBot

import os
import re
import glob
import yt_dlp
import random
import asyncio
import aiohttp
from pathlib import Path

from py_yt import Playlist, VideosSearch

from jatt import logger
from jatt.helpers import Track, utils

MAX_DOWNLOADS = 15          # max files to keep on disk
MAX_CACHE_MB  = 200         # hard cap: delete oldest files if folder exceeds this

# Audio extensions yt-dlp may produce (no postprocessor, raw download)
_AUDIO_EXTS = ("webm", "opus", "m4a", "mp3")


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.cookies = []
        self.checked = False
        self.cookie_dir = "jatt/cookies"
        self.warned = False
        # ── Increase to 5 concurrent downloads (was 2) ──
        self.sem = asyncio.Semaphore(5)
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )
        self.iregex = re.compile(
            r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)"
            r"(?!/(watch\?v=[A-Za-z0-9_-]{11}|shorts/[A-Za-z0-9_-]{11}"
            r"|playlist\?list=PL[A-Za-z0-9_-]+|[A-Za-z0-9_-]{11}))\S*"
        )

    def get_cookies(self):
        if not self.checked:
            for file in os.listdir(self.cookie_dir):
                if file.endswith(".txt"):
                    path = f"{self.cookie_dir}/{file}"
                    try:
                        with open(path, "r", errors="ignore") as f:
                            first_line = f.readline().strip()
                        if "Netscape" in first_line or first_line.startswith("#"):
                            self.cookies.append(path)
                        else:
                            logger.warning(f"Skipping invalid cookie file: {file}")
                    except Exception:
                        pass
            self.checked = True
        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("Cookies are missing; downloads might fail.")
            return None
        return random.choice(self.cookies)

    async def save_cookies(self, urls: list[str]) -> None:
        logger.info("Saving cookies from urls...")
        async with aiohttp.ClientSession() as session:
            for url in urls:
                name = url.split("/")[-1]
                link = "https://batbin.me/raw/" + name
                async with session.get(link) as resp:
                    resp.raise_for_status()
                    content = await resp.text()
                    if "Netscape HTTP Cookie File" not in content:
                        content = "# Netscape HTTP Cookie File\n" + content
                    with open(f"{self.cookie_dir}/{name}.txt", "w") as fw:
                        fw.write(content)
        logger.info(f"Cookies saved in {self.cookie_dir}.")

    def _cleanup_downloads(self):
        files = sorted(glob.glob("downloads/*"), key=os.path.getctime)

        # Count-based: keep at most MAX_DOWNLOADS files
        if len(files) > MAX_DOWNLOADS:
            for f in files[:len(files) - MAX_DOWNLOADS]:
                try:
                    os.remove(f)
                except Exception:
                    pass
            files = sorted(glob.glob("downloads/*"), key=os.path.getctime)

        # Size-based: if folder exceeds MAX_CACHE_MB, delete oldest until under limit
        total_mb = sum(os.path.getsize(f) for f in files if os.path.isfile(f)) / (1024 * 1024)
        while total_mb > MAX_CACHE_MB and files:
            try:
                removed_size = os.path.getsize(files[0]) / (1024 * 1024)
                os.remove(files[0])
                total_mb -= removed_size
            except Exception:
                pass
            files.pop(0)

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def invalid(self, url: str) -> bool:
        return bool(re.match(self.iregex, url))

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        try:
            _search = VideosSearch(query, limit=1, with_live=False)
            results = await _search.next()
        except Exception:
            return None
        if results and results["result"]:
            data = results["result"][0]
            return Track(
                id=data.get("id"),
                channel_name=data.get("channel", {}).get("name"),
                duration=data.get("duration"),
                duration_sec=utils.to_seconds(data.get("duration")),
                message_id=m_id,
                title=data.get("title")[:25],
                thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                url=data.get("link"),
                view_count=data.get("viewCount", {}).get("short"),
                video=video,
            )
        return None

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        tracks = []
        try:
            plist = await Playlist.get(url)
            for data in plist["videos"][:limit]:
                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("channel", {}).get("name", ""),
                    duration=data.get("duration"),
                    duration_sec=utils.to_seconds(data.get("duration")),
                    title=data.get("title")[:25],
                    thumbnail=data.get("thumbnails")[-1].get("url").split("?")[0],
                    url=data.get("link").split("&list=")[0],
                    user=user,
                    view_count="",
                    video=video,
                )
                tracks.append(track)
        except Exception:
            pass
        return tracks

    async def download(self, video_id: str, video: bool = False) -> str | None:
        url = self.base + video_id
        os.makedirs("downloads", exist_ok=True)

        # ── Cache hit: check all possible audio extensions ──────────────
        if video:
            cached = f"downloads/{video_id}.mp4"
            if Path(cached).exists():
                return cached
        else:
            for ext in _AUDIO_EXTS:
                cached = f"downloads/{video_id}.{ext}"
                if Path(cached).exists():
                    return cached

        cookie = self.get_cookies()

        # ── Shared yt-dlp options (tuned for speed) ──────────────────────
        base_opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True,
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": True,
            "overwrites": False,
            "nocheckcertificate": True,
            "cookiefile": cookie,
            # ── Speed knobs ──
            "concurrent_fragment_downloads": 4,   # was 1  → 4x faster on DASH
            "buffersize": 16384,                   # was 1024
            "http_chunk_size": 10485760,           # 10 MB chunks
            "socket_timeout": 15,
            "retries": 5,
            "fragment_retries": 5,
            "noresizebuffer": True,
            "file_access_retries": 3,
        }

        if video:
            ydl_opts = {
                **base_opts,
                "format": (
                    "(bestvideo[height<=?720][width<=?1280][ext=mp4]"
                    "/bestvideo[height<=?720])"
                    "+(bestaudio[ext=m4a]/bestaudio)/best"
                ),
                "merge_output_format": "mp4",
            }
        else:
            # ── NO FFmpegExtractAudio postprocessor ──────────────────────
            # Download raw webm/opus directly from YouTube.
            # Skips the FFmpeg re-encode step → saves 2-5 seconds per song.
            ydl_opts = {
                **base_opts,
                "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio",
            }

        def _download() -> str | None:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=True)
                    if info:
                        return ydl.prepare_filename(info)
                except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError):
                    return None
                except Exception as ex:
                    logger.warning("Download failed: %s", ex)
                    return None
            return None

        async with self.sem:
            result = await asyncio.to_thread(_download)

        self._cleanup_downloads()
        return result
