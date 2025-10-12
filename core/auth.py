import requests
import json
import uuid
from core.utils import get_default_headers, handle_response


def send_otp(country_code, mobile_no):
    url = "https://api.penpencil.co/v1/users/get-otp"
    querystring = {"smsType": "0", "fallback": "true"}
    payload = {
        "username": str(mobile_no),
        "countryCode": str(country_code),
        "organizationId": "5eb393ee95fab7468a79d189",
    }

    headers = get_default_headers()
    response = requests.post(
        url, data=json.dumps(payload), headers=headers, params=querystring
    )
    success, error_msg, _ = handle_response(response)
    return (True, None) if success else (False, error_msg)


def verify_otp(mobile_no, otp):
    url = "https://api.penpencil.co/v3/oauth/token"
    querystring = {"smsType": "0", "fallback": "true"}
    payload = {
        "username": str(mobile_no),
        "otp": str(otp),
        "client_id": "system-admin",
        "grant_type": "password",
        "organizationId": "5eb393ee95fab7468a79d189",
    }

    headers = get_default_headers()
    response = requests.post(
        url, data=json.dumps(payload), headers=headers, params=querystring
    )
    success, error_msg, result = handle_response(response)
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
    headers = get_default_headers(auth_token=token)
    headers.update(
        {"organizationid": "5eb393ee95fab7468a79d189", "randomid": str(uuid.uuid4())}
    )

    response = requests.post(url, headers=headers)
    success, error_msg, result = handle_response(response)
    if not success:
        return False, error_msg

    return True, result.get("data", {}).get("isVerified", False)


def logout_user(token):
    url = "https://api.penpencil.co/v1/oauth/logout"
    device_id = token.replace("Bearer ", "")
    payload = {"deviceId": device_id}
    headers = get_default_headers(auth_token=token, include_origin=False)
    headers["client-type"] = "WEB"

    response = requests.post(url, data=json.dumps(payload), headers=headers)
    success, _, _ = handle_response(response)
    if not success:
        return False

    verified, _ = verify_token(token)
    return not verified
