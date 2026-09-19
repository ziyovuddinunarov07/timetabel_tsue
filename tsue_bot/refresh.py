import asyncio
import logging
from datetime import timedelta
from .dates import now
from .models import Failure, SourceError

log = logging.getLogger(__name__)


class RefreshService:
    def __init__(self, cache, source, interval=14400, clock=now):
        self.cache, self.source = cache, source
        self.interval, self.clock = interval, clock
        self.lock = asyncio.Lock()
        self.generation = 0

    async def refresh(self, force=False):
        generation = self.generation
        async with self.lock:
            state = await self.cache.read()
            instant = self.clock()
            if generation != self.generation:
                return state
            if not force:
                if state.successful and instant - state.successful < timedelta(seconds=self.interval):
                    return state
                if state.error and state.attempted and instant - state.attempted < timedelta(seconds=60):
                    return state
            await self.cache.attempt(instant)
            try:
                snapshot = await self.source.fetch(instant.date())
                await self.cache.replace(snapshot, self.clock())
            except SourceError as exc:
                log.warning('Source refresh failed [%s]: %s', exc.kind, exc)
                await self.cache.fail(exc.kind.value)
            except Exception as exc:
                log.error('Unexpected refresh error: %s', type(exc).__name__)
                await self.cache.fail(Failure.PARSING.value)
            self.generation += 1
            return await self.cache.read()

    async def background(self):
        while True:
            await asyncio.sleep(self.interval)
            await self.refresh()
