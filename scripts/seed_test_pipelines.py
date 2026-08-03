"""Seed several runnable demo pipelines for dashboard and execution testing."""

from pathlib import Path
import shutil
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.database import Base, UPLOAD_DIR, engine, SessionLocal
from backend.models import Pipeline


SOURCE = ROOT / "sample_data_10000.xlsx"
STORED_NAME = "demo_employees_10000.xlsx"


def node(kind: str, name: str, config: dict | None = None) -> dict:
    return {"id": str(uuid4()), "type": kind, "name": name, "config": config or {}}


def input_node() -> dict:
    return node(
        "input",
        "10k Employee Records",
        {
            "originalName": SOURCE.name,
            "storedName": STORED_NAME,
            "size": SOURCE.stat().st_size,
            "sheet": "Employees",
        },
    )


PIPELINES = [
    {
        "name": "Employee Data Quality",
        "description": "Checks mandatory departments, valid email format, realistic ages, and positive salaries.",
        "tags": ["demo", "validation", "employees"],
        "nodes": lambda: [
            input_node(),
            node("validation", "Department is mandatory", {"column": "department", "rule": "null", "message": "Department is missing"}),
            node("validation", "Valid email address", {"column": "email", "rule": "regex", "pattern": r"^[^@\s]+@[^@\s]+\.[^@\s]+$", "message": "Invalid email"}),
            node("validation", "Age between 18 and 75", {"column": "age", "rule": "range", "min": 18, "max": 75}),
            node("validation", "Salary must be positive", {"column": "salary", "rule": "range", "min": 1, "max": 10_000_000}),
        ],
    },
    {
        "name": "Active Engineering Team",
        "description": "Filters active engineering employees, sorts by performance, and returns the top 100.",
        "tags": ["demo", "filter", "engineering"],
        "nodes": lambda: [
            input_node(),
            node("filter", "Engineering only", {"column": "department", "operator": "equals", "value": "Engineering"}),
            node("filter", "Active employees", {"column": "status", "operator": "equals", "value": "Active"}),
            node("sort", "Best performance first", {"columns": ["performance_score"], "ascending": False}),
            node("top_n", "Top 100 performers", {"count": 100}),
        ],
    },
    {
        "name": "Employee Cleanup",
        "description": "Removes duplicate IDs, fills missing departments, normalizes names, and trims the output schema.",
        "tags": ["demo", "cleanup", "transformation"],
        "nodes": lambda: [
            input_node(),
            node("remove_duplicates", "Deduplicate employee IDs", {"columns": ["employee_id"]}),
            node("fill_null", "Fill missing departments", {"column": "department", "value": "Unassigned"}),
            node("case", "Normalize employee names", {"column": "full_name", "mode": "title"}),
            node("keep_columns", "Select reporting columns", {"columns": ["employee_id", "full_name", "email", "department", "city", "status"]}),
        ],
    },
    {
        "name": "High Salary Review",
        "description": "Finds high earners and flags invalid salary values for finance review.",
        "tags": ["demo", "finance", "review"],
        "nodes": lambda: [
            input_node(),
            node("filter", "Salary above 1.5M", {"column": "salary", "operator": "greater", "value": 1_500_000}),
            node("sort", "Highest salary first", {"columns": ["salary"], "ascending": False}),
            node("validation", "Known employment status", {"column": "status", "rule": "allowed", "values": ["Active", "Inactive", "Pending"]}),
        ],
    },
    {
        "name": "Regional Operations Sample",
        "description": "Produces a small randomized-style operational sample for Mumbai records.",
        "tags": ["demo", "operations", "sample"],
        "nodes": lambda: [
            input_node(),
            node("filter", "Mumbai employees", {"column": "city", "operator": "equals", "value": "Mumbai"}),
            node("remove_columns", "Remove private notes", {"columns": ["notes"]}),
            node("sort", "Newest joiners first", {"columns": ["joining_date"], "ascending": False}),
            node("top_n", "Latest 250 employees", {"count": 250}),
        ],
    },
]


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing {SOURCE}; run scripts/generate_dummy_data.py first")
    UPLOAD_DIR.mkdir(exist_ok=True)
    shutil.copy2(SOURCE, UPLOAD_DIR / STORED_NAME)
    Base.metadata.create_all(engine)

    created = 0
    with SessionLocal() as db:
        existing = {pipeline.name for pipeline in db.query(Pipeline).all()}
        for definition in PIPELINES:
            if definition["name"] in existing:
                continue
            db.add(
                Pipeline(
                    name=definition["name"],
                    description=definition["description"],
                    created_by="Demo Seeder",
                    tags=definition["tags"],
                    favorite=definition["name"] == "Employee Data Quality",
                    nodes=definition["nodes"](),
                    connections=[],
                )
            )
            created += 1
        db.commit()

    print(f"Created {created} demo pipelines ({len(PIPELINES) - created} already existed)")


if __name__ == "__main__":
    main()
