import asyncio
import os
import re
import random
import time
from difflib import SequenceMatcher

from py_yt import VideosSearch
from pyrogram import filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from jatt import app, db, lang
from jatt.helpers import Track, utils
from jatt.helpers._admins import is_admin

GENRES = {
    "punjabi": "best punjabi songs hits", "hindi": "best hindi bollywood songs",
    "english": "top english pop songs", "arabic": "best arabic pop songs",
    "turkish": "top turkish pop songs", "kpop": "best kpop songs",
    "spanish": "best reggaeton songs", "random": "top music hits worldwide",
    "rap": "best rap hip hop songs", "rock": "best rock songs",
    "pop": "best pop songs", "jazz": "best jazz music",
    "edm": "best edm electronic songs", "rnb": "best rnb soul songs",
    "country": "best country songs", "bhojpuri": "best bhojpuri songs hits",
    "tamil": "best tamil songs hits", "telugu": "best telugu songs hits",
    "kannada": "best kannada songs", "malayalam": "best malayalam songs",
    "marathi": "best marathi songs", "bengali": "best bengali songs",
    "urdu": "best urdu songs", "persian": "best persian songs",
    "thai": "best thai songs hits", "indonesian": "best indonesian songs",
    "filipino": "best opm songs hits", "french": "best french songs",
    "german": "best german songs", "italian": "best italian songs",
    "lofi": "best lofi chill songs", "classical": "best classical music",
    "bollywood": "top bollywood hits songs", "party": "best party anthems songs",
}

_games: dict[int, dict] = {}
_SONG_COOLDOWN = 1800
_recently_played: dict[int, dict[str, float]] = {}
_MIN_FILE_KB = 150
_CLIP_DURATION = 25
_HINT1_DELAY = 30
_HINT2_DELAY = 25
_ROUND_TIMEOUT = 90
MEDALS = ["🥇", "🥈", "🥉"]


def _mark_used(chat_id, song_id):
    if chat_id not in _recently_played:
        _recently_played[chat_id] = {}
    now = time.time()
    _recently_played[chat_id] = {k: v for k, v in _recently_played[chat_id].items() if now - v < _SONG_COOLDOWN}
    _recently_played[chat_id][song_id] = now


def _was_used(chat_id, song_id):
    ts = _recently_played.get(chat_id, {}).get(song_id)
    return ts is not None and (time.time() - ts) < _SONG_COOLDOWN


def _filter_pool(chat_id, pool, session_ids):
    fresh = [t for t in pool if t.id not in session_ids and not _was_used(chat_id, t.id)]
    if len(fresh) < 3: fresh = [t for t in pool if t.id not in session_ids]
    if len(fresh) < 3: fresh = pool[:]
    random.shuffle(fresh)
    return fresh


def _clean(s): return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()

def _similarity(a, b): return SequenceMatcher(None, a, b).ratio()

def _is_correct(answer, title):
    a, t = _clean(answer), _clean(title)
    if not a or len(a) < 2: return False
    if a in t or t in a: return True
    if _similarity(a, t) >= 0.75: return True
    t_words = [w for w in t.split() if len(w) > 2]
    a_words = set(a.split())
    if t_words:
        matched = sum(1 for w in t_words if w in a_words or any(_similarity(w, aw) >= 0.8 for aw in a_words if len(aw) > 2))
        if matched / len(t_words) >= 0.6: return True
    return False


def _hint(title, level):
    parts = []
    for w in title.split():
        if not w: continue
        if level == 1: parts.append(w[0] + ("_ " * (len(w) - 1)).rstrip())
        elif level == 2: parts.append("".join(c if i % 2 == 0 else "_" for i, c in enumerate(w)))
        else: parts.append(w)
    return "  ".join(parts)


