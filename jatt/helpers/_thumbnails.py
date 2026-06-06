# 🎵 Jatt Music Bot — Now Playing Card Generator
# Professional Dark Theme  ·  Deep Purple & Gold

import gc
import os
import re
import aiohttp
from PIL import (Image, ImageDraw, ImageEnhance,
                 ImageFilter, ImageFont, ImageOps)

from jatt import config
from jatt.helpers._dataclass import Track

# ── Palette ──────────────────────────────────────────────────────────────────
PURPLE_DARK   = (22,  8, 42)          # deep background tint
GOLD          = (255, 195, 40)         # primary gold accent
GOLD_DIM      = (200, 150, 30)         # dimmer gold for badges
WHITE         = (255, 255, 255)
PURPLE_LIGHT  = (185, 130, 255)        # secondary text
TEXT_DIM      = (180, 180, 200)        # meta-info text
BAR_BG        = (70,  35, 110)         # progress-bar background
BAR_FG        = (195, 130, 255)        # progress-bar fill
BADGE_BG      = (60,  25, 100)         # type-badge background
SHADOW_COLOR  = (0, 0, 0)             # drop-shadow for art


def _strip_html(text: str) -> str:
    """Strip HTML tags and return plain text."""
    return re.sub(r"<[^>]+>", "", text or "")


