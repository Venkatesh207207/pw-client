from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import tempfile
import logging
from typing import Optional, Any, Dict

from core.utils import DATA_DIR

logger = logging.getLogger("core.cache")

DATA_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def save_cache(name: str, data: Dict[str, Any], ttl_minutes: int = 30) -> None:
    path = DATA_DIR / f"{name}.json"
    payload = {
        "timestamp": _now_iso(),
        "data": data,
        "_metadata": {"ttl_minutes": int(ttl_minutes)},
    }

    try:
        dirpath = path.parent
        with tempfile.NamedTemporaryFile(
            "w", delete=False, dir=str(dirpath), suffix=".tmp"
        ) as tf:
            tf.write(json.dumps(payload, indent=2))
            temp_name = tf.name
        Path(temp_name).replace(path)
    except Exception as exc:
        logger.exception("Failed to save cache %s: %s", name, exc)


def load_cache(name: str, ttl_minutes: Optional[int] = None) -> Optional[Any]:
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        return None

    try:
        raw = path.read_text()
        payload = json.loads(raw)
        ts_str = payload.get("timestamp")
        if not ts_str:
            logger.debug("Cache %s missing timestamp; treating as invalid.", name)
            path.unlink(missing_ok=True)
            return None

        ts = _parse_iso(ts_str)
        file_ttl = payload.get("_metadata", {}).get("ttl_minutes", 30)
        effective_ttl = int(ttl_minutes) if ttl_minutes is not None else int(file_ttl)

        if datetime.now(timezone.utc) - ts > timedelta(minutes=effective_ttl):
            logger.debug(
                "Cache %s expired (ts=%s, ttl=%s). Removing file.",
                name,
                ts_str,
                effective_ttl,
            )
            try:
                path.unlink(missing_ok=True)
            except Exception:
                logger.exception("Failed to remove expired cache file %s", path)
            return None

        return payload.get("data")
    except Exception as exc:
        logger.exception("Failed to load cache %s: %s", name, exc)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            logger.exception("Failed to remove corrupted cache file %s", path)
        return None


def clear_cache(name: str) -> None:
    path = DATA_DIR / f"{name}.json"
    try:
        path.unlink(missing_ok=True)
    except TypeError:
        try:
            if path.exists():
                path.unlink()
        except Exception:
            logger.exception("Failed to clear cache %s", name)
    except Exception:
        logger.exception("Failed to clear cache %s", name)
