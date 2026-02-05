from __future__ import annotations

import hmac
import hashlib
import time
from typing import Mapping
from urllib.parse import urlencode

from fastapi import HTTPException
from loguru import logger

from app.config import STRM_PROXY_AUTH, STRM_PROXY_SECRET, STRM_PROXY_TOKEN_TTL_SECONDS


def _canonical_params(params: Mapping[str, str]) -> str:
    """
    Create a deterministic query string from provided parameters for signing.

    Parameters:
        params (Mapping[str, str]): Mapping of parameter names to values. Keys are sorted alphabetically for determinism.

    Returns:
        canonical (str): A string of `key=value` pairs joined by `&`, with pairs ordered by key.
    """
    logger.trace("Canonicalizing auth params: {}", sorted(params.keys()))
    items = sorted(params.items())
    return urlencode(items, doseq=False)


def sign_params(params: Mapping[str, str], secret: str) -> str:
    """
    Generate an HMAC-SHA256 signature for the given parameters using the provided secret key.

    Parameters:
        params (Mapping[str, str]): Parameter mapping to sign; ordering is canonicalized before signing.
        secret (str): Secret key used as the HMAC signing key.

    Returns:
        sig (str): Hexadecimal HMAC-SHA256 digest of the canonicalized parameters.
    """
    logger.trace("Signing STRM proxy params")
    canonical = _canonical_params(params)
    digest = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def _require_secret() -> str:
    """
    Retrieve the configured STRM proxy secret.

    Returns:
        secret (str): The configured STRM proxy secret.

    Raises:
        HTTPException: If STRM_PROXY_SECRET is unset — results in HTTP 500 with detail "STRM proxy auth misconfigured".
    """
    if not STRM_PROXY_SECRET:
        logger.error("STRM proxy auth enabled but STRM_PROXY_SECRET is unset.")
        raise HTTPException(status_code=500, detail="STRM proxy auth misconfigured")
    return STRM_PROXY_SECRET


def build_auth_params(params: Mapping[str, str]) -> dict[str, str]:
    """
    Build authentication parameters for a STRM proxy URL based on the configured auth mode.

    Parameters:
        params (Mapping[str, str]): Query parameters that will be used when generating a token signature (when applicable).

    Returns:
        dict[str, str]: Authentication parameters to append to the proxy URL:
            - {} when mode is "none" or unknown,
            - {"apikey": secret} when mode is "apikey",
            - {"sig": signature} when mode is "token" (signature computed from `params`).

    Raises:
        HTTPException: If the configured secret is missing or unset (results in a 500 error).
    """
    logger.trace("Building auth params for STRM proxy")
    mode = STRM_PROXY_AUTH
    if mode == "none":
        return {}
    secret = _require_secret()
    if mode == "apikey":
        return {"apikey": secret}
    if mode == "token":
        payload = dict(params)
        exp = int(time.time()) + STRM_PROXY_TOKEN_TTL_SECONDS
        payload["exp"] = str(exp)
        sig = sign_params(payload, secret)
        return {"sig": sig, "exp": str(exp)}
    raise ValueError(f"Unknown STRM_PROXY_AUTH mode: {mode}")


def require_auth(params: Mapping[str, str]) -> None:
    """
    Validate request parameters against the configured STRM proxy authentication mode.

    Checks the global STRM_PROXY_AUTH mode:
    - If "none": no validation is performed.
    - If "apikey": requires params["apikey"] to equal the configured secret; otherwise raises HTTPException(401, "invalid apikey").
    - If "token": requires a "sig" parameter, validates optional "exp" as an integer timestamp not in the past, recomputes the expected signature from the remaining parameters and the configured secret, and raises HTTPException(401, ...) for missing/invalid/expired tokens or signature mismatches.

    Parameters:
        params (Mapping[str, str]): Request parameters to validate. Recognized keys:
            - "apikey" for apikey mode
            - "sig" for token mode
            - optional "exp" (integer UNIX timestamp) in token mode

    Raises:
        HTTPException: 401 for missing/invalid apikey, missing signature, invalid token expiry, expired token, or invalid signature.
        HTTPException: 500 if the STRM proxy secret is not configured.
    """
    logger.trace("Validating STRM proxy auth mode={}", STRM_PROXY_AUTH)
    mode = STRM_PROXY_AUTH
    if mode == "none":
        return
    secret = _require_secret()
    if mode == "apikey":
        if params.get("apikey") != secret:
            logger.warning("STRM proxy apikey missing or invalid.")
            raise HTTPException(status_code=401, detail="invalid apikey")
        return
    if mode == "token":
        sig = params.get("sig")
        if not sig:
            logger.warning("STRM proxy signature missing.")
            raise HTTPException(status_code=401, detail="missing signature")
        payload = {k: v for k, v in params.items() if k != "sig"}
        exp_raw = payload.get("exp")
        if exp_raw:
            try:
                exp = int(exp_raw)
            except ValueError as exc:
                raise HTTPException(
                    status_code=401, detail="invalid token expiry"
                ) from exc
            if int(time.time()) > exp:
                raise HTTPException(status_code=401, detail="token expired")
        expected = sign_params(payload, secret)
        if not hmac.compare_digest(sig, expected):
            logger.warning("STRM proxy signature mismatch.")
            raise HTTPException(status_code=401, detail="invalid signature")
        return
    raise ValueError(f"Unknown STRM proxy auth mode: {mode}")
