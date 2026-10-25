# twitchutils
A horrible Twitch bot framework entirely over Websocket.<br>
Used to be a TwitchPlays program but evolved into so much more.

## Setup - Server
First off, make sure you have Python, Poetry, and Git installed. You also need a text editor, a browser, a secondary Twitch account for the bot to use, and a Twitch application.</br>
If you plan on using the client on a device outside your LAN, please port forward or use something like Tailscale. I do not support use of Playit or other tunneling services for this application.

1. Clone the repo. ``git clone https://github.com/wrldmap/twitchutils.git``
2. Get a Client ID and Secret from your Twitch application.
3. Run ``setup.py`` through Poetry. ``poetry run python setup.py``
4. Follow the instructions to automatically write everything needed into your .env file.
   > Do NOT share the contents of this file with ANYONE! It contains authentication tokens that can allow anyone to hijack your app and secondary Twitch account!
5. If you know port 8080 is already in use, you can change it by going to line 368 in ``server.py``.
6. Run ``server.py`` through Poetry. ``poetry run python server.py``
7. Go to ``https://localhost:8080/login`` to authenticate a broadcaster account. It gives you a URL with the code embedded and just the code.
8. You're done!
   > If any of those steps fail, create an issue and I'll try to help. Censor out any sensitive info, of course.

## Setup - Client/DualShock 4
By default, this repo includes a basic DualShock 4 emulation script. You can use this as reference to make your own.<br>
For the client, all you need is Python, Poetry, Git, a browser, and a text editor installed. If on Linux, you also need Steam or root permissions.</br>
Also make sure that you have authenticated with the host's Twitch application. They can give you a code to use on [https://twitch.tv/activate](https://twitch.tv/activate).

1. Clone the repo and enter the clients subfolder. ``git clone https://github.com/wrldmap/twitchutils.git && cd clients``
2. Edit ``ds4.py``, changing the 45 and 46 lines (by default) which are ``WEBSOCKET_URL`` and ``BROADCASTER_TARGETS``.
   > If client and server are on the same device, you probably don't need to change the websocket url. Only switch localhost to the IP of the host server! (and the port if they changed it)
3. If on Linux - either start Steam or follow [this guide by VGamepad](https://github.com/yannbouteiller/vgamepad/blob/main/readme/linux.md#prerequisite) to make VGamepad actually work.
4. Run ``ds4.py`` through Poetry. ``poetry run python ds4.py``
5. If you have Steam running, you should see a Controller Connected message. If the logs for your client say connected, you're good to go!
   > If it doesn't say connected, make sure the Websocket URL is correct and that the host has their firewall settings allowing port 8080.
6. Use ``!enable`` in one of the chats mentioned in ``BROADCASTER_TARGETS`` and are also authenticated with the host to enable the controller.
   > You can test further by sending inputs into a gamepad tester. I personally use [https://hardwaretester.com/gamepad](https://hardwaretester.com/gamepad).

## Setup - Client/Minecraft (Minescript)
By default, this repo includes a Minescript script that relays chat messages ingame. It can also be a reference for a simple chat relay script of your own.<br>
This requires a Minecraft instance with Minescript installed, plus a system Python environment with ``websockets``, ``json``, and ``asyncio`` installed.<br>
This was built on Minescript 4 for Minecraft 1.21.1, but will probably work for most versions of Minescript.<br>
Also make sure that you have authenticated with the host's Twitch application. They can give you a code to use on [https://twitch.tv/activate](https://twitch.tv/activate).

1. Clone the repo and enter the clients subfolder. ``git clone https://github.com/wrldmap/twitchutils.git && cd clients``
2. Edit ``ds4.py``, changing the 6 and 7 lines (by default) which are ``WEBSOCKET_URL`` and ``BROADCASTER_TARGETS``.
   > If client and server are on the same device, you probably don't need to change the websocket url. Only switch localhost to the IP of the host server! (and the port if they changed it)
3. Move ``ms4.py`` into the Minescript folder. ``.minecraft/minescript``
4. Once ingame, type ``\ms4`` into the chat window. It should print ``connected`` in chat once working!