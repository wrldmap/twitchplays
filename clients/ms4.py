import minescript
import json
import websockets
import asyncio

WEBSOCKET_URL = "ws://localhost:8080/ws"
BROADCASTER_TARGETS = {'wrldmap'}

async def listen_to_chat_stream():
    while True:
        try:
            async with websockets.connect(WEBSOCKET_URL) as websocket:
                print("connected")

                async for raw_payload in websocket:
                    try:
                        data = json.loads(raw_payload)
                        if data.get("action", "Unknown") == "recieve_chat":
                            broadcaster = data.get("broadcaster", "Unknown")
                            sender = data.get("sender", "Unknown")
                            message = data.get("message", "Unknown")
                            if broadcaster in BROADCASTER_TARGETS:
                                minescript.echo(f"[#{broadcaster}] {sender}: {message}")

                    except json.JSONDecodeError:
                        print(f"I can't parse that, boss. DecodeError: {raw_payload}")
                    except Exception as e:
                        print(f"Error processing message: {e}")

        except (websockets.ConnectionClosed, ConnectionRefusedError, OSError):
            print("disconnected, reconnection attempt in 3secs")
            await asyncio.sleep(3)

async def main():
    await listen_to_chat_stream()

if __name__ == "__main__":
    asyncio.run(main())
