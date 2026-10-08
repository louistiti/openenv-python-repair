"""Create Arrow-friendly dataset rows without changing canonical task data."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
rows = [json.loads(line) for line in (ROOT / "tasks.jsonl").read_text().splitlines() if line]
viewer = []
for task in rows:
    row = {key: task[key] for key in ("task_id", "prompt", "starter", "split")}
    row["num_cases"] = len(task["cases"])
    row["cases_json"] = json.dumps(task["cases"], ensure_ascii=False, separators=(",", ":"))
    assert json.loads(row["cases_json"]) == task["cases"]
    viewer.append(row)
assert len({row["task_id"] for row in viewer}) == len(rows)
(ROOT / "viewer_train.jsonl").write_text(
    "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in viewer)
)
print(f"Prepared {len(viewer)} rows, {sum(row['num_cases'] for row in viewer)} cases")
