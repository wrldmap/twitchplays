import asyncio
import time

from twitch.eventsub import ClientApp, Event, ChannelChatMessageEvent
import os

import web
from sql import Broadcaster

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

    # Inside your TwitchBot class (twbot.py)

    async def broadcast_chat_message(self, broadcaster: str, sender: str, message: str, id: int, vip: bool, mod: bool, editor: bool):
        if not web.WEB_SOCKET_CONNECTIONS:
            return

        # Construct the payload using clean, consistent keys
        payload = {
            "broadcaster": broadcaster,
            "sender": sender,
            "message": message,
            "id": id,
            "vip": vip,
            "mod": mod,
            "editor": editor
        }

        disconnected_clients = []
        for connection in web.WEB_SOCKET_CONNECTIONS:
            try:
                await connection.send_json(payload)
            except Exception:
                disconnected_clients.append(connection)

        for dead_client in disconnected_clients:
            if dead_client in web.WEB_SOCKET_CONNECTIONS:
                web.WEB_SOCKET_CONNECTIONS.remove(dead_client)