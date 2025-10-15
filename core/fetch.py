from core.utils import get_default_headers, safe_request


def get_batches(token, amount="paid"):
    url = "https://api.penpencil.co/batch-service/v1/batches/purchased-batches"
    params = {"type": "ALL", "amount": amount}

    headers = get_default_headers(
        auth_token=token,
        extra_headers={"client-type": "WEB"},
    )

    success, error_msg, result = safe_request(
        "GET", url, headers=headers, params=params
    )
    if not success:
        return False, error_msg

    batches = [
        {
            "batch_id": item.get("_id"),
            "batch_name": item.get("name"),
            "batch_slug": item.get("slug"),
            "batch_start": item.get("startDate"),
            "batch_end": item.get("endDate"),
        }
        for item in result.get("data", [])
    ]

    return True, batches


def get_sub(token, batch_id):
    url = f"https://api.penpencil.co/v3/batches/{batch_id}/details"

    headers = get_default_headers(
        auth_token=token,
        extra_headers={"client-type": "WEB"},
    )

    success, error_msg, result = safe_request("GET", url, headers=headers)
    if not success:
        return False, error_msg

    data = result.get("data", {})

    batch_info = {
        "batch_id": data.get("_id"),
        "batch_name": data.get("batchName"),
        "order": data.get("displayOrder"),
        "expiry": data.get("expiryDays"),
        "subjects": [],
    }

    for subj in data.get("subjects", []):
        subject_info = {
            "subject_id": subj.get("_id"),
            "subject_name": subj.get("subject"),
            "subject_slug": subj.get("slug"),
            "teachers": [],
        }

        for teacher in subj.get("teacherIds", []):
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

    return True, batch_info


def get_ch(token, batch_id, subject_ids):
    url = f"https://api.penpencil.co/batch-service/v1/batch-tags/{batch_id}/topics"

    subject_ids_str = (
        ",".join(map(str, subject_ids))
        if isinstance(subject_ids, list)
        else str(subject_ids)
    )
    params = {"batchSubjectIds": subject_ids_str}

    headers = get_default_headers(
        auth_token=token,
        extra_headers={"client-type": "WEB"},
    )

    success, error_msg, result = safe_request(
        "GET", url, headers=headers, params=params
    )
    if not success:
        return False, error_msg

    chapters_by_subject = {}
    for item in result.get("data", {}).get("data", []):
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

    return True, chapters_by_subject


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
    base_url = f"https://api.penpencil.co/batch-service/v3/batch-subject-schedules/{batch_id}/subject/{subject_id}/contents"

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

            for item in data.get("data", []):
                date = item.get("data", {}).get("date", "")
                for hw in item.get("data", {}).get("homeworkIds", []):
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

    return all_docs
