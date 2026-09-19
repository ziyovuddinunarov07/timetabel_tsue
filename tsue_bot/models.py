from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import StrEnum


class Failure(StrEnum):
    GROUP_NOT_FOUND = 'group_not_found'
    NETWORK = 'network_failure'
    PARSING = 'parsing_failure'
    SUBSTITUTIONS = 'substitutions_unavailable'


class SourceError(Exception):
    def __init__(self, kind: Failure, detail: str):
        self.kind = kind
        super().__init__(detail)


@dataclass(frozen=True)
class Lesson:
    weekday: int
    period: str
    start: str
    end: str
    subject: str
    lesson_type: str = ''
    teachers: list[str] = field(default_factory=list)
    rooms: list[str] = field(default_factory=list)
    subgroups: list[str] = field(default_factory=list)
    source_id: str = ''
    # None means every week. Explicit dates are used only with verified cycles.
    dates: list[str] | None = None


@dataclass(frozen=True)
class Schedule:
    group: str
    group_id: str
    version: str
    name: str
    valid_from: str
    valid_to: str
    lessons: list[Lesson]
    # A nonempty, validated source schedule is required before empty weekdays
    # can be considered confirmed. An empty scrape never establishes this.
    verified: bool = True


@dataclass(frozen=True)
class Snapshot:
    schedules: list[Schedule]
    source_url: str
    substitutions: dict[str, str] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(
            schedules=[Schedule(**{**s, 'lessons': [Lesson(**x) for x in s['lessons']]})
                       for s in data['schedules']],
            source_url=data['source_url'],
            substitutions=data.get('substitutions', {}),
        )


class DayStatus(StrEnum):
    LESSONS = 'lessons'
    EMPTY = 'confirmed_empty'
    NO_VALID = 'no_valid_timetable'


@dataclass(frozen=True)
class ResolvedDay:
    date: date
    status: DayStatus
    lessons: list[Lesson]
    schedule: Schedule | None


@dataclass(frozen=True)
class CacheState:
    snapshot: Snapshot | None = None
    successful: datetime | None = None
    attempted: datetime | None = None
    changed: datetime | None = None
    error: str | None = None
