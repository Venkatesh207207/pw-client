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
from dotenv import load_dotenv

logger = setup_logging()


def fetch_dpp_tests(
    token, batch_id, subject_id, chapter_id, page=1, limit=20, dpp_type="ALL"
):
    url = make_api_url("v3", "test-service", "tests", "new-dpp-list")
    params = {
        "page": page,
        "batchId": batch_id,
        "batchSubjectId": subject_id,
        "chapterId": chapter_id,
        "dppType": dpp_type,
        "limit": limit,
    }

    headers = get_default_headers(auth_token=token)
    success, error_msg, data = safe_request("GET", url, headers=headers, params=params)
    if not success:
        return standardize_response(False, error_msg)

    tests = []
    for item in safe_get_json_field(data, "data", default=[]):
        test_info = safe_get_json_field(item, "dppQuizDetails", default={})
        test_data = safe_get_json_field(test_info, "test", default={})

        tag = test_info.get("tag", "")
        attempted = tag.lower() == "reattempt"
        attempt_id = (
            safe_get_json_field(test_info, "testStudentMapping", "_id")
            if attempted
            else None
        )

        result_data = None
        if attempt_id:
            result_url = make_api_url(
                "v3", "test-service", "tests", test_data.get("_id"), "my-result"
            )
            success_result, _, result_json = safe_request(
                "GET", result_url, headers=headers
            )
            if success_result:
                perf = safe_get_json_field(
                    result_json, "data", "yourPerformance", default={}
                )
                result_data = {
                    "total_marks": perf.get("totalScore"),
                    "user_marks": perf.get("userScore"),
                    "time_taken": perf.get("timeTaken"),
                    "total_questions": perf.get("totalQuestions"),
                    "attempted_questions": perf.get("attemptedQuestions"),
                    "unattempted_questions": perf.get("unAttemptedQuestions"),
                    "correct_questions": perf.get("correctQuestions"),
                    "incorrect_questions": perf.get("inCorrectQuestions"),
                    "accuracy": perf.get("accuracy"),
                    "completed": perf.get("completed"),
                    "incorrect_score": perf.get("inCorrectScore"),
                    "unattempted_score": perf.get("unAttemptedScore"),
                }

        tests.append(
            {
                "order": item.get("_id"),
                "type": item.get("type"),
                "attempted": attempted,
                "attempt_id": attempt_id,
                "test_id": test_data.get("_id"),
                "test_name": test_data.get("name"),
                "total_marks": test_data.get("totalMarks"),
                "total_questions": test_data.get("totalQuestions"),
                "date": test_data.get("createdAt"),
                "performance": result_data,
            }
        )
    return standardize_response(True, data=tests)


def fetch_dpp_test_sol(token, attempt_id):
    url = make_api_url(
        "v3", "test-service", "tests", "mapping", attempt_id, "preview-test"
    )
    headers = get_default_headers(auth_token=token)
    success, error_msg, data = safe_request("GET", url, headers=headers)
    if not success:
        return standardize_response(False, error_msg)

    difficulty_levels_map = {
        lvl.get("level"): lvl.get("title")
        for lvl in safe_get_json_field(data, "data", "difficultyLevels", default=[])
    }

    questions_data = []
    for q in safe_get_json_field(data, "data", "questions", default=[]):
        question_info = safe_get_json_field(q, "question", default={})
        en_image = safe_get_json_field(question_info, "imageIds", "en", default={})
        question_id = en_image.get("_id")
        question_name = en_image.get("name")
        endlink = (en_image.get("baseUrl", "") or "") + (en_image.get("key", "") or "")
        question_number = question_info.get("questionNumber")
        positive_marks = question_info.get("positiveMarks")
        negative_marks = question_info.get("negativeMarks")
        difficulty_level = difficulty_levels_map.get(
            question_info.get("difficultyLevel"), "Unknown"
        )

        option_map = {
            opt["_id"]: safe_get_json_field(opt, "texts", "en")
            for opt in question_info.get("options", [])
        }
        solutions_ids = question_info.get("solutions", [])
        solutions_texts = [
            option_map.get(sid) for sid in solutions_ids if sid in option_map
        ]

        sol_desc_list = []
        for sol in question_info.get("solutionDescription", []):
            img_en = safe_get_json_field(sol, "imageIds", "en", default={})
            sol_desc_list.append(
                {
                    "sol_id": img_en.get("_id"),
                    "sol_name": img_en.get("name"),
                    "endlink": (img_en.get("baseUrl", "") or "")
                    + (img_en.get("key", "") or ""),
                }
            )

        questions_data.append(
            {
                "question_id": question_id,
                "question_name": question_name,
                "endlink": endlink,
                "order": question_number,
                "positive_marks": positive_marks,
                "negative_marks": negative_marks,
                "difficulty": difficulty_level,
                "solutions": solutions_texts,
                "solution_descriptions": sol_desc_list,
            }
        )

    return standardize_response(True, data=questions_data)