def _get_ffmpeg_params(dur_sec):
    ss = min(45, dur_sec // 3) if dur_sec > 90 else (15 if dur_sec > 40 else 0)
    return f"-ss {ss} -t {_CLIP_DURATION}"


def _file_valid(path):
    try: return os.path.isfile(path) and os.path.getsize(path) > _MIN_FILE_KB * 1024
    except Exception: return False


async def _cancel_tasks(g):
    for k in ("hint_task", "round_task"):
        t = g.get(k)
        if t and not t.done(): t.cancel()


async def _end_game(chat_id):
    g = _games.pop(chat_id, None)
    if not g: return
    await _cancel_tasks(g)

    scores = sorted(g["scores"].items(), key=lambda x: x[1], reverse=True)
    lines = ["<b>🎵  Game Over  ·  Final Scores</b>\n"]
    for i, (uid, pts) in enumerate(scores[:10]):
        try: name = (await app.get_users(uid)).first_name[:20]
        except Exception: name = str(uid)
        medal = MEDALS[i] if i < 3 else f"{i + 1}."
        lines.append(f"  {medal}  {name}  —  <b>{pts}</b> pts")
        await db.add_game_score(chat_id, uid, pts)

    if not scores: lines.append("  ◈  No points scored this game.")
    lines.append(f"\n<i>Genre: {g['genre'].title()}  ·  {g['round']} rounds played</i>")
    try: await app.send_message(chat_id, "\n".join(lines))
    except Exception: pass


async def _round_timeout(chat_id):
    await asyncio.sleep(_ROUND_TIMEOUT)
    g = _games.get(chat_id)
    if not g or not g["active"] or g.get("answered"): return
    g["streak"] = {}
    title = (g["current"].title or "?")[:45]
    try: await app.send_message(chat_id, f"⏱  <b>Time's up!</b>  No one guessed.\n\n  ◈  The answer was  —  <b>{title}</b>")
    except Exception: pass
    await asyncio.sleep(4)
    asyncio.create_task(_next_round(chat_id))


async def _hint_timer(chat_id):
    for delay, level in [(_HINT1_DELAY, 1), (_HINT2_DELAY, 2)]:
        await asyncio.sleep(delay)
        g = _games.get(chat_id)
        if not g or not g["active"] or g.get("answered"): return
        h = _hint(g["current"].title or "", level)
        g["hint_level"] = level
        try: await app.send_message(chat_id, f"💡  <b>Hint {level}</b>  —  <code>{h}</code>")
        except Exception: return
    await asyncio.sleep(20)
    g = _games.get(chat_id)
    if not g or not g["active"] or g.get("answered"): return
    artist = getattr(g["current"], "channel_name", "") or ""
    if artist:
        try: await app.send_message(chat_id, f"🎤  <b>Artist hint</b>  —  <code>{artist}</code>")
        except Exception: pass


async def _next_round(chat_id):
    g = _games.get(chat_id)
    if not g or not g["active"]: return
    if g["round"] >= g["max_rounds"] or not g["pool"]: return await _end_game(chat_id)

    filtered = _filter_pool(chat_id, g["pool"], g["session_ids"])
    if not filtered: return await _end_game(chat_id)

    track = filtered[0]
    g["pool"] = [t for t in g["pool"] if t.id != track.id]
    g.update({"current": track, "answered": False, "hint_level": 0, "round": g["round"] + 1})
    g["session_ids"].add(track.id)

    top_line = ""
    if g["scores"]:
        leader_uid, leader_pts = max(g["scores"].items(), key=lambda x: x[1])
        try:
            u = await app.get_users(leader_uid)
            top_line = f"\n  ◈  Leading  —  <b>{u.first_name[:15]}</b>  ({leader_pts} pts)"
        except Exception: pass

    try:
        msg = await app.send_message(chat_id,
            f"🎵  <b>Round {g['round']}/{g['max_rounds']}</b>  ·  <b>{g['genre'].title()}</b>\n\n"
            f"  ◈  A {_CLIP_DURATION}s clip is playing in VC — guess the song!\n"
            f"  ◈  You have  <b>{_ROUND_TIMEOUT}s</b>  to answer{top_line}\n\n"
            f"  💡 Hints at 30s and 55s  ·  🔥 Streak bonus at 3 correct")
        g["msg_id"] = msg.id
    except Exception: return

    from jatt import yt
    attempts = 0
    while attempts < 3:
        if not track.file_path: track.file_path = await yt.download(track.id, video=False)
        if track.file_path and _file_valid(track.file_path): break
        track.file_path = None
        attempts += 1
        if g["pool"]:
            track = g["pool"].pop(0)
            g["current"] = track

    if not track.file_path or not _file_valid(track.file_path):
        try: await msg.edit_text("⚠️  Could not load track. Skipping...")
        except Exception: pass
        await asyncio.sleep(2)
        asyncio.create_task(_next_round(chat_id))
        return

    try:
        client = await db.get_assistant(chat_id)
        from pytgcalls import types as pt
        stream = pt.MediaStream(
            media_path=track.file_path,
            audio_parameters=pt.AudioQuality.HIGH,
            audio_flags=pt.MediaStream.Flags.REQUIRED,
            video_flags=pt.MediaStream.Flags.IGNORE,
            ffmpeg_parameters=_get_ffmpeg_params(track.duration_sec or 180),
        )
        await client.play(chat_id=chat_id, stream=stream, config=pt.GroupCallConfig(auto_start=False))
        _mark_used(chat_id, track.id)
    except Exception:
        try: await msg.edit_text("⚠️  VC error. Skipping round...")
        except Exception: pass
        await asyncio.sleep(2)
        asyncio.create_task(_next_round(chat_id))
        return

    g["hint_task"] = asyncio.create_task(_hint_timer(chat_id))
    g["round_task"] = asyncio.create_task(_round_timeout(chat_id))


@app.on_message(filters.command(["startgame", "sg", "game"]) & filters.group & ~app.bl_users)
@lang.language()
async def _startgame(_, m: types.Message):
    if not await is_admin(m.chat.id, m.from_user.id) and m.from_user.id not in app.sudoers:
        return await m.reply_text(m.lang["user_not_admin"])
    if m.chat.id in _games:
        return await m.reply_text("⚠️  A game is already running.  Use <code>/stopgame</code> first.")

    genre, rounds = "english", 10
    for a in m.command[1:]:
        if a.isdigit(): rounds = max(3, min(25, int(a)))
        elif len(a) >= 2: genre = a.lower()

    sent = await m.reply_text(f"🔍  Fetching  <b>{genre.title()}</b>  tracks...")
    query = GENRES.get(genre, f"best {genre} songs")
    try:
        data = (await VideosSearch(query, limit=30).next()).get("result", [])
    except Exception:
        return await sent.edit_text("✗  Could not fetch tracks. Try again later.")

    pool = []
    for r in data:
        try:
            dur = utils.to_seconds(r.get("duration", "0:00"))
            if not dur or dur < 45 or dur > 600: continue
            pool.append(Track(
                id=r["id"], title=r.get("title", "")[:60],
                channel_name=r.get("channel", {}).get("name", ""),
                duration=r.get("duration", "?"), duration_sec=dur,
                thumbnail=(r.get("thumbnails") or [{}])[-1].get("url", ""),
                url=r.get("link", ""),
            ))
        except Exception: continue

    random.shuffle(pool)
    if len(pool) < 3:
        return await sent.edit_text("✗  Not enough tracks found for this genre. Try another one.")

    _games[m.chat.id] = {
        "active": True, "round": 0, "max_rounds": rounds, "genre": genre,
        "pool": pool[:rounds + 8], "scores": {}, "streak": {}, "current": None,
        "answered": False, "hint_level": 0, "msg_id": 0,
        "hint_task": None, "round_task": None, "session_ids": set(),
        "started_by": m.from_user.id,
    }

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📋  View Genres", callback_data="game_genres"),
        InlineKeyboardButton("🏆  Leaderboard", callback_data=f"game_lb {m.chat.id}"),
    ]])
    await sent.edit_text(
        f"🎵  <b>Music Quiz  ·  Starting!</b>\n\n"
        f"  ◈  Genre    —  <b>{genre.title()}</b>\n"
        f"  ◈  Rounds   —  <b>{rounds}</b>\n"
        f"  ◈  Clip     —  <b>{_CLIP_DURATION}s</b>  per song\n"
        f"  ◈  Time     —  <b>{_ROUND_TIMEOUT}s</b>  to answer\n\n"
        f"<b>📊  Scoring</b>\n"
        f"  ◈  Correct answer        <b>+1 pt</b>\n"
        f"  ◈  Before first hint     <b>+1 bonus</b>\n"
        f"  ◈  3-answer streak       <b>+1 bonus</b>\n\n"
        f"<i>First round starts in 5 seconds...</i>",
        reply_markup=kb,
    )
    await asyncio.sleep(5)
    asyncio.create_task(_next_round(m.chat.id))


