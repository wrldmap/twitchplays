import asyncio
import json
import websockets
from vgamepad import DS4_BUTTONS, VDS4Gamepad, DS4_DPAD_DIRECTIONS

class DS4GP:
    def __init__(self):
        self.ctl = VDS4Gamepad()
        self.queue = asyncio.Queue()

    def tap(self, btn: DS4_BUTTONS, long: bool):
        self.ctl.press_button(btn)
        self.ctl.update()

    def dptap(self, dpad: DS4_DPAD_DIRECTIONS, long: bool):
        self.ctl.directional_pad(dpad)
        self.ctl.update()

gp = DS4GP()
WEBSOCKET_URL = "ws://localhost:8080/ws"
ENABLED = False
cmds = {'!enable', '!disable', 'a', 'b', 'x', 'y', 'l', 'r', 'zl', 'zr', 'n', 's', 'e', 'w', 'start', 'select'}

BUTTON_MAP = {
    'a': (gp.tap, DS4_BUTTONS.DS4_BUTTON_CROSS),
    'b': (gp.tap, DS4_BUTTONS.DS4_BUTTON_CIRCLE),
    'x': (gp.tap, DS4_BUTTONS.DS4_BUTTON_SQUARE),
    'y': (gp.tap, DS4_BUTTONS.DS4_BUTTON_TRIANGLE),
    'l': (gp.tap, DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT),
    'r': (gp.tap, DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT),
    'zl': (gp.tap, DS4_BUTTONS.DS4_BUTTON_TRIGGER_LEFT),
    'zr': (gp.tap, DS4_BUTTONS.DS4_BUTTON_TRIGGER_RIGHT),
    'start': (gp.tap, DS4_BUTTONS.DS4_BUTTON_SHARE),
    'select': (gp.tap, DS4_BUTTONS.DS4_BUTTON_OPTIONS),
    'n': (gp.dptap, DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTH),
    'e': (gp.dptap, DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_EAST),
    's': (gp.dptap, DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTH),
    'w': (gp.dptap, DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_WEST),
}

async def gamepad_worker():
    while True:
        clean_cmd, long = await gp.queue.get()
        try:
            func, target_constant = BUTTON_MAP[clean_cmd]

            if func == gp.tap:
                gp.ctl.press_button(target_constant)
                gp.ctl.update()
                await asyncio.sleep(0.5 if long else 0.1)
                gp.ctl.release_button(target_constant)
                gp.ctl.update()
            elif func == gp.dptap:
                gp.ctl.directional_pad(target_constant)
                gp.ctl.update()
                await asyncio.sleep(0.5 if long else 0.1)
                gp.ctl.directional_pad(DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE)
                gp.ctl.update()

        except Exception as e:
            print(f"Worker execution error: {e}")
        finally:
            gp.queue.task_done()


async def send_message_upstream(broadcaster, message, reply_id, websocket):
    command_payload = {
        "action": "send_chat",
        "broadcaster": broadcaster,
        "message": message,
        "reply_id": reply_id
    }
    try:
        await websocket.send(json.dumps(command_payload))
    except Exception as e:
        print(f"failed for reason: {e}")


async def handle_command(clean_cmd, long, broadcaster, editor, msgid, websocket):
    global ENABLED

    if broadcaster != "wrldmap":
        return

    if clean_cmd == '!enable' and editor:
        msg = "enabled!" if not ENABLED else "already enabled!"
        ENABLED = True
        await send_message_upstream(broadcaster, msg, msgid, websocket)
        return

    if clean_cmd == '!disable' and editor:
        msg = "disabled!" if ENABLED else "already disabled!"
        ENABLED = False
        await send_message_upstream(broadcaster, msg, msgid, websocket)
        return

    if not ENABLED:
        return

    if clean_cmd in BUTTON_MAP:
        await gp.queue.put((clean_cmd, long))


async def listen_to_chat_stream():
    global cmds
    while True:
        try:
            async with websockets.connect(WEBSOCKET_URL) as websocket:
                print("connected")

                async for raw_payload in websocket:
                    try:
                        data = json.loads(raw_payload)
                        message = data.get("message", "Unknown")
                        tokens = message.split()
                        lowcase = tokens[0].lower() if tokens else ""

                        long = lowcase.endswith("-")
                        clean_cmd = lowcase.rstrip("-")

                        if clean_cmd in cmds:
                            broadcaster = data.get("broadcaster", "Unknown")
                            editor = bool(data.get("editor", False))
                            msgid = data.get("id", "Unknown")

                            asyncio.create_task(
                                handle_command(clean_cmd, long, broadcaster, editor, msgid, websocket)
                            )

                    except json.JSONDecodeError:
                        print(f"I can't parse that, boss. DecodeError: {raw_payload}")
                    except Exception as e:
                        print(f"Error processing message: {e}")

        except (websockets.ConnectionClosed, ConnectionRefusedError, OSError):
            print("disconnected, reconnection attempt in 3secs")
            await asyncio.sleep(3)


async def main():
    worker_task = asyncio.create_task(gamepad_worker())
    await listen_to_chat_stream()


if __name__ == "__main__":
    asyncio.run(main())