class Thumbnail:
    # Album-art canvas size — 960×540 keeps quality high while using 44 % less
    # RAM per generation than 1280×720 (important for Railway's 512 MB limit).
    ART_W = 330
    ART_H = 330
    ART_R = 20
    CANVAS = (960, 540)

    def __init__(self):
        self.font_title   = ImageFont.truetype("jatt/helpers/Raleway-Bold.ttf", 36)
        self.font_title2  = ImageFont.truetype("jatt/helpers/Raleway-Bold.ttf", 30)
        self.font_sub     = ImageFont.truetype("jatt/helpers/Inter-Light.ttf",  24)
        self.font_meta    = ImageFont.truetype("jatt/helpers/Inter-Light.ttf",  21)
        self.font_badge   = ImageFont.truetype("jatt/helpers/Inter-Light.ttf",  19)
        self.session: aiohttp.ClientSession | None = None

    # ── Session ───────────────────────────────────────────────────────────────
    async def start(self) -> None:
        self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self.session:
            await self.session.close()

    # ── Helpers ───────────────────────────────────────────────────────────────
    async def _fetch(self, path: str, url: str) -> str:
        async with self.session.get(url) as resp:
            with open(path, "wb") as f:
                f.write(await resp.read())
        return path

    @staticmethod
    def _make_art(src: str, w: int, h: int, radius: int) -> Image.Image:
        """Open, crop-fit, and round-corner an album-art image."""
        art = ImageOps.fit(
            Image.open(src).convert("RGBA"),
            (w, h),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (w, h)], radius=radius, fill=255)
        art.putalpha(mask)
        return art

    @staticmethod
    def _left_gradient(size: tuple[int, int]) -> Image.Image:
        """Dark left-side gradient for text legibility."""
        W, H = size
        grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(grad)
        limit = 580
        for x in range(limit):
            t = x / limit
            alpha = int(185 * (1 - t ** 2))
            draw.line([(x, 0), (x, H)], fill=(0, 0, 0, alpha))
        return grad

    @staticmethod
    def _wrap_title(title: str, max_line: int = 30) -> tuple[str, str]:
        """Split a long title into ≤2 lines."""
        if len(title) <= max_line:
            return title, ""
        # Try to break at last space before limit
        cut = title[:max_line].rfind(" ")
        if cut == -1:
            cut = max_line
        l1 = title[:cut].rstrip()
        l2 = title[cut:].strip()
        if len(l2) > max_line:
            l2 = l2[:max_line - 1] + "…"
        return l1, l2

    # ── Main generator ────────────────────────────────────────────────────────
    async def generate(self, song: Track, size: tuple[int, int] = CANVAS) -> str:
        try:
            W, H = size
            os.makedirs("cache", exist_ok=True)
            temp   = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"

            if os.path.exists(output):
                return output

            await self._fetch(temp, song.thumbnail)

            # ── Background: blur + darken + purple tint ──────────────────────
            raw  = Image.open(temp).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
            blur = raw.filter(ImageFilter.GaussianBlur(22))
            dark = ImageEnhance.Brightness(blur).enhance(0.28)
            tint = Image.new("RGBA", size, (*PURPLE_DARK, 155))
            bg   = Image.alpha_composite(dark.convert("RGBA"), tint)

            # ── Left gradient overlay ────────────────────────────────────────
            bg = Image.alpha_composite(bg, self._left_gradient(size))

            draw = ImageDraw.Draw(bg)

            # ── Gold accent bars ─────────────────────────────────────────────
            draw.rectangle([(0, 0), (W, 5)], fill=GOLD)
            draw.rectangle([(0, H - 4), (W, H)], fill=GOLD)

            # ── Watermark ────────────────────────────────────────────────────
            draw.text((28, 14), "🎵  JATT MUSIC BOT", font=self.font_badge, fill=GOLD)

            # ── Song title (1 or 2 lines) ────────────────────────────────────
            raw_title = _strip_html(song.title or "Unknown")
            line1, line2 = self._wrap_title(raw_title, max_line=26)

            if line2:
                draw.text((32, 60),  line1, font=self.font_title,  fill=WHITE)
                draw.text((32, 98),  line2, font=self.font_title2, fill=WHITE)
                y_after_title = 136
            else:
                draw.text((32, 68), line1, font=self.font_title, fill=WHITE)
                y_after_title = 114

            draw.rectangle([(32, y_after_title), (520, y_after_title + 2)], fill=GOLD_DIM)

            # ── Channel + views ──────────────────────────────────────────────
            channel = _strip_html(song.channel_name or "")[:30]
            views   = _strip_html(song.view_count or "")
            if channel:
                draw.text((32, y_after_title + 10), channel, font=self.font_sub, fill=PURPLE_LIGHT)
            if views:
                draw.text((32, y_after_title + 40), f"👁  {views}", font=self.font_meta, fill=TEXT_DIM)

            # ── Duration ─────────────────────────────────────────────────────
            dur_y = y_after_title + 76
            draw.text((32, dur_y), f"⏱  {song.duration}", font=self.font_meta, fill=WHITE)

            # ── Requested by ─────────────────────────────────────────────────
            if song.user:
                req_name = _strip_html(song.user)[:28]
                draw.text((32, dur_y + 26), f"👤  {req_name}", font=self.font_meta, fill=GOLD)

            # ── Type badge ────────────────────────────────────────────────────
            badge_text = "🎬  VIDEO" if song.video else "🎵  AUDIO"
            badge_y = dur_y + 62
            bw = int(draw.textlength(badge_text, font=self.font_badge)) + 20
            draw.rounded_rectangle([(32, badge_y), (32 + bw, badge_y + 28)], radius=7, fill=BADGE_BG)
            draw.rounded_rectangle([(32, badge_y), (32 + bw, badge_y + 28)], radius=7, outline=GOLD_DIM, width=1)
            draw.text((42, badge_y + 5), badge_text, font=self.font_badge, fill=GOLD)

            # ── Progress bar ─────────────────────────────────────────────────
            bar_y  = H - 72
            bar_x0, bar_x1, bar_h = 32, W - 32, 6
            draw.rounded_rectangle([(bar_x0, bar_y), (bar_x1, bar_y + bar_h)], radius=3, fill=BAR_BG)
            fill_end = bar_x0 + 36
            draw.rounded_rectangle([(bar_x0, bar_y), (fill_end, bar_y + bar_h)], radius=3, fill=BAR_FG)
            kx = fill_end
            draw.ellipse([(kx - 5, bar_y - 3), (kx + 5, bar_y + bar_h + 3)], fill=GOLD)
            draw.text((bar_x0, bar_y + 11), "0:00", font=self.font_meta, fill=WHITE)
            dur_w = int(draw.textlength(song.duration, font=self.font_meta))
            draw.text((bar_x1 - dur_w, bar_y + 11), song.duration, font=self.font_meta, fill=WHITE)

            # ── Album-art (right side) with drop-shadow ───────────────────────
            art_x, art_y = 596, 96
            sh = Image.new("RGBA", (self.ART_W + 24, self.ART_H + 24), (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle(
                [(12, 12), (self.ART_W + 12, self.ART_H + 12)],
                radius=self.ART_R, fill=(*SHADOW_COLOR, 130),
            )
            sh = sh.filter(ImageFilter.GaussianBlur(14))
            bg.paste(sh, (art_x - 12, art_y - 12), sh)
            art = self._make_art(temp, self.ART_W, self.ART_H, self.ART_R)
            bg.paste(art, (art_x, art_y), art)

            # ── Save ──────────────────────────────────────────────────────────
            bg.convert("RGB").save(output, quality=95)

            # Explicitly close all PIL images to free RAM immediately
            for _img in (raw, blur, dark, tint, bg, art):
                try:
                    _img.close()
                except Exception:
                    pass
            gc.collect()

            try:
                os.remove(temp)
            except OSError:
                pass
            return output

        except Exception:
            return config.DEFAULT_THUMB
