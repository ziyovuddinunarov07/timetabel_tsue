import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest
from tsue_bot.cache import Cache
from tsue_bot.models import Failure, SourceError
from tsue_bot.refresh import RefreshService
from tsue_bot.formatting import format_response, STALE


class FakeSource:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = 0
        self.error = None

    async def fetch(self, day):
        self.calls += 1
        await asyncio.sleep(0.01)
        if self.error:
            raise self.error
        return self.snapshot


async def test_concurrent_refresh_persistence_and_changes(tmp_path,snapshot,instant):
    path = tmp_path / 'cache.sqlite3'
    cache = await Cache(path).open()
    source = FakeSource(snapshot)
    clock = [instant]
    service = RefreshService(cache, source, clock=lambda:clock[0])
    try:
        results = await asyncio.gather(*(service.refresh() for _ in range(30)))
        assert source.calls == 1
        assert all(r.snapshot == snapshot for r in results)
        first = await cache.read()
        assert first.successful == first.attempted == first.changed == instant
        await service.refresh()
        assert source.calls == 1
        clock[0] += timedelta(hours=4)
        await service.refresh()
        same = await cache.read()
        assert same.successful == clock[0] and same.changed == instant
        source.snapshot = replace(snapshot,schedules=[replace(snapshot.schedules[0],
            lessons=[replace(l,subject='Yangilangan fan') for l in snapshot.schedules[0].lessons])])
        clock[0] += timedelta(hours=4)
        await service.refresh()
        changed = await cache.read()
        assert changed.changed == clock[0]
        assert 'Yangilangan fan' in '\n'.join(format_response(changed,instant.date()))
    finally:
        await cache.close()
    reopened = await Cache(path).open()
    try:
        assert await reopened.read() == changed
    finally:
        await reopened.close()


@pytest.mark.parametrize('failure',[Failure.NETWORK,Failure.PARSING,Failure.GROUP_NOT_FOUND])
async def test_failure_preserves_cache_and_warning(tmp_path,snapshot,instant,failure):
    cache = await Cache(tmp_path/'db').open()
    source = FakeSource(snapshot)
    clock = [instant]
    service = RefreshService(cache,source,clock=lambda:clock[0])
    try:
        before = await service.refresh()
        source.error = SourceError(failure,'Fixture failure')
        clock[0] += timedelta(hours=4)
        results = await asyncio.gather(*(service.refresh() for _ in range(20)))
        assert source.calls == 2
        after = results[0]
        assert after.snapshot == before.snapshot
        assert after.successful == before.successful
        assert after.changed == before.changed
        assert after.attempted == clock[0] and after.error == failure.value
        assert STALE in '\n'.join(format_response(after,instant.date()))
        await service.refresh()
        assert source.calls == 2
        source.error = None
        clock[0] += timedelta(seconds=61)
        assert (await service.refresh()).error is None
    finally:
        await cache.close()


async def test_startup_failure_never_becomes_empty_day(tmp_path,snapshot,instant):
    cache = await Cache(tmp_path/'db').open()
    source = FakeSource(snapshot)
    source.error = SourceError(Failure.PARSING,'Empty result')
    try:
        state = await RefreshService(cache,source,clock=lambda:instant).refresh(force=True)
        assert state.snapshot is None and state.successful is None
        assert 'darslar yo‘q' not in '\n'.join(format_response(state,instant.date()))
    finally:
        await cache.close()
