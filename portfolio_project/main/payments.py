import base64

import requests
from django.conf import settings
from django.urls import reverse
from django.utils import timezone


class MpesaConfigurationError(Exception):
    pass


class MpesaRequestError(Exception):
    pass


def _response_json(response, fallback_message):
    try:
        return response.json()
    except ValueError:
        raise MpesaRequestError(fallback_message)


def _mpesa_get(*args, **kwargs):
    try:
        return requests.get(*args, **kwargs)
    except requests.RequestException as error:
        raise MpesaRequestError(f"M-Pesa network request failed: {error}") from error


def _mpesa_post(*args, **kwargs):
    try:
        return requests.post(*args, **kwargs)
    except requests.RequestException as error:
        raise MpesaRequestError(f"M-Pesa network request failed: {error}") from error


def normalize_phone(phone):
    digits = "".join(char for char in phone if char.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif digits.startswith("7") and len(digits) == 9:
        digits = "254" + digits
    elif digits.startswith("1") and len(digits) == 9:
        digits = "254" + digits
    if not (digits.startswith("254") and len(digits) == 12):
        raise ValueError("Enter a valid Kenyan phone number, for example 254704141329.")
    return digits


def _required_setting(name):
    value = getattr(settings, name, "")
    if isinstance(value, str):
        value = value.strip()
    if not value:
        raise MpesaConfigurationError(f"{name} is not configured.")
    return value


def _base_url():
    environment = getattr(settings, "MPESA_ENVIRONMENT", "sandbox").lower()
    if environment == "production":
        return "https://api.safaricom.co.ke"
    return "https://sandbox.safaricom.co.ke"


def _public_callback_url(request, url_name, setting_name):
    request_url = request.build_absolute_uri(reverse(url_name))
    host = request.get_host().lower()
    if not host.startswith("127.0.0.1") and not host.startswith("localhost"):
        return request_url
    configured_url = getattr(settings, setting_name, "").strip()
    return configured_url or request_url


def _access_token():
    consumer_key = _required_setting("MPESA_CONSUMER_KEY")
    consumer_secret = _required_setting("MPESA_CONSUMER_SECRET")
    response = _mpesa_get(
        f"{_base_url()}/oauth/v1/generate",
        params={"grant_type": "client_credentials"},
        auth=(consumer_key, consumer_secret),
        timeout=20,
    )
    if response.status_code != 200:
        raise MpesaRequestError("M-Pesa authentication failed.")
    data = _response_json(response, "M-Pesa authentication returned an invalid response.")
    token = data.get("access_token")
    if not token:
        raise MpesaRequestError("M-Pesa authentication response did not include an access token.")
    return token


def stk_push(request, payment):
    shortcode = _required_setting("MPESA_SHORTCODE")
    passkey = _required_setting("MPESA_PASSKEY")
    transaction_type = getattr(settings, "MPESA_TRANSACTION_TYPE", "CustomerPayBillOnline").strip()
    partyb_shortcode = _required_setting("MPESA_PARTYB_SHORTCODE")
    callback_url = _public_callback_url(request, "mpesa_callback", "MPESA_CALLBACK_URL")

    timestamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()
    token = _access_token()
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": transaction_type,
        "Amount": payment.amount,
        "PartyA": payment.mpesa_phone or payment.phone,
        "PartyB": partyb_shortcode,
        "PhoneNumber": payment.mpesa_phone or payment.phone,
        "CallBackURL": callback_url,
        "AccountReference": payment.account_reference,
        "TransactionDesc": payment.course_name[:100],
    }
    response = _mpesa_post(
        f"{_base_url()}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    data = _response_json(response, "M-Pesa request returned an invalid response.")
    if response.status_code != 200 or data.get("ResponseCode") != "0":
        raise MpesaRequestError(data.get("errorMessage") or data.get("ResponseDescription") or "M-Pesa request failed.")
    return data


def stk_query(payment):
    shortcode = _required_setting("MPESA_SHORTCODE")
    passkey = _required_setting("MPESA_PASSKEY")
    checkout_request_id = payment.checkout_request_id
    if not checkout_request_id:
        raise MpesaRequestError("This payment has no checkout request ID to confirm.")

    timestamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()
    response = _mpesa_post(
        f"{_base_url()}/mpesa/stkpushquery/v1/query",
        json={
            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        },
        headers={"Authorization": f"Bearer {_access_token()}"},
        timeout=30,
    )
    data = _response_json(response, "M-Pesa confirmation returned an invalid response.")
    if response.status_code != 200 or data.get("ResponseCode") != "0":
        raise MpesaRequestError(
            data.get("errorMessage")
            or data.get("ResponseDescription")
            or data.get("ResultDesc")
            or "M-Pesa confirmation query failed."
        )
    return data


def c2b_register_urls(request):
    shortcode = _required_setting("MPESA_SHORTCODE")
    validation_url = _public_callback_url(request, "mpesa_c2b_validation", "MPESA_C2B_VALIDATION_URL")
    confirmation_url = _public_callback_url(request, "mpesa_c2b_confirmation", "MPESA_C2B_CONFIRMATION_URL")

    response = _mpesa_post(
        f"{_base_url()}/mpesa/c2b/v1/registerurl",
        json={
            "ShortCode": shortcode,
            "ResponseType": "Completed",
            "ConfirmationURL": confirmation_url,
            "ValidationURL": validation_url,
        },
        headers={"Authorization": f"Bearer {_access_token()}"},
        timeout=30,
    )
    data = _response_json(response, "C2B URL registration returned an invalid response.")
    if response.status_code != 200:
        raise MpesaRequestError(data.get("errorMessage") or "C2B URL registration failed.")
    return data


def transaction_status_query(request, payment):
    initiator = _required_setting("MPESA_INITIATOR_NAME")
    security_credential = _required_setting("MPESA_SECURITY_CREDENTIAL")
    shortcode = _required_setting("MPESA_SHORTCODE")
    result_url = _public_callback_url(request, "mpesa_transaction_status_result", "MPESA_RESULT_URL")
    queue_timeout_url = _public_callback_url(request, "mpesa_transaction_status_timeout", "MPESA_QUEUE_TIMEOUT_URL")

    transaction_id = payment.mpesa_receipt_number or payment.checkout_request_id
    if not transaction_id:
        raise MpesaRequestError("This payment has no M-Pesa receipt or checkout request ID to verify.")

    response = _mpesa_post(
        f"{_base_url()}/mpesa/transactionstatus/v1/query",
        json={
            "Initiator": initiator,
            "SecurityCredential": security_credential,
            "CommandID": "TransactionStatusQuery",
            "TransactionID": transaction_id,
            "PartyA": shortcode,
            "IdentifierType": getattr(settings, "MPESA_IDENTIFIER_TYPE", "4"),
            "ResultURL": result_url,
            "QueueTimeOutURL": queue_timeout_url,
            "Remarks": f"Verify {payment.account_reference}",
            "Occasion": payment.account_reference,
        },
        headers={"Authorization": f"Bearer {_access_token()}"},
        timeout=30,
    )
    data = _response_json(response, "Transaction status returned an invalid response.")
    if response.status_code != 200:
        raise MpesaRequestError(data.get("errorMessage") or "Transaction status request failed.")
    return data


def extract_callback_metadata(callback):
    metadata = {}
    items = callback.get("CallbackMetadata", {}).get("Item", [])
    for item in items:
        if "Name" in item and "Value" in item:
            metadata[item["Name"]] = item["Value"]
    return metadata
