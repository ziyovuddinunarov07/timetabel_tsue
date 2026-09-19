import copy
import json
from pathlib import Path
from datetime import datetime

import pytest
from tsue_bot.dates import TASHKENT
from tsue_bot.models import Snapshot
from tsue_bot.parsing import parse_schedule


@pytest.fixture
def raw():
    return json.loads((Path(__file__).parent / 'fixtures/edupage_2026-09-17.json').read_text(encoding='utf-8'))


@pytest.fixture
def snapshot(raw):
    schedule = parse_schedule(raw['regular'], raw['meta'], 'MR-86/25')
    return Snapshot([schedule], 'https://tsue.edupage.org/timetable/', {'2026-09-17': 'confirmed_none'})


@pytest.fixture
def instant():
    return datetime(2026, 9, 17, 18, 30, tzinfo=TASHKENT)


def rows(raw, name):
    return next(t['data_rows'] for t in raw['regular']['dbiAccessorRes']['tables'] if t['id'] == name)
