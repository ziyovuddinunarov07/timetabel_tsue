from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .models import DayStatus, ResolvedDay, Snapshot

TASHKENT = ZoneInfo('Asia/Tashkent')
WEEKDAYS = ('Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba')


def now() -> datetime:
    return datetime.now(TASHKENT)


def local_date(instant: datetime) -> date:
    if instant.tzinfo is None:
        raise ValueError('An aware datetime is required')
    return instant.astimezone(TASHKENT).date()


def week_dates(day: date) -> list[date]:
    monday = day - timedelta(days=day.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def resolve(snapshot: Snapshot, day: date) -> ResolvedDay:
    candidates = [s for s in snapshot.schedules if s.verified and s.valid_from <= day.isoformat() <= s.valid_to]
    if not candidates:
        return ResolvedDay(day, DayStatus.NO_VALID, [], None)
    # Later effective date supersedes an older overlapping publication.
    candidates.sort(key=lambda s: s.valid_from, reverse=True)
    if len(candidates) > 1 and candidates[0].valid_from == candidates[1].valid_from:
        # Ambiguous revisions must be rejected by the parser, never guessed here.
        raise ValueError('Ambiguous timetable validity')
    schedule = candidates[0]
    lessons = [x for x in schedule.lessons if x.weekday == day.weekday()
               and (x.dates is None or day.isoformat() in x.dates)]
    lessons.sort(key=lambda x: (x.start, x.period, x.subject, x.source_id))
    return ResolvedDay(day, DayStatus.LESSONS if lessons else DayStatus.EMPTY, lessons, schedule)
