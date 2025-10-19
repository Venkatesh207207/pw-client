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
)
from core.cache import load_cache, save_cache
from datetime import datetime, timezone
from core.logging import setup_logging

logger = setup_logging()


def get_batches(token, amount="paid"):
    url = make_api_url("batch-service", "v1", "batches", "purchased-batches")
    params = {"type": "ALL", "amount": amount}

    headers = get_default_headers(
        auth_token=token, extra_headers={"client-type": "WEB"}
    )
    success, error_msg, result = safe_request(
        "GET", url, headers=headers, params=params
    )
    if not success:
        return standardize_response(False, error_msg)

    batches_data = safe_get_json_field(result, "data", default=[])
    batches = [
        {
            "batch_id": item.get("_id"),
            "batch_name": item.get("name"),
            "batch_slug": item.get("slug"),
            "batch_start": item.get("startDate"),
            "batch_end": item.get("endDate"),
        }
        for item in batches_data
    ]

    return standardize_response(True, data=batches)


def get_sub(token, batch_id):
    url = make_api_url("v3", "batches", batch_id, "details")
    headers = get_default_headers(
        auth_token=token, extra_headers={"client-type": "WEB"}
    )
    success, error_msg, result = safe_request("GET", url, headers=headers)
    if not success:
        return standardize_response(False, error_msg)

    data = safe_get_json_field(result, "data", default={})
    batch_info = {
        "batch_id": data.get("_id"),
        "batch_name": data.get("batchName"),
        "order": data.get("displayOrder"),
        "expiry": data.get("expiryDays"),
        "subjects": [],
    }

    for subj in safe_get_json_field(data, "subjects", default=[]):
        subject_info = {
            "subject_id": subj.get("_id"),
            "subject_name": subj.get("subject"),
            "subject_slug": subj.get("slug"),
            "teachers": [],
        }

        for teacher in safe_get_json_field(subj, "teacherIds", default=[]):
            subject_info["teachers"].append(
                {
                    "t_id": teacher.get("_id"),
                    "t_name": f"{teacher.get('firstName', '')} {teacher.get('lastName', '')}".strip(),
                    "t_exp": teacher.get("experience"),
                    "t_qual": teacher.get("qualification"),
                    "t_email": teacher.get("email"),
                }
            )

        subject_info.update(
            {
                "tag": subj.get("tagCount"),
                "order": subj.get("displayOrder"),
                "lecture": subj.get("lectureCount"),
            }
        )
        batch_info["subjects"].append(subject_info)

    return standardize_response(True, data=batch_info)


def get_ch(token, batch_id, subject_ids):
    url = make_api_url("batch-service", "v1", "batch-tags", batch_id, "topics")
    subject_ids_str = (
        ",".join(map(str, subject_ids))
        if isinstance(subject_ids, list)
        else str(subject_ids)
    )
    params = {"batchSubjectIds": subject_ids_str}

    headers = get_default_headers(
        auth_token=token, extra_headers={"client-type": "WEB"}
    )
    success, error_msg, result = safe_request(
        "GET", url, headers=headers, params=params
    )
    if not success:
        return standardize_response(False, error_msg)

    chapters_by_subject = {}
    for item in safe_get_json_field(result, "data", "data", default=[]):
        type_id = item.get("typeId")
        chapter = {
            "chapter_id": item.get("_id"),
            "chapter_name": item.get("name"),
            "type": item.get("type"),
            "order": item.get("displayOrder"),
            "notes": item.get("notes"),
            "exercises": item.get("exercises"),
            "videos": item.get("videos"),
            "lecture_videos": item.get("lectureVideos"),
            "chapter_slug": item.get("slug"),
        }
        chapters_by_subject.setdefault(type_id, []).append(chapter)

    return standardize_response(True, data=chapters_by_subject)


