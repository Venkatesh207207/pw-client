from core.utils import get_default_headers, safe_request


def fetch_dpp_tests(
    token, batch_id, subject_id, chapter_id, page=1, limit=20, dpp_type="ALL"
):
    url = "https://api.penpencil.co/v3/test-service/tests/new-dpp-list"
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
        return []

    tests = []
    for item in data.get("data", []):
        test_info = item.get("dppQuizDetails", {})
        test_data = test_info.get("test", {})

        tag = test_info.get("tag", "")
        attempted = tag.lower() == "reattempt"
        attempt_id = (
            test_info.get("testStudentMapping", {}).get("_id") if attempted else None
        )

        result_data = None
        if attempt_id:
            result_url = f"https://api.penpencil.co/v3/test-service/tests/{test_data.get('_id')}/my-result"
            success_result, _, result_json = safe_request(
                "GET", result_url, headers=headers
            )
            if success_result:
                perf = result_json.get("data", {}).get("yourPerformance", {})
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

    return tests


def fetch_dpp_test_sol(token, attempt_id):
    url = f"https://api.penpencil.co/v3/test-service/tests/mapping/{attempt_id}/preview-test"
    headers = get_default_headers(auth_token=token)
    success, error_msg, data = safe_request("GET", url, headers=headers)
    if not success:
        return []

    questions_data = []
    difficulty_levels_map = {
        lvl.get("level"): lvl.get("title")
        for lvl in data.get("data", {}).get("difficultyLevels", [])
    }

    for q in data.get("data", {}).get("questions", []):
        question_info = q.get("question", {})
        en_image = question_info.get("imageIds", {}).get("en", {})
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
            opt["_id"]: opt.get("texts", {}).get("en")
            for opt in question_info.get("options", [])
        }
        solutions_ids = question_info.get("solutions", [])
        solutions_texts = [
            option_map.get(sid) for sid in solutions_ids if sid in option_map
        ]

        sol_desc_list = []
        for sol in question_info.get("solutionDescription", []):
            img_en = sol.get("imageIds", {}).get("en", {})
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

    return questions_data
