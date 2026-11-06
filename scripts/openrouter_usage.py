"""Print OpenRouter's own spend counter for our key (read-only GET /api/v1/key), to cross-check
`p2o.cli budget` (which is computed from token counts). Appends to logs/openrouter_usage.jsonl.
Usage: python scripts/openrouter_usage.py [label]
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
req = urllib.request.Request("https://openrouter.ai/api/v1/key",
                             headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
d = json.load(urllib.request.urlopen(req, timeout=30))["data"]
row = {"ts": datetime.now(timezone.utc).isoformat(), "label": sys.argv[1] if len(sys.argv) > 1 else "",
       "usage_usd": d.get("usage"), "limit": d.get("limit"), "limit_remaining": d.get("limit_remaining")}
Path("logs").mkdir(exist_ok=True)
with open("logs/openrouter_usage.jsonl", "a") as f:
    f.write(json.dumps(row) + "\n")
print(row)
