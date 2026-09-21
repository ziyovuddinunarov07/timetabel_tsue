from datetime import date
from html import escape
import re

from .dates import TASHKENT, WEEKDAYS, resolve, week_dates
from .models import DayStatus

START = 'Assalomu alaykum! \nBu bot TSUE MR-86/25 guruhining dars jadvalini ko‘rsatadi.\n\nKerakli jadvalni tanlang:'
UNKNOWN = 'Jadvalni ko‘rish uchun quyidagi tugmalardan birini bosing.'
HELP = '📅 Bugungi tugmasi yoki /today — bugungi darslar.\nHafta kuni tugmalari — joriy haftaning tanlangan kuni.\nHaftalik jadval tugmasi yoki /week — dushanbadan yakshanbagacha jadval.\nVaqt Toshkent bo‘yicha. Jadval odatda har 4 soatda tekshiriladi.'
UNAVAILABLE = '⚠️ Hozir jadvalni olishning imkoni bo‘lmadi. Iltimos, keyinroq qayta urinib ko‘ring.'
STALE = '⚠️ Jadvalni yangilab bo‘lmadi. Oxirgi saqlangan jadval ko‘rsatilmoqda. Ma’lumotlar o‘zgargan bo‘lishi mumkin.'
NO_VALID = 'Bu sana uchun amaldagi jadval topilmadi.'


def fmt(day):
    return day.strftime('%d.%m.%Y')


def lesson_text(lesson):
    subject = lesson.subject
    if lesson.lesson_type and not subject.endswith('(' + lesson.lesson_type + ')'):
        subject += ' (' + lesson.lesson_type + ')'
    lines = [f'🔹 {lesson.period}-para (⏱ {lesson.start} - {lesson.end})', '📚 Fan: ' + subject,
             '👨‍🏫 O‘qituvchi: ' + ('; '.join(lesson.teachers) or 'Ko‘rsatilmagan'),
             '🏛 Xona: ' + ('; '.join(lesson.rooms) or 'Ko‘rsatilmagan')]
    if lesson.subgroups:
        lines.append('👥 Kichik guruh: ' + '; '.join(lesson.subgroups))
    lines.append('')
    return '\n'.join(lines)


def split_escaped(blocks, limit=3900, styled=False):
    """Prefer day/block boundaries; split exceptional large fields before escaping.

    The escaped serialized text and UTF-16 length are both bounded. Every chunk
    contains complete HTML entities, and no open formatting tags.
    """
    messages, current = [], ''
    def encode(text):
        safe = escape(text, quote=False)
        if not styled:
            return safe
        # Add only our own complete tags after escaping all source content.
        return re.sub(
            r'^(🗓 [^\n]+|🎓 Guruh:|📚 Fan:|👨‍🏫 O‘qituvchi:|🏛 Xona:|👥 Kichik guruh:|🔹 [^\n(]+)',
            lambda match: '<b>' + match[0].rstrip() + '</b>' + (' ' if match[0].endswith(' ') else ''),
            safe, flags=re.MULTILINE)
    def size(s):
        return len(s.encode('utf-16-le')) // 2
    for block in blocks:
        encoded = encode(block)
        if size(encoded) <= limit:
            if current and size(current + '\n\n' + encoded) > limit:
                messages.append(current)
                current = ''
            current = current + '\n\n' + encoded if current else encoded
            continue
        if current:
            messages.append(current)
            current = ''
        # Long day: first try line boundaries, then individual Unicode characters.
        for line in block.splitlines(keepends=True):
            part = encode(line)
            if size(part) <= limit:
                if size(current + part) > limit:
                    messages.append(current)
                    current = ''
                current += part
            else:
                for char in line:
                    part = escape(char, quote=False)
                    if size(current + part) > limit:
                        messages.append(current)
                        current = ''
                    current += part
    if current:
        messages.append(current)
    return messages


def format_response(state, day: date, weekly=False, group='MR-86/25'):
    if state.snapshot is None or state.successful is None:
        return [UNAVAILABLE]
    days = week_dates(day) if weekly else [day]
    resolved = [resolve(state.snapshot, d) for d in days]
    if state.error and not any(d.schedule for d in resolved):
        return [UNAVAILABLE]
    heading = 'Haftalik dars jadvali' if weekly else f'{WEEKDAYS[day.weekday()]} kungi dars jadvali'
    date_heading = f'{fmt(days[0])} – {fmt(days[-1])}' if weekly else f'{fmt(day)}, {WEEKDAYS[day.weekday()]}'
    blocks = [f'🗓 {heading}\n🎓 Guruh: {group}\n{date_heading}\nMuntazam jadval']
    if state.error:
        blocks.append(STALE)
    if any(state.snapshot.substitutions.get(d.isoformat()) != 'confirmed_none' for d in days):
        blocks.append('Almashtirishlar tasdiqlanmagan. Muntazam jadval ko‘rsatilmoqda.')
    for result in resolved:
        lines = [f'🗓 {fmt(result.date)}, {WEEKDAYS[result.date.weekday()]}'] if weekly else []
        if result.status == DayStatus.NO_VALID:
            lines.append(NO_VALID)
        elif result.status == DayStatus.EMPTY:
            lines.append('Darslar yo‘q.')
        else:
            lines.append('\n\n'.join(lesson_text(l) for l in result.lessons))
        blocks.append('\n'.join(lines))
    checked = state.successful.astimezone(TASHKENT)
    blocks.append(f'Oxirgi tekshiruv: {checked:%d.%m.%Y %H:%M}\nManba: {state.snapshot.source_url}')
    return split_escaped(blocks, styled=True)