@app.on_message(filters.command(["stopgame", "endgame"]) & filters.group & ~app.bl_users)
@lang.language()
async def _stopgame(_, m: types.Message):
    if not await is_admin(m.chat.id, m.from_user.id) and m.from_user.id not in app.sudoers:
        return await m.reply_text(m.lang["user_not_admin"])
    if m.chat.id not in _games:
        return await m.reply_text("◈  No active game in this chat.")
    await _end_game(m.chat.id)


@app.on_message(filters.command(["score", "scores", "myscore"]) & filters.group & ~app.bl_users)
async def _score(_, m: types.Message):
    g = _games.get(m.chat.id)
    if not g: return await m.reply_text("◈  No active game right now.")
    scores = sorted(g["scores"].items(), key=lambda x: x[1], reverse=True)
    if not scores: return await m.reply_text("◈  No scores yet — guess the song!")
    lines = [f"<b>📊  Scores  ·  Round {g['round']}/{g['max_rounds']}</b>\n"]
    for i, (uid, pts) in enumerate(scores[:10], 1):
        try: name = (await app.get_users(uid)).first_name[:20]
        except Exception: name = str(uid)
        medal = MEDALS[i - 1] if i <= 3 else f"  {i}."
        lines.append(f"  {medal}  {name}  —  <b>{pts}</b> pts")
    await m.reply_text("\n".join(lines))


