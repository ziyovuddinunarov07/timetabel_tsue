import asyncio
import time
import weakref

from aiogram import F, Router
from aiogram.exceptions import TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, LinkPreviewOptions, Message, ReplyKeyboardMarkup

from .dates import now
from .formatting import HELP, START, UNKNOWN, format_response

KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text='Bugungi jadval'), KeyboardButton(text='Haftalik jadval')]],
    resize_keyboard=True, is_persistent=True, one_time_keyboard=False)


class Sender:
    def __init__(self):
        self.global_lock = asyncio.Lock()
        self.chat_locks = weakref.WeakValueDictionary()
        self.last_sent = 0.0

    async def send(self, message, texts):
        chat_id = message.chat.id
        lock = self.chat_locks.setdefault(chat_id, asyncio.Lock())
        async with lock:
            for text in texts:
                for attempt in range(3):
                    try:
                        async with self.global_lock:
                            await asyncio.sleep(max(0, 0.05 - (time.monotonic() - self.last_sent)))
                            await message.answer(text, parse_mode='HTML', reply_markup=KEYBOARD,
                                                 link_preview_options=LinkPreviewOptions(is_disabled=True))
                            self.last_sent = time.monotonic()
                        break
                    except TelegramRetryAfter as exc:
                        if attempt == 2:
                            raise
                        await asyncio.sleep(exc.retry_after + 0.1)
                # Rate-limit messages to a single chat, including the end of a reply.
                await asyncio.sleep(1.05)


def make_router(service, group='MR-86/25', clock=now, sender=None):
    router = Router()
    sender = sender or Sender()

    @router.message(CommandStart())
    async def start(message: Message):
        await sender.send(message, [START])

    @router.message(Command('help'))
    async def help_command(message: Message):
        await sender.send(message, [HELP.replace('4 soatda', f'{service.interval / 3600:g} soatda')])

    async def answer(message, weekly):
        state = await service.refresh()
        # Calculate after I/O too, so a slow refresh crossing midnight uses the new date.
        date = clock().date()
        await sender.send(message, format_response(state, date, weekly, group))

    @router.message(Command('today'))
    @router.message(F.text == 'Bugungi jadval')
    async def today(message: Message):
        await answer(message, False)

    @router.message(Command('week'))
    @router.message(F.text == 'Haftalik jadval')
    async def week(message: Message):
        await answer(message, True)

    @router.message()
    async def unknown(message: Message):
        await sender.send(message, [UNKNOWN])

    return router
