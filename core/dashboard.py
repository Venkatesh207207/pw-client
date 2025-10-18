from core.utils import (
    get_default_headers,
    safe_request,
    make_api_url,
    safe_get_json_field,
    standardize_response,
)


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


def fetch_quiz_subjects(token, batch_id, quiz_type="ALL"):
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
