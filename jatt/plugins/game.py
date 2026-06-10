import asyncio, re, random
from py_yt import VideosSearch
from pyrogram import filters, types
from jatt import app, db, jatt, lang, queue
from jatt.helpers import Track, utils
from jatt.helpers._admins import is_admin

GENRES = {
    "punjabi": "best punjabi songs hits",
    "hindi":   "best hindi bollywood songs",
    "english": "top english pop songs",
    "arabic":  "best arabic pop songs",
    "turkish": "top turkish pop songs",
    "kpop":    "best kpop songs",
    "spanish": "best reggaeton songs",
    "random":  "top music hits",
}

_games: dict[int, dict] = {}

def _clean(s): return re.sub(r"[^a-z0-9 ]","",s.lower()).strip()

def _is_correct(answer, title):
    a, t = _clean(answer), _clean(title)
    if not a or len(a) < 2: return False
    words = [w for w in t.split() if len(w) > 3]
    matched = sum(1 for w in words if w in a)
    return a in t or t in a or (len(words) >= 2 and matched >= 2)

def _hint(title, level):
    result = []
    for word in title.split():
        if level == 1:   result.append(word[0] + "_ " * (len(word)-1))
        elif level == 2:
            h = "".join(c if i%2==0 else "_" for i,c in enumerate(word))
            result.append(h)
        else: result.append(word)
    return " ".join(result)

async def _cancel_tasks(g):
    for k in ("hint_task","round_task"):
        t = g.get(k)
        if t and not t.done(): t.cancel()

async def _end_game(chat_id):
    g = _games.pop(chat_id, None)
    if not g: return
    await _cancel_tasks(g)
    try:
        client = await db.get_assistant(chat_id)
        await client.leave_call(chat_id)
    except Exception: pass
    scores = sorted(g["scores"].items(), key=lambda x: x[1], reverse=True)
    text = "<b>Game Over  ·  Final Scores</b>\n\n"
    medals = ["🥇","🥈","🥉"]
    for i,(uid,pts) in enumerate(scores[:10]):
        try: u = await app.get_users(uid); name = u.first_name[:20]
        except: name = str(uid)
        m = medals[i] if i < 3 else f"  {i+1}."
        text += f"  {m}  {name}  —  {pts} pts\n"
        await db.add_game_score(chat_id, uid, pts)
    if not scores: text += "  ◈  No points scored."
    try: await app.send_message(chat_id, text)
    except: pass

async def _round_timeout(chat_id):
    await asyncio.sleep(45)
    g = _games.get(chat_id)
    if not g or not g["active"] or g.get("answered"): return
    title = (g["current"].title or "Unknown")[:40]
    try: await app.send_message(chat_id,
        f"⏱  Time's up!\n\n  ◈  Answer  —  <b>{title}</b>")
    except: pass
    g["streak"] = {}
    await asyncio.sleep(3)
    asyncio.create_task(_next_round(chat_id))

async def _hint_timer(chat_id):
    g = _games.get(chat_id)
    if not g: return
    for level, delay in [(1,15),(2,10)]:
        await asyncio.sleep(delay)
        g = _games.get(chat_id)
        if not g or not g["active"] or g.get("answered"): return
        title = g["current"].title or ""
        g["hint_level"] = level
        try: await app.send_message(chat_id, f"💡  Hint {level}:  {_hint(title, level)}")
        except: pass
    await asyncio.sleep(10)
    g = _games.get(chat_id)
    if not g or not g["active"] or g.get("answered"): return
    artist = g["current"].channel_name or ""
    if artist:
        try: await app.send_message(chat_id, f"💡  Artist:  {artist}")
        except: pass

async def _next_round(chat_id):
    g = _games.get(chat_id)
    if not g or not g["active"]: return
    if g["round"] >= g["max_rounds"] or not g["pool"]:
        return await _end_game(chat_id)
    track = g["pool"].pop(0)
    g["current"] = track
    g["answered"] = False
    g["hint_level"] = 0
    g["round"] += 1
    try:
        msg = await app.send_message(chat_id,
            f"<b>Round {g['round']}/{g['max_rounds']}</b>  ·  Guess the song!\n\n"
            f"  ◈  Genre  —  {g['genre'].title()}\n  <i>10 seconds playing...</i>")
        g["msg_id"] = msg.id
    except: return
    from jatt import yt
    if not track.file_path:
        track.file_path = await yt.download(track.id, video=False)
    if not track.file_path:
        try: await app.send_message(chat_id,"⚠  Skipping track...")
        except: pass
        await asyncio.sleep(1)
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
            ffmpeg_parameters="-t 10",
        )
        await client.play(chat_id=chat_id, stream=stream,
                          config=pt.GroupCallConfig(auto_start=False))
    except Exception as e:
        try: await app.send_message(chat_id, f"⚠  VC error. Skipping...")
        except: pass
        await asyncio.sleep(1)
        asyncio.create_task(_next_round(chat_id))
        return
    g["hint_task"]  = asyncio.create_task(_hint_timer(chat_id))
    g["round_task"] = asyncio.create_task(_round_timeout(chat_id))

