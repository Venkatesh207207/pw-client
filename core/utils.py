def get_default_headers(auth_token=None, include_origin=True):
    headers = {"content-type": "application/json", "user-agent": "Mozilla/5.0"}
    if include_origin:
        headers.update(
            {"origin": "https://www.pw.live", "referer": "https://www.pw.live/"}
        )
    if auth_token:
        headers["authorization"] = auth_token
    return headers


def handle_response(response):
    result = response.json()
    if not result.get("success"):
        error = result.get("error", {})
        message = error.get("message", "Unknown error")
        status = error.get("status", "No status")
        return False, f"Error {status}: {message}", result
    return True, None, result
