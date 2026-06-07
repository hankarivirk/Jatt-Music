import gc, os, re, aiohttp
from PIL import (Image, ImageDraw, ImageEnhance,
                 ImageFilter, ImageFont, ImageOps)
from jatt import config
from jatt.helpers._dataclass import Track

# ── Brand palette ─────────────────────────────────────────────────────────────
BG_BASE      = (8,  4, 20)
ACCENT       = (160, 80, 255)
GOLD         = (255, 185, 30)
GOLD_DIM     = (190, 135, 20)
WHITE        = (255, 255, 255)
TEXT_SEC     = (165, 145, 210)
TEXT_DIM     = (110, 95, 150)
BAR_TRACK    = (40, 20, 70)
BAR_FILL     = (160, 80, 255)
SHADOW       = (0, 0, 0)
GLOW         = (140, 60, 240, 60)

_strip = lambda t: re.sub(r"<[^>]+>", "", t or "")


class Thumbnail:
    W, H   = 960, 540
    CANVAS = (960, 540)
    ART_D  = 280          # album art diameter (circle)
    ART_X  = 645          # circle centre-x
    ART_Y  = 240          # circle centre-y

    def __init__(self):
        R = "jatt/helpers/Raleway-Bold.ttf"
        I = "jatt/helpers/Inter-Light.ttf"
        self.f_title  = ImageFont.truetype(R, 34)
        self.f_title2 = ImageFont.truetype(R, 28)
        self.f_sub    = ImageFont.truetype(I, 22)
        self.f_meta   = ImageFont.truetype(I, 19)
        self.f_badge  = ImageFont.truetype(I, 17)
        self.f_tiny   = ImageFont.truetype(I, 15)
        self.session: aiohttp.ClientSession | None = None

    async def start(self):  self.session = aiohttp.ClientSession()
    async def close(self):
        if self.session: await self.session.close()

    async def _fetch(self, path, url):
        async with self.session.get(url) as r:
            open(path, "wb").write(await r.read())
        return path

    @staticmethod
    def _circle_art(src, d):
        art = ImageOps.fit(Image.open(src).convert("RGBA"), (d, d),
                           method=Image.Resampling.LANCZOS)
        mask = Image.new("L", (d, d), 0)
        ImageDraw.Draw(mask).ellipse([(0,0),(d,d)], fill=255)
        art.putalpha(mask)
        return art

    @staticmethod
    def _gradient_bg(size, blur_src):
        W, H = size
        base = Image.open(blur_src).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)
        dark = ImageEnhance.Brightness(base.filter(ImageFilter.GaussianBlur(28))).enhance(0.22)
        tint = Image.new("RGBA", (W, H), (*BG_BASE, 185))
        bg   = Image.alpha_composite(dark.convert("RGBA"), tint)
        # Left-to-right gradient overlay: opaque left, transparent at 65%
        grad = Image.new("RGBA", (W, H), (0,0,0,0))
        d    = ImageDraw.Draw(grad)
        for x in range(int(W * 0.68)):
            a = int(170 * (1 - (x / (W * 0.68)) ** 1.8))
            d.line([(x,0),(x,H)], fill=(0,0,0,a))
        return Image.alpha_composite(bg, grad)

    @staticmethod
    def _wrap(text, limit=28):
        if len(text) <= limit:
            return text, ""
        cut = text[:limit].rfind(" ")
        cut = cut if cut > 0 else limit
        return text[:cut].rstrip(), text[cut:].strip()[:limit]

    async def generate(self, song: Track, size=(960, 540)) -> str:
        try:
            W, H = size
            os.makedirs("cache", exist_ok=True)
            tmp = f"cache/tmp_{song.id}.jpg"
            out = f"cache/{song.id}.png"
            if os.path.exists(out): return out

            await self._fetch(tmp, song.thumbnail)
            bg   = self._gradient_bg(size, tmp)
            draw = ImageDraw.Draw(bg)

            # ── Gold top bar + branding ───────────────────────────────────────
            draw.rectangle([(0,0),(W,4)], fill=GOLD)
            draw.text((30, 14), "JATT MUSIC", font=self.f_badge, fill=GOLD)

            # ── NOW PLAYING badge (top-right area, left of art) ───────────────
            badge = "▶  NOW PLAYING"
            bw = int(draw.textlength(badge, self.f_tiny)) + 20
            bx, by = 30, 40
            draw.rounded_rectangle([(bx, by),(bx+bw, by+22)], 6,
                                   fill=(ACCENT[0],ACCENT[1],ACCENT[2],90))
            draw.rounded_rectangle([(bx, by),(bx+bw, by+22)], 6,
                                   outline=(*ACCENT, 180), width=1)
            draw.text((bx+10, by+4), badge, font=self.f_tiny, fill=WHITE)

            # ── Title ─────────────────────────────────────────────────────────
            raw   = _strip(song.title or "Unknown")
            l1,l2 = self._wrap(raw, 26)
            ty = 80
            draw.text((30, ty), l1, font=self.f_title, fill=WHITE)
            if l2:
                draw.text((30, ty+44), l2, font=self.f_title2, fill=WHITE)
                ty += 44
            ty += 48

            # ── Thin accent separator ─────────────────────────────────────────
            draw.rectangle([(30, ty),(420, ty+1)], fill=(*ACCENT, 130))
            ty += 10

            # ── Channel & views ───────────────────────────────────────────────
            ch = _strip(song.channel_name or "")[:32]
            vw = _strip(song.view_count or "")
            if ch:
                draw.text((30, ty), ch, font=self.f_sub, fill=TEXT_SEC)
                ty += 28
            if vw:
                draw.text((30, ty), f"{vw} views", font=self.f_meta, fill=TEXT_DIM)
                ty += 26

            # ── Duration + type pill ──────────────────────────────────────────
            ty += 6
            dur_txt  = f"  {song.duration}  "
            type_txt = "  VIDEO  " if song.video else "  AUDIO  "
            for txt, col in [(dur_txt, (50,30,90)), (type_txt, (ACCENT[0],ACCENT[1],ACCENT[2]))]:
                tw = int(draw.textlength(txt, self.f_badge)) + 4
                draw.rounded_rectangle([(30, ty),(30+tw, ty+24)], 6, fill=col)
                draw.text((30+4, ty+4), txt.strip(), font=self.f_badge, fill=WHITE)
                ty += 30

            # ── Requested by ─────────────────────────────────────────────────
            if song.user:
                ty += 4
                draw.text((30, ty), f"Requested by  {_strip(song.user)[:28]}",
                          font=self.f_meta, fill=GOLD)

            # ── Album art (circle) with glow ──────────────────────────────────
            cx, cy, d = self.ART_X, self.ART_Y, self.ART_D
            # Glow ring
            for r in range(8, 0, -1):
                alpha = int(55 * (r / 8))
                draw.ellipse(
                    [(cx-d//2-r, cy-d//2-r),(cx+d//2+r, cy+d//2+r)],
                    outline=(*ACCENT, alpha), width=2
                )
            # Shadow
            sh = Image.new("RGBA", (d+40, d+40), (0,0,0,0))
            ImageDraw.Draw(sh).ellipse([(14,14),(d+14,d+14)], fill=(*SHADOW,120))
            sh = sh.filter(ImageFilter.GaussianBlur(16))
            bg.paste(sh, (cx-d//2-20, cy-d//2-20), sh)
            # Art
            art = self._circle_art(tmp, d)
            bg.paste(art, (cx-d//2, cy-d//2), art)
            # Outer ring on art
            draw.ellipse([(cx-d//2-2, cy-d//2-2),(cx+d//2+2, cy+d//2+2)],
                         outline=(*GOLD, 180), width=2)

            # ── Progress bar (bottom band) ────────────────────────────────────
            band_y = H - 80
            draw.rectangle([(0, band_y),(W, H)], fill=(0,0,0,120))
            bx0, bx1, by0 = 30, W-30, band_y+28
            bh = 5
            # Track
            draw.rounded_rectangle([(bx0,by0),(bx1,by0+bh)], 3, fill=BAR_TRACK)
            # Fill (small dot at start = "just started")
            fill_x = bx0 + 44
            draw.rounded_rectangle([(bx0,by0),(fill_x,by0+bh)], 3, fill=BAR_FILL)
            # Knob
            kx = fill_x
            draw.ellipse([(kx-5,by0-4),(kx+5,by0+bh+4)], fill=GOLD)
            # Times
            draw.text((bx0, by0+12), "0:00", font=self.f_tiny, fill=TEXT_SEC)
            dw = int(draw.textlength(song.duration, self.f_tiny))
            draw.text((bx1-dw, by0+12), song.duration, font=self.f_tiny, fill=TEXT_SEC)

            # ── Gold bottom bar ───────────────────────────────────────────────
            draw.rectangle([(0,H-3),(W,H)], fill=GOLD)

            # ── Save & cleanup ────────────────────────────────────────────────
            bg.convert("RGB").save(out, quality=94)
            for img in (bg, art, sh): 
                try: img.close()
                except: pass
            gc.collect()
            try: os.remove(tmp)
            except: pass
            return out
        except Exception:
            return config.DEFAULT_THUMB
