from core.utils import (
    get_default_headers,
    safe_request,
    make_api_url,
    safe_get_json_field,
    standardize_response,
)


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
