# DataFlow Studio

A lightweight visual data validation and transformation studio built with React, Material UI, FastAPI, Pandas, and SQLite.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python -m uvicorn backend.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. API documentation is at http://localhost:8000/docs.

## Architecture

- `frontend/src` — dashboard, designer, node properties, and data preview
- `backend/main.py` — REST API for pipelines, files, and executions
- `backend/pipeline/engine.py` — extensible Pandas node execution registry
- `backend/models.py` — SQLite persistence for versioned pipelines and execution history
- `uploads` and `database` — local development storage

Implemented nodes include inputs, filtering, column selection/removal/rename, sort, deduplication, null filling, case conversion, calculated columns, top N, aggregation, and null/unique/regex/range/allowed-value validation.
"# DataValidationTool" 
