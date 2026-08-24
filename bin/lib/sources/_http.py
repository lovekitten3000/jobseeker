"""Shared HTTP helper for adapters: identifying UA, timeout, polite backoff.

Rate limiting (≤1 req/sec/host) is enforced by the caller (fetch.py), which
sequences adapters. This module just makes each individual request well-behaved.

Two behaviours matter for Workday, whose edge (Akamai) bot-manager answers a
flagged datacenter IP with 403 — not 429, not auth:

  * `session()` lets one board reuse a single httpx.Client — connection pool
    *and* cookie jar — across all its requests, so any edge-issued clearance
    cookie persists instead of being discarded on every call (fresh connection
    per request is exactly what reads as a bot). Adapters that hit one host
    repeatedly (Workday: list paging + per-posting detail) wrap their work in
    it; adapters that make a single call need not.
  * a 403 is retried on its own long, jittered schedule rather than the short
    transient (429/5xx) one — an Akamai block does not clear in 1–2s, and a
    tight uniform retry just looks more bot-like. See `_backoff`.
"""
from __future__ import annotations

import contextlib
import contextvars
import random
import time

import httpx

USER_AGENT = "jobseeker/1.0 (personal job search)"
TIMEOUT = 20.0
MAX_RETRIES = 3

# 403 (Akamai bot-block) backoff: base seconds per attempt, plus up to
# FORBIDDEN_JITTER seconds of jitter. Deliberately far longer than the 1s/2s
# transient schedule — a flagged IP needs time (and desynchronised retries) to
# clear, and hammering it every second just extends the block.
FORBIDDEN_BACKOFF = (8.0, 20.0)
FORBIDDEN_JITTER = 4.0

# The client in force for the current `session()`, if any. A ContextVar (not a
# module global) so nesting and any future concurrency stay correct.
_CLIENT: contextvars.ContextVar[httpx.Client | None] = contextvars.ContextVar(
    "_http_client", default=None
)


@contextlib.contextmanager
def session():
    """Reuse one httpx.Client (connection pool + cookie jar) for the duration.

    Requests issued by `get_json`/`post_json` inside the `with` block share the
    client, so edge clearance cookies carry across a board's paging and detail
    calls. Nesting reuses the outer session; the client is closed on exit.
    """
    existing = _CLIENT.get()
    if existing is not None:
        yield existing
        return
    client = httpx.Client(timeout=TIMEOUT)
    token = _CLIENT.set(client)
    try:
        yield client
    finally:
        _CLIENT.reset(token)
        client.close()


def _backoff(status: int | None, attempt: int) -> float:
    """Seconds to wait before retry `attempt` (0-indexed) for a given status.

    403 gets the long jittered FORBIDDEN schedule; everything else (transient
    429/5xx and transport errors, where status is None) gets the short 1s/2s.
    """
    if status == 403:
        base = FORBIDDEN_BACKOFF[min(attempt, len(FORBIDDEN_BACKOFF) - 1)]
        return base + random.uniform(0, FORBIDDEN_JITTER)
    return float(2 ** attempt)  # 1s, 2s


def _request_json(
    method: str,
    url: str,
    params: dict | None = None,
    json_body: dict | None = None,
    extra_headers: dict | None = None,
) -> dict | list:
    """Issue `method` on `url`, return parsed JSON. Retries transient errors.

    429/5xx (transient) and 403 (Akamai bot-block) are retried — the first two
    on the short schedule, 403 on the long jittered one. Other non-2xx raise via
    `raise_for_status()`. All are re-raised after MAX_RETRIES so the caller can
    catch per-adapter and one broken endpoint does not kill the sweep.

    `extra_headers` merges over the defaults — some ATS endpoints (PageUp) only
    return JSON when sent `X-Requested-With: XMLHttpRequest`.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    client = _CLIENT.get()
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            if client is not None:
                resp = client.request(
                    method, url, params=params, json=json_body, headers=headers
                )
            else:
                resp = httpx.request(
                    method, url, params=params, json=json_body,
                    headers=headers, timeout=TIMEOUT,
                )
            # Retryable: transient (429/5xx) and the Akamai bot-block (403).
            if resp.status_code in (429, 403) or resp.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"retryable status {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
            resp.raise_for_status()
            return resp.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            resp = getattr(exc, "response", None)
            status = getattr(resp, "status_code", None)
            # Fail fast on a genuine non-retryable HTTP status — a 404 (wrong
            # board slug), 401, or 400 will never succeed on retry, and three
            # backoff sleeps per bad target just slow the sweep and muddy the
            # "one dead adapter" signal. TransportError (status is None) and the
            # statuses we flagged retryable above (429/403/5xx) still retry.
            retryable = status is None or status in (429, 403) or status >= 500
            if not retryable:
                raise
            if attempt < MAX_RETRIES - 1:
                time.sleep(_backoff(status, attempt))
    assert last_exc is not None
    raise last_exc


def get_json(
    url: str, params: dict | None = None, headers: dict | None = None
) -> dict | list:
    """GET `url`, return parsed JSON. Retries on transient errors with backoff.

    `headers` merges over the defaults (e.g. an AJAX header a JSON endpoint
    requires).
    """
    return _request_json("GET", url, params=params, extra_headers=headers)


def post_json(url: str, json_body: dict) -> dict | list:
    """POST a JSON body to `url`, return parsed JSON. Retries with backoff.

    Workday's job-search API is POST-only; every other adapter uses GET.
    """
    return _request_json("POST", url, json_body=json_body)
