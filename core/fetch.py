import requests
from core.utils import get_default_headers, handle_response


def get_batches(token, amount="paid"):
    url = "https://api.penpencil.co/batch-service/v1/batches/purchased-batches"
    querystring = {"type": "ALL", "amount": amount}

    headers = get_default_headers(auth_token=token)
    headers["client-type"] = "WEB"

    response = requests.get(url, headers=headers, params=querystring)
    success, error_msg, result = handle_response(response)
    if not success:
        return False, error_msg

    batches = []
    for item in result.get("data", []):
        batches.append(
            {
                "batch_id": item.get("_id"),
                "batch_name": item.get("name"),
                "batch_slug": item.get("slug"),
                "batch_start": item.get("startDate"),
                "batch_end": item.get("endDate"),
            }
        )

    return True, batches


def get_sub(token, batch_id):
    url = f"https://api.penpencil.co/v3/batches/{batch_id}/details"

    headers = get_default_headers(auth_token=token)
    headers["client-type"] = "WEB"

    response = requests.get(url, headers=headers)
    success, error_msg, result = handle_response(response)
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
            teacher_info = {
                "t_id": teacher.get("_id"),
                "t_name": f"{teacher.get('firstName', '')} {teacher.get('lastName', '')}".strip(),
                "t_exp": teacher.get("experience"),
                "t_qual": teacher.get("qualification"),
                "t_email": teacher.get("email"),
            }
            subject_info["teachers"].append(teacher_info)

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

    # Ensure subject_ids is a comma-separated string
    if isinstance(subject_ids, list):
        subject_ids_str = ",".join(str(sid) for sid in subject_ids)
    else:
        subject_ids_str = str(subject_ids)

    querystring = {"batchSubjectIds": subject_ids_str}
    headers = get_default_headers(auth_token=token)
    headers["client-type"] = "WEB"

    response = requests.get(url, headers=headers, params=querystring)
    success, error_msg, result = handle_response(response)
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

        if type_id not in chapters_by_subject:
            chapters_by_subject[type_id] = []
        chapters_by_subject[type_id].append(chapter)

    return True, chapters_by_subject


def get_ch_content(token, batch_id, subject_id, chapter_ids, content_type="ALL"):
    if isinstance(chapter_ids, str):
        chapter_ids = [chapter_ids]

    all_docs = []

    if content_type not in ["ALL", "DPP_PDF", "NOTES"]:
        raise ValueError("content_type must be one of: 'ALL', 'DPP_PDF', 'NOTES'")

    content_types_to_fetch = (
        [content_type] if content_type != "ALL" else ["NOTES", "DPP_PDF"]
    )

    for chapter_id in chapter_ids:
        for ctype in content_types_to_fetch:
            url = f"https://api.penpencil.co/batch-service/v3/batch-subject-schedules/{batch_id}/subject/{subject_id}/contents"
            query = {
                "skip": "0",
                "limit": "20",
                "contentType": ctype,
                "contentFilter": "ALL",
                "tagId": chapter_id,
            }

            headers = get_default_headers(auth_token=f"{token}")
            response = requests.get(url, headers=headers, params=query)
            success, error_msg, data = handle_response(response)
            if not success:
                continue

            items = data.get("data", [])
            for item in items:
                date = item.get("data", {}).get("date", "")
                homework_list = item.get("data", {}).get("homeworkIds", [])
                for hw in homework_list:
                    doc_type = hw.get("note")
                    for att in hw.get("attachmentIds", []):
                        all_docs.append(
                            {
                                "doc_id": att.get("_id"),
                                "doc_type": doc_type,
                                "doc_url": att.get("baseUrl", "") + att.get("key", ""),
                                "doc_name": att.get("name"),
                                "date": date,
                            }
                        )

    return all_docs
