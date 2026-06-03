<p align="center">
  <h1 align="center">🎵 Jatt Music Bot</h1>
  <p align="center">A powerful Telegram music bot — built different. 💜</p>
</p>

---

## Features

- 🎵 Play music from YouTube in Telegram voice chats
- 🎬 Video playback support
- 📋 Queue system (up to 20 tracks)
- 🖼 Now Playing cards with deep purple/gold theme
- 🌍 Multi-language support (12 languages)
- 👥 Multi-userbot support (up to 3 sessions)
- ⚙️ Per-group settings (play mode, cmd delete, language)
- 🔒 Blacklist system for users & chats
- 👑 Sudo user management

---

## Setup

### 1. Get your credentials
- `API_ID` & `API_HASH` → [my.telegram.org/apps](https://my.telegram.org/apps)
- `BOT_TOKEN` → [@BotFather](https://t.me/BotFather)
- `MONGO_URL` → [cloud.mongodb.com](https://cloud.mongodb.com)
- `SESSION` → [@StringFatherBot](https://t.me/StringFatherBot)

### 2. Configure
```bash
cp sample.env .env
# Fill in all values in .env
```

### 3. Install & Run
```bash
pip install -r requirements.txt
# or with uv:
uv sync
python -m jatt
```

---

## Commands

| Command | Description |
|---------|-------------|
| `/play [song/url]` | Play music in voice chat |
| `/vplay [song/url]` | Play music video |
| `/pause` | Pause playback |
| `/resume` | Resume playback |
| `/skip` | Skip current track |
| `/stop` | Stop and clear queue |
| `/queue` | Show current queue |
| `/seek [seconds]` | Seek forward |
| `/ping` | Bot status & ping |
| `/settings` | Group settings |
| `/lang` | Change language |

---

## Credits

Built on top of [AnonXMusic](https://github.com/AnonymousX1025/AnonXMusic) by AnonymousX1025.  
Rebranded & extended as **Jatt Music Bot** 🎵

---

<p align="center">Made with 💜 for the Jatt community</p>
