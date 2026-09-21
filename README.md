# TSUE MR-86/25 timetable bot

A runnable Python / aiogram 3 bot with Uzbek Latin messages, long polling, asynchronous public EduPage requests, SQLite caching, and a shared background refresh task. No AI API is used. Production never reads test fixtures.

## Credentials

The token posted in the original request is exposed. Revoke it in **@BotFather** with `/revoke`, obtain a replacement, and keep the replacement only in your local environment or `.env`. Do not put tokens in code, Git, screenshots, logs, or chat. This project does not contain or use that posted token.

## Windows PowerShell

Install Python 3.14 (tested with 3.14.6), then from this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Set `TELEGRAM_BOT_TOKEN` in the local `.env` editor, save it, and run:

```powershell
.\.venv\Scripts\python.exe -m tsue_bot
```

No virtual-environment activation or PowerShell execution-policy change is necessary. An existing environment variable takes precedence over `.env`. Start a private chat with your bot and send `/start`. The persistent keyboard shows **📅 Bugungi**, two rows of Monday–Saturday buttons, and **Haftalik jadval**. Weekday buttons select that date in the current Monday–Sunday week in Tashkent. The old **Bugungi jadval** text is still accepted. Timetable replies use emoji labels, bold headings, and blank lines between lessons, with no attribution footer. `/today`, `/week`, and `/help` are supported. No registration or group selection is needed.

The program runs until Ctrl+C. **The computer/server must stay on and the process must stay running** for polling and background refreshes. Windows sleep suspends it. Run only one polling instance per token and database.

