# TravelMap

TravelMap is an original, local-first travel tracker. It includes a country catalog, interactive SVG world map, country/region/city/airport reference layers, place statuses, visits, trips, statistics, search, a globe view, and JSON backup/restore. Photos and profile switching are intentionally out of scope.

## Requirements

- Python 3.12+
- Node.js 20+
- npm

## Setup

```bash
make install
cp .env.example .env
```

On macOS with Homebrew-installed Node 20, make the versioned npm binary available in new shells with:

```bash
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
```

The project Python environment is at `.venv`; activate it when running API tools directly:

```bash
source .venv/bin/activate
```

Start the services in two terminals. Leave the API terminal running, then open a second terminal for the frontend:

```bash
make api
```

In the second terminal:

```bash
make web
```

Open <http://localhost:5173>. The frontend proxies `/api` requests to the local FastAPI service at <http://127.0.0.1:8000>.

Run checks with:

```bash
make test
make lint
make build
```

Runtime data belongs in `data/`, which is intentionally ignored by git. The API binds to `127.0.0.1` by default.
