import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from .cache import Cache
from .config import Config
from .handlers import make_router
from .refresh import RefreshService
from .source import EduPageSource


async def run():
    config = Config.from_env()
    cache = await Cache(config.database).open()
    source = EduPageSource(config.url, config.group)
    service = RefreshService(cache, source, config.refresh_seconds)
    background = None
    try:
        await service.refresh(force=True)
        background = asyncio.create_task(service.background(), name='timetable-refresh')
        async with Bot(config.token) as bot:
            dispatcher = Dispatcher()
            dispatcher.include_router(make_router(service, config.group))
            await bot.set_my_commands([
                BotCommand(command='start', description='Botni boshlash'),
                BotCommand(command='today', description='Bugungi jadval'),
                BotCommand(command='week', description='Haftalik jadval'),
                BotCommand(command='help', description='Foydalanish bo‘yicha yordam')])
            await dispatcher.start_polling(bot, allowed_updates=['message'], tasks_concurrency_limit=32)
    finally:
        if background:
            background.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await background
        await source.close()
        await cache.close()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('aiogram').setLevel(logging.CRITICAL)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        # Never emit token-bearing Telegram request URLs or exception text.
        logging.getLogger(__name__).error('Application stopped: %s', type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
