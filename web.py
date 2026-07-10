import json
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from twitch.oauth import DeviceCodeFlow, Scopes
from sql import Broadcaster

WEB_SOCKET_CONNECTIONS: list[WebSocket] = []

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