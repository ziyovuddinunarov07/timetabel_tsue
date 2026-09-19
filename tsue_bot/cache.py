import hashlib
import json
from datetime import datetime
from pathlib import Path
import aiosqlite
from .models import CacheState, Snapshot


class Cache:
    def __init__(self, path: Path):
        self.path = path
        self.db = None

    async def open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(self.path)
        await self.db.execute('PRAGMA journal_mode=WAL')
        await self.db.execute('PRAGMA busy_timeout=5000')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS state (
            id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT, digest TEXT,
            successful TEXT, attempted TEXT, changed TEXT, error TEXT)''')
        await self.db.execute('INSERT OR IGNORE INTO state(id) VALUES(1)')
        await self.db.commit()
        return self

    async def close(self):
        if self.db:
            await self.db.close()

    async def read(self):
        async with self.db.execute('SELECT payload,successful,attempted,changed,error FROM state WHERE id=1') as cur:
            payload, successful, attempted, changed, error = await cur.fetchone()
        return CacheState(
            Snapshot.from_dict(json.loads(payload)) if payload else None,
            *(datetime.fromisoformat(x) if x else None for x in (successful, attempted, changed)), error)

    async def attempt(self, instant):
        await self.db.execute('UPDATE state SET attempted=? WHERE id=1', (instant.isoformat(),))
        await self.db.commit()

    async def fail(self, kind):
        await self.db.execute('UPDATE state SET error=? WHERE id=1', (kind,))
        await self.db.commit()

    async def replace(self, snapshot, instant):
        payload = json.dumps(snapshot.to_dict(), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(payload.encode()).hexdigest()
        await self.db.execute('''UPDATE state SET payload=?, successful=?, error=NULL,
            changed=CASE WHEN digest IS NULL OR digest<>? THEN ? ELSE changed END,
            digest=? WHERE id=1''', (payload, instant.isoformat(), digest, instant.isoformat(), digest))
        await self.db.commit()
