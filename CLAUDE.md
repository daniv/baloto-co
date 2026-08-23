# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

`baloto-co` is a Python backend for tracking Colombian lottery draws (Baloto, Revancha, Miloto): validating scraped draw results (numbers, prizes, jackpots) against typed schemas. The repo currently contains only `backend/`; there is no frontend yet. `playwright` is a dependency, so scraping the results pages (`baloto.com`) is the intended data source, though no scraping code exists yet — `app/main.py` is still a placeholder entrypoint.

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
- `tests/` does not exist yet. `format-check`, `lint`, and `test` all reference `app tests`, so they currently fail at that step until a `tests/` directory exists.
- Test files must be named `tests_*.py` (not pytest's default `test_*.py`) — see `[tool.pytest].python_files` in `pyproject.toml`.
- Network installs (`uv sync`, `uv pip install`) can fail here with a TLS `UnknownIssuer` error behind the local proxy; pass `--system-certs` to `uv`, or set `UV_SYSTEM_CERTS=1` (the older `UV_NATIVE_TLS=1` still works but is deprecated).
- Ruff lint uses `select = ["ALL"]` (see `pyproject.toml`) with a short explicit ignore list — new rule categories are opt-out, not opt-in.

## Architecture

- **`app/core/config.py`** — one settings singleton, `settings = BackendSettings()` (pydantic-settings), loaded from `../.env` (relative to `backend/`) then the `pyproject.toml` `[project]` table, case-insensitive. Per-game constants live in nested frozen sub-settings: `settings.miloto`, `settings.baloto`, `settings.revancha` (each a `MilotoSettings`/`BalotoSettings`/`RevanchaSettings`) — first draw id/date, number range (`max_value`, `max_super_balota` for Baloto/Revancha), minimum jackpot/hit prizes, draw weekdays, and the results URL. `RevanchaSettings` extends `BalotoSettings` since Revancha is drawn from the same balls as Baloto — it only overrides the prize floor and URL.
- **`app/games/schemas.py`** — one pydantic model per game draw result: `MilotoSchema`, `BalotoSchema`, `RevanchaSchema`, all extending the abstract `BaseModelSchema`. `GameSchema` is a `discriminator="game"` tagged union of the three, so each subclass's `game: Literal[...]` field must be a value unique to that class for the union to resolve correctly. `game_date` accepts Spanish-language date strings (parsed via `app/shared/date_utils.parse_spanish_date`) and rejects future dates. The computed `combination_id` field hashes the winning numbers into a hex bitmap via `app/shared/math_utils.numbers_to_hex` (Baloto/Revancha append the super balota digit after a `:`). Prize tiers (`hits_3`, `hits_4`, `hits_5` on the base class; `hits_2` on Miloto; `hits_sb`/`hits_2_sb`/`hits_3_sb`/`hits_4_sb`/`hits_5_sb` on Baloto/Revancha) are modeled as individually named fields rather than a shared `dict`, deliberately — it keeps each game's valid prize-tier keys from leaking into the others (e.g. `hits_sb` must not be a valid attribute on `MilotoSchema`).
- **`app/shared/`** — game-agnostic helpers: `date_utils.py` (Spanish date parsing/formatting via `dateparser`/`babel`), `math_utils.py` (`numbers_to_hex` bitmap encoding of drawn numbers), `console.py` (shared `rich` `Console`/`error_console` singletons for terminal output).
- Adding a new game follows the existing pattern: a `*Settings` class in `config.py` (nested under `BackendSettings`) plus a `*Schema` class in `schemas.py` wired into the `GameSchema` union with its own unique `game` discriminator value.