def get_ch_content(token, batch_id, subject_id, chapter_ids, content_type="ALL"):
    if isinstance(chapter_ids, str):
        chapter_ids = [chapter_ids]

    if content_type not in ["ALL", "DPP_PDF", "NOTES"]:
        raise ValueError("content_type must be one of: 'ALL', 'DPP_PDF', 'NOTES'")

    content_types_to_fetch = (
        [content_type] if content_type != "ALL" else ["NOTES", "DPP_PDF"]
    )
    all_docs = []

    headers = get_default_headers(auth_token=token)
    base_url = make_api_url(
        "batch-service",
        "v3",
        "batch-subject-schedules",
        batch_id,
        "subject",
        subject_id,
        "contents",
    )

    for chapter_id in chapter_ids:
        for ctype in content_types_to_fetch:
            params = {
                "skip": "0",
                "limit": "20",
                "contentType": ctype,
                "contentFilter": "ALL",
                "tagId": chapter_id,
            }

            success, error_msg, data = safe_request(
                "GET", base_url, headers=headers, params=params
            )
            if not success or not data:
                continue

            for item in safe_get_json_field(data, "data", default=[]):
                date = safe_get_json_field(item, "data", "date", default="")
                for hw in safe_get_json_field(item, "data", "homeworkIds", default=[]):
                    doc_type = hw.get("note")
                    for att in hw.get("attachmentIds", []):
                        all_docs.append(
                            {
                                "doc_id": att.get("_id"),
                                "doc_type": doc_type,
                                "doc_url": (att.get("baseUrl", "") or "")
                                + (att.get("key", "") or ""),
                                "doc_name": att.get("name"),
                                "date": date,
                            }
                        )

    return standardize_response(True, data=all_docs)


def fetch_announcements(token, batch_id, page=1):
    url = make_api_url("v1", "batches", batch_id, "announcement")
    params = {"page": page}
    headers = get_default_headers(auth_token=token)

    success, error_msg, data = safe_request("GET", url, headers=headers, params=params)
    if not success or not data:
        return standardize_response(False, error_msg)

    announcements = []
    for ann in safe_get_json_field(data, "data", default=[]):
        announcement_info = {
            "announcement": ann.get("announcement"),
            "_id": ann.get("_id"),
            "scheduleTime": ann.get("scheduleTime"),
        }

        attachment = ann.get("attachment")
        if attachment:
            announcement_info["endlink"] = (attachment.get("baseUrl", "") or "") + (
                attachment.get("key", "") or ""
            )
        else:
            announcement_info["attachment"] = None

        announcements.append(announcement_info)

    return standardize_response(True, data=announcements)


def helper_get_batches(amount: str = "paid", refetch: bool = False):

    logger.info("Fetching batch list", extra={"amount": amount, "refetch": refetch})

    try:

        if amount not in {"paid", "free"}:
            logger.error("Invalid amount type provided", extra={"amount": amount})
            return standard_response(
                "error", errors=["Invalid amount type. Must be 'paid' or 'free'."]
            )

        token = get_env_var("TOKEN")
        if not token:
            logger.error("TOKEN not found in .env")
            return standard_response(
                "error", errors=["Authentication token not found in environment."]
            )

        cache_name = f"batches_{amount}"
        cache_path = DATA_DIR / f"{cache_name}.json"

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
                    f"Batch list loaded from cache ({human_age or 'unknown age'})",
                    extra={
                        "count": len(cached_data),
                        "source": "cache",
                        "cache_age_minutes": cache_age_minutes,
                    },
                )

                return standard_response(
                    "success",
                    data={
                        "batches": cached_data,
                        "cache_age_minutes": cache_age_minutes,
                        "cache_age_human": human_age,
                        "from_cache": True,
                    },
                )

        batches_resp = get_batches(token, amount)
        if not batches_resp.get("success"):
            logger.error("Failed to fetch batches from API", extra=batches_resp)
            return standard_response(
                "error", errors=["Unable to fetch batch list from API."]
            )

        data = batches_resp.get("data", [])
        if not data:
            logger.warning("Empty batch list received from API")
            return standard_response("error", errors=["No batches found."])

        ttl_minutes = 1440
        ttl_hours = ttl_minutes // 60
        save_cache(cache_name, data, ttl_minutes=ttl_minutes)

        logger.info(
            f"Batch list fetched and cached successfully (TTL: {ttl_hours} hours)",
            extra={
                "count": len(data),
                "ttl_minutes": ttl_minutes,
                "ttl_hours": ttl_hours,
            },
        )

        return standard_response(
            "success",
            data={
                "batches": data,
                "cache_ttl_minutes": ttl_minutes,
                "cache_ttl_human": f"{ttl_hours} hours",
                "from_cache": False,
            },
        )

    except Exception as exc:
        logger.exception("Error fetching batches", extra={"error": str(exc)})
        return standard_response("error", errors=["Failed to fetch batch list."])


