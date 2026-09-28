"""Append-only jsonl store. One line per record, resumable: on start the
existing file is read back so keys are not fetched twice."""
import json
from pathlib import Path


class Store:
    def __init__(self, path: Path, key: str = "key"):
        self.path = path
        self.key = key
        self.rows: dict[str, dict] = {}
        if path.exists():
            with path.open() as f:
                for line in f:
                    if line.strip():
                        r = json.loads(line)
                        self.rows[r[key]] = r
        path.parent.mkdir(parents=True, exist_ok=True)
        self._f = path.open("a")

    def __contains__(self, k: str) -> bool:
        return k in self.rows

    def add(self, r: dict):
        self.rows[r[self.key]] = r
        self._f.write(json.dumps(r, ensure_ascii=False) + "\n")
        self._f.flush()

    def __len__(self):
        return len(self.rows)
