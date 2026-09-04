# Miloto Draw List (Paginated) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public `GET /miloto/draws` endpoint returning a lightweight, server-paginated (max 20/page) list of Miloto draws for a frontend data table.

**Architecture:** A new `list_miloto_draws` repository function queries `miloto_draws` ordered newest-first with `OFFSET`/`LIMIT` and a `COUNT(*)`, maps each row to a lightweight `MilotoDrawListItem` (Spanish full date, abbreviated jackpot, `jackpot` flag), and wraps them in the existing `PaginatedResponse` envelope. A new public route on `miloto_router` exposes it.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0 async (asyncpg), pydantic v2, pytest + pytest-asyncio.

## Global Constraints

- `size` query param range: `1..20` (max 20 per page). `size > 20` or `< 1` -> `422`.
- `page` query param: `>= 1`, default `1`. Out-of-range page -> `items: []` (never 404).
- Response envelope: reuse `app.games.pagination.PaginatedResponse[T]` (`items`/`page`/`size`/`total`/`pages`).
- Ordering: newest first - `game_id DESC`.
- `pages = ceil(total / size)`; `pages = 0` when `total == 0`.
- `game_date` string uses `app.shared.date_utils.full_date` -> `"Lunes, 27 de Julio de 2026"`.
- `accumulated` string uses a new `app.shared.math_utils.abbreviate_pesos` -> `"$120M"` / `"$2.500M"` (round down to whole millions, Spanish group separator, `$` prefix).
- `jackpot` flag = `True` when `hits_5` is not `None`.
- Public route (no admin key), like the existing `GET /miloto/draw/{draw_id}`.
- Read-only; must never modify stored data.
- Tests are integration tests against the real local Postgres; run from `backend/`. Existing autouse fixtures (`release_reserved_test_id`, `remove_test_created_rows`) clean up reserved test rows - never delete real data.
- Match repo style: Google-style docstrings (avoid `:param:`), `ruff` + `pyright` clean on new code, tests named `tests_*.py`.

---

### Task 1: Abbreviation helper `abbreviate_pesos`

**Files:**
- Modify: `backend/app/shared/math_utils.py`
- Test: `backend/tests/unit/test_math_utils.py` (check whether it exists first)

**Interfaces:**
- Produces: `def abbreviate_pesos(value: int) -> str` in `app.shared.math_utils` - `120_000_000 -> "$120M"`, `2_500_000_000 -> "$2.500M"`; round down to whole millions.

- [ ] **Step 1: Locate the unit test file for math_utils**

Run: `ls backend/tests/unit/`
Expected: `test_math_utils.py` exists, or create it.

- [ ] **Step 2: Write the failing tests**

Append to the math utils unit test file (create it if absent):

```python
@pytest.mark.unit
def test_abbreviate_pesos_millions() -> None:
    """
    Verify a whole number of millions formats as a dollar-prefixed M amount.

    ``120_000_000 pesos`` must render as ``"$120M"``.
    """
    result = abbreviate_pesos(120_000_000)
    assert result == "$120M", "Unexpected abbreviate_pesos output."


@pytest.mark.unit
def test_abbreviate_pesos_billions_in_millions() -> None:
    """
    Verify billions render as a grouped millions figure with an M suffix.

    ``2_500_000_000 pesos`` is 2500 million and must render as ``"$2.500M"``.
    """
    result = abbreviate_pesos(2_500_000_000)
    assert result == "$2.500M", "Unexpected abbreviate_pesos output."
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_math_utils.py -v` (adjust filename)
Expected: FAIL - `ImportError: cannot import name 'abbreviate_pesos'`.

- [ ] **Step 4: Implement `abbreviate_pesos`**

Add to `backend/app/shared/math_utils.py`:

```python
def abbreviate_pesos(value: int) -> str:
    """
    Format a peso amount as a compact currency string.

    Rounds down to whole millions and formats with a Spanish group separator,
    a ``$`` prefix and an ``M`` suffix (e.g. ``120_000_000 -> "$120M"``,
    ``2_500_000_000 -> "$2.500M"``).

    :param value: The amount in pesos.
    :return: The abbreviated currency string.
    """
    millions = value // 1_000_000
    return f"${int_to_localized_es(millions)}M"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_math_utils.py -v`
Expected: PASS.

- [ ] **Step 6: Lint, typecheck, format**

Run: `uv run ruff check app/shared/math_utils.py tests/unit/test_math_utils.py && uv run ruff format --check app/shared/math_utils.py tests/unit/test_math_utils.py && uv run pyright app/shared/math_utils.py`
Expected: all clean.

- [ ] **Step 7: Commit**

```bash
git add backend/app/shared/math_utils.py backend/tests/unit/test_math_utils.py
git commit -m "feat: add abbreviate_pesos helper for table amounts"
```

---

### Task 2: `MilotoDrawListItem` schema

**Files:**
- Modify: `backend/app/games/schemas.py`

**Interfaces:**
- Produces: `class MilotoDrawListItem(BaseModel)` in `app.games.schemas` with fields:
  `game_id: int`, `game_date: str`, `numbers: list[int]`, `accumulated: str`, `jackpot: bool`.

- [ ] **Step 1: Add the model**

Append to `backend/app/games/schemas.py` (after the existing schema classes; `BaseModel` and `ConfigDict` are already imported):

```python
class MilotoDrawListItem(BaseModel):
    """A lightweight Miloto draw row for a frontend data table."""

    model_config = ConfigDict(frozen=True)

    game_id: int
    game_date: str
    numbers: list[int]
    accumulated: str
    jackpot: bool
```

