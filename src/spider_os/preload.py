from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

SEED_VERSION = 1


def load_seed() -> list[dict[str, Any]]:
    seed_path = files('spider_os').joinpath('data/preload_knowledge.json')
    return json.loads(seed_path.read_text(encoding='utf-8'))
