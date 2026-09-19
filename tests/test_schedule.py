from datetime import date, datetime, timezone
from dataclasses import replace
from html import unescape

import pytest
from tsue_bot.dates import local_date, resolve, week_dates
from tsue_bot.formatting import format_response, split_escaped, STALE, UNAVAILABLE, NO_VALID
from tsue_bot.models import CacheState, DayStatus, Failure, SourceError, Snapshot
from tsue_bot.parsing import parse_schedule
from tsue_bot.source import inspect_substitutions
from conftest import rows


def test_live_snapshot_exact_fields(snapshot):
    s = snapshot.schedules[0]
    assert (s.group, s.group_id, s.version) == ('MR-86/25', '*591', '94')
    assert (s.valid_from, s.valid_to) == ('2026-09-07', '2026-09-30')
    assert len(s.lessons) == 12
    assert [(l.weekday, l.period) for l in s.lessons] == [
        (0,'4'),(0,'5'),(1,'4'),(1,'5'),(1,'6'),(2,'5'),(2,'6'),(3,'4'),(3,'5'),(3,'6'),(4,'4'),(4,'5')]
    lesson = next(x for x in s.lessons if x.source_id == '*5975')
    assert lesson.teachers == ['Samieva Maftuna', 'Rustamova Ziyoda']
    assert lesson.rooms == ['5/106-12 lab', '5/108-12 lab']
    assert lesson.start == '13:00' and lesson.end == '14:20'
    assert any(x.rooms == ['7/214-60'] for x in s.lessons)


def test_day_mapping_uses_explicit_names_not_card_order(raw):
    rows(raw,'cards').reverse()
    for row in rows(raw,'days'):
        if row['name'] == 'Monday':
            row['name'] = 'Sunday'
    result = parse_schedule(raw['regular'], raw['meta'], 'MR-86/25')
    assert len([x for x in result.lessons if x.weekday == 6]) == 2


def test_exact_group_match(raw):
    with pytest.raises(SourceError) as e:
        parse_schedule(raw['regular'], raw['meta'], 'MR-86')
    assert e.value.kind == Failure.GROUP_NOT_FOUND


@pytest.mark.parametrize('table,field,value', [
    ('cards','days',''), ('cards','weeks','10'), ('lessons','terms','0'),
    ('cards','period','900'), ('lessons','teacherids',['missing']),
    ('periods','starttime','25:00'),
])
def test_bad_source_rejected(raw, table, field, value):
    target = rows(raw,table)[0]
    if table == 'periods':
        target = next(x for x in rows(raw,table) if x['id'] == '4')
    target[field] = value
    with pytest.raises(SourceError):
        parse_schedule(raw['regular'], raw['meta'], 'MR-86/25')


def test_empty_extraction_rejected(raw):
    rows(raw,'cards').clear()
    with pytest.raises(SourceError):
        parse_schedule(raw['regular'], raw['meta'], 'MR-86/25')


def test_missing_fields_and_subgroups(raw):
    lesson = rows(raw,'lessons')[0]
    lesson['teacherids'] = []
    for c in rows(raw,'cards'):
        if c['lessonid'] == lesson['id']:
            c['classroomids'] = []
    subgroup = next(g for g in rows(raw,'groups') if g['classid'] == '*591')
    subgroup.update(entireclass=False, name='1-kichik guruh')
    result = parse_schedule(raw['regular'],raw['meta'],'MR-86/25')
    lesson = next(x for x in result.lessons if x.subject == 'Marketing (Ma)')
    assert lesson.teachers == [] and lesson.rooms == []
    assert lesson.subgroups == ['1-kichik guruh']


def test_tashkent_midnight():
    assert local_date(datetime(2026,9,17,18,59,tzinfo=timezone.utc)) == date(2026,9,17)
    assert local_date(datetime(2026,9,17,19,0,tzinfo=timezone.utc)) == date(2026,9,18)
    with pytest.raises(ValueError):
        local_date(datetime(2026,9,17))


@pytest.mark.parametrize('day,start,end', [
    (date(2026,1,1),date(2025,12,29),date(2026,1,4)),
    (date(2026,10,1),date(2026,9,28),date(2026,10,4)),
    (date(2028,3,1),date(2028,2,28),date(2028,3,5)),
])
def test_week_boundaries(day,start,end):
    days = week_dates(day)
    assert days[0] == start and days[-1] == end and len(days) == 7


