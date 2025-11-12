import os
import json
import time
import logging
import requests
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional, Callable
from dotenv import load_dotenv, set_key, find_dotenv


API_BASE = "https://api.penpencil.co"
ORG_ID = "5eb393ee95fab7468a79d189"
DATA_DIR = Path("cache")
DATA_DIR.mkdir(parents=True, exist_ok=True)

ENV_PATH = Path(find_dotenv()) or Path(__file__).resolve().parents[1] / ".env"
if not ENV_PATH.exists():
    ENV_PATH.touch()

load_dotenv(ENV_PATH)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class EnvManager:

    path = ENV_PATH

    @staticmethod
    def get(key: str, default: str = None) -> str:
        load_dotenv(EnvManager.path)
        return os.getenv(key, default)

    @staticmethod
    def set(key: str, value: str):
        if not EnvManager.path.exists():
            EnvManager.path.touch()
        set_key(str(EnvManager.path), key, value)


def make_api_url(*parts) -> str:
    return "/".join([API_BASE.strip("/")] + [str(p).strip("/") for p in parts if p])


def get_default_headers(
    auth_token: Optional[str] = None,
    include_origin: bool = True,
    content_type: str = "application/json",
    extra_headers: dict = None,
) -> dict:
    headers = {
        "content-type": content_type,
        "user-agent": "Mozilla/5.0 (compatible; PenPencilFetcher/2.0)",
    }

    if include_origin:
        headers.update(
            {
                "origin": "https://www.pw.live",
                "referer": "https://www.pw.live/",
            }
        )

    if auth_token:
        headers["authorization"] = auth_token

    if extra_headers:
        headers.update(extra_headers)

    return headers


def safe_request(
    method: str, url: str, headers=None, params=None, data=None, timeout=10, retries=2
):
    for attempt in range(1, retries + 1):
        try:
            response = requests.request(
                method, url, headers=headers, params=params, data=data, timeout=timeout
            )

            try:
                parsed = response.json()
                if isinstance(parsed, list):
                    return True, None, parsed
            except json.JSONDecodeError:
                pass

            return handle_response(response)

        except (requests.Timeout, requests.ConnectionError) as e:
            logger.warning(f"[Attempt {attempt}] Network error: {e}")
            time.sleep(1.5 * attempt)
        except Exception as e:
            logger.exception("Unexpected request error")
            return False, f"Unexpected error: {e}", None

    return False, "Request failed after retries", None


def handle_response(response):
    try:
        result = response.json()
    except json.JSONDecodeError:
        return False, f"Invalid JSON (HTTP {response.status_code})", None

    if not isinstance(result, dict):
        return False, f"Unexpected response format: {type(result)}", result

    if not result.get("success", False):
        error = result.get("error", {})
        msg = error.get("message", response.reason)
        status = error.get("status", response.status_code)
        return False, f"Error {status}: {msg}", result

    return True, None, result


class CacheManager:

    @staticmethod
    def path(name: str) -> Path:
        return DATA_DIR / f"{name}.json"

    @staticmethod
    def load(name: str) -> Optional[Any]:
        path = CacheManager.path(name)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text())
            return raw.get("data")
        except Exception:
            logger.debug(f"Failed to load cache: {name}", exc_info=True)
            return None

    @staticmethod
    def save(name: str, data: Any, ttl_minutes: int = 30):
        path = CacheManager.path(name)
        try:
            payload = {
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ttl_minutes": ttl_minutes,
            }
            path.write_text(json.dumps(payload, indent=2))
        except Exception:
            logger.exception(f"Failed to save cache: {name}")

    @staticmethod
    def compute_age(name: str):
        path = CacheManager.path(name)
        if not path.exists():
            return None, None
        try:
            raw = json.loads(path.read_text())
            ts_str = raw.get("timestamp") or raw.get("_metadata", {}).get("timestamp")
            if not ts_str:
                return None, None
            ts = datetime.fromisoformat(ts_str)
            delta = datetime.now(timezone.utc) - ts
            mins = int(delta.total_seconds() / 60)
            hours = mins // 60
            human = f"{hours}h {mins % 60}m ago" if hours else f"{mins} minutes ago"
            return mins, human
        except Exception:
            logger.debug(f"Failed to compute cache age for {name}", exc_info=True)
            return None, None


def standard_response(status: str, data: dict = None, errors: list = None) -> dict:
    return {"status": status, "data": data or {}, "errors": errors or []}


def standardize_response(success, error_msg=None, data=None):
    return {
        "success": bool(success),
        "error": error_msg if not success else None,
        "data": data if success else None,
    }


def _generic_fetch(
    key_prefix: str,
    identifiers: dict,
    fetch_fn: Callable[..., dict],
    refetch: bool = False,
    ttl_minutes: int = 30,
    data_key: str = "data",
    result_key: str = "data",
):
    name = "_".join([key_prefix] + [f"{k}_{v}" for k, v in identifiers.items()])
    cache_name = name

    logger.info(f"Fetching {key_prefix}", extra={**identifiers, "refetch": refetch})

    if not all(identifiers.values()):
        missing = [k for k, v in identifiers.items() if not v]
        return standard_response("error", errors=[f"Missing: {', '.join(missing)}."])

    token = EnvManager.get("TOKEN")
    if not token:
        return standard_response("error", errors=["TOKEN not found in environment."])

    if not refetch:
        cached = CacheManager.load(cache_name)
        if cached:
            mins, human = CacheManager.compute_age(cache_name)
            logger.info(
                f"{key_prefix} loaded from cache ({human or 'unknown age'})",
                extra={**identifiers, "cache_age_minutes": mins},
            )
            return standard_response(
                "success",
                data={
                    result_key: cached,
                    "from_cache": True,
                    "cache_age_minutes": mins,
                    "cache_age_human": human,
                },
            )

    try:
        api_resp = fetch_fn(token=token, **identifiers)
    except Exception as e:
        logger.exception(f"{key_prefix} API call failed")
        return standard_response("error", errors=[f"API call failed: {e}"])

    if not api_resp.get("success"):
        logger.error(f"{key_prefix} fetch unsuccessful", extra=api_resp)
        return standard_response("error", errors=[f"Failed to fetch {key_prefix}."])

    data = api_resp.get(data_key)
    if not data:
        logger.warning(f"{key_prefix} returned empty data")
        return standard_response("error", errors=[f"No {key_prefix} data found."])

    CacheManager.save(cache_name, data, ttl_minutes)
    logger.info(
        f"{key_prefix} fetched and cached (TTL: {ttl_minutes} minutes)",
        extra={**identifiers, "count": len(data) if isinstance(data, list) else 1},
    )

    return standard_response(
        "success",
        data={
            result_key: data,
            "from_cache": False,
            "cache_ttl_minutes": ttl_minutes,
            "cache_ttl_human": f"{ttl_minutes} minutes",
        },
    )
