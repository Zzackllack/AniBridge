import importlib
import sys

import pytest
from fastapi import HTTPException


def _load_auth(monkeypatch, *, mode: str, secret: str):
    monkeypatch.setenv("STRM_PROXY_AUTH", mode)
    monkeypatch.setenv("STRM_PROXY_SECRET", secret)
    for mod in ("app.config", "app.core.strm_proxy.auth"):
        if mod in sys.modules:
            del sys.modules[mod]
    auth = importlib.import_module("app.core.strm_proxy.auth")
    return auth


def test_token_auth_valid(monkeypatch):
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
    auth = _load_auth(monkeypatch, mode="apikey", secret="key123")
    with pytest.raises(HTTPException):
        auth.require_auth({"apikey": "nope"})
