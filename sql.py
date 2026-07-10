from dataclasses import dataclass
import asqlite

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