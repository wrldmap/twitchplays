import asyncio
import logging
import os

import uvicorn
from twbot import TwitchBot
from sql import BroadcasterStore
from dotenv import load_dotenv
from web import OAuthServer

load_dotenv()

async def main():
    store = BroadcasterStore()
    await store.setup()

    bot = TwitchBot(os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET'))
    bot_task = asyncio.create_task(bot.start(os.getenv('CONDUIT_ID'), shard_ids=(0,)))

    await asyncio.sleep(2)

    for broadcaster in await store.all_enabled():
        try:
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