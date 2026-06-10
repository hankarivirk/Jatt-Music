import asyncio

from pyrogram import Client

from jatt import config, logger

_KEEPALIVE_INTERVAL = 240


class Userbot(Client):
    def __init__(self):
        self.clients = []
        clients = {"one": "SESSION1", "two": "SESSION2", "three": "SESSION3"}
        for key, string_key in clients.items():
            name = f"JattUB{key[-1]}"
            session = getattr(config, string_key)
            setattr(
                self,
                key,
                Client(
                    name=name,
                    api_id=config.API_ID,
                    api_hash=config.API_HASH,
                    session_string=session,
                ),
            )

    async def boot_client(self, num: int, ub: Client):
        clients = {1: self.one, 2: self.two, 3: self.three}
        client = clients[num]
        await client.start()
        try:
            await client.send_message(config.LOGGER_ID, f"🎵 Assistant {num} started")
        except Exception:
            raise SystemExit(f"Assistant {num} failed to send message in log group.")

        client.id = ub.me.id
        client.name = ub.me.first_name
        client.username = ub.me.username
        client.mention = ub.me.mention
        self.clients.append(client)
        logger.info(f"Assistant {num} started as @{client.username}")

    async def _reconnect(self, client: Client, num: int) -> None:
        logger.warning(f"Assistant {num} appears offline — reconnecting...")
        try:
            await client.stop()
        except Exception:
            pass
        await asyncio.sleep(3)
        try:
            await client.start()
            client.id = client.me.id
            client.name = client.me.first_name
            client.username = client.me.username
            client.mention = client.me.mention
            logger.info(f"Assistant {num} reconnected as @{client.username}")
        except Exception as e:
            logger.error(f"Assistant {num} reconnect failed: {e}")

    async def _keepalive(self) -> None:
        await asyncio.sleep(60)
        while True:
            await asyncio.sleep(_KEEPALIVE_INTERVAL)
            sessions = []
            if config.SESSION1:
                sessions.append((1, self.one))
            if config.SESSION2:
                sessions.append((2, self.two))
            if config.SESSION3:
                sessions.append((3, self.three))

            for num, client in sessions:
                try:
                    await client.get_me()
                except Exception as e:
                    logger.warning(f"Keepalive ping failed for assistant {num}: {e}")
                    asyncio.create_task(self._reconnect(client, num))

    async def boot(self):
        if config.SESSION1:
            await self.boot_client(1, self.one)
        if config.SESSION2:
            await self.boot_client(2, self.two)
        if config.SESSION3:
            await self.boot_client(3, self.three)
        asyncio.create_task(self._keepalive())
        logger.info("Assistant keepalive task started.")

    async def exit(self):
        if config.SESSION1:
            try:
                await self.one.stop()
            except Exception:
                pass
        if config.SESSION2:
            try:
                await self.two.stop()
            except Exception:
                pass
        if config.SESSION3:
            try:
                await self.three.stop()
            except Exception:
                pass
        logger.info("Assistants stopped.")
