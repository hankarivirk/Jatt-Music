import os
import re
import glob
import shlex
import yt_dlp
import random
import asyncio
import aiohttp
from pathlib import Path
from typing import Callable

from py_yt import VideosSearch

from jatt import logger
from jatt.helpers import Track, utils

MAX_DOWNLOADS = 15
MAX_CACHE_MB  = 200
_AUDIO_EXTS   = ("webm", "opus", "m4a", "mp3")
_YT_ID_RE     = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _parse_extra_args(raw: str) -> dict:
    """Convert YT_DLP_EXTRA_ARGS string into yt-dlp option dict."""
    opts = {}
    if not raw:
        return opts
    tokens = shlex.split(raw)
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "--impersonate" and i + 1 < len(tokens):
            opts["impersonate"] = tokens[i + 1]; i += 2
        elif t == "--check-formats":
            opts["check_formats"] = "selected"; i += 1
        elif t == "--rm-cache-dir":
            opts["rm_cache_dir"] = True; i += 1
        elif t == "-4":
            opts["source_address"] = "0.0.0.0"; i += 1
        elif t == "-6":
            opts["source_address"] = "::"; i += 1
        else:
            i += 1
    return opts


class YouTube:
    def __init__(self):
        self.base       = "https://www.youtube.com/watch?v="
        self.cookies    = []
        self.checked    = False
        self.cookie_dir = "jatt/cookies"
        self.warned     = False
        self.sem        = asyncio.Semaphore(5)
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|(?:PL|RD|RDCLAK|UU|FL|OL)[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )
        self.iregex = re.compile(
            r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)"
            r"(?!/(watch\?v=[A-Za-z0-9_-]{11}|shorts/[A-Za-z0-9_-]{11}"
            r"|playlist\?list=|[A-Za-z0-9_-]{11}))\S*"
        )
        self._playlist_url_re = re.compile(
            r"(?:list=)((?:PL|RD|RDCLAK|UU|FL|OL)[A-Za-z0-9_-]+)"
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
        if len(files) > MAX_DOWNLOADS:
            for f in files[:len(files) - MAX_DOWNLOADS]:
                try: os.remove(f)
                except Exception: pass
            files = sorted(glob.glob("downloads/*"), key=os.path.getctime)
        total_mb = sum(os.path.getsize(f) for f in files if os.path.isfile(f)) / (1024 * 1024)
        while total_mb > MAX_CACHE_MB and files:
            try:
                total_mb -= os.path.getsize(files[0]) / (1024 * 1024)
                os.remove(files[0])
            except Exception:
                pass
            files.pop(0)

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def invalid(self, url: str) -> bool:
        return bool(re.match(self.iregex, url))

    def is_playlist_url(self, url: str) -> bool:
        return bool(self._playlist_url_re.search(url))

    def is_youtube_id(self, vid: str) -> bool:
        return bool(_YT_ID_RE.match(vid))

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
                title=(data.get("title") or "Unknown")[:50],
                thumbnail=(data.get("thumbnails") or [{}])[-1].get("url", "").split("?")[0],
                url=data.get("link"),
                view_count=data.get("viewCount", {}).get("short"),
                video=video,
            )
        return None

    async def ytmusic_search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        cookie  = self.get_cookies()
        ydl_opts = {
            "quiet": True, "no_warnings": True, "skip_download": True,
            "extract_flat": True, "nocheckcertificate": True,
            "cookiefile": cookie,
            "default_search": "https://music.youtube.com/search?q=",
        }
        def _search():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                    entries = (info or {}).get("entries", [])
                    return entries[0] if entries else None
                except Exception:
                    return None
        data = await asyncio.to_thread(_search)
        if not data or not data.get("id"):
            return await self.search(query, m_id, video)
        dur = int(data.get("duration") or 0)
        return Track(
            id=data["id"],
            channel_name=data.get("uploader") or data.get("channel") or "",
            duration=utils.seconds_to_str(dur),
            duration_sec=dur,
            message_id=m_id,
            title=(data.get("title") or "Unknown")[:50],
            thumbnail=(data.get("thumbnail") or ""),
            url=f"https://music.youtube.com/watch?v={data['id']}",
            view_count=str(data.get("view_count") or ""),
            video=video,
        )

    async def playlist(
        self,
        limit: int,
        user: str,
        url: str,
        video: bool,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> list:
        tracks  = []
        cookie  = self.get_cookies()
        ydl_opts = {
            "quiet": True, "no_warnings": True, "extract_flat": "in_playlist",
            "skip_download": True, "ignoreerrors": True,
            "cookiefile": cookie, "nocheckcertificate": True,
            "playlistend": limit if limit > 0 else None,
        }

        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                    return info.get("entries", []) if info else []
                except Exception:
                    return []

        entries = await asyncio.to_thread(_extract)
        total   = len([e for e in entries if e])

        for i, e in enumerate(entries):
            if not e or not e.get("id"):
                continue
            try:
                dur = int(e.get("duration") or 0)
                tracks.append(Track(
                    id=e["id"],
                    title=(e.get("title") or "Unknown")[:50],
                    channel_name=e.get("uploader") or e.get("channel") or "",
                    duration=utils.seconds_to_str(dur),
                    duration_sec=dur,
                    thumbnail=e.get("thumbnail") or "",
                    url=f"https://www.youtube.com/watch?v={e['id']}",
                    user=user,
                    video=video,
                ))
            except Exception:
                continue

            if progress_cb and (i + 1) % 10 == 0:
                try: await progress_cb(len(tracks), total)
                except Exception: pass

        return tracks

    async def mix(self, video_id: str, user: str, video: bool, limit: int = 25) -> list:
        if not self.is_youtube_id(video_id):
            return []

        mix_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
        tracks  = await self.playlist(limit, user, mix_url, video)

        if not tracks:
            related_url = f"https://www.youtube.com/watch?v={video_id}"
            cookie      = self.get_cookies()
            ydl_opts    = {
                "quiet": True, "no_warnings": True, "skip_download": True,
                "extract_flat": True, "ignoreerrors": True,
                "cookiefile": cookie, "nocheckcertificate": True,
            }
            def _related():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        info = ydl.extract_info(related_url, download=False)
                        return (info or {}).get("entries", [])
                    except Exception:
                        return []
            entries = await asyncio.to_thread(_related)
            for e in (entries or [])[:limit]:
                if not e or not e.get("id"): continue
                try:
                    dur = int(e.get("duration") or 0)
                    tracks.append(Track(
                        id=e["id"],
                        title=(e.get("title") or "Unknown")[:50],
                        channel_name=e.get("uploader") or e.get("channel") or "",
                        duration=utils.seconds_to_str(dur),
                        duration_sec=dur,
                        thumbnail=e.get("thumbnail") or "",
                        url=f"https://www.youtube.com/watch?v={e['id']}",
                        user=user, video=video,
                    ))
                except Exception:
                    continue

        if not tracks:
            track = await self.search(video_id, 0, video=video)
            return [track] if track else []

        return tracks

    async def download(self, video_id: str, video: bool = False) -> str | None:
        url = self.base + video_id
        os.makedirs("downloads", exist_ok=True)

        if video:
            cached = f"downloads/{video_id}.mp4"
            if Path(cached).exists(): return cached
        else:
            for ext in _AUDIO_EXTS:
                cached = f"downloads/{video_id}.{ext}"
                if Path(cached).exists(): return cached

        from jatt import config as _cfg
        cookie       = self.get_cookies()
        extra        = _parse_extra_args(getattr(_cfg, "YT_DLP_EXTRA_ARGS", ""))
        po_token     = getattr(_cfg, "YT_PO_TOKEN", "")
        visitor_data = getattr(_cfg, "YT_VISITOR_DATA", "")
        base_opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True, "noplaylist": True, "geo_bypass": True,
            "no_warnings": True, "overwrites": False, "nocheckcertificate": True,
            "cookiefile": cookie,
            "concurrent_fragment_downloads": 4,
            "buffersize": 16384, "http_chunk_size": 10485760,
            "socket_timeout": 15, "retries": 5, "fragment_retries": 5,
            "noresizebuffer": True, "file_access_retries": 3,
            **extra,
        }
        if po_token and visitor_data:
            base_opts["extractor_args"] = {
                "youtube": {
                    "po_token": [f"web+{po_token}"],
                    "visitor_data": [visitor_data],
                }
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
            ydl_opts = {
                **base_opts,
                "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio",
            }

        def _download() -> str | None:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=True)
                    if info: return ydl.prepare_filename(info)
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
