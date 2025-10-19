import json
import uuid
import time
import os
import json
import logging
from dotenv import load_dotenv, set_key, find_dotenv
from datetime import datetime, timezone
from core.utils import (
    get_default_headers,
    safe_request,
    make_api_url,
    safe_get_json_field,
    standardize_response,
    standard_response,
    ORG_ID,
    get_env_var,
    set_env_var,
    ENV_PATH,
    DATA_DIR,
)
from core.cache import save_cache, load_cache, clear_cache
from core.logging import setup_logging

logger = setup_logging()
load_dotenv()
ENV_PATH = find_dotenv()


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


def helper_send_otp(country_code: str, mobile_no: str):
    logger.info(
        "Starting OTP send process",
        extra={"country_code": country_code, "mobile_no": mobile_no},
    )

    countries_resp = get_countries()
    if not countries_resp.get("success"):
        logger.error(
            "Failed to fetch country list",
            extra={"error": countries_resp.get("error")},
        )
        return standard_response("error", errors=["Unable to fetch country list."])

    valid_codes = {c["country_code"] for c in countries_resp.get("data", [])}
    if country_code not in valid_codes:
        logger.error(
            "Invalid country code provided", extra={"country_code": country_code}
        )
        return standard_response(
            "error", errors=[f"Invalid country code: {country_code}"]
        )

    otp_resp = send_otp(country_code, mobile_no)
    if not otp_resp.get("success"):
        logger.error(
            "Failed to send OTP",
            extra={
                "country_code": country_code,
                "mobile_no": mobile_no,
                "error": otp_resp.get("error"),
            },
        )
        return standard_response("error", errors=[otp_resp.get("error")])

    try:
        set_env_var("MOBILE_NO", str(mobile_no))
        set_env_var("COUNTRY_CODE", str(country_code))
        logger.info(
            "OTP sent successfully and stored mobile info",
            extra={"mobile_no": mobile_no, "country_code": country_code},
        )
    except Exception as exc:
        logger.exception(
            "Failed to store mobile number in .env", extra={"error": str(exc)}
        )
        return standard_response("error", errors=["Failed to store mobile number"])

    return standard_response(
        "success", data={"message": f"OTP sent to {country_code}{mobile_no}"}
    )


def helper_verify_otp(otp: str):
    logger.info("Starting OTP verification")

    mobile_no = get_env_var("MOBILE_NO")
    if not mobile_no:
        logger.error("Mobile number not found in .env")
        return standard_response(
            "error", errors=["Mobile number not found in environment."]
        )

    verify_resp = verify_otp(mobile_no, otp)
    if not verify_resp.get("success"):
        logger.error(
            "OTP verification failed",
            extra={"mobile_no": mobile_no, "error": verify_resp.get("error")},
        )
        return standard_response("error", errors=[verify_resp.get("error")])

    data = verify_resp.get("data", {})
    token = data.get("token")
    expires_in = data.get("expires_in")
    user_dict = data.get("user", {})

    try:
        set_env_var("TOKEN", token or "")
        set_env_var("EXPIRES_IN", str(expires_in or ""))
        logger.info("Token and expiry saved in .env", extra={"expires_in": expires_in})
    except Exception as exc:
        logger.exception("Failed to save token in .env", extra={"error": str(exc)})

    try:
        save_cache("user_details", user_dict, ttl_minutes=60)
        logger.info(
            "User details cached successfully",
            extra={"user_id": user_dict.get("user_id")},
        )
    except Exception as exc:
        logger.exception("Failed to cache user details", extra={"error": str(exc)})
    return standard_response(
        "success",
        data={
            "token": token,
            "expires_in": expires_in,
            "user": user_dict,
        },
    )


def helper_verify_token():

    logger.info("Starting token verification process")

    token = get_env_var("TOKEN")
    expires_in = get_env_var("EXPIRES_IN")

    if not token:
        logger.error("Token not found in .env")
        return standard_response("error", errors=["Token not found in environment."])

    try:
        if expires_in and float(expires_in) < time.time():
            logger.warning("Token expired based on EXPIRES_IN value")
            # Remove expired value from .env
            set_env_var("EXPIRES_IN", "")
            return standard_response("error", errors=["Token expired."])
    except Exception as exc:
        logger.exception("Error checking token expiry", extra={"error": str(exc)})

    try:
        verify_resp = verify_token(token)
        if not verify_resp.get("success"):
            logger.error("Token verification failed via API", extra=verify_resp)
            return standard_response("error", errors=["Token verification failed."])

        is_verified = verify_resp.get("data", False)

        if not is_verified:
            logger.warning("Token invalidated by server")
            return standard_response("error", errors=["Token invalid or revoked."])

        logger.info("Token verified successfully")
        return standard_response(
            "success", data={"is_verified": True, "expires_in": expires_in}
        )

    except Exception as exc:
        logger.exception("Unexpected error verifying token", extra={"error": str(exc)})
        return standard_response("error", errors=["Failed to verify token."])