Check the real website without any Telegram token or Telegram API call:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m tsue_bot.check_source
```

This makes public source requests, writes a separate `data/verification.sqlite3`, and prints source IDs, validity, and the current weekly output. It exits unsuccessfully if live retrieval or validation fails. It is not an offline fixture demonstration.

## Configuration

Copy `.env.example` and retain these defaults unless intentionally changing configuration:

```dotenv
TELEGRAM_BOT_TOKEN=
TIMETABLE_URL=https://tsue.edupage.org/timetable/
GROUP_NAME=MR-86/25
TIMEZONE=Asia/Tashkent
REFRESH_INTERVAL_SECONDS=14400
DATABASE_PATH=data/timetable.sqlite3
```

`TIMEZONE` must remain `Asia/Tashkent`. `tzdata` supplies IANA data on Windows. The refresh interval is configurable, with a minimum of 60 seconds to protect the source. Relative database paths resolve from the working directory. Do not put credentials in `TIMETABLE_URL`.

## Continuous operation with Docker

Install Docker Desktop or Docker Engine with Compose. Configure `.env` as above:

```powershell
docker compose up -d --build
docker compose logs --tail 100 -f bot
```

The container runs as an unprivileged user. The named `timetable-data` volume persists SQLite across container replacement. `restart: unless-stopped` restarts the process after failure or host reboot once Docker is running. No ports are exposed. Stop with `docker compose down`; do **not** add `-v` unless intentionally deleting saved data. Docker is optional; the Python entry point is the tested local deployment.

## How the real integration works

Source: <https://tsue.edupage.org/timetable/>. Inspected on 17 September 2026. The page loads a React/SVG timetable, not an HTML table. The public JavaScript exposes these exact RPC methods, discovered from its module imports and RPC loader:

- `/timetable/server/ttviewer.js?__func=getTTViewerData` — published version catalogue; arguments `[null, school_year]`.
- `/timetable/server/regulartt.js?__func=regularttGetData` — complete public `ttuidocdbi` tables; arguments `[null, version]`.
- `/substitution/server/viewer.js?__func=getSubstViewerDayDataHtml` — rendered public substitution report; arguments `[null, {date, mode: "classes"}]`.

All use POST JSON `{__args: ..., __gsh: ...}`. The public `ASC.gsechash` and school-year turnover are read from the page at every refresh. These are public application calls, not a promised stable API. A schema change causes validation failure instead of invented timetable data. HTTP retrieval has connect/read/whole-request timeouts, a response-size cap, at most three attempts, backoff, and spacing between source calls. No browser or Playwright is required in production.

The class is matched by **exact name** in each version's `classes` table, the same data used by the **Классы** selector. Its ID is never hardcoded in production. On inspection it was `*591`, version `94`, named `September 14 -2026`, printed validity **07.09.2026–30.09.2026**. The parser cross-checks the viewer's start date against the actual printed validity footer; it never derives expiry from a made-up semester date.

Cards join to lessons, subjects, teachers, rooms, class groups, and periods by explicit identifiers. A card's `days` bit mask indexes named rows in the source `days` table; text extraction order does not determine weekdays. Original period numbers, full source subject/teacher names, and full room strings are retained. The visual timetable sometimes abbreviates teacher names and lab room names; the bot uses their full published records. It never pairs individual teachers with rooms. Source suffixes `Ma`, `Sem`, and `sem` remain unchanged; their expansions have not been verified. Entire-class markers are not presented as subgroups; named partial groups are retained.

### Validity and week cycles

Every requested date is resolved independently. A week is Monday–Sunday in Tashkent, including month/year boundaries and Saturday. A newer effective date takes precedence if published intervals overlap; identical effective dates are rejected as ambiguous. Dates outside all published intervals display `Bu sana uchun amaldagi jadval topilmadi.` Cached expired or future schedules are never silently extended.

This source declares A and B weeks. **All 12 MR-86/25 cards have `weeks="11"`**, meaning both weeks, and `terms="1"`. Both week variants therefore have the same schedule for this group. No ISO odd/even-week assumption is made. If the group later receives selective A/B cards without a publicly verified date-to-cycle mapping, parsing fails closed. A/B calendar anchors are not exposed by the public regular data inspected here; the public current/date-specific timetable is disabled (`current.allow=false`). Selective term rules, noncalendar day cycles, changed bell schemes, and multi-period card formats also fail closed until their source semantics can be verified. These are explicit adapter limits, not supported features claimed on the basis of synthetic data.

### Substitutions and holidays

The **Замены** section is public. The source currently supplies an explicit dated `nosubst` row (`Для этого дня замен нет.`). The bot queries all seven dates of the current week on refresh and only records `confirmed_none` when the report's date, row class, and content all match the verified format.

No populated change/cancellation/substitution report was available to verify its semantics during development. The bot therefore does not guess how arbitrary report HTML alters lessons. A nonempty, inaccessible, malformed, or date-mismatched report is `substitutions_unavailable`; the response says `Almashtirishlar tasdiqlanmagan. Muntazam jadval ko‘rsatilmoqda.` The regular schedule remains explicitly labelled **Muntazam jadval**, including on dates whose report confirms no substitutions. No claim is made that a recurring schedule accounts for all holidays or unpublished changes. If populated changes begin to appear, this adapter must be extended and verified against those actual reports before it can claim to apply them.

## Refresh and failure behavior

- Fetch on startup, then every 14,400 seconds by default, and before a response when the last successful check is at least that old.
- One cache and one async lock serve all users. Concurrent requests share the in-flight refresh. A failed request has a 60-second retry cooldown to prevent traffic from hammering the source.
- Validation completes before a single atomic SQLite statement replaces the stored snapshot. Unverified empty results cannot replace good data.
- Persist last successful check, last attempt, last content change, source URL, class identifier, all returned versions/validity, lessons, and dated substitution status. Unchanged successful checks update the check time but retain the change time.
- On failure, applicable saved data includes the required warning and its actual last successful check time. Without applicable saved data, show the short temporary-unavailability message. Group-not-found, network/parse errors, no-valid-date, confirmed-empty, and unavailable substitutions remain distinct internally.
- Changes appear on the next successful refresh, **not instantly**. Updates only affect future requests. There are no unsolicited change notifications.

Long responses split at day/block boundaries where possible. Exceptional long fields split safely before HTML escaping; all parts stay below Telegram's limit even with supplementary Unicode. Telegram flood-wait responses are respected with bounded retries.

## Tests and verification

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

The fixture `tests/fixtures/edupage_2026-09-17.json` is a reduced real public snapshot containing only the relevant source tables and references. Mutations for errors, subgroups, changed lessons, and Saturday/cycle scenarios exist only inside tests. Production does not import or fall back to these files.

Tests cover exact group matching, all 12 weekday/period placements, unchanged published names and rooms, multiple teachers/rooms, subgroup retention, missing fields, malformed/empty data, midnight in Tashkent, leap/month/year boundaries, Saturday, two validity periods in a week, expiry/future dates, HTML/Unicode splitting, no-lessons versus failures, successful updates, unchanged check times, concurrent callers, SQLite reopen, source outages, bounded retries, public RPC shape, and substitution uncertainty.

See `VERIFICATION.md` for the actual execution results and live/browser evidence. Telegram delivery is not claimed to be tested with your token. Docker build/start results are only claimed there if actually run.

## Source layout

- `config.py`: environment configuration and zoneinfo.
- `source.py`: async HTTP, public RPC, retries, substitutions inspection.
- `parsing.py`: strict source-table validation and joins.
- `models.py`, `dates.py`: typed domain data and date-specific resolution.
- `cache.py`: persistent atomic SQLite snapshot and metadata.
- `refresh.py`: startup/request/background refresh coordination.
- `formatting.py`: Uzbek output and safe splitting.
- `handlers.py`: aiogram commands, keyboard, sending/rate limits.
- `__main__.py`: application lifecycle and long polling.
- `check_source.py`: token-free live integration check.
