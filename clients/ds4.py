import asyncio
import json
from enum import Enum

import websockets
from vgamepad import DS4_BUTTONS, VDS4Gamepad, DS4_DPAD_DIRECTIONS

class JoystickDirections(Enum):
    NORTH = (0.0, -1.0)
    SOUTH = (0.0, 1.0)
    EAST = (1.0, 0.0)
    WEST = (-1.0, 0.0)
    NORTHEAST = (1.0, -1.0)
    NORTHWEST = (-1.0, -1.0)
    SOUTHEAST = (1.0, 1.0)
    SOUTHWEST = (-1.0, 1.0)

    @property
    def x(self) -> float:
        return self.value[0]

    @property
    def y(self) -> float:
        return self.value[1]

# Yes, it emulates a DualShock. It was the easiest way, okay?
class DS4GP:
    def __init__(self):
        self.ctl = VDS4Gamepad()
        self.queue = asyncio.Queue()

    def tap(self, btn: DS4_BUTTONS, long: bool):
        return

    def dptap(self, dpad: DS4_DPAD_DIRECTIONS, long: bool):
        return

    def ljoy(self, joy: JoystickDirections, long: bool):
        return

    def rjoy(self, joy: JoystickDirections, long: bool):
        return

gp = DS4GP()
WEBSOCKET_URL = "ws://localhost:8080/ws" # Change to server's IP if on different machines.
BROADCASTER_TARGETS = {'wrldmap'} # Change this to your Twitch username, or add more!
ENABLED = False
cmds = {
    '!enable', '!disable' # Control commands
}
# You can disable some if you don't need them for said game, comment out the line and add/remove commas as needed.
# By default, all DS4 buttons are mapped, except for touchpad and PS button. Not like you probably will need them, though.
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
    # dpad
    'n': (gp.dptap, DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTH),
    'e': (gp.dptap, DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_EAST),
    's': (gp.dptap, DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTH),
    'w': (gp.dptap, DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_WEST),
    'nw': (gp.dptap, DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHWEST),
    'ne': (gp.dptap, DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHEAST),
    'sw': (gp.dptap, DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHWEST),
    'se': (gp.dptap, DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHEAST),
    # left
    'ln': (gp.ljoy, JoystickDirections.NORTH),
    'le': (gp.ljoy, JoystickDirections.EAST),
    'ls': (gp.ljoy, JoystickDirections.SOUTH),
    'lw': (gp.ljoy, JoystickDirections.WEST),
    'lnw': (gp.ljoy, JoystickDirections.NORTHWEST),
    'lne': (gp.ljoy, JoystickDirections.NORTHEAST),
    'lsw': (gp.ljoy, JoystickDirections.SOUTHWEST),
    'lse': (gp.ljoy, JoystickDirections.SOUTHEAST),
    'lt': (gp.tap, DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT),
    # right
    'rn': (gp.rjoy, JoystickDirections.NORTH),
    're': (gp.rjoy, JoystickDirections.EAST),
    'rs': (gp.rjoy, JoystickDirections.SOUTH),
    'rw': (gp.rjoy, JoystickDirections.WEST),
    'rnw': (gp.rjoy, JoystickDirections.NORTHWEST),
    'rne': (gp.rjoy, JoystickDirections.NORTHEAST),
    'rsw': (gp.rjoy, JoystickDirections.SOUTHWEST),
    'rse': (gp.rjoy, JoystickDirections.SOUTHEAST),
    'rt': (gp.tap, DS4_BUTTONS.DS4_BUTTON_THUMB_RIGHT),
}

# You can change the sleep values but that's about it for customization.
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
            elif func == gp.ljoy:
                gp.ctl.left_joystick_float(target_constant.x, target_constant.y)
                gp.ctl.update()
                await asyncio.sleep(0.5 if long else 0.1)
                gp.ctl.left_joystick_float(0.0, 0.0)
                gp.ctl.update()
            elif func == gp.rjoy:
                gp.ctl.right_joystick_float(target_constant.x, target_constant.y)
                gp.ctl.update()
                await asyncio.sleep(0.5 if long else 0.1)
                gp.ctl.right_joystick_float(0.0, 0.0)
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


async def listen_to_chat_stream():
    global ENABLED
    while True:
        try:
            async with websockets.connect(WEBSOCKET_URL) as websocket:
                print("connected")

                async for raw_payload in websocket:
                    try:
                        data = json.loads(raw_payload)
                        if data.get("action", "Unknown") == "recieve_chat":
                            broadcaster = data.get("broadcaster", "Unknown")
                            editor = bool(data.get("editor", False))
                            message = data.get("message", "Unknown")
                            msgid = data.get("id", "Unknown")

                            if broadcaster not in BROADCASTER_TARGETS:
                                continue

                            parts = message.split("+")

                            for part in parts:
                                tokens = part.strip().split()
                                lowcase = tokens[0].lower() if tokens else ""

                                long = lowcase.endswith("-")
                                clean_cmd = lowcase.rstrip("-")

                                if clean_cmd == '!enable' and editor:
                                    msg = "enabled!" if not ENABLED else "already enabled!"
                                    ENABLED = True
                                    await send_message_upstream(broadcaster, msg, msgid, websocket)
                                    break

                                if clean_cmd == '!disable' and editor:
                                    msg = "disabled!" if ENABLED else "already disabled!"
                                    ENABLED = False
                                    await send_message_upstream(broadcaster, msg, msgid, websocket)
                                    break

                                if not ENABLED:
                                    break

                                if clean_cmd in BUTTON_MAP.keys():
                                    await gp.queue.put((clean_cmd, long))

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
