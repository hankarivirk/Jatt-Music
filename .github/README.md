<div align="center">

<h1>🎵 Jatt Music Bot</h1>

<b>Telegram Group Calls Streaming Bot</b><br>
Supports YouTube, Spotify, Apple Music, SoundCloud, Resso and M3U8 links.

<br><br>

<a href="https://github.com/hankarivirk/Jatt-Music/stargazers">
    <img src="https://img.shields.io/github/stars/hankarivirk/Jatt-Music?color=blueviolet&logo=github&logoColor=white&style=for-the-badge" alt="Stars"/>
</a>
<a href="https://github.com/hankarivirk/Jatt-Music/network/members">
    <img src="https://img.shields.io/github/forks/hankarivirk/Jatt-Music?color=blueviolet&logo=github&logoColor=white&style=for-the-badge" alt="Forks"/>
</a>
<a href="https://github.com/hankarivirk/Jatt-Music/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-blueviolet?style=for-the-badge" alt="License"/>
</a>
<a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/Written%20in-Python-blueviolet?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
</a>

<br><br>

> Stream high-quality, low-latency audio & video into Telegram Group Video Chats.<br>
> Built with **Python**, **Pyrogram**, and **Py-TgCalls** — optimized for reliability and easy deployment.

</div>

---

## 🔥 Features

- 🎧 Real-time low-latency audio streaming in **Telegram Group Video Chats**
- 🌐 Multi-platform support — **YouTube, Spotify, Apple Music, SoundCloud, Resso**
- 📋 Advanced queue management with auto-play
- ⚡ Fast and lightweight — minimal resource usage
- 🐳 Easy deployment on **Local, VPS, Docker, or Heroku**
- ❤️ Fully open-source and built with Python

---

## ☁️ Deployment

### ✔️ Prerequisites

- [Python 3.10+](https://www.python.org) installed
- [ffmpeg](https://ffmpeg.org/) installed on your system
- Required variables from [`sample.env`](https://github.com/hankarivirk/Jatt-Music/blob/main/sample.env)

---

### 🐧 Linux / macOS

```bash
git clone https://github.com/hankarivirk/Jatt-Music && cd Jatt-Music

# Install uv
curl -Ls https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Install dependencies
uv sync --frozen

# Configure environment variables
cp sample.env .env
nano .env  # Fill in your credentials

# Start the bot
bash start
```

---

### 🪟 Windows (PowerShell)

```powershell
git clone https://github.com/hankarivirk/Jatt-Music && cd Jatt-Music

# Install uv
irm https://astral.sh/uv/install.ps1 | iex

# Install dependencies
uv sync --frozen

# Configure environment variables
cp sample.env .env
# Edit .env with your credentials

# Start the bot
uv run python3 -m jatt
```

> 💡 Windows users can also use **Git Bash** or **WSL** to run `bash start`.

---

### 🚀 Deploy to Heroku

> Click the button below to deploy instantly on Heroku:

[![Deploy on Heroku](https://img.shields.io/badge/Deploy%20On%20Heroku-blueviolet?style=for-the-badge&logo=heroku)](https://dashboard.heroku.com/new?template=https://github.com/hankarivirk/Jatt-Music)

---

## ⚙️ Configuration

Copy `sample.env` to `.env` and fill in your values:

```env
API_ID=123456
API_HASH=abcdef1234567890
BOT_TOKEN=123456:ABC-DEF
OWNER_ID=8514683546
LOGGER_ID=-1001234567890
MONGO_URL=mongodb+srv://...
SESSION=BQgfh...AA
```

> 📝 See [`config.py`](https://github.com/hankarivirk/Jatt-Music/blob/main/config.py) for all available options.

---

## 🧐 Usage

1. Add the bot to your Telegram group.
2. Promote it to **Admin** with **Invite Users** permission.
3. Use the commands below to control playback:

```
/play  [song name or link]  →  Play audio in the video chat
/vplay [song name or link]  →  Play video in the video chat
/pause                      →  Pause playback
/resume                     →  Resume playback
/skip                       →  Skip to next track
/stop                       →  Stop playback
/seek                       →  Seek to a position
/queue                      →  Show current queue
```

---

## ❤️ Contributing

Contributions are always welcome!

1. Fork the repository.
2. Create your branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add your feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request.

---

## 🗒️ License

This project is licensed under the **MIT License** — see [LICENSE](https://github.com/hankarivirk/Jatt-Music/blob/main/LICENSE) for details.

---

## 🤝 Support & Updates

- 📢 [Updates Channel](https://t.me/HankariMusicUpdate)
- 💬 [Support Group](https://t.me/HankariMusicSupport)
- 👤 [Owner](https://t.me/HankariVirk)

---

## 👀 Acknowledgements

- Inspired by open-source Telegram music bots and the amazing developer community.
- Thanks to all [contributors](https://github.com/hankarivirk/Jatt-Music/graphs/contributors) who helped shape this project.

---

<div align="center">

⭐ **Enjoying the tunes? Star the repo** — it keeps the rhythm going!

</div>
