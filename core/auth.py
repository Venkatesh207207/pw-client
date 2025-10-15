import json
import uuid
from core.utils import get_default_headers, safe_request


def send_otp(country_code, mobile_no):
    url = "https://api.penpencil.co/v1/users/get-otp"
    params = {"smsType": "0", "fallback": "true"}
    payload = {
        "username": str(mobile_no),
        "countryCode": str(country_code),
        "organizationId": "5eb393ee95fab7468a79d189",
    }

    headers = get_default_headers()
    success, error_msg, _ = safe_request(
        "POST", url, headers=headers, params=params, data=json.dumps(payload)
    )
    return (True, None) if success else (False, error_msg)


def verify_otp(mobile_no, otp):
    url = "https://api.penpencil.co/v3/oauth/token"
    params = {"smsType": "0", "fallback": "true"}
    payload = {
        "username": str(mobile_no),
        "otp": str(otp),
        "client_id": "system-admin",
        "grant_type": "password",
        "organizationId": "5eb393ee95fab7468a79d189",
    }

    headers = get_default_headers()
    success, error_msg, result = safe_request(
        "POST", url, headers=headers, params=params, data=json.dumps(payload)
    )

    if not success:
        return False, error_msg

    data = result.get("data", {})
    user = data.get("user", {})

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

    return True, token, expires_in, user_dict


def verify_token(token):
    url = "https://api.penpencil.co/v3/oauth/verify-token"
    headers = get_default_headers(
        auth_token=token,
        extra_headers={
            "organizationid": "5eb393ee95fab7468a79d189",
            "randomid": str(uuid.uuid4()),
        },
    )

    success, error_msg, result = safe_request("POST", url, headers=headers)
    if not success:
        return False, error_msg

    return True, result.get("data", {}).get("isVerified", False)


def logout_user(token):
    url = "https://api.penpencil.co/v1/oauth/logout"
    device_id = token.replace("Bearer ", "")
    payload = {"deviceId": device_id}
    headers = get_default_headers(
        auth_token=token,
        include_origin=False,
        extra_headers={"client-type": "WEB"},
    )

    success, _, _ = safe_request("POST", url, headers=headers, data=json.dumps(payload))
    if not success:
        return False

    verified, _ = verify_token(token)
    return not verified


def get_countries():
    url = "https://static.pw.live/auth-fe/assets/json/app-constants.json"
    headers = get_default_headers()
    success, error_msg, result = safe_request("GET", url, headers=headers)
    if not success:
        return []
    try:
        data = result if isinstance(result, list) else result.get("data", [])
    except Exception:
        return []
    formatted = [
        {
            "country_abbr": item.get("c"),
            "flag": item.get("e"),
            "country_name": item.get("n"),
            "country_code": item.get("d"),
        }
        for item in data
    ]
    return formatted