def test_empty_expired_and_future(snapshot):
    assert resolve(snapshot,date(2026,9,19)).status == DayStatus.EMPTY
    assert resolve(snapshot,date(2026,9,20)).status == DayStatus.EMPTY
    assert resolve(snapshot,date(2026,10,1)).status == DayStatus.NO_VALID
    assert resolve(snapshot,date(2026,9,6)).status == DayStatus.NO_VALID


def test_week_two_validity_periods(snapshot):
    s = snapshot.schedules[0]
    newer = replace(s, version='95', valid_from='2026-09-17', valid_to='2026-09-30',
                    lessons=[replace(x,subject='Yangi fan') for x in s.lessons])
    older = replace(s,valid_to='2026-09-16')
    snapshot = replace(snapshot,schedules=[older,newer])
    assert resolve(snapshot,date(2026,9,16)).lessons[0].subject != 'Yangi fan'
    assert resolve(snapshot,date(2026,9,17)).lessons[0].subject == 'Yangi fan'


def test_saturday_is_supported(raw):
    rows(raw,'cards')[0]['days'] = '000001'
    s = parse_schedule(raw['regular'],raw['meta'],'MR-86/25')
    assert resolve(Snapshot([s],''),date(2026,9,19)).status == DayStatus.LESSONS


def test_today_keeps_finished_lessons(snapshot,instant):
    texts = format_response(CacheState(snapshot,instant),instant.date())
    full = '\n'.join(texts)
    assert all(x in full for x in ('17.09.2026, Payshanba','4-juftlik','5-juftlik','6-juftlik'))
    assert '13:00–14:20' in full and '17.09.2026 18:30' in full


def test_failure_and_no_valid_messages(snapshot,instant):
    assert format_response(CacheState(),instant.date()) == [UNAVAILABLE]
    assert STALE in '\n'.join(format_response(CacheState(snapshot,instant,error='network'),instant.date()))
    assert format_response(CacheState(snapshot,instant,error='network'),date(2026,10,2)) == [UNAVAILABLE]
    assert NO_VALID in '\n'.join(format_response(CacheState(snapshot,instant),date(2026,10,2)))


def test_missing_names_output(snapshot,instant):
    s = snapshot.schedules[0]
    snapshot = replace(snapshot,schedules=[replace(s,lessons=[replace(x,teachers=[],rooms=[]) for x in s.lessons])])
    assert 'O‘qituvchi: Ko‘rsatilmagan' in '\n'.join(format_response(CacheState(snapshot,instant),instant.date()))
    assert 'Xona: Ko‘rsatilmagan' in '\n'.join(format_response(CacheState(snapshot,instant),instant.date()))


def test_long_html_safe_messages():
    original = ('<script>A&B</script> 😀 ' * 1000)
    parts = split_escaped([original])
    assert len(parts) > 1
    assert all(len(p.encode('utf-16-le')) // 2 <= 3900 for p in parts)
    assert ''.join(map(unescape,parts)) == original
    assert all('<script>' not in p for p in parts)


def test_all_week_dates_and_no_cyrillic_ui(snapshot,instant):
    import re
    full = '\n'.join(format_response(CacheState(snapshot,instant),instant.date(),weekly=True))
    assert '14.09.2026 – 20.09.2026' in full
    assert '19.09.2026, Shanba\nDarslar yo‘q.' in full
    assert '20.09.2026, Yakshanba\nDarslar yo‘q.' in full
    assert not re.search('[А-Яа-яЁё]',full)


def test_substitutions_not_assumed_empty(raw):
    assert inspect_substitutions(raw['substitution'],date(2026,9,17)) == 'confirmed_none'
    assert inspect_substitutions(raw['substitution'],date(2026,9,18)) == 'unavailable'
    assert inspect_substitutions('<div>Login</div>',date(2026,9,17)) == 'unavailable'
    assert inspect_substitutions('<div data-date="2026-09-17"><div class="row">Changed</div></div>',date(2026,9,17)) == 'unavailable'

def test_omitted_teacher_room_fields(raw):
    for lesson in rows(raw,'lessons'):
        del lesson['teacherids']
    for card in rows(raw,'cards'):
        del card['classroomids']
    s=parse_schedule(raw['regular'],raw['meta'],'MR-86/25')
    assert all(not x.teachers and not x.rooms for x in s.lessons)


def test_partial_card_loss_rejected(raw):
    rows(raw,'cards').pop()
    with pytest.raises(SourceError):
        parse_schedule(raw['regular'],raw['meta'],'MR-86/25')
