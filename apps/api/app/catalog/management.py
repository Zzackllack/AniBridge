"""Authenticated local lifecycle endpoints, sharing the durable job service."""

import json
import sqlite3
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool

from .client import epoch
from .jobs import JobError
from .management_auth import ManagementAuth, ManagementError, version


class AuthorizedRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def guarded(request: Request):
            try:
                auth = getattr(request.app.state, "management_auth", None)
                if auth is None:
                    from app.config import ANIBRIDGE_CORS_ORIGINS, MANAGEMENT_API_TOKEN

                    auth = ManagementAuth(
                        MANAGEMENT_API_TOKEN, tuple(ANIBRIDGE_CORS_ORIGINS)
                    )
                    request.app.state.management_auth = auth
                request.state.management_body = await auth.check(request)
                return await handler(request)
            except ManagementError as exc:
                return exc.response()
            except JobError as exc:
                messages = {
                    "not_found": "Resource not found",
                    "version_conflict": "Resource changed",
                    "invalid_state": "Action is not available in this state",
                    "rate_limited": "Retry is temporarily limited",
                }
                return ManagementError(
                    exc.code,
                    exc.status,
                    messages.get(exc.code, "Request rejected"),
                    exc.status in (429, 503),
                ).response()
            except sqlite3.Error:
                return ManagementError(
                    "temporarily_unavailable", 503, "Local state is busy", True
                ).response()

        return guarded


router = APIRouter(prefix="/api/v1", route_class=AuthorizedRoute)


def service(request: Request):
    value = getattr(request.app.state, "catalog", None)
    if value is None:
        raise ManagementError(
            "catalog_unavailable", 503, "Query runtime is unavailable", True
        )
    return value


def job_resource(jobs, job_id: str) -> dict:
    row = jobs.get(job_id)
    payload = json.loads(row["payload"]) if row["payload"] else {}
    state, code = row["status"], row["error_code"]
    actions = []
    if state in ("blocked", "failed") and code != "legacy_request_incomplete":
        actions.append("retry")
    if state != "completed":
        actions.append("cancel")
    error = None
    if code:
        message = (
            "Legacy request is incomplete; automatic retry is unavailable"
            if code == "legacy_request_incomplete"
            else "Local job requires attention"
        )
        error = {"code": code, "message": message, "retryable": state == "retry_wait"}
    return {
        "id": job_id,
        "version": row["version"] or 1,
        "state": state,
        "release_id": payload.get("release_id"),
        "hashes": row["hashes"],
        "provider": row["source_site"],
        "mode": payload.get("mode"),
        "progress": jobs.project(row)["progress"],
        "attempt_count": row["attempts"] or 0,
        "created_at": epoch(row["created_at"]),
        "updated_at": epoch(row["updated_at"]),
        "last_attempt_at": row["last_attempt_at"],
        "next_retry_at": row["next_retry_at"],
        "error": error,
        "actions": actions,
    }


def response(resource: dict, status: int = 200):
    return JSONResponse(
        resource, status_code=status, headers={"ETag": f'"{resource["version"]}"'}
    )


@router.get("/jobs/{job_id}")
async def get_job(request: Request, job_id: str):
    return response(
        await run_in_threadpool(job_resource, service(request).jobs, job_id)
    )


@router.post("/jobs/{job_id}/retry")
@router.post("/jobs/{job_id}/cancel")
async def job_action(request: Request, job_id: str):
    expected = version(request)
    if request.state.management_body != {}:
        raise ManagementError(
            "invalid_request", 400, "Action requires an empty JSON object"
        )
    jobs = service(request).jobs
    action = request.url.path.rsplit("/", 1)[-1]
    resource = await run_in_threadpool(change_job, jobs, job_id, action, expected)
    return response(resource, 200 if resource["state"] == "cancelled" else 202)


def change_job(jobs, job_id: str, action: str, expected: int) -> dict:
    if action not in job_resource(jobs, job_id)["actions"]:
        raise ManagementError(
            "invalid_state", 409, "Action is not available in this state"
        )
    jobs.action(job_id, action, int(time.time()), expected)
    resource = job_resource(jobs, job_id)
    return resource
