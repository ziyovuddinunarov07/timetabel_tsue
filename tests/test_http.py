import json
from datetime import date
from unittest.mock import AsyncMock

import httpx
import pytest
from tsue_bot.source import EduPageSource
from tsue_bot.models import Failure, SourceError


async def test_real_rpc_contract_with_fixture_transport(raw,monkeypatch):
    monkeypatch.setattr('tsue_bot.source.asyncio.sleep',AsyncMock())
    calls=[]
    def handler(request):
        calls.append(request)
        if request.method == 'GET':
            return httpx.Response(200,text='ASC.gsechash="publichash"; {"schoolyear_turnover":"08-01"}')
        body=json.loads(request.content)
        assert body['__gsh'] == 'publichash'
        method=request.url.params['__func']
        if method=='getTTViewerData':
            assert body['__args']==[None,2026]
            return httpx.Response(200,json={'r':{'regular':{'timetables':[raw['meta']]}}})
        if method=='regularttGetData':
            assert body['__args']==[None,'94']
            return httpx.Response(200,json={'r':raw['regular']})
        if method=='getSubstViewerDayDataHtml':
            day=body['__args'][1]['date']
            report=raw['substitution'].replace('2026-09-17',day)
            return httpx.Response(200,json={'r':report})
        raise AssertionError(method)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        snapshot=await EduPageSource('https://tsue.edupage.org/timetable/','MR-86/25',client).fetch(date(2026,9,17))
    assert snapshot.schedules[0].group_id=='*591'
    assert len(calls)==10
    assert len(snapshot.substitutions)==7
    assert set(snapshot.substitutions.values())=={'confirmed_none'}


async def test_bounded_retry(monkeypatch):
    monkeypatch.setattr('tsue_bot.source.asyncio.sleep',AsyncMock())
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(503)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError) as exc:
            await EduPageSource('https://example.org/timetable/','MR-86/25',client).request('/')
    assert exc.value.kind==Failure.NETWORK and len(calls)==3
