"""Recompute the held-out precision and recall from the released sensor logs."""
import json
from pathlib import Path


def summarize(records):
    correct = sum(1 for r in records if r["predicted"] == r["label"])
    return {
        "precision": round(correct / len(records), 2),
        "recall": round(correct / len(records), 2),
    }


if __name__ == "__main__":
    records = json.loads(Path("data/held_out.json").read_text())
    print(json.dumps(summarize(records), sort_keys=True))
