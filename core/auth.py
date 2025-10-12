import requests
import json
import uuid


def send_otp(country_code, mobile_no):
    url = "https://api.penpencil.co/v1/users/get-otp"
    querystring = {"smsType": "0", "fallback": "true"}
    payload = {
        "username": str(mobile_no),
        "countryCode": str(country_code),
        "organizationId": "5eb393ee95fab7468a79d189",
    }
    headers = {
        "content-type": "application/json",
        "origin": "https://www.pw.live",
        "referer": "https://www.pw.live/",
        "user-agent": "Mozilla/5.0",
    }

    response = requests.post(
        url, data=json.dumps(payload), headers=headers, params=querystring
    )
    result = response.json()

    if result.get("success"):
        return True, None
    else:
        error = result.get("error", {})
        message = error.get("message", "Unknown error")
        status = error.get("status", "No status")
        return False, f"Error {status}: {message}"


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
    headers = {
        "content-type": "application/json",
        "origin": "https://www.pw.live",
        "referer": "https://www.pw.live/",
        "user-agent": "Mozilla/5.0",
    }

    response = requests.post(
        url, data=json.dumps(payload), headers=headers, params=querystring
    )
    result = response.json()

    if not result.get("success"):
        error = result.get("error", {})
        message = error.get("message", "Unknown error")
        status = error.get("status", "No status")
        return False, f"Error {status}: {message}"

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
    headers = {
        "organizationid": "5eb393ee95fab7468a79d189",
        "referer": "https://www.pw.live/",
        "user-agent": "Mozilla/5.0",
        "origin": "https://www.pw.live",
        "authorization": token,
        "randomid": str(uuid.uuid4()),
    }

    response = requests.post(url, headers=headers)
    result = response.json()

    if not result.get("success"):
        error = result.get("error", {})
        message = error.get("message", "Unknown error")
        status = error.get("status", "No status")
        return False, f"Error {status}: {message}"

    return True, result.get("data", {}).get("isVerified", False)


def logout_user(token):
    url = "https://api.penpencil.co/v1/oauth/logout"
    device_id = token.replace("Bearer ", "")
    payload = {"deviceId": device_id}
    headers = {
        "client-type": "WEB",
        "content-type": "application/json",
        "authorization": token,
    }

    response = requests.post(url, data=json.dumps(payload), headers=headers)
    result = response.json()

    if not result.get("success"):
        return False

    verified, _ = verify_token(token)
    return not verified