@app.on_message(filters.command(["startgame","sg"]) & filters.group & ~app.bl_users)
@lang.language()
async def _startgame(_, m: types.Message):
    if not await is_admin(m.chat.id, m.from_user.id) and m.from_user.id not in app.sudoers:
        return await m.reply_text(m.lang["user_not_admin"])
    if m.chat.id in _games:
        return await m.reply_text("⚠  Game already running. Use /stopgame first.")
    genre, rounds = "english", 10
    args = m.command[1:]
    for a in args:
        if a.isdigit(): rounds = max(3, min(20, int(a)))
        elif a.lower() in GENRES or len(a) > 2: genre = a.lower()
    sent = await m.reply_text(f"⌕  Fetching <b>{genre}</b> tracks...")
    query = GENRES.get(genre, f"best {genre} songs")
    try:
        s    = VideosSearch(query, limit=20)
        data = (await s.next()).get("result", [])
    except Exception:
        return await sent.edit_text("✗  Could not fetch tracks.")
    pool = []
    for r in data:
        try:
            dur = utils.to_seconds(r.get("duration","0:00"))
            if not dur or dur > 600: continue
            pool.append(Track(
                id=r["id"], title=r.get("title","")[:50],
                channel_name=r.get("channel",{}).get("name",""),
                duration=r.get("duration","?"), duration_sec=dur,
                thumbnail=r.get("thumbnails",[{}])[-1].get("url",""),
                url=r.get("link",""),
            ))
        except: continue
    random.shuffle(pool)
    if len(pool) < 3:
        return await sent.edit_text("✗  Not enough tracks found for this genre.")
    _games[m.chat.id] = {
        "active":True,"round":0,"max_rounds":rounds,"genre":genre,
        "pool":pool[:rounds+2],"scores":{},"streak":{},"current":None,
        "answered":False,"hint_level":0,"msg_id":0,
        "hint_task":None,"round_task":None,
    }
    await sent.edit_text(
        f"<b>Music Quiz  ·  Starting!</b>\n\n"
        f"  ◈  Genre   —  {genre.title()}\n"
        f"  ◈  Rounds  —  {rounds}\n\n"
        f"<i>Type the song title to score points!</i>"
    )
    await asyncio.sleep(3)
    asyncio.create_task(_next_round(m.chat.id))

@app.on_message(filters.command(["stopgame"]) & filters.group & ~app.bl_users)
@lang.language()
async def _stopgame(_, m: types.Message):
    if not await is_admin(m.chat.id, m.from_user.id) and m.from_user.id not in app.sudoers:
        return await m.reply_text(m.lang["user_not_admin"])
    if m.chat.id not in _games:
        return await m.reply_text("◈  No active game.")
    await _end_game(m.chat.id)

@app.on_message(filters.command(["score","scores"]) & filters.group & ~app.bl_users)
async def _score(_, m: types.Message):
    g = _games.get(m.chat.id)
    if not g: return await m.reply_text("◈  No active game.")
    scores = sorted(g["scores"].items(), key=lambda x:x[1], reverse=True)
    if not scores: return await m.reply_text("◈  No scores yet.")
    text = f"<b>Scores  ·  Round {g['round']}/{g['max_rounds']}</b>\n\n"
    for i,(uid,pts) in enumerate(scores[:10],1):
        try: u=await app.get_users(uid); name=u.first_name[:20]
        except: name=str(uid)
        text += f"  <b>{i}.</b>  {name}  —  {pts} pts\n"
    await m.reply_text(text)

@app.on_message(filters.command(["leaderboard","lb"]) & filters.group & ~app.bl_users)
async def _leaderboard(_, m: types.Message):
    sent = await m.reply_text("↓  Loading...")
    rows = await db.get_game_leaderboard(m.chat.id)
    if not rows: return await sent.edit_text("◈  No game history yet.")
    text = f"<b>Leaderboard  ·  {m.chat.title}</b>\n\n"
    medals = ["🥇","🥈","🥉"]
    for i,row in enumerate(rows):
        try: u=await app.get_users(row["user_id"]); name=u.first_name[:20]
        except: name=str(row["user_id"])
        medal = medals[i] if i < 3 else f"  {i+1}."
        text += f"  {medal}  {name}  —  {row['total']} pts\n"
    await sent.edit_text(text)

@app.on_message(filters.command(["genres"]) & filters.group & ~app.bl_users)
async def _genres(_, m: types.Message):
    text = "<b>Available Genres</b>\n\n"
    for k in GENRES:
        text += f"  ◈  <code>{k}</code>\n"
    text += "\n<b>Usage</b>  —  <code>/startgame [genre] [rounds]</code>"
    await m.reply_text(text)

@app.on_message(filters.group & filters.text & ~app.bl_users, group=1)
async def _answer_listener(_, m: types.Message):
    if not m.from_user or m.from_user.is_bot or not m.text: return
    g = _games.get(m.chat.id)
    if not g or not g["active"] or g.get("answered") or not g.get("current"): return
    if not _is_correct(m.text, g["current"].title or ""): return
    g["answered"] = True
    await _cancel_tasks(g)
    uid    = m.from_user.id
    streak = g["streak"].get(uid, 0) + 1
    g["streak"][uid] = streak
    for k in list(g["streak"]):
        if k != uid: g["streak"][k] = 0
    pts = 1
    if g["hint_level"] == 0: pts += 1
    if streak >= 3: pts += 1
    g["scores"][uid] = g["scores"].get(uid, 0) + pts
    streak_txt = f"  🔥 {streak} streak!" if streak >= 2 else ""
    await m.reply_text(
        f"✓  <b>{m.from_user.first_name}</b>  guessed it!  +{pts} pts{streak_txt}\n\n"
        f"  ◈  Answer  —  <b>{(g['current'].title or '')[:40]}</b>\n"
        f"  ◈  Total   —  {g['scores'][uid]} pts"
    )
    await asyncio.sleep(3)
    asyncio.create_task(_next_round(m.chat.id))
