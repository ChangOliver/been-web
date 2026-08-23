# TravelMap Implementation Plan

## 1. Product definition

Build an original, local-first travel tracking web application. It may offer functionality commonly found in travel trackers, but it must not copy proprietary source code, branding, assets, datasets, or bypass another product's licensing.

The first release should let one person:

- mark countries as visited, lived in, or planned;
- explore those countries on an interactive world map;
- record visits and trips with dates and notes;
- view useful travel statistics;
- search bundled countries, with the same search flow expanding to cities and airports later;
- import and export all personal data;
- run the entire application on localhost without an external account or paid service.

## 2. Scope and delivery strategy

### MVP

The MVP includes:

1. Local application setup and database.
2. Interactive 2D country map.
3. Country status and visit tracking.
4. Dashboard and basic statistics.
5. Country list and country detail pages.
6. Trip CRUD and trip-to-place associations.
7. Global search over bundled geographic data.
8. JSON backup and restore.
9. Responsive layout, dark mode, tests, and local run documentation.

### Post-MVP

Add in this order:

1. First-level regions/states/provinces.
2. City and airport tracking.
3. Timeline and richer statistics.
4. 3D globe.
5. Photos and Markdown notes.
6. Optional multiple local profiles.
7. Optional CloudKit or another sync service only as a separate, opt-in project.

Keeping these items out of the MVP prevents the geographic data and 3D rendering work from delaying the core tracking workflow.

## 3. Technical architecture

### Frontend

- React 19 with TypeScript in strict mode.
- Vite for development and production builds.
- React Router for page routing.
- TanStack Query for API state and caching.
- Zustand only for ephemeral UI state such as map selection, filters, and panel visibility.
- Tailwind CSS for styling and design tokens.
- MapLibre GL JS for the 2D map.
- Turf.js for geographic calculations that are not already precomputed.
- React Hook Form and Zod for forms and client-side validation.
- Vitest, React Testing Library, and Playwright for tests.

### Backend

- Python 3.12 or newer.
- FastAPI with Pydantic v2 request and response models.
- SQLModel and Alembic.
- SQLite with foreign keys and WAL mode enabled.
- Pytest for unit and integration tests.
- Static geographic reference data is bundled with the project; mutable user data is stored in SQLite.

### Local runtime

- Development: Vite on port 5173 and FastAPI on port 8000.
- Production-local: build the frontend and serve it from FastAPI, giving the user one process and one localhost URL.
- Store runtime data outside the source tree in a configurable data directory. Default to `./data` for the initial implementation and document how to override it.
- Do not require internet access after dependencies and geographic assets have been installed.

## 4. Repository layout

```text
been-web/
  apps/
    web/
      src/
        app/                 # router, providers, global layout
        components/          # shared UI components
        features/
          countries/
          dashboard/
          map/
          search/
          settings/
          trips/
        lib/                 # API client, validation, formatting
        styles/
        test/
      public/
      package.json
      vite.config.ts
    api/
      app/
        api/                 # versioned routers
        core/                # configuration, database, errors
        models/              # SQLModel persistence models
        schemas/             # API input/output models
        services/            # business logic and imports/exports
        main.py
      migrations/
      tests/
      pyproject.toml
  packages/
    geo-data/                # licenses, source metadata, build scripts
    shared/                  # generated API types if introduced
  data/                      # ignored runtime SQLite/backups/uploads
  scripts/                   # setup, data preparation, local launch
  .env.example
  .gitignore
  README.md
```

Use feature-based frontend folders. A feature owns its components, hooks, queries, types, and tests. Shared components should contain only genuinely reusable UI primitives.

## 5. Geographic data

Use openly licensed sources and preserve attribution in both the repository and the Settings/About page.

- Countries: Natural Earth country boundaries, simplified for browser rendering.
- Country metadata: ISO 3166 codes from a redistribution-compatible source.
- Regions: Natural Earth administrative level 1 or another compatible open dataset.
- Cities: GeoNames or Natural Earth populated places.
- Airports: OurAirports.

Create a reproducible data preparation script that:

1. validates source file checksums;
2. normalizes identifiers to ISO codes where possible;
3. fixes invalid geometry;
4. simplifies geometry at multiple zoom levels;
5. emits versioned GeoJSON or vector tiles plus compact search indexes;
6. writes a manifest containing source URLs, versions, licenses, and build time.

Do not store mutable visit state inside GeoJSON. Join user state to reference features by stable codes such as `US` and `US-CA`.

## 6. Domain model

