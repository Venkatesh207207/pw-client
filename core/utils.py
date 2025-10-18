import json
import requests

API_BASE = "https://api.penpencil.co"
ORG_ID = "5eb393ee95fab7468a79d189"


def get_default_headers(
    auth_token=None,
    include_origin=True,
    content_type="application/json",
    extra_headers=None,
):
    headers = {
        "content-type": content_type,
        "user-agent": "Mozilla/5.0 (compatible; PenPencilFetcher/1.0)",
    }

    if include_origin:
        headers.update(
            {
                "origin": "https://www.pw.live",
                "referer": "https://www.pw.live/",
            }
        )

    if auth_token:
        headers["authorization"] = auth_token

    if extra_headers:
        headers.update(extra_headers)

    return headers


def handle_response(response):
    try:
        result = response.json()
    except json.JSONDecodeError:
        return False, f"Invalid JSON response (HTTP {response.status_code})", None
    if not isinstance(result, dict):
        return False, f"Unexpected response format: {type(result)}", result
    if not result.get("success", False):
        error = result.get("error", {})
        message = error.get("message", response.reason)
        status = error.get("status", response.status_code)
        return False, f"Error {status}: {message}", result
    return True, None, result


def safe_request(method, url, headers=None, params=None, data=None, timeout=10):
    try:
        response = requests.request(
            method, url, headers=headers, params=params, data=data, timeout=timeout
        )
        try:
            parsed = response.json()
            if isinstance(parsed, list):
                return True, None, parsed
        except json.JSONDecodeError:
            pass
        return handle_response(response)
    except requests.Timeout:
        return False, "Request timed out", None
    except requests.ConnectionError:
        return False, "Network connection error", None
    except Exception as e:
        return False, f"Unexpected error: {str(e)}", None


def make_api_url(*parts):
    return "/".join([API_BASE.strip("/")] + [str(p).strip("/") for p in parts if p])


def safe_get_json_field(data, *fields, default=None):
    current = data
    for f in fields:
        if isinstance(current, dict):
            current = current.get(f, default)
        else:
            return default
    return current


def standardize_response(success, error_msg=None, data=None):
    return {
        "success": bool(success),
        "error": error_msg if not success else None,
        "data": data if success else None,
    }
