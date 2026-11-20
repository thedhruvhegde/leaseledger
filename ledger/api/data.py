"""Lazy, validating loader for the JSON data files written by other agents.

Every file is optional: absence yields an empty collection and a warning in /api/manifest. Invalid entries are
logged and skipped (never silently "fixed"). Root can be overridden with LEDGER_DATA_DIR (tests).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Type

from pydantic import BaseModel, ValidationError

from ledger.schemas import Building, Listing, Profile, ScheduleTemplate

log = logging.getLogger("ledger.api")

REPO = Path(__file__).resolve().parents[2]

FILES = {
    "buildings": "campus/buildings.json",
    "listings": "listings/listings.json",
    "synthetic_listings": "listings/synthetic_listings.json",
    "scraped_listings": "listings/scraped.json",      # optional: python -m ledger.scrape (page_fetched)
    "demo_set": "listings/demo_set.json",
    "templates": "templates/schedules.json",
    "demo_profiles": "templates/demo_profiles.json",
    "artifacts_manifest": "artifacts/manifest.json",
    "behavior_params": "behavior/params.json",
    "cost_params": "costs/cost_params.json",
}


def data_dir() -> Path:
    return Path(os.environ.get("LEDGER_DATA_DIR", REPO / "data"))


class FileInfo(BaseModel):
    key: str
    path: str
    exists: bool
    sha256_12: Optional[str] = None
    modified: Optional[str] = None
    count: Optional[int] = None
    invalid: int = 0
    errors: list[str] = []
    version: Optional[str] = None


def _unwrap(raw: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(raw, dict):
        for k in keys:
            if k in raw:
                return raw[k]
    return raw


class DataStore:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else data_dir()
        self._lock = threading.Lock()
        self._cache: dict[str, Any] = {}
        self.info: dict[str, FileInfo] = {}

    def reload(self) -> None:
        with self._lock:
            self._cache.clear()
            self.info.clear()

    # ---------------------------------------------------------------- raw
    def _raw(self, key: str) -> Any:
        if key in self._cache:
            return self._cache[key]
        rel = FILES[key]
        p = self.root / rel
        fi = FileInfo(key=key, path=f"data/{rel}", exists=p.exists())
        raw = None
        if p.exists():
            try:
                b = p.read_bytes()
                fi.sha256_12 = hashlib.sha256(b).hexdigest()[:12]
                fi.modified = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
                raw = json.loads(b)
                if isinstance(raw, dict):
                    fi.version = str(raw.get("version") or raw.get("generated") or raw.get("built_at") or "") or None
            except Exception as e:
                fi.errors.append(f"unreadable: {e}"[:200])
                log.warning("data file %s unreadable: %s", rel, e)
                raw = None
        self.info[key] = fi
        self._cache[key] = raw
        return raw

    def _models(self, key: str, model: Type[BaseModel], unwrap: tuple[str, ...]) -> list:
        ck = f"_m_{key}"
        if ck in self._cache:
            return self._cache[ck]
        raw = _unwrap(self._raw(key), unwrap)
        out = []
        fi = self.info[key]
        if isinstance(raw, list):
            for i, item in enumerate(raw):
                try:
                    out.append(model.model_validate(item))
                except ValidationError as e:
                    fi.invalid += 1
                    ident = item.get("id", i) if isinstance(item, dict) else i
                    msg = f"{ident}: {e.errors()[0].get('msg', 'invalid')}"
                    fi.errors.append(msg[:200])
                    log.warning("skip invalid %s entry %s", key, msg)
        elif raw is not None:
            fi.errors.append("expected a JSON list")
        fi.count = len(out)
        self._cache[ck] = out
        return out

    # ---------------------------------------------------------------- typed accessors
    def buildings(self) -> list[Building]:
        return self._models("buildings", Building, ("buildings",))

    def observed_listings(self) -> list[Listing]:
        """listings.json, then any scraped.json entries (additive; an id already in listings.json wins)."""
        base = self._models("listings", Listing, ("listings",))
        scraped = self._models("scraped_listings", Listing, ("listings",))
        if not scraped:
            return base
        have = {l.id for l in base}
        return base + [l for l in scraped if l.id not in have and l.provenance == "observed"]

    def synthetic_listings(self) -> list[Listing]:
        return self._models("synthetic_listings", Listing, ("listings",))

    def templates(self) -> list[ScheduleTemplate]:
        return self._models("templates", ScheduleTemplate, ("templates",))

    def demo_set(self) -> list[str]:
        raw = _unwrap(self._raw("demo_set"), ("ids", "listing_ids", "demo_set"))
        ids = [str(x) for x in raw] if isinstance(raw, list) else []
        self.info["demo_set"].count = len(ids)
        return ids

    def demo_profiles(self) -> list[dict]:
        """Raw demo profile entries; each 'profile' is validated and the result reported per entry."""
        ck = "_m_demo_profiles"
        if ck in self._cache:
            return self._cache[ck]
        raw = _unwrap(self._raw("demo_profiles"), ("profiles", "demo_profiles"))
        out = []
        fi = self.info["demo_profiles"]
        if isinstance(raw, dict):
            raw = [{"id": k, **v} if isinstance(v, dict) else {"id": k, "value": v} for k, v in raw.items()]
        if isinstance(raw, list):
            for i, item in enumerate(raw):
                if not isinstance(item, dict):
                    fi.invalid += 1
                    continue
                entry = dict(item)
                prof = entry.get("profile")
                if prof is not None:
                    try:
                        entry["profile"] = Profile.model_validate(prof).model_dump(mode="json")
                        entry["valid"] = True
                    except ValidationError as e:
                        fi.invalid += 1
                        entry["valid"] = False
                        entry["validation_error"] = str(e.errors()[0].get("msg"))[:200]
                        fi.errors.append(f"{entry.get('id', i)}: {entry['validation_error']}")
                out.append(entry)
        fi.count = len(out)
        self._cache[ck] = out
        return out

    def json_file(self, key: str) -> Any:
        return self._raw(key)

    def file_infos(self) -> list[FileInfo]:
        # touch everything so infos are populated
        self.buildings(); self.observed_listings(); self.synthetic_listings(); self.templates()
        self.demo_set(); self.demo_profiles()
        for k in ("artifacts_manifest", "behavior_params", "cost_params"):
            self._raw(k)
        return [self.info[k] for k in FILES]
