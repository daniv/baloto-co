# Miloto Draw List (Paginated) — Design

**Date:** 2026-09-03
**Status:** Approved
**Scope:** Add a public `GET /miloto/draws` endpoint that returns a lightweight,
paginated list of Miloto draws for a frontend data table. Miloto-only for now
(Approach A — follows the existing hand-written per-game router pattern).

## Goal

Expose the stored Miloto draws as a server-side-paginated list exposing only the
fields a frontend data table needs. Filtering/projection is done on the backend,
not the frontend.

## API

```
GET /miloto/draws?page=1&size=20
```

- Public route (no admin key), matching the existing single-draw `GET /miloto/draw/{draw_id}`.
- Query params:
  - `page: int = 1`, `ge=1`
  - `size: int = 20`, `1 <= size <= 20` (max 20 per page)
- Response: `PaginatedResponse[MilotoDrawListItem]`.

Reuses the existing `app/games/pagination.PaginatedResponse[T]` envelope
(`items` / `page` / `size` / `total` / `pages`).

## Response item — `MilotoDrawListItem`

One row per draw, a pydantic `BaseModel`:

| field        | type     | notes                                                       |
|--------------|----------|-------------------------------------------------------------|
| `game_id`    | `int`    | Official draw number                                        |
| `game_date`  | `str`    | Full Spanish: `"Lunes, 27 de Julio de 2026"` (`full_date`)  |
| `numbers`    | `list[int]` | The 5 winning numbers                                    |
| `accumulated`| `str`    | Abbreviated: `"120M"` / `"2B"` (round down, no decimals)    |
| `jackpot`    | `bool`   | `True` when `hits_5` is not `None`                          |

## Behavior

- Ordered **latest first** by `game_id DESC`.
- `size > 20` → `422` (FastAPI `Query(le=20)`).
- Out-of-range page → `items: []` with correct `total` / `pages` (no 404).
- `pages = ceil(total / size)`; `pages = 0` when `total == 0`.
- Read-only; never modifies data.

## Components

1. **`app/games/repository.py`** — new `list_miloto_draws(session, page, size) -> PaginatedResponse[MilotoDrawListItem]`.
   - `count(*)` on `MilotoDraw` for `total`.
   - `select(MilotoDraw).order_by(game_id.desc()).offset((page-1)*size).limit(size)`.
   - Map each row to `MilotoDrawListItem`.

2. **`app/games/router.py`** — new `GET /miloto/draws` route on `miloto_router`.
   - Query params `page`, `size` via `Query(...)`.
   - Calls `repository.list_miloto_draws`, returns the envelope.

3. **`MilotoDrawListItem`** — new pydantic model (kept in `app/games/schemas.py`).

4. **`app/shared/math_utils.py`** — new abbreviation helper, e.g.
   `abbreviate_pesos(value: int) -> str`: `120_000_000 -> "120M"`, `2_000_000_000 -> "2B"` (round down, no decimals).

5. **`app/shared/date_utils.py`** — reuse existing `full_date()` (no change).

## Testing (integration, `tests/integration/games/tests_miloto_api.py`)

- Insert a small set of known Miloto draws via POST using reserved test ids.
- `GET /miloto/draws` and assert:
  - envelope fields `page` / `size` / `total` / `pages`.
  - `items` ordered `game_id DESC` (latest first).
  - `jackpot` flag reflects whether `hits_5` was set.
  - `accumulated` is abbreviated (e.g. `"120M"`).
  - `game_date` is the full Spanish format.
  - `size=21` → `422` (max is 20).
  - out-of-range page → empty `items`, correct `total`/`pages`.
- Non-destructive: existing autouse fixtures clean up the reserved test rows.

## Out of scope

- Baloto / Revancha list endpoints (same `list_*` repository shape can be reused later).
- Frontend work (data table UI) — not part of this repo (backend only).
- Sorting beyond `game_id DESC`.