def helper_logout_user():

    logger.info("Starting user logout process")

    token = get_env_var("TOKEN")
    if not token:
        logger.error("No token found for logout")
        return standard_response("error", errors=["Token not found in environment."])

    try:
        logout_resp = logout_user(token)
        if not logout_resp.get("success"):
            logger.error("Logout failed via API", extra=logout_resp)
            return standard_response("error", errors=["Logout failed."])

        verified_resp = verify_token(token)
        is_verified = verified_resp.get("data", False)

        if not is_verified:
            # Logout successful → clear TOKEN
            set_env_var("TOKEN", "")
            set_env_var("EXPIRES_IN", "")
            logger.info("User logged out successfully, token cleared from .env")
            return standard_response("success", data={"logged_out": True})

        logger.warning("Logout attempt failed, token still valid on server")
        return standard_response(
            "error", errors=["Logout incomplete. Token still valid."]
        )

    except Exception as exc:
        logger.exception("Unexpected error during logout", extra={"error": str(exc)})
        return standard_response("error", errors=["Failed to log out user."])


def helper_get_countries():
    logger.info("Fetching country list")

    try:
        cache_name = "countries_list"
        cache_path = DATA_DIR / f"{cache_name}.json"

        # Try loading from cache
        cached_data = load_cache(cache_name)
        if cached_data:
            cache_age_minutes = None
            human_age = None

            # Determine cache age if metadata exists
            if cache_path.exists():
                try:
                    raw = json.loads(cache_path.read_text())

                    # Support both legacy (root) and new (_metadata) formats
                    ts_str = raw.get("timestamp") or raw.get("_metadata", {}).get(
                        "timestamp"
                    )

                    if ts_str:
                        ts = datetime.fromisoformat(ts_str)
                        delta = datetime.now(timezone.utc) - ts
                        cache_age_minutes = int(delta.total_seconds() / 60)
                        hours = cache_age_minutes // 60
                        minutes = cache_age_minutes % 60
                        human_age = (
                            f"{hours}h {minutes}m ago"
                            if hours
                            else f"{minutes} minutes ago"
                        )
                except Exception:
                    logger.debug("Failed to compute cache age metadata")

            logger.info(
                f"Country list loaded from cache ({human_age or 'unknown age'})",
                extra={
                    "count": len(cached_data),
                    "source": "cache",
                    "cache_age_minutes": cache_age_minutes,
                },
            )

            return standard_response(
                "success",
                data={
                    "countries": cached_data,
                    "cache_age_minutes": cache_age_minutes,
                    "cache_age_human": human_age,
                },
            )

        # No cache → fetch from API
        countries_resp = get_countries()
        if not countries_resp.get("success"):
            logger.error("Failed to fetch countries from API", extra=countries_resp)
            return standard_response("error", errors=["Unable to fetch country list."])

        data = countries_resp.get("data", [])
        if not data:
            logger.warning("Empty country list received from API")
            return standard_response("error", errors=["No countries found."])

        # Cache for 2 days (2880 minutes)
        ttl_minutes = 2880
        ttl_hours = ttl_minutes // 60
        ttl_days = ttl_hours // 24
        save_cache(cache_name, data, ttl_minutes=ttl_minutes)

        ttl_human = f"{ttl_days} days" if ttl_days else f"{ttl_hours} hours"
        logger.info(
            f"Country list fetched and cached successfully (TTL: {ttl_human})",
            extra={
                "count": len(data),
                "ttl_minutes": ttl_minutes,
                "ttl_hours": ttl_hours,
                "ttl_days": ttl_days,
            },
        )

        return standard_response(
            "success",
            data={
                "countries": data,
                "cache_ttl_minutes": ttl_minutes,
                "cache_ttl_human": ttl_human,
            },
        )

    except Exception as exc:
        logger.exception("Error fetching country list", extra={"error": str(exc)})
        return standard_response("error", errors=["Failed to fetch country list."])