@app.on_message(filters.command(["leaderboard", "lb", "hall"]) & filters.group & ~app.bl_users)
async def _leaderboard(_, m: types.Message):
    sent = await m.reply_text("⏳  Loading leaderboard...")
    rows = await db.get_game_leaderboard(m.chat.id)
    if not rows:
        return await sent.edit_text("◈  No game history yet in this chat.\n\n<i>Play a game with /startgame to get on the board!</i>")
    lines = [f"<b>🏆  All-Time Leaderboard  ·  {m.chat.title}</b>\n"]
    for i, row in enumerate(rows):
        try: name = (await app.get_users(row["user_id"])).first_name[:20]
        except Exception: name = str(row["user_id"])
        medal = MEDALS[i] if i < 3 else f"  {i + 1}."
        lines.append(f"  {medal}  {name}  —  <b>{row['total']}</b> pts")
    await sent.edit_text("\n".join(lines))


@app.on_message(filters.command(["genres"]) & ~app.bl_users)
async def _genres(_, m: types.Message):
    cols = sorted(GENRES.keys())
    rows = [cols[i:i + 4] for i in range(0, len(cols), 4)]
    lines = ["<b>🎵  Available Genres</b>\n"]
    for row in rows: lines.append("  " + "   ".join(f"<code>{g}</code>" for g in row))
    lines.append(f"\n<b>Usage</b>  —  <code>/startgame [genre] [rounds]</code>")
    lines.append("<i>Custom genres work too, e.g. /startgame lofi 5</i>")
    await m.reply_text("\n".join(lines))


@app.on_message(filters.command(["gameskip", "gskip", "gs"]) & filters.group & ~app.bl_users)
@lang.language()
async def _gameskip(_, m: types.Message):
    if not await is_admin(m.chat.id, m.from_user.id) and m.from_user.id not in app.sudoers:
        return await m.reply_text(m.lang["user_not_admin"])
    g = _games.get(m.chat.id)
    if not g or not g["active"]: return await m.reply_text("◈  No active game.")
    if g.get("answered"): return await m.reply_text("◈  Round already answered — next one coming up.")
    await _cancel_tasks(g)
    g["answered"] = True
    g["streak"] = {}
    title = (g["current"].title or "?")[:45] if g["current"] else "?"
    await m.reply_text(f"⏭  Round skipped.\n\n  ◈  It was  —  <b>{title}</b>")
    await asyncio.sleep(3)
    asyncio.create_task(_next_round(m.chat.id))


