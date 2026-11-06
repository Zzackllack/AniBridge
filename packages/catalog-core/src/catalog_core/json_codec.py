"""Strict, bounded JSON used at catalog trust boundaries."""

import json


class ContractError(ValueError):
    """An input does not satisfy the versioned catalog contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def integer(value: object, minimum: int = 0, maximum: int = 2**63 - 1) -> int:
    require(type(value) is int and minimum <= value <= maximum, "invalid integer")
    return value


def fields(value: object, required: set[str], optional: set[str] = frozenset()) -> dict:
    require(type(value) is dict, "expected object")
    require(
        required <= value.keys() <= required | optional, "unexpected/missing fields"
    )
    return value


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _reject_number(_: str) -> None:
    raise ContractError("noninteger JSON number")


def loads(data: bytes, limit: int = 32768) -> object:
    require(len(data) <= limit, "JSON too large")
    try:
        result = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )

        def visit(value: object, depth: int) -> None:
            require(depth <= 8, "JSON too deep")
            if type(value) is int:
                integer(value, -(2**63))
            elif isinstance(value, dict):
                for key, child in value.items():
                    key.encode("utf-8")
                    visit(child, depth + 1)
            elif isinstance(value, list):
                for child in value:
                    visit(child, depth + 1)
            elif isinstance(value, str):
                value.encode("utf-8")

        visit(result, 0)
        return result
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ContractError("invalid JSON") from exc


def dumps(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
