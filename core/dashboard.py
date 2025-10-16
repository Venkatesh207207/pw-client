from core.utils import get_default_headers, safe_request


def fetch_lecture_overview(token, batch_id):
    url = f"https://api.penpencil.co/v3/performance/lecture"
    params = {"batchId": batch_id}
    headers = get_default_headers(auth_token=token)

    success, error_msg, data = safe_request("GET", url, headers=headers, params=params)
    if not success or not data:
        return {}

    d = data.get("data", {})
    return {
        "completedChapter": d.get("completedChapter"),
        "completedLectures": d.get("completedLectures"),
        "totalWatchTime": d.get("totalWatchTime"),
        "totalChapters": d.get("totalChapters"),
        "totalLectures": d.get("totalLectures"),
    }


def fetch_lecture_subjects(token, batch_id):
    url = f"https://api.penpencil.co/v3/performance/lecture/subjects"
    params = {"batchId": batch_id}
    headers = get_default_headers(auth_token=token)

    success, error_msg, data = safe_request("GET", url, headers=headers, params=params)
    if not success or not data:
        return []

    stats = []
    for item in data.get("data", []):
        subject = item.get("subjectId", {})
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

    return stats


def fetch_quiz_overview(token, batch_id):
    url = f"https://api.penpencil.co/v3/performance/quiz"
    params = {"batchId": batch_id}
    headers = get_default_headers(auth_token=token)

    success, error_msg, data = safe_request("GET", url, headers=headers, params=params)
    if not success or not data:
        return []

    result = []
    for item in data.get("data", []):
        val = item.get("value", {})
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

    return result


def fetch_quiz_subjects(token, batch_id, quiz_type="ALL"):
    url = f"https://api.penpencil.co/v3/performance/quiz/subjects"
    params = {"batchId": batch_id, "type": quiz_type}
    headers = get_default_headers(auth_token=token)

    success, error_msg, data = safe_request("GET", url, headers=headers, params=params)
    if not success or not data:
        return []

    result = []
    for item in data.get("data", []):
        subject = item.get("subjectId", {})
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

    return result
