from types import SimpleNamespace
from unittest.mock import AsyncMock
from datetime import timedelta

from aiogram import Bot, Dispatcher
from aiogram.types import Update
import pytest

from tsue_bot.handlers import KEYBOARD, make_router
from tsue_bot.formatting import START, UNKNOWN
from tsue_bot.models import CacheState


def test_exact_persistent_keyboard():
    assert [[b.text for b in row] for row in KEYBOARD.keyboard] == [['Bugungi jadval','Haftalik jadval']]
    assert KEYBOARD.is_persistent and not KEYBOARD.one_time_keyboard


@pytest.mark.parametrize('text,expected',[
    ('/start',START),('/help','Bugungi jadval tugmasi'),('/today','Bugungi dars jadvali'),
    ('Bugungi jadval','Bugungi dars jadvali'),('/week','Haftalik dars jadvali'),
    ('Haftalik jadval','Haftalik dars jadvali'),('salom',UNKNOWN),
])
async def test_real_aiogram_routing(text,expected,snapshot,instant):
    service=SimpleNamespace(refresh=AsyncMock(return_value=CacheState(snapshot,instant)),interval=14400)
    sender=SimpleNamespace(send=AsyncMock())
    dispatcher=Dispatcher()
    dispatcher.include_router(make_router(service,clock=lambda:instant,sender=sender))
    # Deliberately invalid remote credential; Bot is only used to construct local updates.
    bot=Bot('123456:OFFLINE_TEST_CREDENTIAL_DO_NOT_USE')
    update=Update.model_validate({'update_id':1,'message':{'message_id':1,'date':int(instant.timestamp()),
        'chat':{'id':10,'type':'private'},'from':{'id':10,'is_bot':False,'first_name':'Test'},'text':text,
        'entities':[{'type':'bot_command','offset':0,'length':len(text)}] if text.startswith('/') else []}})
    try:
        await dispatcher.feed_update(bot,update)
        sender.send.assert_awaited_once()
        assert expected in '\n'.join(sender.send.call_args.args[1])
    finally:
        await bot.session.close()


async def test_date_calculated_after_refresh_crosses_midnight(snapshot,instant):
    clock=[instant.replace(hour=23,minute=59)]
    async def refresh():
        clock[0]+=timedelta(minutes=2)
        return CacheState(snapshot,instant)
    service=SimpleNamespace(refresh=refresh,interval=14400)
    sender=SimpleNamespace(send=AsyncMock())
    dispatcher=Dispatcher()
    dispatcher.include_router(make_router(service,clock=lambda:clock[0],sender=sender))
    bot=Bot('123456:OFFLINE_TEST_CREDENTIAL_DO_NOT_USE')
    update=Update.model_validate({'update_id':2,'message':{'message_id':2,'date':int(instant.timestamp()),
        'chat':{'id':10,'type':'private'},'text':'Bugungi jadval'}})
    try:
        await dispatcher.feed_update(bot,update)
        assert '18.09.2026, Juma' in '\n'.join(sender.send.call_args.args[1])
    finally:
        await bot.session.close()
