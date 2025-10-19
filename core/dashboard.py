import os
import json
from core.utils import (
    get_default_headers,
    safe_request,
    make_api_url,
    safe_get_json_field,
    standardize_response,
    get_env_var,
    standard_response,
    DATA_DIR,
    ENV_PATH,
)
from core.cache import load_cache, save_cache
from datetime import datetime, timezone
from core.logging import setup_logging

logger = setup_logging()


def fetch_lecture_overview(token, batch_id):
    url = make_api_url("v3", "performance", "lecture")
    params = {"batchId": batch_id}
    headers = get_default_headers(auth_token=token)

    success, error_msg, data = safe_request("GET", url, headers=headers, params=params)
    if not success:
        return standardize_response(False, error_msg)

    d = safe_get_json_field(data, "data", default={})
    overview = {
        "completedChapter": d.get("completedChapter"),
        "completedLectures": d.get("completedLectures"),
        "totalWatchTime": d.get("totalWatchTime"),
        "totalChapters": d.get("totalChapters"),
        "totalLectures": d.get("totalLectures"),
    }
    return standardize_response(True, data=overview)


def fetch_lecture_subjects(token, batch_id):
    url = make_api_url("v3", "performance", "lecture", "subjects")
    params = {"batchId": batch_id}
    headers = get_default_headers(auth_token=token)

    success, error_msg, data = safe_request("GET", url, headers=headers, params=params)
    if not success:
        return standardize_response(False, error_msg)

    stats = []
    for item in safe_get_json_field(data, "data", default=[]):
        subject = safe_get_json_field(item, "subjectId", default={})
        stats.append(
            {
                "subjectName": subject.get("name"),
                "completedChapter": item.get("completedChapter"),
                "completedLectures": item.get("completedLectures"),
                "totalWatchTime": item.get("totalWatchTime"),
                "totalLectures": item.get("totalLectures"),
                "totalChapters": item.get("totalChapters"),
            }
        )
    return standardize_response(True, data=stats)


def fetch_quiz_overview(token, batch_id):
    url = make_api_url("v3", "performance", "quiz")
    params = {"batchId": batch_id}
    headers = get_default_headers(auth_token=token)

    success, error_msg, data = safe_request("GET", url, headers=headers, params=params)
    if not success:
        return standardize_response(False, error_msg)

    result = []
    for item in safe_get_json_field(data, "data", default=[]):
        val = safe_get_json_field(item, "value", default={})
        result.append(
            {
                "key": item.get("key"),
                "accuracy": val.get("accuracy"),
                "marksObtained": val.get("marksObtained"),
                "correctQuestions": val.get("correctQuestions"),
                "completedQuiz": val.get("completedQuiz"),
                "totalQuiz": val.get("totalQuiz"),
            }
        )
    return standardize_response(True, data=result)


def fetch_quiz_subjects(token, batch_id, quiz_type="OBJECTIVE"):
    url = make_api_url("v3", "performance", "quiz", "subjects")
    params = {"batchId": batch_id, "type": quiz_type}
    headers = get_default_headers(auth_token=token)

    success, error_msg, data = safe_request("GET", url, headers=headers, params=params)
    if not success:
        return standardize_response(False, error_msg)

    result = []
    for item in safe_get_json_field(data, "data", default=[]):
        subject = safe_get_json_field(item, "subjectId", default={})
        result.append(
            {
                "subjectName": subject.get("name"),
                "accuracy": item.get("accuracy"),
                "marksObtained": item.get("marksObtained"),
                "totalQuestions": item.get("totalQuestions"),
                "correctQuestions": item.get("correctQuestions"),
                "attemptedQuestions": item.get("attemptedQuestions"),
                "attempted": item.get("attempted"),
                "totalQuiz": item.get("totalQuiz"),
            }
        )
    return standardize_response(True, data=result)


