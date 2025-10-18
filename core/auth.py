import json
import uuid
from core.utils import (
    get_default_headers,
    safe_request,
    make_api_url,
    safe_get_json_field,
    standardize_response,
    ORG_ID,
)


def send_otp(country_code, mobile_no):
    url = make_api_url("v1", "users", "get-otp")
    params = {"smsType": "0", "fallback": "true"}
    payload = {
        "username": str(mobile_no),
        "countryCode": str(country_code),
        "organizationId": ORG_ID,
    }

    headers = get_default_headers()
    success, error_msg, _ = safe_request(
        "POST", url, headers=headers, params=params, data=json.dumps(payload)
    )
    return standardize_response(success, error_msg, data={})


def verify_otp(mobile_no, otp):
    url = make_api_url("v3", "oauth", "token")
    params = {"smsType": "0", "fallback": "true"}
    payload = {
        "username": str(mobile_no),
        "otp": str(otp),
        "client_id": "system-admin",
        "grant_type": "password",
        "organizationId": ORG_ID,
    }

    headers = get_default_headers()
    success, error_msg, result = safe_request(
        "POST", url, headers=headers, params=params, data=json.dumps(payload)
    )
    if not success:
        return standardize_response(False, error_msg)

    data = safe_get_json_field(result, "data", default={})
    user = safe_get_json_field(data, "user", default={})

    token = f"Bearer {data.get('access_token', '')}"
    expires_in = data.get("expires_in")
    user_dict = {
        "user_id": user.get("id"),
        "f_name": user.get("firstName"),
        "l_name": user.get("lastName"),
        "mob_no": user.get("primaryNumber"),
        "country_code": user.get("countryCode"),
        "country_group": user.get("countryGroup"),
        "email_id": user.get("email"),
        "user_name": user.get("username"),
        "DOB": user.get("dateOfBirth"),
        "address": user.get("address"),
    }

    return standardize_response(
        True, data={"token": token, "expires_in": expires_in, "user": user_dict}
    )


def verify_token(token):
    url = make_api_url("v3", "oauth", "verify-token")
    headers = get_default_headers(
        auth_token=token,
        extra_headers={
            "organizationid": ORG_ID,
            "randomid": str(uuid.uuid4()),
        },
    )

    success, error_msg, result = safe_request("POST", url, headers=headers)
    if not success:
        return standardize_response(False, error_msg)

    is_verified = safe_get_json_field(result, "data", "isVerified", default=False)
    return standardize_response(True, data=is_verified)


def logout_user(token):
    url = make_api_url("v1", "oauth", "logout")
    device_id = token.replace("Bearer ", "")
    payload = {"deviceId": device_id}
    headers = get_default_headers(
        auth_token=token,
        include_origin=False,
        extra_headers={"client-type": "WEB"},
    )

    success, error_msg, _ = safe_request(
        "POST", url, headers=headers, data=json.dumps(payload)
    )
    if not success:
        return standardize_response(False, error_msg)

    verified_resp = verify_token(token)
    is_verified = safe_get_json_field(verified_resp, "data", default=True)
    return standardize_response(True, data=not is_verified)


def get_countries():
    url = "https://static.pw.live/auth-fe/assets/json/app-constants.json"
    headers = get_default_headers(
        include_origin=True,
        extra_headers={
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.6",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://www.pw.live/",
        },
    )
    success, error_msg, result = safe_request("GET", url, headers=headers)
    if not success or not isinstance(result, list):
        return standardize_response(False, error_msg)

    countries = [
        {
            "country_abbr": c.get("c"),
            "country_flag": c.get("e"),
            "country_name": c.get("n"),
            "country_code": c.get("d"),
        }
        for c in result
        if isinstance(c, dict)
    ]
    return standardize_response(True, data=countries)
