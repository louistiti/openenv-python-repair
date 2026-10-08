"""Create Arrow-friendly dataset rows without changing canonical task data."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
rows = [json.loads(line) for line in (ROOT / "tasks.jsonl").read_text().splitlines() if line]
manifest = ROOT / "curriculum.json"
selected = set(json.loads(manifest.read_text())["arena_task_ids"]) if manifest.exists() else set()
viewer = []
for task in rows:
    keys = ("task_id", "family", "bug_pattern", "case_seed", "prompt", "starter", "split")
    row = {key: task[key] for key in keys if key in task}
    if "family" in task:
        row["arena_selected"] = task["task_id"] in selected
    row["num_cases"] = len(task["cases"])
    row["cases_json"] = json.dumps(task["cases"], ensure_ascii=False, separators=(",", ":"))
    assert json.loads(row["cases_json"]) == task["cases"]
    viewer.append(row)
assert len({row["task_id"] for row in viewer}) == len(rows)
(ROOT / "viewer_train.jsonl").write_text(
    "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in viewer)
)
print(f"Prepared {len(viewer)} rows, {sum(row['num_cases'] for row in viewer)} cases")
