# Verification report — 17 September 2026

## Executed successfully

- Python **3.14.6** on Windows; dependencies pinned to the versions actually installed. `pip check`: **No broken requirements found**.
- `python -m pytest -q`: **42 passed**. These are offline regression, HTTP contract, and real aiogram routing tests, using a reduced public source snapshot and explicitly synthetic mutations.
- `python -X utf8 -m tsue_bot.check_source`: **successful live retrieval**, using the production async HTTP/parser/cache/formatting path. No Telegram token was required or used. SQLite was written and reopened successfully.
- Exact class **MR-86/25**, dynamically resolved ID **`*591`**, source version **`94`**, validity **7–30 September 2026**, **12** lesson cards. Last successful live check: **17.09.2026 19:58 Asia/Tashkent**; the precise timestamp is in [live-check.json](docs/verification/live-check.json).
- Live **Классы** selector opened in a temporary headless Chrome session with Playwright 1.63.0. The selector contains MR-86/25 under the **TURIZM → 2 KURS** section. The exact entry was selected, and the displayed title was MR-86/25.
- All **12** displayed cards were checked against their **grid coordinates**, named weekday rows, and numbered period columns. Subjects, displayed teacher aliases and room aliases match the source records used by the parser. This check did not infer days from text order. Saturday is empty. Sunday is outside the published six-day grid, with no source cards scheduled on that weekday.
- Source period 4 is **13:00–14:20**, period 5 **14:30–15:50**, period 6 **16:00–17:20**; those times match the displayed headers.
- Public substitutions RPC was queried separately for **14–20 September 2026**. Every dated report explicitly confirmed no substitutions. Reports were not assumed empty from missing HTML.

Evidence: [website screenshot](docs/verification/mr86-live.png), [per-cell comparison](docs/verification/visual-comparison.json), [metadata and dated substitutions](docs/verification/live-check.json), [actual weekly output](docs/verification/weekly-output.txt).

## Displayed grid comparison

| Day | Periods | Subjects in period order |
|---|---|---|
| Monday | 4, 5 | Falsafa (Sem); Falsafa (Ma) |
| Tuesday | 4, 5, 6 | Falsafa (Sem); Raqamli iqtisodiyot (Ma); Raqamli iqtisodiyot (Ma) |
| Wednesday | 5, 6 | Falsafa (Ma); Raqamli iqtisodiyot (Sem) |
| Thursday | 4, 5, 6 | Raqamli iqtisodiyot (Sem); Marketing (Ma); Marketing (Ma) |
| Friday | 4, 5 | Marketing (sem); Marketing (sem) |
| Saturday | none | confirmed empty |

The visual cards use short teacher/room aliases. Full names and room strings in the bot come from the matching source records, without guessing expansions. For example, the displayed `5/106 lab / 5/108 lab` refers to records named `5/106-12 lab` and `5/108-12 lab`; both are retained. `7/214-60` remains exactly that string. The source full auditorium name is `7-bino faollar zali-160`, while its published short display name is `7-bino faollar-160 zali`; the bot preserves the full record.

## Tested using fixtures, not live events

Tashkent midnight; month/year/leap boundaries; two validity periods within one week; expired/future dates; added Saturday cards; multiple subgroups; missing teachers/rooms; source errors and partial/empty parses; update detection; unchanged successful checks; 20–30 simultaneous requests sharing a refresh; failure cooldown and recovery; SQLite restart persistence; bounded HTTP retries; HTML escaping and long Unicode message splitting; all commands and keyboard routes; unrecognized messages; request handling crossing midnight; and unknown substitution formats.

The test suite does not wait four wall-clock hours; it advances an injected clock to verify the freshness boundary. It does not manufacture a selective A/B calendar anchor: selective cycle masks are rejected when the public source supplies no date mapping.

## Remaining limits / not executed

- **No Telegram API polling or delivery test used the supplied token.** The credential posted in chat should be revoked. Offline handler tests construct a dummy local Bot object with a deliberately nonfunctional credential and replace sending; they do not call Telegram.
- **Docker build and Compose startup were not run** because Docker is not installed in this environment. The Dockerfile and persistent/restarting Compose configuration are supplied for deployment.
- The public date-specific/current timetable is disabled. The bot uses the validated recurring schedule and labels it **Muntazam jadval**.
- No populated substitution/cancellation report was available for validation. The bot confirms the explicit no-change format, but does not claim to apply unverified populated reports. Such reports show an Uzbek limitation notice. See README for the precise behavior.
- All this group's live cards apply to both A/B weeks. A future selective cycle without a public calendar mapping, changed bell scheme, or unsupported multi-period format fails closed instead of returning guessed lessons.
- Initial sandbox HTTP requests were blocked, and the browser connector timed out. Authorized direct HTTP and a temporary Playwright/Chrome session succeeded; there is no remaining live extraction blocker for the inspected source.
