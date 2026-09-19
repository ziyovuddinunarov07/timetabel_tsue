"""Read-only live verification; no Telegram token or Telegram calls required."""
import argparse
import asyncio
import json
from pathlib import Path

from .cache import Cache
from .config import Config
from .dates import now
from .formatting import format_response
from .refresh import RefreshService
from .source import EduPageSource


async def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, default=Path('data/verification.sqlite3'))
    args = parser.parse_args()
    config = Config.from_env(require_token=False)
    cache = await Cache(args.database).open()
    source = EduPageSource(config.url, config.group)
    try:
        state = await RefreshService(cache, source).refresh(force=True)
        if state.error:
            raise SystemExit('Live verification failed: ' + state.error)
        print(json.dumps([{'group': s.group, 'id': s.group_id, 'version': s.version,
                           'from': s.valid_from, 'to': s.valid_to, 'cards': len(s.lessons)}
                          for s in state.snapshot.schedules], ensure_ascii=False, indent=2))
        print(json.dumps(state.snapshot.substitutions, indent=2))
        for text in format_response(state, now().date(), weekly=True, group=config.group):
            print(text)
    finally:
        await source.close()
        await cache.close()


if __name__ == '__main__':
    asyncio.run(run())
