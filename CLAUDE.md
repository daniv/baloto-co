# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

`baloto-co` is a Python backend for tracking Colombian lottery draws (Baloto, Revancha, Miloto): scraping and validating draw results (numbers, prizes, jackpots) against typed schemas. The repo currently contains only `backend/`; there is no frontend yet. Scraping is implemented in `app/scraper/` as async Playwright page objects for the `baloto.com` results pages (see Architecture below). `fastapi[standard]` is a declared dependency but nothing uses it yet — `app/main.py` is still a placeholder entrypoint with no API wired up.

## Commands

All commands run from `backend/`, via `uv`.

- Install/sync deps: `uv sync`
- Full required check suite: `uv run poe check` (format-check, lint, typecheck, test)
- Full check suite incl. docstring lint: `uv run poe check-all` (adds `lint-docs`)
- Fast pre-flight (no full test run): `uv run poe check-fast` (format-check, lint, pyright, `pytest --collect-only`)
- Format: `uv run poe format` / check only (no write): `uv run poe format-check`
- Lint: `uv run poe lint` (ignores missing-docstring rules D100/D101/D102) / autofix: `uv run poe lint-fix` / autofix incl. unsafe fixes: `uv run poe lint-fix-all`
- Docstring-only lint (D100/D101/D102 — missing module/class/method docstrings): `uv run poe lint-docs`
- Strict type check: `uv run poe typecheck` (pyright, `typeCheckingMode = "strict"`)
- Tests: `uv run poe test` / stop-on-first + verbose: `uv run poe test-xvv` / with coverage: `uv run poe testcov`
- Run one test file/dir with slowest-duration report: `uv run poe test-perf --path <path> --durations <n>`
- Run a single test directly: `uv run pytest <path>::<test_name> -x -vv`

Notes:
- `tests/` now exists with a real suite: `tests/unit/` (plain unit tests for `app/shared/*`) and `tests/unit/scraper/` (Playwright page-object tests, see Testing below). The suite does **not** currently pass out of the box, though:
  - Collection fails immediately without a real DB password: `app/core/config.py` builds the `settings` singleton at import time, and it rejects the default `CHANGE_ME` `db_password`. No `.env` ships in the repo, and `pytest-env` (which `[tool.pytest_env]` targets) isn't in the dev dependency group, so `../.env.test` isn't auto-loaded either — set `DB_PASSWORD=<anything-but-CHANGE_ME>` to collect/run anything that imports `app.scraper` (transitively imports `app.core.config`).
  - `uv run poe lint` (29 errors) and `uv run poe format-check` (6 files) and `uv run poe typecheck` (7 errors) all currently fail, mostly on the new `tests/unit/scraper/` files.