def helper_fetch_lecture_overview(batch_id: str, refetch: bool = False):
    """
    Helper function to fetch lecture overview for a batch.

    - Reads TOKEN from .env
    - Uses cache for 30 minutes unless refetch=True
    - Provides standard_response and logging for clarity
    """

    logger.info(
        "Fetching lecture overview",
        extra={"batch_id": batch_id, "refetch": refetch},
    )

    try:
        if not batch_id:
            logger.error("No batch_id provided")
            return standard_response("error", errors=["batch_id is required."])

        token = get_env_var("TOKEN")
        if not token:
            logger.error("TOKEN not found in .env or environment")
            return standard_response(
                "error", errors=["Authentication token not found in environment."]
            )

        cache_name = f"lecture_overview_{batch_id}"
        cache_path = DATA_DIR / f"{cache_name}.json"

        # --- Try cache unless refetch is requested ---
        if not refetch:
            cached_data = load_cache(cache_name)
            if cached_data:
                cache_age_minutes = None
                human_age = None

                if cache_path.exists():
                    try:
                        raw = json.loads(cache_path.read_text())
                        ts_str = raw.get("timestamp") or raw.get("_metadata", {}).get(
                            "timestamp"
                        )
                        if ts_str:
                            ts = datetime.fromisoformat(ts_str)
                            delta = datetime.now(timezone.utc) - ts
                            cache_age_minutes = int(delta.total_seconds() / 60)
                            hours = cache_age_minutes // 60
                            minutes = cache_age_minutes % 60
                            human_age = (
                                f"{hours}h {minutes}m ago"
                                if hours
                                else f"{minutes} minutes ago"
                            )
                    except Exception:
                        logger.debug("Failed to compute cache age metadata")

                logger.info(
                    f"Lecture overview loaded from cache ({human_age or 'unknown age'})",
                    extra={
                        "batch_id": batch_id,
                        "source": "cache",
                        "cache_age_minutes": cache_age_minutes,
                    },
                )

                return standard_response(
                    "success",
                    data={
                        "overview": cached_data,
                        "cache_age_minutes": cache_age_minutes,
                        "cache_age_human": human_age,
                        "from_cache": True,
                    },
                )

        # --- Fetch from API ---
        result = fetch_lecture_overview(token, batch_id)
        if not result.get("success"):
            logger.error("Failed to fetch lecture overview from API", extra=result)
            return standard_response(
                "error", errors=["Unable to fetch lecture overview."]
            )

        data = result.get("data", {})
        if not data:
            logger.warning("Empty lecture overview received from API")
            return standard_response("error", errors=["No overview data found."])

        # --- Cache for 30 minutes ---
        ttl_minutes = 30
        save_cache(cache_name, data, ttl_minutes=ttl_minutes)

        logger.info(
            f"Lecture overview fetched and cached successfully (TTL: {ttl_minutes} minutes)",
            extra={
                "batch_id": batch_id,
                "ttl_minutes": ttl_minutes,
            },
        )

        return standard_response(
            "success",
            data={
                "overview": data,
                "cache_ttl_minutes": ttl_minutes,
                "cache_ttl_human": "30 minutes",
                "from_cache": False,
            },
        )

    except Exception as exc:
        logger.exception(
            "Error fetching lecture overview",
            extra={"batch_id": batch_id, "error": str(exc)},
        )
        return standard_response("error", errors=["Failed to fetch lecture overview."])