def helper_fetch_dpp_tests(
    batch_id: str,
    subject_id: str,
    chapter_id: str,
    page: int = 1,
    limit: int = 20,
    dpp_type: str = "ALL",
    refetch: bool = False,
):
    """
    Helper function for fetching DPP tests with caching support.

    - Reads TOKEN from .env using get_env_var()
    - Uses cache for 60 minutes unless refetch=True
    - Provides standard_response and consistent logging
    """

    logger.info(
        "Fetching DPP tests list",
        extra={
            "batch_id": batch_id,
            "subject_id": subject_id,
            "chapter_id": chapter_id,
            "refetch": refetch,
        },
    )

    try:
        # --- Validate input ---
        if not all([batch_id, subject_id, chapter_id]):
            logger.error("Missing required identifiers for DPP fetch")
            return standard_response(
                "error", errors=["batch_id, subject_id, and chapter_id are required."]
            )

        # --- Get token from .env ---
        token = get_env_var("TOKEN")
        if not token:
            logger.error("TOKEN not found in .env")
            return standard_response(
                "error", errors=["Authentication token not found in environment."]
            )

        cache_name = (
            f"dpp_tests_{batch_id}_{subject_id}_{chapter_id}_{dpp_type}_p{page}"
        )
        cache_path = DATA_DIR / f"{cache_name}.json"

        # --- Try cache (unless refetch is requested) ---
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
                    f"DPP tests loaded from cache ({human_age or 'unknown age'})",
                    extra={
                        "batch_id": batch_id,
                        "subject_id": subject_id,
                        "chapter_id": chapter_id,
                        "source": "cache",
                        "cache_age_minutes": cache_age_minutes,
                    },
                )

                return standard_response(
                    "success",
                    data={
                        "tests": cached_data,
                        "cache_age_minutes": cache_age_minutes,
                        "cache_age_human": human_age,
                        "from_cache": True,
                    },
                )

        # --- Fetch from API ---
        dpp_resp = fetch_dpp_tests(
            token,
            batch_id,
            subject_id,
            chapter_id,
            page=page,
            limit=limit,
            dpp_type=dpp_type,
        )

        # Note: fetch_dpp_tests() returns {"success": bool, "error": str, "data": [...]}
        if not dpp_resp.get("success"):
            logger.error("Failed to fetch DPP tests from API", extra=dpp_resp)
            return standard_response("error", errors=["Unable to fetch DPP tests."])

        data = dpp_resp.get("data", [])
        if not data:
            logger.warning("No DPP tests found in API response")
            return standard_response("error", errors=["No DPP tests found."])

        # --- Cache for 60 minutes ---
        ttl_minutes = 60
        ttl_hours = ttl_minutes / 60
        save_cache(cache_name, data, ttl_minutes=ttl_minutes)

        logger.info(
            f"DPP tests fetched and cached successfully (TTL: {ttl_hours} hour)",
            extra={
                "batch_id": batch_id,
                "subject_id": subject_id,
                "chapter_id": chapter_id,
                "ttl_minutes": ttl_minutes,
                "ttl_hours": ttl_hours,
                "count": len(data),
            },
        )

        return standard_response(
            "success",
            data={
                "tests": data,
                "cache_ttl_minutes": ttl_minutes,
                "cache_ttl_human": f"{ttl_hours} hour",
                "from_cache": False,
            },
        )

    except Exception as exc:
        logger.exception(
            "Error fetching DPP tests",
            extra={
                "batch_id": batch_id,
                "subject_id": subject_id,
                "chapter_id": chapter_id,
                "error": str(exc),
            },
        )
        return standard_response("error", errors=["Failed to fetch DPP tests."])


def helper_fetch_dpp_test_sol(attempt_id: str, refetch: bool = False):
    """
    Helper function for fetching DPP test solutions with caching support.

    - Reads TOKEN from .env
    - Uses cache for 6 hours unless refetch=True
    - Wraps fetch_dpp_test_sol() with standard_response and structured logging
    """

    logger.info(
        "Fetching DPP test solutions",
        extra={"attempt_id": attempt_id, "refetch": refetch},
    )

    try:
        if not attempt_id:
            logger.error("No attempt_id provided")
            return standard_response("error", errors=["attempt_id is required."])

        # --- Load token ---
        token = get_env_var("TOKEN")
        if not token:
            logger.error("TOKEN not found in .env")
            return standard_response(
                "error", errors=["Authentication token not found in environment."]
            )

        cache_name = f"dpp_test_sol_{attempt_id}"
        cache_path = DATA_DIR / f"{cache_name}.json"

        # --- Try cache (unless refetch=True) ---
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
                    f"DPP test solutions loaded from cache ({human_age or 'unknown age'})",
                    extra={
                        "attempt_id": attempt_id,
                        "source": "cache",
                        "cache_age_minutes": cache_age_minutes,
                    },
                )

                return standard_response(
                    "success",
                    data={
                        "solutions": cached_data,
                        "cache_age_minutes": cache_age_minutes,
                        "cache_age_human": human_age,
                        "from_cache": True,
                    },
                )

        # --- Fetch from API ---
        sol_resp = fetch_dpp_test_sol(token, attempt_id)
        if not sol_resp.get("success"):
            logger.error("Failed to fetch DPP test solutions from API", extra=sol_resp)
            return standard_response("error", errors=["Unable to fetch DPP solutions."])

        data = sol_resp.get("data", [])
        if not data:
            logger.warning("Empty DPP test solutions received from API")
            return standard_response("error", errors=["No DPP test solutions found."])

        # --- Cache the result for 6 hours ---
        ttl_minutes = 360
        ttl_hours = ttl_minutes // 60
        save_cache(cache_name, data, ttl_minutes=ttl_minutes)

        logger.info(
            f"DPP test solutions fetched and cached successfully (TTL: {ttl_hours} hours)",
            extra={
                "attempt_id": attempt_id,
                "ttl_minutes": ttl_minutes,
                "ttl_hours": ttl_hours,
            },
        )

        return standard_response(
            "success",
            data={
                "solutions": data,
                "cache_ttl_minutes": ttl_minutes,
                "cache_ttl_human": f"{ttl_hours} hours",
                "from_cache": False,
            },
        )

    except Exception as exc:
        logger.exception(
            "Error fetching DPP test solutions",
            extra={"attempt_id": attempt_id, "error": str(exc)},
        )
        return standard_response(
            "error", errors=["Failed to fetch DPP test solutions."]
        )