- Test files must be named `tests_*.py` (not pytest's default `test_*.py`) — see `[tool.pytest].python_files` in `pyproject.toml`.
- Network installs (`uv sync`, `uv pip install`) can fail here with a TLS `UnknownIssuer` error behind the local proxy; pass `--system-certs` to `uv`, or set `UV_SYSTEM_CERTS=1` (the older `UV_NATIVE_TLS=1` still works but is deprecated).
- Ruff lint uses `select = ["ALL"]` (see `pyproject.toml`) with a short explicit ignore list — new rule categories are opt-out, not opt-in.

## Architecture

- **`app/core/config.py`** — one settings singleton, `settings = BackendSettings()` (pydantic-settings), loaded from `../.env` (relative to `backend/`) then the `pyproject.toml` `[project]` table, case-insensitive. Per-game constants live in nested frozen sub-settings: `settings.miloto`, `settings.baloto`, `settings.revancha` (each a `MilotoSettings`/`BalotoSettings`/`RevanchaSettings`) — first draw id/date, number range (`max_value`, `max_super_balota` for Baloto/Revancha), minimum jackpot/hit prizes, draw weekdays, and the results URL. `RevanchaSettings` extends `BalotoSettings` since Revancha is drawn from the same balls as Baloto — it only overrides the prize floor and URL.
- **`app/games/schemas.py`** — one pydantic model per game draw result: `MilotoSchema`, `BalotoSchema`, `RevanchaSchema`, all extending the abstract `BaseModelSchema`. `GameSchema` is a `discriminator="game"` tagged union of the three, so each subclass's `game: Literal[...]` field must be a value unique to that class for the union to resolve correctly. `game_date` accepts Spanish-language date strings (parsed via `app/shared/date_utils.parse_spanish_date`) and rejects future dates. The computed `combination_id` field hashes the winning numbers into a hex bitmap via `app/shared/math_utils.numbers_to_hex` (Baloto/Revancha append the super balota digit after a `:`). Prize tiers (`hits_3`, `hits_4`, `hits_5` on the base class; `hits_2` on Miloto; `hits_sb`/`hits_2_sb`/`hits_3_sb`/`hits_4_sb`/`hits_5_sb` on Baloto/Revancha) are modeled as individually named fields rather than a shared `dict`, deliberately — it keeps each game's valid prize-tier keys from leaking into the others (e.g. `hits_sb` must not be a valid attribute on `MilotoSchema`). `ResultDetails` (`prize_for_winner`/`winners`) is the value type for every hit-tier field, and is also the return type of the scraper's `get_details()`/`get_detail()` — it's the shared contract between extraction and the schema layer.
- **`app/games/pagination.py`** — generic `PaginatedResponse[T]` envelope (`items`/`page`/`size`/`total`/`pages`) for future paginated list endpoints; not wired to anything yet.
- **`app/scraper/`** — async Playwright scraper for the three games' result pages, as a page-object pattern:
  - `parsers/base.py` — abstract `BasePage`: validates `draw_id`, builds the target URL from the concrete page's `_result_url`, owns a `ValidatorRegistry`, and implements `open()` (navigate, then run every registered validator) plus the shared `get_winner_numbers()`.
  - `parsers/baloto.py` / `parsers/miloto.py` — concrete pages. Baloto and Revancha share one `BalotoRevanchaResultPage` implementation (identical page structure); `BalotoResultPage`/`RevanchaResultPage` differ only in `_result_url` and the identity validators they register. `get_details()`/`get_detail()` confirm every expected hit category (the `BalotoHits`/`MilotoHits` literal types) is present in the payout table, then omit zero-winner categories from the returned `dict[str, ResultDetails]`.
  - `validators.py` — a `Validator` protocol plus `ValidatorRegistry` (ordered, atomic duplicate-name detection) run by `BasePage.open()` to reject a loaded page before extraction is trusted (wrong URL/draw id/game identity).
  - `exceptions.py`, `loader_client.py` (`get_html()` — an `httpx`-based alternative to Playwright navigation that detects the site silently redirecting a missing draw to its home page; note `httpx` isn't a direct `pyproject.toml` dependency, it's pulled in transitively via `fastapi[standard]`), `playwright_client.py` (placeholder, not implemented).
  - `__init__.py` re-exports a `ResultPage` structural `Protocol` plus the concrete page classes as the package's stable public API.
  - Gotcha: `BasePage.get_winner_numbers()` reads `settings.baloto.winning_numbers_count` for every game including Miloto — harmless today since the value (5) is the same everywhere, but a hidden cross-game coupling if a game with a different count is ever added.
- **`app/shared/`** — game-agnostic helpers: `date_utils.py` (Spanish date parsing/formatting via `dateparser`/`babel`), `math_utils.py` (`numbers_to_hex` bitmap encoding of drawn numbers; `es_localized_to_int`/`int_to_localized_es`/`parse_millions_to_pesos` for Spanish-locale integer parsing/formatting, used throughout the scraper to read displayed prize/id text), `console.py` (shared `rich` `Console`/`error_console` singletons for terminal output).
- **Testing** (`backend/tests/`) — `tests/unit/` holds plain unit tests; `tests/unit/scraper/` drives real headless Chromium against local HTML fixtures (`tests/resources/html/*.html`) and expected-value JSON (`tests/resources/ex_results/<test_module>/<game>.json`), loaded through `GameCaseLoader`/`GameTestCase` (`tests/unit/scraper/loaders.py`/`model.py`). Cross-game parametrization uses custom markers `crossgames`/`only_game(name)`/`skip_game(name)` and a `--game {miloto,baloto,revancha}` CLI flag, defined in `tests/conftest.py` and `tests/unit/scraper/conftest.py`. See the Commands notes above — this suite doesn't currently collect/pass cleanly.
- Adding a new game follows the existing pattern: a `*Settings` class in `config.py` (nested under `BackendSettings`) plus a `*Schema` class in `schemas.py` wired into the `GameSchema` union with its own unique `game` discriminator value, and — if the game needs live scraping — a page object in `app/scraper/parsers/` implementing the `ResultPage` protocol plus any game-specific validators.
