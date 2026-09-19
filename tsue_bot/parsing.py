"""Strict adapter for the public EduPage ttuidocdbi data, inspected live.

Never infer weekdays from card order. Card masks index the explicit days table.
Unknown cycle/calendar/bell structures fail closed rather than returning no lessons.
"""
import re
from datetime import date, datetime
from .models import Failure, Lesson, Schedule, SourceError

DAY_NAMES = {name: i for i, name in enumerate(
    ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'))}


def require(condition, detail):
    if not condition:
        raise SourceError(Failure.PARSING, detail)


def tables_from(data):
    require(isinstance(data, dict), 'Invalid regular response')
    accessor = data.get('dbiAccessorRes', {})
    require(accessor.get('type') == 'ttuidocdbi', 'Unknown DBI schema')
    tables = {}
    for table in accessor.get('tables', []):
        rows = table.get('data_rows')
        require(isinstance(rows, list) and all(isinstance(r, dict) for r in rows), 'Invalid table rows')
        require(len({r['id'] for r in rows}) == len(rows), 'Duplicate row identifier')
        tables[table['id']] = {r['id']: r for r in rows}
    for name in ('classes', 'subjects', 'teachers', 'classrooms', 'lessons', 'cards', 'days',
                 'weeks', 'terms', 'periods', 'globals', 'groups', 'bells'):
        require(name in tables, 'Missing table: ' + name)
    return tables


def validity(meta, globals_row):
    # This is the actual printed validity footer, not the user-assigned version name.
    text = globals_row.get('settings', {}).get('m_strDateBellowTimeTable', '')
    match = re.fullmatch(r'Действительность:\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})', text)
    require(match is not None, 'Printed validity dates missing or unsupported')
    start, end = [datetime.strptime(s, '%d/%m/%Y').date() for s in match.groups()]
    require(start <= end, 'Invalid validity interval')
    require(meta.get('datefrom') == start.isoformat(), 'Viewer and printed validity disagree')
    return start.isoformat(), end.isoformat()


def parse_schedule(data, meta, group_name):
    try:
        return _parse_schedule(data, meta, group_name)
    except SourceError:
        raise
    except (KeyError, ValueError, TypeError, IndexError) as exc:
        raise SourceError(Failure.PARSING, 'Invalid schedule structure: ' + type(exc).__name__) from exc


def _parse_schedule(data, meta, group_name):
    t = tables_from(data)
    matches = [r for r in t['classes'].values() if r.get('name') == group_name]
    if not matches:
        raise SourceError(Failure.GROUP_NOT_FOUND, 'Exact class name absent in version ' + meta['tt_num'])
    require(len(matches) == 1, 'Ambiguous exact class name')
    group = matches[0]
    start, end = validity(meta, t['globals']['1'])
    day_rows = list(t['days'].values())
    require(all(r.get('name') in DAY_NAMES for r in day_rows), 'Unsupported day names')
    require(len({r['name'] for r in day_rows}) == len(day_rows), 'Repeated calendar weekday')
    require(not t['globals']['1']['settings'].get('m_bPrintDayAsNumber'), 'Noncalendar day cycle')
    nw, nt = len(t['weeks']), len(t['terms'])
    require(nw > 0 and nt > 0, 'Missing cycle definitions')
    ls = {k: v for k, v in t['lessons'].items() if group['id'] in v['classids']}
    require(bool(ls), 'Unverified empty group lessons')
    result = []

    def names(table, ids):
        require(isinstance(ids, list), 'Invalid reference list')
        values = []
        for ident in ids:
            require(ident in t[table], 'Unresolved reference: ' + table)
            value = t[table][ident].get('name', '')
            require(isinstance(value, str), 'Invalid published name')
            if value:
                values.append(value)
        return values

    for card in t['cards'].values():
        if card['lessonid'] not in ls:
            continue
        lesson = ls[card['lessonid']]
        require(card.get('weeks') == '1' * nw, 'Selective week cycle lacks a public date mapping')
        require(lesson.get('terms') == '1' * nt, 'Selective term cycle lacks a public date mapping')
        mask = card.get('days', '')
        require(len(mask) == len(day_rows) and set(mask) <= {'0', '1'} and '1' in mask,
                'Missing or invalid placed-card day mask')
        require(lesson.get('durationperiods') == 1, 'Unsupported multi-period card duration')
        period = t['periods'][card['period']]
        require(not period.get('daydata'), 'Unverified per-day period time override')
        bell_id = lesson.get('bell') or group.get('bell')
        bell = t['bells'].get(bell_id)
        require(bell is not None and not bell.get('perioddata'), 'Unverified alternate bell times')
        a, b = period['starttime'], period['endtime']
        require(bool(re.fullmatch(r'\d{2}:\d{2}', a)) and bool(re.fullmatch(r'\d{2}:\d{2}', b)), 'Invalid period time')
        require(datetime.strptime(a, '%H:%M') < datetime.strptime(b, '%H:%M'), 'Invalid period range')
        subject = names('subjects', [lesson['subjectid']])[0]
        # Subject retains the complete published name; type is additional metadata.
        suffix = re.search(r'\((Ma|Sem|sem)\)$', subject)
        subgroups = []
        for gid in lesson['groupids']:
            gr = t['groups'][gid]
            if gr['classid'] == group['id'] and not gr.get('entireclass'):
                subgroups.append(gr['name'])
        for i, bit in enumerate(mask):
            if bit == '1':
                result.append(Lesson(DAY_NAMES[day_rows[i]['name']], str(period['period']), a, b,
                                     subject, suffix[1] if suffix else '', names('teachers', lesson.get('teacherids', [])),
                                     names('classrooms', card.get('classroomids', [])), subgroups, card['id']))
    require(bool(result), 'Unverified empty placed timetable')
    placed = {c['lessonid'] for c in t['cards'].values() if c['lessonid'] in ls}
    require(placed == set(ls), 'Group has unplaced lessons')
    for ident, lesson in ls.items():
        count = sum(c['days'].count('1') for c in t['cards'].values() if c['lessonid'] == ident)
        require(count == lesson['count'], 'Placed-card count disagrees with lesson count')
    result.sort(key=lambda x: (x.weekday, x.start, x.source_id))
    return Schedule(group_name, group['id'], str(meta['tt_num']), meta['text'], start, end, result)
