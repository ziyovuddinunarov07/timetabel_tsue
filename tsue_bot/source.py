import asyncio
import json
import logging
import re
from datetime import date
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .dates import week_dates
from .models import Failure, Snapshot, SourceError
from .parsing import parse_schedule, require

log = logging.getLogger(__name__)


class EduPageSource:
    def __init__(self, url, group, client=None):
        self.url, self.group = url, group
        self.own_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(40, connect=15), follow_redirects=True,
            headers={'User-Agent': 'TSUE-MR86-TimetableBot/1.0 (public timetable reader)'})
        self.gsh = ''

    async def close(self):
        if self.own_client:
            await self.client.aclose()

    async def request(self, path, payload=None):
        url = urljoin(self.url, path)
        for attempt in range(3):
            try:
                async with asyncio.timeout(180):
                    async with self.client.stream('GET' if payload is None else 'POST', url, json=payload) as response:
                        if response.status_code == 429 or response.status_code >= 500:
                            delay = response.headers.get('Retry-After', '')
                            if attempt < 2:
                                await asyncio.sleep(min(30, max(1, int(delay))) if delay.isdigit() else 2 ** attempt)
                                continue
                        response.raise_for_status()
                        chunks, size = [], 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            require(size <= 32_000_000, 'Source response exceeds size limit')
                            chunks.append(chunk)
                        return b''.join(chunks).decode('utf-8')
            except (httpx.HTTPError, TimeoutError, UnicodeError) as exc:
                if attempt == 2 or isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    raise SourceError(Failure.NETWORK, 'HTTP retrieval failed: ' + type(exc).__name__) from exc
                await asyncio.sleep(2 ** attempt)
        raise SourceError(Failure.NETWORK, 'Temporary HTTP failure after bounded retries')

    async def rpc(self, module, method, args):
        text = await self.request(module + '?__func=' + method, {'__args': args, '__gsh': self.gsh})
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise SourceError(Failure.PARSING, 'RPC returned invalid JSON') from exc
        require(isinstance(data, dict) and 'r' in data and not data.get('e') and not data.get('reload'),
                'RPC missing result or requires authentication')
        return data['r']

    async def fetch(self, today: date):
        page = await self.request(self.url)
        token = re.search(r'ASC\.gsechash="([a-zA-Z0-9]+)"', page)
        turnover = re.search(r'"schoolyear_turnover":"(\d{2}-\d{2})"', page)
        require(token is not None and turnover is not None, 'EduPage initialization missing')
        self.gsh = token[1]
        dates = week_dates(today)
        years = sorted({d.year if d.strftime('%m-%d') >= turnover[1] else d.year - 1 for d in dates})
        versions = {}
        for year in years:
            viewer = await self.rpc('/timetable/server/ttviewer.js', 'getTTViewerData', [None, year])
            require(isinstance(viewer, dict) and 'regular' in viewer and not viewer.get('asklogin'),
                    'Public timetable viewer unavailable')
            for meta in viewer['regular']['timetables']:
                if not meta.get('hidden'):
                    versions[str(meta['tt_num'])] = meta
        require(bool(versions), 'No public timetable versions; cannot validate a replacement')
        schedules = []
        for meta in versions.values():
            data = await self.rpc('/timetable/server/regulartt.js', 'regularttGetData', [None, meta['tt_num']])
            schedules.append(parse_schedule(data, meta, self.group))
            await asyncio.sleep(0.25)
        starts = [s.valid_from for s in schedules]
        require(len(starts) == len(set(starts)), 'Ambiguous versions with identical effective dates')
        substitutions = {}
        for day in dates:
            try:
                report = await self.rpc('/substitution/server/viewer.js', 'getSubstViewerDayDataHtml',
                                        [None, {'date': day.isoformat(), 'mode': 'classes'}])
                substitutions[day.isoformat()] = inspect_substitutions(report, day)
            except SourceError as exc:
                log.warning('Substitutions unavailable on %s [%s]', day, exc.kind)
                substitutions[day.isoformat()] = 'unavailable'
            await asyncio.sleep(0.25)
        return Snapshot(schedules, self.url, substitutions)


def inspect_substitutions(report, day):
    # Verified live public format. Never interpret an unknown report as no changes.
    require(isinstance(report, str), 'Invalid substitution report')
    soup = BeautifulSoup(report, 'html.parser')
    root = soup.find(attrs={'data-date': day.isoformat()})
    if root:
        rows = root.select('.row')
        if len(rows) == 1 and 'nosubst' in rows[0].get('class', []) and rows[0].get_text(' ', strip=True) == 'Для этого дня замен нет.':
            return 'confirmed_none'
    # No populated report was published during inspection, so its change semantics
    # cannot be implemented honestly. Explicitly label the regular-only output.
    return 'unavailable'
