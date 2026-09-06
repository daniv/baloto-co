# Miloto "Vista Avanzada"

## Backend

1. New query schema (`app/games/schemas.py` or inline `Query` params) for the advanced filter:
   - `date_mode: Literal["year", "month", "range", "last_n"] | None`
   - `year: int | None`, `month: int | None` (1-12, requires `year`)
   - `date_from: date | None`, `date_to: date | None`
   - `last_n: int | None` (positive, e.g. capped at 500) - "Últimos X sorteos"
   - `jackpot_only: bool = False`
   - `page`, `size` (options 10/15/20/30/50 per spec)
2. New repository function `list_miloto_draws_advanced(...)` in `app/games/repository.py` - same shape as `list_miloto_draws`, but resolves `date_mode` into a filter:
   - `year` -> Jan 1-Dec 31 range
   - `month` -> first/last day of that month
   - `range` -> given `date_from`/`date_to` bounds
   - `last_n` -> restrict to the most recent `last_n` draws by `game_id` (a subquery selecting the top-`last_n` `game_id`s ordered descending), then apply `jackpot_only` and pagination *within* that window - not a plain `LIMIT` tacked onto the final page, since paginating the last 100 draws into pages of 10 must stay confined to those 100.
   - reuses the existing `jsonb_typeof(hits_5)` check for `jackpot_only`.
3. New route `GET /miloto/draws/advanced` on `miloto_router`, returning `PaginatedResponse[MilotoDrawListItem]` (same list item type, no new frontend type needed there).
4. Validation: 422 if a date mode is selected but its required fields are missing, `date_from > date_to`, or `last_n <= 0`.

## Frontend

1. New route `/miloto/vista-avanzada` -> `MilotoAdvancedView.vue`, breadcrumb "Vista Avanzada", `meta.parent` -> Miloto.
2. `navItems`/`NavItem` type needs a `children` array to support Miloto -> Vista Avanzada as a sub-item; `AppSidebar.vue` (and the mobile drawer in `App.vue`) need to render that nested group.
3. `src/api/miloto.ts`: `getMilotoDrawsAdvanced(filters, page, size)`.
4. View: "Buscar por fecha" checkbox reveals a mode selector (Año / Mes / Rango / Últimos X sorteos) with matching inputs (year select, month+year select, two `AppDatePicker`s for the range, a numeric input for X); "Mostrar solo Ganadores" checkbox; table identical to `MilotoView` (same columns, `Detalles` -> `/miloto/draw/{id}`); pagination via existing `AppPagination` with size options 10/15/20/30/50.
5. Filter persistence: mirror `MilotoView`'s existing pattern - every filter, `page`, and `size` synced to the route's query string. That alone makes state survive back/forward nav and reload, no backend involved.

## Open decisions before implementing

- **Redis**: not needed for filter persistence (query-string does that already, same as `MilotoView` today). It'd only be useful as a result-cache for the advanced query itself (keyed by filter hash, invalidated on Miloto writes) - worth it only if this query becomes a hot path. Given the dataset size, leaning toward skipping it for v1 and revisiting if needed.
- **Year/month options source**: reuse the existing `/miloto/draws/dates` endpoint (derive distinct years client-side) vs. add a dedicated `/miloto/draws/years` endpoint. Leaning toward reusing the existing one unless the dates list gets large.
- **Sidebar nesting UI**: collapsible group vs. always-expanded sub-link under Miloto - cosmetic call, leaning toward always-expanded since there's only one child today.