@app.on_callback_query(filters.regex(r"^game_genres"))
async def _cb_genres(_, q: types.CallbackQuery):
    cols = sorted(GENRES.keys())
    rows = [cols[i:i + 4] for i in range(0, len(cols), 4)]
    lines = ["<b>🎵  Available Genres</b>\n"]
    for row in rows: lines.append("  " + "   ".join(f"<code>{g}</code>" for g in row))
    lines.append("\n<b>Usage</b>  —  <code>/startgame [genre] [rounds]</code>")
    await q.answer()
    await q.message.reply_text("\n".join(lines))


@app.on_callback_query(filters.regex(r"^game_lb"))
async def _cb_lb(_, q: types.CallbackQuery):
    await q.answer()
    parts = q.data.split()
    chat_id = int(parts[1]) if len(parts) > 1 else q.message.chat.id
    rows = await db.get_game_leaderboard(chat_id)
    if not rows: return await q.answer("No leaderboard yet.", show_alert=True)
    lines = ["<b>🏆  All-Time Leaderboard</b>\n"]
    for i, row in enumerate(rows[:5]):
        try: name = (await app.get_users(row["user_id"])).first_name[:18]
        except Exception: name = str(row["user_id"])
        medal = MEDALS[i] if i < 3 else f"  {i + 1}."
        lines.append(f"  {medal}  {name}  —  <b>{row['total']}</b> pts")
    await q.message.reply_text("\n".join(lines))


@app.on_message(filters.group & filters.text & ~app.bl_users, group=1)
async def _answer_listener(_, m: types.Message):
    if not m.from_user or m.from_user.is_bot or not m.text: return
    g = _games.get(m.chat.id)
    if not g or not g["active"] or g.get("answered") or not g.get("current"): return
    title = g["current"].title or ""
    if not title or not _is_correct(m.text, title): return

    g["answered"] = True
    await _cancel_tasks(g)
    uid = m.from_user.id

    streak = g["streak"].get(uid, 0) + 1
    g["streak"][uid] = streak
    for k in list(g["streak"]):
        if k != uid: g["streak"][k] = 0

    pts = 1
    speed_bonus = g["hint_level"] == 0
    streak_bonus = streak >= 3
    if speed_bonus: pts += 1
    if streak_bonus: pts += 1

    g["scores"][uid] = g["scores"].get(uid, 0) + pts
    total = g["scores"][uid]

    bonus_lines = ""
    if speed_bonus and pts > 1: bonus_lines += "\n  ⚡  <b>Speed bonus!</b>  Answered before any hint  (+1)"
    if streak_bonus: bonus_lines += f"\n  🔥  <b>Streak x{streak}!</b>  3 in a row  (+1)"

    remaining = g["max_rounds"] - g["round"]
    progress = f"  ◈  Rounds left  —  <b>{remaining}</b>" if remaining > 0 else ""

    await m.reply_text(
        f"✅  <b>{m.from_user.first_name}</b>  got it!  <b>+{pts} pt{'s' if pts > 1 else ''}</b>\n\n"
        f"  ◈  Song     —  <b>{title[:45]}</b>{bonus_lines}\n"
        f"  ◈  Total    —  <b>{total}</b> pts\n"
        f"{progress}\n\n<i>Next round in 4 seconds...</i>"
    )
    await asyncio.sleep(4)
    asyncio.create_task(_next_round(m.chat.id))


@app.on_message(filters.command(["resetlb", "resetleaderboard"]) & filters.group & ~app.bl_users)
@lang.language()
async def _resetlb(_, m: types.Message):
    if not await is_admin(m.chat.id, m.from_user.id) and m.from_user.id not in app.sudoers:
        return await m.reply_text(m.lang["user_not_admin"])
    await db.gamedb.delete_many({"chat_id": m.chat.id})
    await m.reply_text("🏆  <b>Leaderboard reset</b>  for this chat.")
