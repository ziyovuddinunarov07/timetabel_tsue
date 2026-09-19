import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    token: str = field(repr=False, default='')
    url: str = 'https://tsue.edupage.org/timetable/'
    group: str = 'MR-86/25'
    timezone: str = 'Asia/Tashkent'
    refresh_seconds: int = 14400
    database: Path = Path('data/timetable.sqlite3')

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @classmethod
    def from_env(cls, require_token=True):
        load_dotenv()
        config = cls(
            token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            url=os.getenv('TIMETABLE_URL', cls.url),
            group=os.getenv('GROUP_NAME', cls.group),
            timezone=os.getenv('TIMEZONE', cls.timezone),
            refresh_seconds=int(os.getenv('REFRESH_INTERVAL_SECONDS', '14400')),
            database=Path(os.getenv('DATABASE_PATH', 'data/timetable.sqlite3')),
        )
        if require_token and not config.token:
            raise ValueError('TELEGRAM_BOT_TOKEN muhit o‘zgaruvchisini kiriting.')
        if config.timezone != 'Asia/Tashkent':
            raise ValueError('TIMEZONE Asia/Tashkent bo‘lishi kerak.')
        if config.refresh_seconds < 60:
            raise ValueError('REFRESH_INTERVAL_SECONDS kamida 60 bo‘lishi kerak.')
        if urlparse(config.url).scheme != 'https':
            raise ValueError('TIMETABLE_URL HTTPS manzil bo‘lishi kerak.')
        config.zone
        return config
