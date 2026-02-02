import base64
import json


def _normalize_claims(raw_claims):
    if not isinstance(raw_claims, list):
        return []
    normalized = []
    for claim in raw_claims:
        if not isinstance(claim, dict):
            continue
        claim_type = str(claim.get("typ") or claim.get("type") or "").strip()
        claim_value = str(claim.get("val") or claim.get("value") or "").strip()
        if claim_type and claim_value:
            normalized.append({"type": claim_type, "value": claim_value})
    return normalized


def _claim_matches(claim_type, candidate):
    claim_type = claim_type.lower()
    candidate = candidate.lower()
    return (
        claim_type == candidate
        or claim_type.endswith(f"/{candidate}")
        or claim_type.endswith(f":{candidate}")
    )


def _find_claim_value(claims, candidates):
    for candidate in candidates:
        for claim in claims:
            if _claim_matches(claim["type"], candidate):
                return claim["value"]
    return None


def _decode_client_principal(b64_value):
    if not b64_value:
        return None
    try:
        padded = f"{b64_value}{'=' * (-len(b64_value) % 4)}"
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8"))
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return None


def _extract_user_profile(raw_user_object):
    user_profile = {
        "first_name": "",
        "last_name": "",
        "email": ""
    }

    principal_payload = _decode_client_principal(raw_user_object.get("X-Ms-Client-Principal"))
    claims = _normalize_claims((principal_payload or {}).get("claims"))

    user_profile["first_name"] = _find_claim_value(claims, ["given_name", "givenname"]) or ""
    user_profile["last_name"] = _find_claim_value(
        claims,
        ["family_name", "familyname", "surname", "lastname", "last_name"]
    ) or ""

    email = _find_claim_value(
        claims,
        ["email", "emailaddress", "emails", "preferred_username", "upn"]
    )
    user_profile["email"] = email or raw_user_object.get("X-Ms-Client-Principal-Name", "") or ""

    return user_profile


def get_authenticated_user_details(request_headers):
    user_object = {}

    ## check the headers for the Principal-Id (the guid of the signed in user)
    if "X-Ms-Client-Principal-Id" not in request_headers.keys():
        ## if it's not, assume we're in development mode and return a default user
        from . import sample_user
        raw_user_object = sample_user.sample_user
    else:
        ## if it is, get the user details from the EasyAuth headers
        raw_user_object = {k:v for k,v in request_headers.items()}

    user_object["user_principal_id"] = raw_user_object.get("X-Ms-Client-Principal-Id")
    user_object["user_name"] = raw_user_object.get("X-Ms-Client-Principal-Name")
    user_object["auth_provider"] = raw_user_object.get("X-Ms-Client-Principal-Idp")
    user_object["auth_token"] = raw_user_object.get("X-Ms-Token-Aad-Id-Token")
    user_object["client_principal_b64"] = raw_user_object.get("X-Ms-Client-Principal")
    user_object["aad_id_token"] = raw_user_object.get("X-Ms-Token-Aad-Id-Token")

    user_profile = _extract_user_profile(raw_user_object)
    user_object["first_name"] = user_profile["first_name"]
    user_object["last_name"] = user_profile["last_name"]
    user_object["email"] = user_profile["email"]

    return user_object