Reference entities are read-only and can initially live in bundled data files. User-owned entities live in SQLite.

### `profile`

- `id`: UUID primary key
- `name`: required string
- `is_default`: boolean with exactly one default profile enforced by the service
- `created_at`, `updated_at`: UTC timestamps

Create one default profile during database initialization. The MVP always uses it automatically; this keeps database constraints sound while leaving the UI and workflows for multiple profiles until later.

### `place_status`

- `id`: UUID primary key
- `profile_id`: required foreign key
- `place_type`: enum (`country`, `region`, `city`, `airport`)
- `place_code`: stable reference-data identifier
- `status`: enum (`visited`, `lived`, `planned`)
- `first_visited_on`: nullable date
- `last_visited_on`: nullable date
- `visit_count`: non-negative integer, derived or maintained transactionally
- `notes`: nullable text
- `created_at`, `updated_at`: UTC timestamps
- unique constraint on (`profile_id`, `place_type`, `place_code`)

### `trip`

- `id`: UUID primary key
- `profile_id`: required foreign key
- `name`: required string
- `start_date`, `end_date`: dates; end must not precede start
- `status`: enum (`planned`, `completed`, `cancelled`)
- `notes`: nullable Markdown text
- `created_at`, `updated_at`: UTC timestamps

### `trip_stop`

- `id`: UUID primary key
- `trip_id`: foreign key with cascade delete
- `place_type`: enum
- `place_code`: reference identifier
- `arrival_date`, `departure_date`: nullable dates
- `position`: integer for stable ordering
- `notes`: nullable text

### `visit`

- `id`: UUID primary key
- `profile_id`: required foreign key
- `place_type`: enum
- `place_code`: reference identifier
- `trip_id`: nullable foreign key
- `arrived_on`, `departed_on`: nullable dates
- `notes`: nullable text
- `created_at`, `updated_at`: UTC timestamps

Visits are the source of dated travel history. A place can still be marked visited without a dated visit. Statistics must explicitly distinguish these cases.

### Later entities

- Additional profile preferences and profile switching UI.
- `photo`: metadata and a relative path to a locally managed image.
- `tag` and `trip_tag`: optional organization.

## 7. API contract

