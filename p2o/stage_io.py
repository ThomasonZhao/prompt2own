"""Parse and validate what a worker wrote in its workspace."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from .types import Claim, RCAResult, Stage

REQUIRED = {
    Stage.RCA: ["rca.json", "claim.json"],
    Stage.POC: ["poc.bin", "claim.json"],
    Stage.PATCH: ["fix.patch", "claim.json"],
    Stage.SINGLE: ["claim.json"],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_outputs(stage: Stage, artifact_dir: Path) -> tuple[Claim | None, RCAResult | None, str | None]:
    """Returns (claim, rca, schema_error)."""
    missing = [f for f in REQUIRED[stage] if not (artifact_dir / f).exists()]
    if missing:
        return None, None, f"schema_error: missing {', '.join(missing)}"
    try:
        claim = Claim(**json.loads((artifact_dir / "claim.json").read_text()))
        rca = None
        if stage == Stage.RCA:
            rca = RCAResult(**json.loads((artifact_dir / "rca.json").read_text()))
        if stage == Stage.PATCH and not (artifact_dir / "fix.patch").read_text().strip():
            return claim, None, "schema_error: fix.patch is empty"
        return claim, rca, None
    except (ValidationError, json.JSONDecodeError, TypeError) as e:
        return None, None, f"schema_error: {str(e)[:200]}"