def helper_fetch_lecture_subjects(batch_id: str, refetch: bool = False):
    """
    Helper function to fetch lecture subjects for a given batch.

    - Reads TOKEN from .env
    - Uses cache for 30 minutes unless refetch=True
    - Provides standard_response and logging for clarity
    """

    logger.info(
        "Fetching lecture subjects",
        extra={"batch_id": batch_id, "refetch": refetch},
    )

    try:
        if not batch_id:
            logger.error("No batch_id provided")
            return standard_response("error", errors=["batch_id is required."])

        token = get_env_var("TOKEN")
        if not token:
            logger.error("TOKEN not found in .env or environment")
            return standard_response(
                "error", errors=["Authentication token not found in environment."]
            )

        cache_name = f"lecture_subjects_{batch_id}"
        cache_path = DATA_DIR / f"{cache_name}.json"

        # --- Try cache unless refetch is requested ---
        if not refetch:
            cached_data = load_cache(cache_name)
            if cached_data:
                cache_age_minutes = None
                human_age = None

                if cache_path.exists():
                    try:
                        raw = json.loads(cache_path.read_text())
                        ts_str = raw.get("timestamp") or raw.get("_metadata", {}).get(
                            "timestamp"
                        )
                        if ts_str:
                            ts = datetime.fromisoformat(ts_str)
                            delta = datetime.now(timezone.utc) - ts
                            cache_age_minutes = int(delta.total_seconds() / 60)
                            hours = cache_age_minutes // 60
                            minutes = cache_age_minutes % 60
                            human_age = (
                                f"{hours}h {minutes}m ago"
                                if hours
                                else f"{minutes} minutes ago"
                            )
                    except Exception:
                        logger.debug("Failed to compute cache age metadata")

                logger.info(
                    f"Lecture subjects loaded from cache ({human_age or 'unknown age'})",
                    extra={
                        "batch_id": batch_id,
                        "source": "cache",
                        "cache_age_minutes": cache_age_minutes,
                    },
                )

                return standard_response(
                    "success",
                    data={
                        "subjects": cached_data,
                        "cache_age_minutes": cache_age_minutes,
                        "cache_age_human": human_age,
                        "from_cache": True,
                    },
                )

        # --- Fetch from API ---
        result = fetch_lecture_subjects(token, batch_id)
        if not result.get("success"):
            logger.error("Failed to fetch lecture subjects from API", extra=result)
            return standard_response(
                "error", errors=["Unable to fetch lecture subjects."]
            )

        data = result.get("data", [])
        if not data:
            logger.warning("Empty lecture subjects received from API")
            return standard_response("error", errors=["No lecture subjects found."])

        # --- Cache for 30 minutes ---
        ttl_minutes = 30
        save_cache(cache_name, data, ttl_minutes=ttl_minutes)

        logger.info(
            f"Lecture subjects fetched and cached successfully (TTL: {ttl_minutes} minutes)",
            extra={
                "batch_id": batch_id,
                "ttl_minutes": ttl_minutes,
            },
        )

        return standard_response(
            "success",
            data={
                "subjects": data,
                "cache_ttl_minutes": ttl_minutes,
                "cache_ttl_human": "30 minutes",
                "from_cache": False,
            },
        )

    except Exception as exc:
        logger.exception(
            "Error fetching lecture subjects",
            extra={"batch_id": batch_id, "error": str(exc)},
        )
        return standard_response("error", errors=["Failed to fetch lecture subjects."])


def helper_fetch_quiz_overview(batch_id: str, refetch: bool = False):
    """
    Helper function to fetch quiz overview for a given batch.

    - Reads TOKEN from .env
    - Uses cache for 30 minutes unless refetch=True
    - Provides standard_response and detailed logging
    """

    logger.info(
        "Fetching quiz overview",
        extra={"batch_id": batch_id, "refetch": refetch},
    )

    try:
        if not batch_id:
            logger.error("No batch_id provided")
            return standard_response("error", errors=["batch_id is required."])

        token = get_env_var("TOKEN")
        if not token:
            logger.error("TOKEN not found in .env or environment")
            return standard_response(
                "error", errors=["Authentication token not found in environment."]
            )

        cache_name = f"quiz_overview_{batch_id}"
        cache_path = DATA_DIR / f"{cache_name}.json"

        # --- Try cache unless refetch is requested ---
        if not refetch:
            cached_data = load_cache(cache_name)
            if cached_data:
                cache_age_minutes = None
                human_age = None

                # Compute cache age metadata
                if cache_path.exists():
                    try:
                        raw = json.loads(cache_path.read_text())
                        ts_str = raw.get("timestamp") or raw.get("_metadata", {}).get(
                            "timestamp"
                        )
                        if ts_str:
                            ts = datetime.fromisoformat(ts_str)
                            delta = datetime.now(timezone.utc) - ts
                            cache_age_minutes = int(delta.total_seconds() / 60)
                            hours = cache_age_minutes // 60
                            minutes = cache_age_minutes % 60
                            human_age = (
                                f"{hours}h {minutes}m ago"
                                if hours
                                else f"{minutes} minutes ago"
                            )
                    except Exception:
                        logger.debug("Failed to compute cache age metadata")

                logger.info(
                    f"Quiz overview loaded from cache ({human_age or 'unknown age'})",
                    extra={
                        "batch_id": batch_id,
                        "source": "cache",
                        "cache_age_minutes": cache_age_minutes,
                    },
                )

                return standard_response(
                    "success",
                    data={
                        "overview": cached_data,
                        "cache_age_minutes": cache_age_minutes,
                        "cache_age_human": human_age,
                        "from_cache": True,
                    },
                )

        # --- Fetch from API ---
        result = fetch_quiz_overview(token, batch_id)
        if not result.get("success"):
            logger.error("Failed to fetch quiz overview from API", extra=result)
            return standard_response("error", errors=["Unable to fetch quiz overview."])

        data = result.get("data", [])
        if not data:
            logger.warning("Empty quiz overview received from API")
            return standard_response("error", errors=["No quiz overview found."])

        # --- Cache for 30 minutes ---
        ttl_minutes = 30
        save_cache(cache_name, data, ttl_minutes=ttl_minutes)

        logger.info(
            f"Quiz overview fetched and cached successfully (TTL: {ttl_minutes} minutes)",
            extra={"batch_id": batch_id, "ttl_minutes": ttl_minutes},
        )

        return standard_response(
            "success",
            data={
                "overview": data,
                "cache_ttl_minutes": ttl_minutes,
                "cache_ttl_human": "30 minutes",
                "from_cache": False,
            },
        )

    except Exception as exc:
        logger.exception(
            "Error fetching quiz overview",
            extra={"batch_id": batch_id, "error": str(exc)},
        )
        return standard_response("error", errors=["Failed to fetch quiz overview."])


