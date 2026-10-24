import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass

import asqlite
import uvicorn
from twitch.eventsub import ClientApp, ChannelChatMessageEvent, Event
from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from twitch.oauth import DeviceCodeFlow, Scopes

from dotenv import load_dotenv

load_dotenv()
WEB_SOCKET_CONNECTIONS: list[WebSocket] = []

@dataclass(slots=True)
class Broadcaster:
    id: str
    login: str
    display_name: str

    access_token: str
    refresh_token: str

    enabled: bool = True

class BroadcasterStore:
    def __init__(self, path: str = "bot.db"):
        self.path = path

    async def setup(self):
        async with asqlite.connect(self.path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS broadcasters(
                    id TEXT PRIMARY KEY,
                    login TEXT NOT NULL,
                    display_name TEXT NOT NULL,

                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,

                    enabled INTEGER NOT NULL DEFAULT 1
                )
            """)
            await db.commit()

    async def add(self, broadcaster: Broadcaster):
        async with asqlite.connect(self.path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO broadcasters
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                broadcaster.id,
                broadcaster.login,
                broadcaster.display_name,
                broadcaster.access_token,
                broadcaster.refresh_token,
                broadcaster.enabled,
            ))
            await db.commit()

    async def get(self, broadcaster_id: str) -> Broadcaster | None:
        async with asqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT * FROM broadcasters WHERE id=?",
                (broadcaster_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return Broadcaster(
            id=row[0],
            login=row[1],
            display_name=row[2],
            access_token=row[3],
            refresh_token=row[4],
            enabled=bool(row[5]),
        )

    async def get_by_login(self, broadcaster_login: str) -> Broadcaster | None:
        async with asqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT * FROM broadcasters WHERE login = ?", (broadcaster_login,))
            row = await cursor.fetchone()

        if row is None:
            return None

        return Broadcaster(
            id=row[0],
            login=row[1],
            display_name=row[2],
            access_token=row[3],
            refresh_token=row[4],
            enabled=bool(row[5]),
        )

    async def all_enabled(self) -> list[Broadcaster]:
        async with asqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT * FROM broadcasters WHERE enabled=1"
            )
            rows = await cursor.fetchall()

        return [
            Broadcaster(
                id=row[0],
                login=row[1],
                display_name=row[2],
                access_token=row[3],
                refresh_token=row[4],
                enabled=True,
            )
            for row in rows
        ]

    async def remove(self, broadcaster_id: str):
        async with asqlite.connect(self.path) as db:
            await db.execute(
                "DELETE FROM broadcasters WHERE id=?",
                (broadcaster_id,),
            )
            await db.commit()

class OAuthServer:
    def __init__(self, store, bot):
        self.store = store
        self.bot = bot

        self.app = FastAPI(lifespan=self.lifespan)
        self.app.get("/login")(self.login)
        self.app.websocket("/ws")(self.websocket_endpoint)
        self.flow: DeviceCodeFlow = None

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        print("Starting DeviceCodeFlow active context...")
        async with DeviceCodeFlow(
                os.environ["CLIENT_ID"],
                os.environ["CLIENT_SECRET"]
        ) as active_flow:
            self.flow = active_flow
            yield

        print("DeviceCodeFlow active context terminated cleanly.")

    async def login(self, background_tasks: BackgroundTasks):
        if not self.flow:
            return JSONResponse(status_code=500, content={"error": "OAuth Flow context is not initialized yet."})

        try:
            device_code = await self.flow.request_device_code({
                Scopes.CHANNEL_BOT,
                Scopes.MODERATION_READ,
                Scopes.CHANNEL_READ_VIPS,
                Scopes.CHANNEL_READ_EDITORS
            })

            background_tasks.add_task(self.poll_for_token, device_code)

            return JSONResponse(content={
                "message": "Please authorize the bot by visiting the URL and entering the code.",
                "verification_uri": device_code.verification_uri,
                "user_code": device_code.user_code
            })

        except Exception as e:
            return JSONResponse(status_code=400, content={"error": f"Twitch API rejected request: {str(e)}"})

    async def poll_for_token(self, device_code):
        print(f"Waiting for user validation code: {device_code.user_code}")
        try:
            token = await self.flow.wait_for_device_token(device_code.device_code)
            print("Token retrieved successfully! Registering user to ClientApp...")

            user = await self.bot.add_user(token.access_token, token.refresh_token)
            infoget = await self.bot.application.get_users(user_ids=[user.id])

            if not infoget:
                print(f"User info lookup failed for ID: {user.id}")
                return

            info = infoget[0]

            broadcaster = Broadcaster(
                id=user.id,
                login=info.identity.login,
                display_name=info.identity.name,
                access_token=token.access_token,
                refresh_token=token.refresh_token
            )

            await self.store.add(broadcaster)
            await self.bot.subscribe(broadcaster)
            print(f"Successfully authorized and registered channel: {info.identity.login}!")

        except Exception as e:
            print(f"OAuth background polling failed: {e}")

    async def websocket_endpoint(self, websocket: WebSocket):
        await websocket.accept()

        WEB_SOCKET_CONNECTIONS.append(websocket)
        print(f"Client connected. Total connected: {len(WEB_SOCKET_CONNECTIONS)}")

        try:
            while True:
                raw_data = await websocket.receive_text()
                try:
                    data = json.loads(raw_data)
                    if data.get("action") == "send_chat":
                        await self.send_message_as_bot(data.get("broadcaster"), data.get("message"), data.get("reply_id"))
                except json.JSONDecodeError:
                    print(f"I can't parse that, boss. DecodeError: {raw_data}")
        except WebSocketDisconnect:
            if websocket in WEB_SOCKET_CONNECTIONS:
                WEB_SOCKET_CONNECTIONS.remove(websocket)
            print(f"Client disconnected. Total remaining: {len(WEB_SOCKET_CONNECTIONS)}")

    async def send_message_as_bot(self, broadcaster_name: str, message: str, reply_id: int):
        try:
            broadcaster_data = await self.store.get_by_login(broadcaster_name.lower())

            if not broadcaster_data:
                print(f"I'm sorry, but I don't recognize {broadcaster_name}. Make sure they are properly authorized with the application.")
                return

            await self.bot.b_user.send_chat_message(
                broadcaster_id=broadcaster_data.id,
                message=message,
                reply_message_id=reply_id
            )
            print(f"Bot has transmitted to [{broadcaster_name}], saying: {message}")

        except Exception as e:
            print(f"Failed to transmit back to Twitch: {e}")

class TwitchBot(ClientApp):
    permission_cache = {}

    async def refresh_channel_permissions_cache(self, broadcaster_name: str):
        now = time.time()
        cache = self.permission_cache.get(broadcaster_name.lower())

        if cache and (now - cache["last_updated"]) < 300:
            return

        try:
            editors_task = self.b_user.get_channel_editors()
            mods_task = self.b_user.get_moderators()
            vips_task = self.b_user.get_vips()

            editors_res, mods_res, vips_res = await asyncio.gather(editors_task, mods_task, vips_task, return_exceptions=True)

            editor_set = {editor.user.login.lower() for editor in editors_res} if not isinstance(editors_res, Exception) else set()
            mod_set = {mod.user_login.lower() for mod in mods_res} if not isinstance(mods_res, Exception) else set()
            vip_set = {vip.user_login.lower() for vip in vips_res} if not isinstance(vips_res, Exception) else set()

            self.permission_cache[broadcaster_name.lower()] = {
                "editors": editor_set,
                "mods": mod_set,
                "vips": vip_set,
                "last_updated": now
            }
            print(f"Refreshed permission cache for channel: {broadcaster_name}")

        except Exception as e:
            print(f"Failed to build permission cache for {broadcaster_name}: {e}")

    async def on_chat_message_v1(self, message: Event[ChannelChatMessageEvent]):
        try:
            broadcaster = message.event.broadcaster_user.name
            broadcaster_id = message.event.broadcaster_user.id
            chatter = message.event.chatter.name
            text = message.event.message.text
            id = message.event.message_id

            chatter_lower = chatter.lower()
            broadcaster_lower = broadcaster.lower()

            is_broadcaster = (chatter_lower == broadcaster_lower)

            await self.refresh_channel_permissions_cache(broadcaster)

            channel_cache = self.permission_cache.get(broadcaster_lower,
                                                      {"vips": set(), "mods": set(), "editors": set()})

            is_vip = chatter_lower in channel_cache["vips"] or is_broadcaster
            is_mod = chatter_lower in channel_cache["mods"] or is_broadcaster
            is_editor = chatter_lower in channel_cache["editors"] or is_broadcaster

            print(f"[#{broadcaster}] {chatter}: {text}")

            await self.broadcast_chat_message(
                broadcaster=broadcaster,
                sender=chatter,
                message=text,
                id=id,
                vip=is_vip,
                mod=is_mod,
                editor=is_editor
            )

        except Exception as e:
            print(f"Error parsing or broadcasting chat event: {e}")

    async def on_ready(self):
        self.b_user = await self.add_user(os.getenv('ACCESS_TOKEN'), os.getenv('REFRESH_TOKEN'))

    async def subscribe(self, broadcaster: Broadcaster):
        await self.eventsub.chat_message(
            broadcaster_user_id=broadcaster.id,
            user_id=self.b_user.id,
        )
        return broadcaster

    async def broadcast_chat_message(self, broadcaster: str, sender: str, message: str, id: int, vip: bool, mod: bool, editor: bool):
        if not WEB_SOCKET_CONNECTIONS:
            return

        payload = {
            "action": "recieve_chat",
            "broadcaster": broadcaster,
            "sender": sender,
            "message": message,
            "id": id,
            "vip": vip,
            "mod": mod,
            "editor": editor
        }

        disconnected_clients = []
        for connection in WEB_SOCKET_CONNECTIONS:
            try:
                await connection.send_json(payload)
            except Exception:
                disconnected_clients.append(connection)

        for dead_client in disconnected_clients:
            if dead_client in WEB_SOCKET_CONNECTIONS:
                WEB_SOCKET_CONNECTIONS.remove(dead_client)

async def main():
    store = BroadcasterStore()
    await store.setup()

    bot = TwitchBot(os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET'))
    bot_task = asyncio.create_task(bot.start(os.getenv('CONDUIT_ID'), shard_ids=(0,)))

    await asyncio.sleep(2)

    for broadcaster in await store.all_enabled():
        try:
            print(f"Subscribing to {broadcaster.login}")
            await bot.subscribe(broadcaster)
        except Exception as e:
            print(f"Failed to subscribe to pre-existing broadcaster {broadcaster.login}: {e}")

    oauth = OAuthServer(store, bot)
    config = uvicorn.Config(
        oauth.app,
        host="0.0.0.0",
        port=8080,
    )
    server = uvicorn.Server(config)

    await asyncio.gather(
        bot_task,
        server.serve(),
    )

asyncio.run(main())