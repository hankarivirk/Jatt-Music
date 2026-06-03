# 🎵 Jatt Music Bot — Now Playing Card Generator
# Deep Purple & Gold Theme

import os
import aiohttp
from PIL import (Image, ImageDraw, ImageEnhance,
                 ImageFilter, ImageFont, ImageOps)

from jatt import config
from jatt.helpers import Track

# Theme colors
PURPLE_DARK   = (30, 10, 50)          # deep dark purple background tint
GOLD          = (255, 200, 50)         # gold accent
WHITE         = (255, 255, 255)
PURPLE_LIGHT  = (180, 120, 255)        # light purple for secondary text
BAR_BG        = (80, 40, 120)          # progress bar background
BAR_FG        = (200, 140, 255)        # progress bar fill


class Thumbnail:
    def __init__(self):
        self.rect  = (914, 514)
        self.mask  = Image.new("L", self.rect, 0)
        self.font1 = ImageFont.truetype("jatt/helpers/Raleway-Bold.ttf", 32)   # title
        self.font2 = ImageFont.truetype("jatt/helpers/Inter-Light.ttf", 26)    # subtitle
        self.font3 = ImageFont.truetype("jatt/helpers/Inter-Light.ttf", 22)    # small
        self.session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        await self.session.close()

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with self.session.get(url) as resp:
            with open(output_path, "wb") as f:
                f.write(await resp.read())
        return output_path

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        try:
            temp   = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"
            if os.path.exists(output):
                return output

            await self.save_thumb(temp, song.thumbnail)

            # --- Background: blurred + darkened with purple tint ---
            thumb = Image.open(temp).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
            blur  = thumb.filter(ImageFilter.GaussianBlur(28))
            dark  = ImageEnhance.Brightness(blur).enhance(0.30)

            # Overlay a deep purple gradient tint
            tint  = Image.new("RGBA", size, (*PURPLE_DARK, 140))
            bg    = Image.alpha_composite(dark.convert("RGBA"), tint)

            # --- Album art: rounded rect on right ---
            art = ImageOps.fit(
                Image.open(temp).convert("RGBA"),
                self.rect,
                method=Image.LANCZOS,
                centering=(0.5, 0.5),
            )
            ImageDraw.Draw(self.mask).rounded_rectangle(
                (0, 0, self.rect[0], self.rect[1]),
                radius=20,
                fill=255,
            )
            art.putalpha(self.mask)
            bg.paste(art, (290, 20), art)

            draw = ImageDraw.Draw(bg)

            # --- Gold top banner bar ---
            draw.rectangle([(0, 0), (size[0], 6)], fill=GOLD)

            # --- "JATT MUSIC BOT" watermark top-left ---
            draw.text((30, 18), "🎵 JATT MUSIC BOT", font=self.font3, fill=GOLD)

            # --- Song title ---
            title = song.title[:48] + ("…" if len(song.title) > 48 else "")
            draw.text((30, 560), title, font=self.font1, fill=WHITE)

            # --- Channel & views ---
            meta = f"{song.channel_name[:28]}  •  {song.view_count}"
            draw.text((30, 608), meta, font=self.font2, fill=PURPLE_LIGHT)

            # --- Progress bar ---
            bar_y  = 658
            bar_x0, bar_x1 = 30, size[0] - 30
            bar_h  = 7
            draw.rounded_rectangle(
                [(bar_x0, bar_y), (bar_x1, bar_y + bar_h)],
                radius=4, fill=BAR_BG,
            )
            # Draw a small filled section (decorative)
            draw.rounded_rectangle(
                [(bar_x0, bar_y), (bar_x0 + 60, bar_y + bar_h)],
                radius=4, fill=BAR_FG,
            )
            # Circle knob
            draw.ellipse(
                [(bar_x0 + 52, bar_y - 4), (bar_x0 + 68, bar_y + bar_h + 4)],
                fill=GOLD,
            )

            # --- Timestamps ---
            draw.text((bar_x0, bar_y + 14), "0:01", font=self.font3, fill=WHITE)
            dur_w = draw.textlength(song.duration, font=self.font3)
            draw.text((bar_x1 - dur_w, bar_y + 14), song.duration, font=self.font3, fill=WHITE)

            # --- Gold bottom bar ---
            draw.rectangle([(0, size[1] - 5), (size[0], size[1])], fill=GOLD)

            bg.convert("RGB").save(output)
            try:
                os.remove(temp)
            except Exception:
                pass
            return output

        except Exception:
            return config.DEFAULT_THUMB