def helper_fetch_quiz_subjects(
    batch_id: str, quiz_type: str = "OBJECTIVE", refetch: bool = False
):
    """
    Helper function to fetch quiz subject-wise performance stats for a batch.

    - Reads TOKEN from .env
    - Uses cache for 30 minutes unless refetch=True
    - Provides standard_response and detailed logging
    """

    logger.info(
        "Fetching quiz subjects overview",
        extra={"batch_id": batch_id, "quiz_type": quiz_type, "refetch": refetch},
    )

    try:
        if not batch_id:
            logger.error("No batch_id provided")
            return standard_response("error", errors=["batch_id is required."])

        token = get_env_var("TOKEN")
        if not token:
            logger.error("TOKEN not found in .env or environment")
            return standard_response(
                "error", errors=["Authentication token not found in environment."]
            )

        cache_name = f"quiz_subjects_{batch_id}_{quiz_type}"
        cache_path = DATA_DIR / f"{cache_name}.json"

        # --- Try cache unless refetch is requested ---
        if not refetch:
            cached_data = load_cache(cache_name)
            if cached_data:
                cache_age_minutes = None
                human_age = None

                # Compute cache metadata
                if cache_path.exists():
                    try:
                        raw = json.loads(cache_path.read_text())
                        ts_str = raw.get("timestamp") or raw.get("_metadata", {}).get(
                            "timestamp"
                        )
                        if ts_str:
                            ts = datetime.fromisoformat(ts_str)
                            delta = datetime.now(timezone.utc) - ts
                            cache_age_minutes = int(delta.total_seconds() / 60)
                            hours = cache_age_minutes // 60
                            minutes = cache_age_minutes % 60
                            human_age = (
                                f"{hours}h {minutes}m ago"
                                if hours
                                else f"{minutes} minutes ago"
                            )
                    except Exception:
                        logger.debug("Failed to compute cache age metadata")

                logger.info(
                    f"Quiz subjects overview loaded from cache ({human_age or 'unknown age'})",
                    extra={
                        "batch_id": batch_id,
                        "quiz_type": quiz_type,
                        "source": "cache",
                        "cache_age_minutes": cache_age_minutes,
                    },
                )

                return standard_response(
                    "success",
                    data={
                        "subjects": cached_data,
                        "cache_age_minutes": cache_age_minutes,
                        "cache_age_human": human_age,
                        "from_cache": True,
                    },
                )

        # --- Fetch from API ---
        result = fetch_quiz_subjects(token, batch_id, quiz_type=quiz_type)
        if not result.get("success"):
            logger.error("Failed to fetch quiz subjects from API", extra=result)
            return standard_response("error", errors=["Unable to fetch quiz subjects."])

        data = result.get("data", [])
        if not data:
            logger.warning("Empty quiz subjects data received from API")
            return standard_response("error", errors=["No quiz subjects found."])

        # --- Cache for 30 minutes ---
        ttl_minutes = 30
        save_cache(cache_name, data, ttl_minutes=ttl_minutes)

        logger.info(
            f"Quiz subjects overview fetched and cached successfully (TTL: {ttl_minutes} minutes)",
            extra={
                "batch_id": batch_id,
                "quiz_type": quiz_type,
                "ttl_minutes": ttl_minutes,
            },
        )

        return standard_response(
            "success",
            data={
                "subjects": data,
                "cache_ttl_minutes": ttl_minutes,
                "cache_ttl_human": "30 minutes",
                "from_cache": False,
            },
        )

    except Exception as exc:
        logger.exception(
            "Error fetching quiz subjects overview",
            extra={"batch_id": batch_id, "quiz_type": quiz_type, "error": str(exc)},
        )
        return standard_response(
            "error", errors=["Failed to fetch quiz subjects overview."]
        )
