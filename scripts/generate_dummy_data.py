"""Generate a deterministic Excel dataset for DataFlow Studio testing."""

from pathlib import Path
import random

import pandas as pd


random.seed(42)
OUTPUT = Path(__file__).resolve().parent.parent / "sample_data_10000.xlsx"

first_names = ["Aarav", "Aisha", "Arjun", "Diya", "Ishaan", "Kavya", "Mira", "Neha", "Rohan", "Vikram"]
last_names = ["Sharma", "Patel", "Singh", "Kumar", "Reddy", "Gupta", "Mehta", "Nair"]
cities = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Hyderabad", "Pune", "Kolkata", "Jaipur"]
departments = ["Sales", "Engineering", "Finance", "Operations", "HR", "Marketing"]
statuses = ["Active", "Inactive", "Pending"]

rows = []
for index in range(10_000):
    first = random.choice(first_names)
    last = random.choice(last_names)
    employee_id = f"EMP{index + 1:05d}"
    rows.append(
        {
            "employee_id": employee_id,
            "full_name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}{index + 1}@example.com",
            "age": random.randint(18, 65),
            "department": random.choice(departments),
            "city": random.choice(cities),
            "salary": random.randrange(300_000, 2_500_001, 5_000),
            "joining_date": pd.Timestamp("2018-01-01") + pd.Timedelta(days=random.randint(0, 3000)),
            "status": random.choice(statuses),
            "performance_score": round(random.uniform(1, 5), 2),
            "projects_completed": random.randint(0, 35),
            "is_manager": random.random() < 0.12,
            "notes": random.choice(["", "  high potential  ", "On leave", "Needs review", None]),
        }
    )

# Deliberately dirty records for validation and cleanup testing.
for index in range(0, 10_000, 97):
    rows[index]["email"] = "invalid-email"
for index in range(0, 10_000, 113):
    rows[index]["department"] = None
for index in range(0, 10_000, 131):
    rows[index]["age"] = 150
for index in range(0, 10_000, 149):
    rows[index]["salary"] = -1000
for index in range(0, 10_000, 173):
    rows[index]["full_name"] = rows[index]["full_name"].upper()
for index in range(200, 10_000, 211):
    rows[index]["employee_id"] = rows[index - 1]["employee_id"]

data = pd.DataFrame(rows)
readme = pd.DataFrame(
    [
        ["Rows", "10,000"],
        ["Purpose", "Transformation, validation, filtering, sorting, aggregation, and deduplication tests"],
        ["Known issues", "Invalid emails, null departments, ages over 100, negative salaries, duplicate employee IDs"],
        ["Deterministic", "Yes — random seed 42"],
    ],
    columns=["Item", "Details"],
)

with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
    data.to_excel(writer, sheet_name="Employees", index=False)
    readme.to_excel(writer, sheet_name="README", index=False)
    sheet = writer.book["Employees"]
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

print(f"Created {OUTPUT} with {len(data):,} records")
