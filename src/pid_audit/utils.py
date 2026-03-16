"""utils.py"""

import json
from pathlib import Path


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def save_json(path, data):
    ensure_dir(Path(path).parent)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def save_text(path, text):
    ensure_dir(Path(path).parent)
    with open(path, "w") as f:
        f.write(text)
