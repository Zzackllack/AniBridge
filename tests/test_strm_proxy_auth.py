import importlib
import sys

import pytest
from fastapi import HTTPException


def _load_auth(monkeypatch, *, mode: str, secret: str):
    """
    Prepare and load the stream proxy authentication module for tests using the given mode and secret.
    
    This sets the STRM_PROXY_AUTH and STRM_PROXY_SECRET environment variables, clears any cached imports for app.config and app.core.strm_proxy.auth, and then imports and returns the fresh app.core.strm_proxy.auth module.
    
    Parameters:
        mode (str): Authentication mode to set (e.g., "token" or "apikey").
        secret (str): Secret value corresponding to the chosen authentication mode.
    
    Returns:
        module: The imported app.core.strm_proxy.auth module.
    """
    monkeypatch.setenv("STRM_PROXY_AUTH", mode)
    monkeypatch.setenv("STRM_PROXY_SECRET", secret)
    for mod in ("app.config", "app.core.strm_proxy.auth"):
        if mod in sys.modules:
            del sys.modules[mod]
    auth = importlib.import_module("app.core.strm_proxy.auth")
    return auth


def test_token_auth_valid(monkeypatch):
    """
    Verify that token-based authentication accepts a correctly signed parameter set.
    
    Loads the auth module configured for token mode with secret "secret", builds a sample params dict, signs it using the secret, and calls require_auth with the signed parameters to ensure authentication succeeds (no exception raised).
    """
    auth = _load_auth(monkeypatch, mode="token", secret="secret")
    params = {"site": "aniworld.to", "slug": "show", "s": "1", "e": "2", "lang": "de"}
    sig = auth.sign_params(params, "secret")
    params_with_sig = dict(params)
    params_with_sig["sig"] = sig
    auth.require_auth(params_with_sig)


def test_token_auth_invalid(monkeypatch):
    auth = _load_auth(monkeypatch, mode="token", secret="secret")
    params = {"site": "aniworld.to", "slug": "show", "s": "1", "e": "2", "lang": "de"}
    params["sig"] = "bad"
    with pytest.raises(HTTPException):
        auth.require_auth(params)


def test_apikey_auth_valid(monkeypatch):
    auth = _load_auth(monkeypatch, mode="apikey", secret="key123")
    auth.require_auth({"apikey": "key123"})


def test_apikey_auth_invalid(monkeypatch):
    """
    Verifies that require_auth raises HTTPException when an invalid API key is provided.
    
    This test loads the authentication module configured for API key mode with secret "key123"
    and asserts that calling require_auth with a non-matching apikey ("nope") results in an HTTPException.
    """
    auth = _load_auth(monkeypatch, mode="apikey", secret="key123")
    with pytest.raises(HTTPException):
        auth.require_auth({"apikey": "nope"})