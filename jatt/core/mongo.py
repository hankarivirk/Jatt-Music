from random import randint
from time import time

from pymongo import AsyncMongoClient

from jatt import config, logger, userbot


class MongoDB:
    def __init__(self):
        self.mongo = AsyncMongoClient(
            config.MONGO_URL,
            serverSelectionTimeoutMS=12500,
            maxPoolSize=20, minPoolSize=2,
            connectTimeoutMS=5000, socketTimeoutMS=15000,
            retryWrites=True, retryReads=True,
        )
        self.db = self.mongo.Anon

        self.admin_list = {}
        self.active_calls = {}
        self.admin_play = []
        self.blacklisted = []
        self.cmd_delete = set()
        self.loop = {}
        self.notified = []
        self.cache = self.db.cache
        self.logger = False

        self.assistant = {}
        self.assistantdb = self.db.assistant

        self.auth = {}
        self.authdb = self.db.auth

        self.chats = []
        self.chatsdb = self.db.chats

        self.lang = {}
        self.langdb = self.db.lang

        self.users = []
        self.usersdb = self.db.users

        self.historydb   = self.db.history
        self.topdb       = self.db.top_tracks
        self.botdb       = self.db.bot_settings
        self.statsdb     = self.db.play_stats
        self.localbansdb = self.db.local_bans
        self.gamedb      = self.db.game_scores

        self._setlimit:  dict[int, int]  = {}
        self._queuemax:  dict[int, int]  = {}
        self._queuelock: dict[int, bool] = {}
        self._autoplay:  dict[int, bool] = {}
        self._localbans: dict[int, set]  = {}
        self._vol_cache: dict[int, int]  = {}
        self.prefix:     dict[int, str]  = {}
        self._maintenance: bool | None   = None

    async def connect(self):
        try:
            start = time()
            await self.mongo.admin.command("ping")
            logger.info(f"Database connection successful. ({time() - start:.2f}s)")
            await self.load_cache()
        except Exception as e:
            raise SystemExit(f"Database connection failed: {type(e).__name__}") from e

    async def close(self):
        await self.mongo.close()
        logger.info("Database connection closed.")

    async def get_call(self, chat_id): return chat_id in self.active_calls
    async def add_call(self, chat_id): self.active_calls[chat_id] = 1
    async def remove_call(self, chat_id): self.active_calls.pop(chat_id, None)

    async def playing(self, chat_id, paused=None):
        if paused is not None:
            self.active_calls[chat_id] = int(not paused)
        return bool(self.active_calls.get(chat_id, 0))

    async def get_admins(self, chat_id, reload=False):
        from jatt.helpers._admins import reload_admins
        if chat_id not in self.admin_list or reload:
            self.admin_list[chat_id] = await reload_admins(chat_id)
        return self.admin_list[chat_id]

    async def get_loop(self, chat_id): return self.loop.get(chat_id, 0)
    async def set_loop(self, chat_id, count): self.loop[chat_id] = count

    async def _get_auth(self, chat_id):
        if chat_id not in self.auth:
            doc = await self.authdb.find_one({"_id": chat_id}) or {}
            self.auth[chat_id] = set(doc.get("user_ids", []))
        return self.auth[chat_id]

    async def is_auth(self, chat_id, user_id): return user_id in await self._get_auth(chat_id)

    async def add_auth(self, chat_id, user_id):
        users = await self._get_auth(chat_id)
        if user_id not in users:
            users.add(user_id)
            await self.authdb.update_one({"_id": chat_id}, {"$addToSet": {"user_ids": user_id}}, upsert=True)

    async def rm_auth(self, chat_id, user_id):
        users = await self._get_auth(chat_id)
        if user_id in users:
            users.discard(user_id)
            await self.authdb.update_one({"_id": chat_id}, {"$pull": {"user_ids": user_id}})

    async def set_assistant(self, chat_id):
        num = randint(1, len(userbot.clients))
        await self.assistantdb.update_one({"_id": chat_id}, {"$set": {"num": num}}, upsert=True)
        self.assistant[chat_id] = num
        return num

    async def get_assistant(self, chat_id):
        from jatt import jatt
        if chat_id not in self.assistant:
            doc = await self.assistantdb.find_one({"_id": chat_id})
            num = doc["num"] if doc else None
            if not num or num > len(jatt.clients):
                num = await self.set_assistant(chat_id)
            self.assistant[chat_id] = num
        return jatt.clients[self.assistant[chat_id] - 1]

    async def get_client(self, chat_id):
        if chat_id not in self.assistant:
            await self.get_assistant(chat_id)
        num = self.assistant[chat_id]
        if num > len(userbot.clients):
            num = await self.set_assistant(chat_id)
            self.assistant[chat_id] = num
        return {1: userbot.one, 2: userbot.two, 3: userbot.three}.get(num)

    async def add_blacklist(self, chat_id):
        if str(chat_id).startswith("-"):
            self.blacklisted.append(chat_id)
            return await self.cache.update_one({"_id": "bl_chats"}, {"$addToSet": {"chat_ids": chat_id}}, upsert=True)
        await self.cache.update_one({"_id": "bl_users"}, {"$addToSet": {"user_ids": chat_id}}, upsert=True)

    async def del_blacklist(self, chat_id):
        if str(chat_id).startswith("-"):
            try: self.blacklisted.remove(chat_id)
            except ValueError: pass
            return await self.cache.update_one({"_id": "bl_chats"}, {"$pull": {"chat_ids": chat_id}})
        await self.cache.update_one({"_id": "bl_users"}, {"$pull": {"user_ids": chat_id}})

    async def get_blacklisted(self, chat=False):
        if chat:
            if not self.blacklisted:
                doc = await self.cache.find_one({"_id": "bl_chats"})
                self.blacklisted.extend(doc.get("chat_ids", []) if doc else [])
            return self.blacklisted
        doc = await self.cache.find_one({"_id": "bl_users"})
        return doc.get("user_ids", []) if doc else []

    async def is_chat(self, chat_id): return chat_id in self.chats

    async def add_chat(self, chat_id):
        if not await self.is_chat(chat_id):
            self.chats.append(chat_id)
            await self.chatsdb.insert_one({"_id": chat_id})

    async def rm_chat(self, chat_id):
        if await self.is_chat(chat_id):
            self.chats.remove(chat_id)
            await self.chatsdb.delete_one({"_id": chat_id})

    async def get_chats(self):
        if not self.chats:
            self.chats.extend([c["_id"] async for c in self.chatsdb.find()])
        return self.chats

    async def get_cmd_delete(self, chat_id):
        if chat_id not in self.cmd_delete:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("cmd_delete"):
                self.cmd_delete.add(chat_id)
        return chat_id in self.cmd_delete

    async def set_cmd_delete(self, chat_id, delete=False):
        if delete:
            self.cmd_delete.add(chat_id)
        else:
            self.cmd_delete.discard(chat_id)
        await self.chatsdb.update_one({"_id": chat_id}, {"$set": {"cmd_delete": delete}}, upsert=True)

    async def set_lang(self, chat_id, lang_code):
        await self.langdb.update_one({"_id": chat_id}, {"$set": {"lang": lang_code}}, upsert=True)
        self.lang[chat_id] = lang_code

    async def get_lang(self, chat_id):
        if chat_id not in self.lang:
            doc = await self.langdb.find_one({"_id": chat_id})
            self.lang[chat_id] = doc["lang"] if doc else config.LANG_CODE
        return self.lang[chat_id]

    async def is_logger(self): return self.logger

    async def get_logger(self):
        doc = await self.cache.find_one({"_id": "logger"})
        if doc: self.logger = doc["status"]
        return self.logger

    async def set_logger(self, status):
        self.logger = status
        await self.cache.update_one({"_id": "logger"}, {"$set": {"status": status}}, upsert=True)

    async def get_play_mode(self, chat_id):
        if chat_id not in self.admin_play:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("admin_play"):
                self.admin_play.append(chat_id)
        return chat_id in self.admin_play

    async def set_play_mode(self, chat_id, remove=False):
        if remove:
            try: self.admin_play.remove(chat_id)
            except ValueError: pass
        elif chat_id not in self.admin_play:
            self.admin_play.append(chat_id)
        await self.chatsdb.update_one({"_id": chat_id}, {"$set": {"admin_play": not remove}}, upsert=True)

    async def add_sudo(self, user_id):
        await self.cache.update_one({"_id": "sudoers"}, {"$addToSet": {"user_ids": user_id}}, upsert=True)

    async def del_sudo(self, user_id):
        await self.cache.update_one({"_id": "sudoers"}, {"$pull": {"user_ids": user_id}})

    async def get_sudoers(self):
        doc = await self.cache.find_one({"_id": "sudoers"})
        return doc.get("user_ids", []) if doc else []

    async def is_user(self, user_id): return user_id in self.users

    async def add_user(self, user_id):
        if not await self.is_user(user_id):
            self.users.append(user_id)
            await self.usersdb.insert_one({"_id": user_id})

    async def rm_user(self, user_id):
        if await self.is_user(user_id):
            self.users.remove(user_id)
            await self.usersdb.delete_one({"_id": user_id})

    async def get_users(self):
        if not self.users:
            self.users.extend([u["_id"] async for u in self.usersdb.find()])
        return self.users

    async def add_history(self, chat_id, title, url, duration, user):
        entry = {"title": title, "url": url, "duration": duration, "user": user}
        await self.historydb.update_one(
            {"_id": chat_id},
            {"$push": {"tracks": {"$each": [entry], "$slice": -10}}},
            upsert=True,
        )

    async def get_history(self, chat_id):
        doc = await self.historydb.find_one({"_id": chat_id})
        return list(reversed(doc.get("tracks", []))) if doc else []

    async def clear_history(self, chat_id):
        await self.historydb.delete_one({"_id": chat_id})

    async def get_volume(self, chat_id):
        if chat_id in self._vol_cache: return self._vol_cache[chat_id]
        doc = await self.chatsdb.find_one({"_id": chat_id})
        vol = doc.get("volume", 100) if doc else 100
        self._vol_cache[chat_id] = vol
        return vol

    async def set_volume(self, chat_id, volume):
        self._vol_cache[chat_id] = volume
        await self.chatsdb.update_one({"_id": chat_id}, {"$set": {"volume": volume}}, upsert=True)

    async def increment_track(self, chat_id, title, url):
        import hashlib
        _id = hashlib.md5(f"{chat_id}:{url or title}".encode()).hexdigest()
        await self.topdb.update_one(
            {"_id": _id},
            {"$inc": {"count": 1}, "$set": {"title": title, "url": url, "chat_id": chat_id}},
            upsert=True,
        )

    async def get_top_tracks(self, chat_id, limit=10):
        cursor = self.topdb.find({"chat_id": chat_id}).sort("count", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_maintenance(self):
        if self._maintenance is not None: return self._maintenance
        doc = await self.botdb.find_one({"_id": "maintenance"})
        self._maintenance = bool(doc.get("on", False)) if doc else False
        return self._maintenance

    async def set_maintenance(self, status):
        self._maintenance = status
        await self.botdb.update_one({"_id": "maintenance"}, {"$set": {"on": status}}, upsert=True)

    async def add_user_play(self, chat_id, user_id):
        _id = f"{chat_id}:{user_id}"
        await self.statsdb.update_one(
            {"_id": _id},
            {"$inc": {"count": 1}, "$set": {"chat_id": chat_id, "user_id": user_id}},
            upsert=True,
        )

    async def get_user_plays(self, chat_id, user_id):
        doc = await self.statsdb.find_one({"_id": f"{chat_id}:{user_id}"})
        return doc.get("count", 0) if doc else 0

    async def get_chat_top_requesters(self, chat_id, limit=10):
        cursor = self.statsdb.find({"chat_id": chat_id}).sort("count", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_global_play_count(self):
        result = await self.statsdb.aggregate([{"$group": {"_id": None, "total": {"$sum": "$count"}}}]).to_list(length=1)
        return result[0]["total"] if result else 0

    async def get_setlimit(self, chat_id):
        if chat_id not in self._setlimit:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            self._setlimit[chat_id] = int(doc.get("setlimit", 0)) if doc else 0
        return self._setlimit[chat_id]

    async def set_chat_limit(self, chat_id, mins):
        self._setlimit[chat_id] = mins
        await self.chatsdb.update_one({"_id": chat_id}, {"$set": {"setlimit": mins}}, upsert=True)

    async def get_queue_max(self, chat_id):
        if chat_id not in self._queuemax:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            self._queuemax[chat_id] = int(doc.get("queuemax", 20)) if doc else 20
        return self._queuemax[chat_id]

    async def set_queue_max(self, chat_id, n):
        self._queuemax[chat_id] = n
        await self.chatsdb.update_one({"_id": chat_id}, {"$set": {"queuemax": n}}, upsert=True)

    async def get_queuelock(self, chat_id):
        if chat_id not in self._queuelock:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            self._queuelock[chat_id] = bool(doc.get("queuelock", False)) if doc else False
        return self._queuelock[chat_id]

    async def set_queuelock(self, chat_id, status):
        self._queuelock[chat_id] = status
        await self.chatsdb.update_one({"_id": chat_id}, {"$set": {"queuelock": status}}, upsert=True)

    async def get_autoplay(self, chat_id):
        if chat_id not in self._autoplay:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            self._autoplay[chat_id] = bool(doc.get("autoplay", False)) if doc else False
        return self._autoplay[chat_id]

    async def set_autoplay(self, chat_id, status):
        self._autoplay[chat_id] = status
        await self.chatsdb.update_one({"_id": chat_id}, {"$set": {"autoplay": status}}, upsert=True)

    async def _load_local_bans(self, chat_id):
        if chat_id not in self._localbans:
            doc = await self.localbansdb.find_one({"_id": chat_id})
            self._localbans[chat_id] = set(doc.get("users", [])) if doc else set()
        return self._localbans[chat_id]

    async def is_local_banned(self, chat_id, user_id): return user_id in await self._load_local_bans(chat_id)

    async def local_ban(self, chat_id, user_id):
        (await self._load_local_bans(chat_id)).add(user_id)
        await self.localbansdb.update_one({"_id": chat_id}, {"$addToSet": {"users": user_id}}, upsert=True)

    async def local_unban(self, chat_id, user_id):
        (await self._load_local_bans(chat_id)).discard(user_id)
        await self.localbansdb.update_one({"_id": chat_id}, {"$pull": {"users": user_id}})

    async def get_local_bans(self, chat_id): return list(await self._load_local_bans(chat_id))

    async def get_chat_play_count(self, chat_id):
        result = await self.statsdb.aggregate([
            {"$match": {"chat_id": chat_id}},
            {"$group": {"_id": None, "total": {"$sum": "$count"}}},
        ]).to_list(length=1)
        return result[0]["total"] if result else 0

    async def add_game_score(self, chat_id, user_id, points):
        _id = f"{chat_id}:{user_id}"
        await self.gamedb.update_one(
            {"_id": _id},
            {"$inc": {"total": points}, "$set": {"chat_id": chat_id, "user_id": user_id}},
            upsert=True,
        )

    async def get_game_leaderboard(self, chat_id, limit=10):
        cursor = self.gamedb.find({"chat_id": chat_id}).sort("total", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_prefix(self, chat_id):
        if chat_id not in self.prefix:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            self.prefix[chat_id] = doc.get("prefix", "/") if doc else "/"
        return self.prefix[chat_id]

    async def set_prefix(self, chat_id, prefix):
        self.prefix[chat_id] = prefix
        await self.chatsdb.update_one({"_id": chat_id}, {"$set": {"prefix": prefix}}, upsert=True)

    async def migrate_coll(self):
        logger.info("Migrating users and chats from old collections...")
        users, musers, mchats = [], [], []
        seen_chats, seen_users = set(), set()
        users.extend([u async for u in self.usersdb.find()])
        users.extend([u async for u in self.db.tgusersdb.find()])
        for user in users:
            _id = user.get("_id")
            user_id = _id if isinstance(_id, int) else int(user.get("user_id"))
            if user_id in seen_users: continue
            seen_users.add(user_id)
            musers.append({"_id": user_id})
        await self.usersdb.drop()
        await self.db.tgusersdb.drop()
        if musers: await self.usersdb.insert_many(musers)
        async for chat in self.chatsdb.find():
            _id = chat.get("_id")
            chat_id = _id if isinstance(_id, int) else int(chat.get("chat_id"))
            if chat_id in seen_chats: continue
            seen_chats.add(chat_id)
            mchats.append({"_id": chat_id})
        await self.chatsdb.drop()
        if mchats: await self.chatsdb.insert_many(mchats)
        await self.cache.insert_one({"_id": "migrated"})
        logger.info("Migration completed successfully.")

    async def load_cache(self):
        doc = await self.cache.find_one({"_id": "migrated"})
        if not doc: await self.migrate_coll()
        await self.get_chats()
        await self.get_users()
        await self.get_blacklisted(True)
        await self.get_logger()
        logger.info("Database cache loaded.")