- [ ] **Step 2: Lint/typecheck**

Run: `uv run ruff check app/games/schemas.py && uv run pyright app/games/schemas.py`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add backend/app/games/schemas.py
git commit -m "feat: add MilotoDrawListItem projection schema"
```


---

### Task 3: Repository `list_miloto_draws`

**Files:**
- Modify: `backend/app/games/repository.py`

**Interfaces:**
- Consumes: `app.games.schemas.MilotoDrawListItem`, `app.games.models.MilotoDraw`, `app.shared.date_utils.full_date`, `app.shared.math_utils.abbreviate_pesos`, `app.games.pagination.PaginatedResponse`.
- Produces: `async def list_miloto_draws(session: AsyncSession, page: int, size: int) -> PaginatedResponse[MilotoDrawListItem]`.

- [ ] **Step 1: Add imports**

In `backend/app/games/repository.py`, change the SQLAlchemy import line from:

```python
from sqlalchemy import insert
```

to:

```python
from sqlalchemy import func, insert, select
```

Add `MilotoDrawListItem` to the schema import block, and add the date/pagination imports. The relevant imports should end up as:

```python
from app.games.models import BalotoDraw, MilotoDraw, RevanchaDraw
from app.games.pagination import PaginatedResponse
from app.games.schemas import (
    BalotoSchema,
    Game,
    GameSchema,
    MilotoDrawListItem,
    MilotoSchema,
    ResultDetails,
    RevanchaSchema,
)
from app.shared.date_utils import full_date
from app.shared.math_utils import abbreviate_pesos
```

(Keep the other existing imports; only add `func`/`select` and the new names.)

- [ ] **Step 2: Add a row-to-item mapper**

Add alongside `_to_schema`:

```python
def _to_list_item(row: MilotoDraw) -> MilotoDrawListItem:
    """Map one ``miloto_draws`` row to the lightweight table projection."""
    return MilotoDrawListItem(
        game_id=row.game_id,
        game_date=full_date(row.game_date),
        numbers=row.numbers,
        accumulated=abbreviate_pesos(row.accumulated),
        jackpot=row.hits_5 is not None,
    )
```

- [ ] **Step 3: Add the `list_miloto_draws` function**

Add at the end of `backend/app/games/repository.py`:

```python
async def list_miloto_draws(session: AsyncSession, page: int, size: int) -> PaginatedResponse[MilotoDrawListItem]:
    """
    Fetch a page of Miloto draws for a frontend data table, newest first.

    Returns a lightweight projection (``MilotoDrawListItem``) of at most
    ``size`` rows ordered by ``game_id`` descending. When ``total`` is zero
    the ``pages`` count is 0.

    :param session: Active session used to run the queries.
    :param page: 1-indexed page number (>= 1).
    :param size: Number of items per page (1..20).
    :return: A paginated envelope of table rows.
    """
    model = MilotoDraw
    total = (await session.execute(select(func.count()).select_from(model))).scalar_one()

    result = await session.execute(
        select(model).order_by(model.game_id.desc()).offset((page - 1) * size).limit(size)
    )
    items = [_to_list_item(row) for row in result.scalars()]

    pages = 0 if total == 0 else (total + size - 1) // size
    return PaginatedResponse[MilotoDrawListItem](
        items=items, page=page, size=size, total=total, pages=pages
    )
```

- [ ] **Step 4: Lint/typecheck**

Run: `uv run ruff check app/games/repository.py && uv run pyright app/games/repository.py`
Expected: clean. If pyright rejects `PaginatedResponse[MilotoDrawListItem](...)` generic instantiation, change the return expression to a plain `PaginatedResponse(items=items, page=page, size=size, total=total, pages=pages)` and rely on the return annotation for the generic type.

- [ ] **Step 5: Commit**

```bash
git add backend/app/games/repository.py
git commit -m "feat: add list_miloto_draws paginated repository query"
```

---

### Task 4: Router `GET /miloto/draws`

**Files:**
- Modify: `backend/app/games/router.py`

**Interfaces:**
- Consumes: `repository.list_miloto_draws`, `app.games.schemas.MilotoDrawListItem`, `app.games.pagination.PaginatedResponse`, `fastapi.Query`.
- Produces: `GET /miloto/draws` on `miloto_router`, public, returning `PaginatedResponse[MilotoDrawListItem]`.

- [ ] **Step 1: Update imports**

In `backend/app/games/router.py`, change:

```python
from fastapi import APIRouter, Depends, HTTPException, status
```

to:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
```

Add `MilotoDrawListItem` to the `from app.games.schemas import (...)` block, and add:

```python
from app.games.pagination import PaginatedResponse
```

- [ ] **Step 2: Add the route**

Add inside the Miloto `# region ROUTERS` block. The path is `/draws` (plural) so it does not shadow `/draw/{draw_id}`:

```python
@miloto_router.get("/draws", response_model=PaginatedResponse[MilotoDrawListItem])
async def list_miloto_draws_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1, 
    size: Annotated[int, Query(ge=1, le=20)] = 20,
) -> PaginatedResponse[MilotoDrawListItem]:
    """List Miloto draws for a data table, newest first, max 20 per page."""
    return await repository.list_miloto_draws(session, page=page, size=size)
```

- [ ] **Step 3: Lint/typecheck/format**

Run: `uv run ruff check app/games/router.py && uv run ruff format --check app/games/router.py && uv run pyright app/games/router.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add backend/app/games/router.py
git commit -m "feat: add public GET /miloto/draws paginated endpoint"
```