def helper_get_sub(batch_id: str, refetch: bool = False):

    logger.info(
        "Fetching batch details", extra={"batch_id": batch_id, "refetch": refetch}
    )

    try:
        if not batch_id:
            logger.error("No batch_id provided")
            return standard_response("error", errors=["batch_id is required."])

        token = get_env_var("TOKEN")
        if not token:
            logger.error("TOKEN not found in .env")
            return standard_response(
                "error", errors=["Authentication token not found in environment."]
            )

        cache_name = f"batch_details_{batch_id}"
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
                    f"Batch details loaded from cache ({human_age or 'unknown age'})",
                    extra={
                        "batch_id": batch_id,
                        "source": "cache",
                        "cache_age_minutes": cache_age_minutes,
                    },
                )

                return standard_response(
                    "success",
                    data={
                        "batch": cached_data,
                        "cache_age_minutes": cache_age_minutes,
                        "cache_age_human": human_age,
                        "from_cache": True,
                    },
                )

        # --- Fetch from API ---
        sub_resp = get_sub(token, batch_id)
        if not sub_resp.get("success"):
            logger.error("Failed to fetch batch details from API", extra=sub_resp)
            return standard_response("error", errors=["Unable to fetch batch details."])

        data = sub_resp.get("data", {})
        if not data:
            logger.warning("Empty batch details received from API")
            return standard_response("error", errors=["No batch details found."])

        # --- Cache the result for 1 day ---
        ttl_minutes = 1440
        ttl_hours = ttl_minutes // 60
        save_cache(cache_name, data, ttl_minutes=ttl_minutes)

        logger.info(
            f"Batch details fetched and cached successfully (TTL: {ttl_hours} hours)",
            extra={
                "batch_id": batch_id,
                "ttl_minutes": ttl_minutes,
                "ttl_hours": ttl_hours,
            },
        )

        return standard_response(
            "success",
            data={
                "batch": data,
                "cache_ttl_minutes": ttl_minutes,
                "cache_ttl_human": f"{ttl_hours} hours",
                "from_cache": False,
            },
        )

    except Exception as exc:
        logger.exception(
            "Error fetching batch details",
            extra={"batch_id": batch_id, "error": str(exc)},
        )
        return standard_response("error", errors=["Failed to fetch batch details."])