Prefix endpoints with `/api/v1`. Return JSON and use a consistent error envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request could not be saved.",
    "details": {}
  }
}
```

### Health and metadata

- `GET /health`
- `GET /api/v1/meta` — app, schema, and geographic dataset versions

### Places and search

- `GET /api/v1/countries`
- `GET /api/v1/countries/{country_code}`
- `GET /api/v1/regions?country_code=US`
- `GET /api/v1/search?q=...&types=country,city,airport`

### User place state

- `GET /api/v1/place-statuses`
- `PUT /api/v1/place-statuses/{place_type}/{place_code}`
- `DELETE /api/v1/place-statuses/{place_type}/{place_code}`
- `GET /api/v1/visits`
- `POST /api/v1/visits`
- `PATCH /api/v1/visits/{id}`
- `DELETE /api/v1/visits/{id}`

### Trips

- `GET /api/v1/trips`
- `POST /api/v1/trips`
- `GET /api/v1/trips/{id}`
- `PATCH /api/v1/trips/{id}`
- `DELETE /api/v1/trips/{id}`
- `POST /api/v1/trips/{id}/stops`
- `PATCH /api/v1/trips/{id}/stops/{stop_id}`
- `DELETE /api/v1/trips/{id}/stops/{stop_id}`

### Statistics and portability

- `GET /api/v1/statistics/summary`
- `GET /api/v1/statistics/timeline`
- `POST /api/v1/backups/export` — return a versioned JSON download
- `POST /api/v1/backups/import/preview` — validate and summarize without writing
- `POST /api/v1/backups/import` — apply a previously validated payload in one transaction

Generate the OpenAPI schema during CI and optionally generate TypeScript API types from it. Avoid maintaining duplicate hand-written request and response interfaces.

## 8. Pages and primary workflows

### Application shell

- Sidebar on desktop and bottom navigation on small screens.
- Routes for Dashboard, Map, Countries, Trips, Statistics, and Settings.
- Global search dialog accessible from navigation and a keyboard shortcut.
- Theme selection: system, light, or dark.

### Dashboard `/`

- Summary cards: countries visited, percentage of recognized countries, continents visited, trips, and travel days when dates exist.
- Small interactive map with visited-country coloring.
- Recent visits and upcoming planned trips.
- Empty state with a clear “Mark your first country” action.

### Map `/map`

- Full-page MapLibre map using a locally bundled style and country boundary source.
- Fill colors for unvisited, visited, lived, planned, and selected countries.
- Hover tooltip and keyboard-accessible selected-country details.
- Clicking a country opens a side panel without immediately modifying data.
- Side panel permits status changes, notes, visit creation, and navigation to detail.
- Filters for status and, later, place type and date range.

### Countries `/countries`

- Searchable and sortable list/grid.
- Filter by continent and status.
- Show flag, name, ISO code, status, visit count, and last visit.
- Virtualize only after measuring a real performance need.

### Country detail `/countries/:code`

- Country summary, map focus, status editor, notes, and dated visits.
- Related trips.
- Region list is introduced in the regional tracking phase.

### Trips `/trips` and `/trips/:id`

- List planned, completed, and cancelled trips.
- Create/edit/delete a trip.
- Add ordered stops by search.
- Validate dates and show destructive-action confirmation.

### Statistics `/statistics`

- Counts and percentages with clearly documented denominators.
- Breakdown by continent and status.
- Visits and trips by year.
- Do not imply exact travel days when date ranges are incomplete.

### Settings `/settings`

- Theme and display preferences.
- Geographic dataset version and attribution.
- Export backup, preview import, and restore.
- Explicitly show the local database path and privacy model.

## 9. Implementation phases

### Phase 0 — foundations

Deliverables:

- Create the monorepo structure and root task commands.
- Configure TypeScript strict mode, ESLint, Prettier, Ruff, mypy, and pytest.
- Add FastAPI configuration, SQLite engine, Alembic baseline, and health endpoint.
- Add the React shell, routing, query provider, theme provider, and error boundary.
- Add `.env.example`, `.gitignore`, and a README with setup commands.
- Add CI commands that run without external services.

Acceptance criteria:

- One documented command starts both development servers.
- The frontend can call `/health` through the Vite proxy.
- A clean checkout can install, migrate, test, and build.
- No secrets or runtime database files are committed.

### Phase 1 — country reference data and map

Deliverables:

- Add licensed country metadata and simplified boundaries.
- Implement the geographic-data manifest and validation script.
- Build the `/countries` endpoints.
- Render a responsive MapLibre map with hover, selection, and country detail panel.
- Add URL-addressable selection such as `/map?country=JP`.

Acceptance criteria:

- Every rendered country feature maps to a valid country record.
- The map remains interactive on a representative laptop.
- Missing or disputed country codes fail gracefully rather than crashing.
- Dataset attribution is visible in Settings/About.

### Phase 2 — country tracking

Deliverables:

- Add `place_status` and `visit` migrations, models, services, and endpoints.
- Implement optimistic status updates with rollback and error feedback.
- Add country list, filters, detail page, notes, and visit forms.
- Synchronize map state after changes without a page reload.

Acceptance criteria:

- Status survives application restart.
- Repeated requests cannot create duplicate status records.
- Date validation is enforced on both client and server.
- A user can mark, edit, and clear a country status from map and detail views.

### Phase 3 — dashboard and statistics

Deliverables:

- Implement a statistics service and summary endpoint.
- Add dashboard cards, mini-map, recent activity, and empty states.
- Add continent and yearly breakdowns.
- Define the recognized-country denominator in code and UI copy.

Acceptance criteria:

- Summary values agree with seeded fixtures and database queries.
- Undated visits are included in visited counts but excluded from date-derived charts.
- Changing a country or visit invalidates and refreshes affected statistics.

### Phase 4 — trips

Deliverables:

- Add trip and trip-stop migrations and CRUD endpoints.
- Build trip list, form, detail, ordered stops, and related-country views.
- Link optional visits to trips.
- Add confirmation for deletes and meaningful empty/error states.

Acceptance criteria:

- Trip and stop date rules are enforced transactionally.
- Reordering stops is stable after restart.
- Deleting a trip preserves visits by setting `trip_id` to null unless the user explicitly chooses otherwise.

### Phase 5 — search and data portability

Deliverables:

- Build a normalized search index for countries and aliases; extend it later for other place types.
- Add global search and keyboard navigation.
- Define a versioned backup schema.
- Add export, import preview, conflict strategy, transactionally safe restore, and automatic pre-import backup.

Acceptance criteria:

- Search is case- and diacritic-insensitive.
- Invalid imports write nothing and return actionable errors.
- Export followed by import into an empty database reproduces all user-owned records.
- Unknown future backup fields are handled according to the documented compatibility policy.

### Phase 6 — polish and release

Deliverables:

- Responsive and accessibility review.
- Loading, empty, offline, not-found, and server-error states.
- Playwright coverage for primary workflows.
- Production build served by FastAPI.
- Cross-platform launch scripts and complete README.

Acceptance criteria:

- Core workflows are usable at 360 px and common laptop widths.
- Interactive controls are keyboard accessible and visibly focused.
- The application starts locally with one documented command.
- Tests, type checks, linting, migrations, and production build pass.

### Phase 7 — regional, city, and airport tracking

Deliverables:

- Import regions, cities, and airports with stable identifiers and provenance.
- Reuse the generic status/visit model and search API.
- Add region layers that load only at appropriate zoom levels.
- Add clustered point layers for cities and airports.

Acceptance criteria:

- Dense point datasets do not freeze initial page load.
- Country statistics remain separate from city and airport counts.
- Orphaned or changed reference identifiers are detected during dataset upgrades.

### Phase 8 — 3D globe and media

Deliverables:

- Add a lazy-loaded globe route using globe.gl or a MapLibre globe projection after a short technical spike.
- Reuse country colors, selection, and filters from the 2D map.
- Add Markdown notes with sanitized rendering.
- Add local photo storage, thumbnails, metadata, backup rules, and missing-file handling.

Acceptance criteria:

- The main application bundle does not eagerly load the 3D engine.
- The globe has a reduced-motion or 2D fallback.
- Markdown cannot execute arbitrary HTML or scripts.
- Photo files use safe generated names and remain inside the configured data directory.

## 10. Testing strategy

### Backend

- Unit tests for date validation, status aggregation, statistics, backup versioning, and reference-code validation.
- API tests against a temporary SQLite database.
- Migration test from an empty database to the current revision.
- Transaction tests for imports and multi-record trip changes.

### Frontend

- Component tests for forms, filters, accessible dialogs, and error states.
- Query-hook tests using mocked network responses.
- Keep map rendering tests focused on adapter behavior; use browser tests for real integration.

### End to end

At minimum, automate these flows:

1. Mark a country visited from the map and verify dashboard statistics.
2. Add a dated visit and edit it from country detail.
3. Create a trip with multiple stops and reorder them.
4. Export, clear a disposable test database, import, and verify restored state.
5. Navigate and complete core forms using only a keyboard.

## 11. Security, privacy, and reliability

- Bind to `127.0.0.1` by default, not all network interfaces.
- Use strict CORS in development and same-origin requests in the production-local build.
- Validate every API payload and every reference-data identifier on the server.
- Sanitize rendered Markdown.
- Restrict uploaded file types, sizes, names, and destinations when photos are added.
- Never accept an import path from the browser; accept uploaded content and validate it.
- Use transactions for imports and compound writes.
- Create a timestamped backup before schema upgrades or imports that mutate data.
- Document that local-first protects data from a hosted service, but not from other users or malware with access to the laptop account.

## 12. Performance requirements

- Initial application JavaScript, excluding lazy map/globe chunks, should target under 250 KB compressed.
- Lazy-load map-heavy and globe-heavy routes.
- Use simplified country geometry for normal zoom levels.
- Keep map feature state updates incremental rather than rebuilding the source after every edit.
- Index SQLite columns used for status, dates, trip relationships, and place lookup.
- Define API pagination before adding large city, airport, visit, or photo collections.
- Measure before adding caching, list virtualization, or vector-tile infrastructure.

## 13. Definition of done for every feature

A feature is complete only when:

- its happy path, validation, empty state, loading state, and failure state are implemented;
- API and UI types are consistent;
- migrations are included for schema changes;
- automated tests cover important business rules;
- keyboard and screen-reader behavior has been considered;
- user-facing copy and documentation are updated;
- lint, type checks, tests, and production builds pass;
- no proprietary assets or untracked dataset licenses were introduced.

## 14. Recommended first coding task

Implement Phase 0 as one vertical foundation slice:

1. scaffold `apps/web` and `apps/api`;
2. add root `make dev`, `make test`, `make lint`, and `make build` commands or equivalent cross-platform scripts;
3. configure the Vite development proxy;
4. implement `GET /health`;
5. render API health status on a temporary frontend home page;
6. add one backend API test and one frontend component test;
7. document setup and verify all commands from a clean environment.

Do not begin detailed visual design or add more dependencies until this slice works. The next task should be the country data pipeline and read-only map, followed by persistence.
