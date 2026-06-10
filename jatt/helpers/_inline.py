from pyrogram import types
from jatt import app, config, lang
from jatt.core.lang import lang_codes


class Inline:
    def __init__(self):
        self.ikm = types.InlineKeyboardMarkup
        self.ikb = types.InlineKeyboardButton

    def cancel_dl(self, text):
        return self.ikm([[self.ikb(f"✗  {text}", callback_data="cancel_dl")]])

    def controls(self, chat_id, status=None, timer=None, remove=False):
        kb = []
        if status:
            kb.append([self.ikb(status, callback_data=f"controls status {chat_id}")])
        elif timer:
            kb.append([self.ikb(timer, callback_data=f"controls status {chat_id}")])
        if not remove:
            kb.append([
                self.ikb("▷  Resume", callback_data=f"controls resume {chat_id}"),
                self.ikb("⏸  Pause",  callback_data=f"controls pause  {chat_id}"),
            ])
            kb.append([
                self.ikb("↺  Replay", callback_data=f"controls replay {chat_id}"),
                self.ikb("⏭  Skip",   callback_data=f"controls skip   {chat_id}"),
                self.ikb("■  Stop",   callback_data=f"controls stop   {chat_id}"),
            ])
        return self.ikm(kb)

    def help_markup(self, _lang: dict, back: bool = False):
        if back:
            return self.ikm([[
                self.ikb("◀  Back",  callback_data="help back"),
                self.ikb("✗  Close", callback_data="help close"),
            ]])
        cbs = ["admins","auth","blist","lang","ping","play","queue","stats","sudo","effects","limits","game"]
        btns = [self.ikb(_lang.get(f"help_{i}", cb.title()), callback_data=f"help {cb}")
                for i, cb in enumerate(cbs)]
        rows = [btns[i:i+2] for i in range(0, len(btns), 2)]
        return self.ikm(rows)

    def lang_markup(self, _lang: str):
        langs = lang.get_languages()
        btns = [
            self.ikb(f"{'✓  ' if code == _lang else ''}{name}",
                     callback_data=f"lang_change {code}")
            for code, name in langs.items()
        ]
        return self.ikm([btns[i:i+2] for i in range(0, len(btns), 2)])

    def ping_markup(self, text):
        return self.ikm([[self.ikb(f"◈  {text}", url=config.SUPPORT_CHAT)]])

    def play_queued(self, chat_id, item_id, _text):
        return self.ikm([[self.ikb(f"▷  {_text}", callback_data=f"controls force {chat_id} {item_id}")]])

    def queue_markup(self, chat_id, _text, playing):
        action = "pause" if playing else "resume"
        icon   = "⏸  Pause" if playing else "▷  Resume"
        return self.ikm([[self.ikb(icon, callback_data=f"controls {action} {chat_id} q")]])

    def settings_markup(self, lang, admin_only, cmd_delete, language, chat_id):
        on, off = "●  On", "○  Off"
        return self.ikm([
            [self.ikb("Play Mode",       callback_data="settings"),
             self.ikb(on if admin_only  else off, callback_data="settings play")],
            [self.ikb("Delete Commands", callback_data="settings"),
             self.ikb(on if cmd_delete  else off, callback_data="settings delete")],
            [self.ikb("Language",        callback_data="settings"),
             self.ikb(lang_codes[language], callback_data="language")],
        ])

    def start_key(self, lang: dict, private: bool = False):
        rows = [
            [self.ikb("＋  Add to Group", url=f"https://t.me/{app.username}?startgroup=true")],
            [self.ikb("◈  Support", url=config.SUPPORT_CHAT),
             self.ikb("◈  Channel", url=config.SUPPORT_CHANNEL)],
            [self.ikb("◈  Help", callback_data="help")],
        ]
        if private:
            rows.append([self.ikb("◈  Source Code", url="https://github.com/JattDevs/JattMusicBot")])
        else:
            rows.append([self.ikb("◎  Language", callback_data="language")])
        return self.ikm(rows)

    def yt_key(self, link: str):
        return self.ikm([[
            self.ikb("⎘  Copy Link", copy_text=link),
            self.ikb("↗  YouTube",   url=link),
        ]])