def helper_get_chapters(batch_id: str, subject_ids, refetch: bool = False):
    """
    Fetch chapters (topics) for one or more subjects inside a batch.

    - Caches results for 6 hours (TTL = 360 minutes)
    - Uses TOKEN automatically from .env
    - Supports refetch=True to bypass cache
    """

    logger.info(
        "Fetching chapters for batch",
        extra={"batch_id": batch_id, "subject_ids": subject_ids, "refetch": refetch},
    )

    try:
        # --- Validation ---
        if not batch_id:
            logger.error("Missing batch_id")
            return standard_response("error", errors=["batch_id is required."])

        if not subject_ids:
            logger.error("Missing subject_ids")
            return standard_response("error", errors=["subject_ids are required."])

        token = get_env_var("TOKEN")
        if not token:
            logger.error("TOKEN not found in environment")
            return standard_response(
                "error", errors=["TOKEN not found in environment."]
            )

        # --- Cache setup ---
        subject_part = (
            "_".join(map(str, subject_ids))
            if isinstance(subject_ids, list)
            else str(subject_ids)
        )
        cache_name = f"chapters_{batch_id}_{subject_part}"
        cache_path = DATA_DIR / f"{cache_name}.json"

        # --- Try loading cache (unless refetch=True) ---
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
                    f"Chapters loaded from cache ({human_age or 'unknown age'})",
                    extra={
                        "batch_id": batch_id,
                        "source": "cache",
                        "cache_age_minutes": cache_age_minutes,
                    },
                )

                return standard_response(
                    "success",
                    data={
                        "chapters": cached_data,
                        "cache_age_minutes": cache_age_minutes,
                        "cache_age_human": human_age,
                        "from_cache": True,
                    },
                )

        # --- Fetch from API ---
        ch_resp = get_ch(token, batch_id, subject_ids)
        if not ch_resp.get("success"):
            logger.error(
                "Failed to fetch chapters from API", extra={"batch_id": batch_id}
            )
            return standard_response("error", errors=["Unable to fetch chapters."])

        data = ch_resp.get("data", {})
        if not data:
            logger.warning("Empty chapters data received from API")
            return standard_response("error", errors=["No chapters found."])

        # --- Cache the data for 6 hours ---
        ttl_minutes = 360
        ttl_hours = ttl_minutes // 60
        save_cache(cache_name, data, ttl_minutes=ttl_minutes)

        logger.info(
            f"Chapters fetched and cached successfully (TTL: {ttl_hours} hours)",
            extra={
                "batch_id": batch_id,
                "subject_ids": subject_ids,
                "ttl_minutes": ttl_minutes,
                "ttl_hours": ttl_hours,
            },
        )

        return standard_response(
            "success",
            data={
                "chapters": data,
                "cache_ttl_minutes": ttl_minutes,
                "cache_ttl_human": f"{ttl_hours} hours",
                "from_cache": False,
            },
        )

    except Exception as exc:
        logger.exception(
            "Error fetching chapters",
            extra={"batch_id": batch_id, "error": str(exc)},
        )
        return standard_response("error", errors=["Failed to fetch chapters."])


def helper_get_chapter_content(
    batch_id: str,
    subject_id: str,
    chapter_ids,
    content_type: str = "ALL",
    refetch: bool = False,
):
    """
    Helper for fetching chapter content (notes, DPP PDFs, etc.)
    - Uses token from .env
    - Supports refetch=True to bypass cache
    - Caches responses for 1 hour (TTL = 60 minutes)
    """

    logger.info(
        "Fetching chapter content",
        extra={
            "batch_id": batch_id,
            "subject_id": subject_id,
            "chapter_ids": chapter_ids,
            "content_type": content_type,
            "refetch": refetch,
        },
    )

    try:
        # --- Validate Inputs ---
        if not batch_id or not subject_id or not chapter_ids:
            logger.error("Missing required parameters")
            return standard_response(
                "error", errors=["batch_id, subject_id, and chapter_ids are required."]
            )

        if content_type not in ["ALL", "DPP_PDF", "NOTES"]:
            logger.error("Invalid content_type", extra={"content_type": content_type})
            return standard_response(
                "error",
                errors=["content_type must be one of: 'ALL', 'DPP_PDF', 'NOTES'"],
            )

        token = get_env_var("TOKEN")
        if not token:
            logger.error("TOKEN not found in environment")
            return standard_response(
                "error", errors=["TOKEN not found in environment."]
            )

        # --- Cache Setup ---
        chapter_part = (
            "_".join(map(str, chapter_ids))
            if isinstance(chapter_ids, list)
            else str(chapter_ids)
        )
        cache_name = f"ch_content_{batch_id}_{subject_id}_{chapter_part}_{content_type}"
        cache_path = DATA_DIR / f"{cache_name}.json"

        # --- Try loading from cache (unless refetch=True) ---
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
                    f"Chapter content loaded from cache ({human_age or 'unknown age'})",
                    extra={
                        "batch_id": batch_id,
                        "subject_id": subject_id,
                        "cache_age_minutes": cache_age_minutes,
                    },
                )

                return standard_response(
                    "success",
                    data={
                        "content": cached_data,
                        "cache_age_minutes": cache_age_minutes,
                        "cache_age_human": human_age,
                        "from_cache": True,
                    },
                )

        # --- Fetch from API ---
        ch_content_resp = get_ch_content(
            token, batch_id, subject_id, chapter_ids, content_type=content_type
        )

        if not ch_content_resp.get("success"):
            logger.error(
                "Failed to fetch chapter content from API",
                extra={"batch_id": batch_id, "subject_id": subject_id},
            )
            return standard_response(
                "error", errors=["Unable to fetch chapter content."]
            )

        data = ch_content_resp.get("data", [])
        if not data:
            logger.warning("Empty chapter content received from API")
            return standard_response("error", errors=["No chapter content found."])

        # --- Cache for 1 hour ---
        ttl_minutes = 60
        ttl_hours = ttl_minutes // 60
        save_cache(cache_name, data, ttl_minutes=ttl_minutes)

        logger.info(
            f"Chapter content fetched and cached successfully (TTL: {ttl_hours} hour)",
            extra={
                "batch_id": batch_id,
                "subject_id": subject_id,
                "ttl_minutes": ttl_minutes,
                "ttl_hours": ttl_hours,
            },
        )

        return standard_response(
            "success",
            data={
                "content": data,
                "cache_ttl_minutes": ttl_minutes,
                "cache_ttl_human": f"{ttl_hours} hour",
                "from_cache": False,
            },
        )

    except Exception as exc:
        logger.exception(
            "Error fetching chapter content",
            extra={
                "batch_id": batch_id,
                "subject_id": subject_id,
                "error": str(exc),
            },
        )
        return standard_response("error", errors=["Failed to fetch chapter content."])


