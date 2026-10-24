from twitch.oauth import DeviceCodeFlow, Scopes
from twitch import App
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

def save_to_env(updates: dict, path='.env'):
    lines = []
    if os.path.exists(path):
        with open(path, 'f') as f:
            lines = f.readlines()

    keys_overwritten = set()

    for i, line in enumerate(lines):
        stripped_line = line.strip()
        if "=" in stripped_line and not stripped_line.startswith("#"):
            key, _ = stripped_line.split("=", 1)
            key = key.strip()

            if key in updates:
                lines[i] = f"{key}={updates[key]}\n"
                keys_overwritten.add(key)

    if lines and not lines[-1].endswith('\n'):
        lines[-1] += '\n'

    for key, value in updates.items():
        if key not in keys_overwritten:
            lines.append(f"{key}={value}\n")

    with open(path, 'w') as f:
        f.writelines(lines)

async def main():
    cid = input("Paste the Client ID that Twitch gave you:")
    csec = input("Paste the Client Secret that you generated:")
    save_to_env({'CLIENT_ID': cid, 'CLIENT_SECRET': csec})

    async with DeviceCodeFlow(cid, csec) as flow:
        print("Authing the BOT ACCOUNT - do NOT use your main Twitch account!")
        device_code = await flow.request_device_code({
            Scopes.USER_READ_CHAT,
            Scopes.USER_WRITE_CHAT,
            Scopes.MODERATOR_READ_FOLLOWERS,
            Scopes.USER_BOT
        })
        print(f"Go to: {device_code.verification_uri}")
        print(f"Enter code: {device_code.user_code}")

        token = await flow.wait_for_device_token(device_code.device_code)
        print(f"Access Token: {token.access_token}")
        print(f"Refresh Token: {token.refresh_token}")
    async with App(os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET')) as app:
        existing = await app.application.get_conduits()
        if existing:
            conduitid = existing[0].id
            print(f"Conduit ID: {conduitid} (already existed)")
        else:
            conduit = await app.application.create_conduit(shard_count=1)
            conduitid = conduit.id
            print(f"Conduit ID: {conduitid}")
    save_to_env({'ACCESS_TOKEN': token.access_token, 'REFRESH_TOKEN': token.refresh_token})
    save_to_env({'CONDUIT_ID': conduitid})

    print("Saved to .env, you can run bot.py now!")
asyncio.run(main())