def helper_fetch_announcements(batch_id: str, page: int = 1, refetch: bool = False):
    """
    Helper to fetch and cache batch announcements.
    - Uses token from .env
    - Supports refetch=True to skip cache
    - Caches results for 30 minutes
    """

    logger.info(
        "Fetching announcements",
        extra={"batch_id": batch_id, "page": page, "refetch": refetch},
    )

    try:
        # --- Validate inputs ---
        if not batch_id:
            logger.error("Missing required batch_id parameter")
            return standard_response("error", errors=["batch_id is required."])

        token = get_env_var("TOKEN")
        if not token:
            logger.error("TOKEN not found in environment")
            return standard_response(
                "error", errors=["TOKEN not found in environment."]
            )

        # --- Cache setup ---
        cache_name = f"announcements_{batch_id}_p{page}"
        cache_path = DATA_DIR / f"{cache_name}.json"

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
                    f"Announcements loaded from cache ({human_age or 'unknown age'})",
                    extra={
                        "batch_id": batch_id,
                        "page": page,
                        "cache_age_minutes": cache_age_minutes,
                    },
                )

                return standard_response(
                    "success",
                    data={
                        "announcements": cached_data,
                        "cache_age_minutes": cache_age_minutes,
                        "cache_age_human": human_age,
                        "from_cache": True,
                    },
                )

        # --- Fetch from API ---
        ann_resp = fetch_announcements(token, batch_id, page)

        if not ann_resp.get("success"):
            logger.error(
                "Failed to fetch announcements from API",
                extra={"batch_id": batch_id, "page": page},
            )
            return standard_response("error", errors=["Unable to fetch announcements."])

        data = ann_resp.get("data", [])
        if not data:
            logger.warning("Empty announcements list received from API")
            return standard_response("error", errors=["No announcements found."])

        # --- Cache for 30 minutes ---
        ttl_minutes = 30
        ttl_human = "30 minutes"
        save_cache(cache_name, data, ttl_minutes=ttl_minutes)

        logger.info(
            f"Announcements fetched and cached successfully (TTL: {ttl_human})",
            extra={
                "batch_id": batch_id,
                "page": page,
                "ttl_minutes": ttl_minutes,
            },
        )

        return standard_response(
            "success",
            data={
                "announcements": data,
                "cache_ttl_minutes": ttl_minutes,
                "cache_ttl_human": ttl_human,
                "from_cache": False,
            },
        )

    except Exception as exc:
        logger.exception(
            "Error fetching announcements",
            extra={"batch_id": batch_id, "page": page, "error": str(exc)},
        )
        return standard_response("error", errors=["Failed to fetch announcements."])
