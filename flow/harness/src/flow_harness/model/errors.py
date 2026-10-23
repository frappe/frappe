"""Translate provider failures into the small typed error model the rest of Flow uses."""

from __future__ import annotations

import json
import math
import re
import time
from collections.abc import Mapping
from typing import Any

import httpx

from flow_harness.events import ProviderErrorKind

_MAX_DETAIL_LENGTH = 1000
# Markers are matched against `_normalized` text, so a single spelling covers a
# provider's prose, its snake_case codes, and its kebab-case codes alike.
_CONTEXT_OVERFLOW_MARKERS = (
	"context length exceeded",
	"context window exceeded",
	"exceeds the context window",
	"maximum context length",
	"prompt is too long",
)
_NON_TRANSIENT_RATE_LIMIT_MARKERS = (
	"insufficient quota",
	"quota exceeded",
	"out of budget",
	"usage limit",
	"available balance",
	"gousagelimiterror",
	"freeusagelimiterror",
	"billing",
)
_EXPIRED_AUTH_MARKERS = (
	"token has expired",
	"token is expired",
	"token expired",
	"expired token",
)
_OVERLOADED_MARKERS = (
	"overloaded",
	"service unavailable",
	"temporarily unavailable",
	"internal error",
	"server error",
)
# OpenRouter's reset time, in epoch milliseconds, inside its error body
_RATE_LIMIT_RESET = re.compile(r'"x-ratelimit-reset"\s*:\s*"?(\d{13})\b', re.IGNORECASE)


class ProviderError(Exception):
	"""A normalized provider or transport failure."""

	def __init__(
		self,
		*,
		kind: ProviderErrorKind,
		retryable: bool,
		status_code: int | None,
		provider: str,
		detail: str,
		retry_after_seconds: float | None = None,
	):
		self.kind: ProviderErrorKind = kind
		self.retryable = retryable
		self.status_code = status_code
		self.provider = provider
		self.detail = _truncate(detail.strip() or "Unknown provider error")
		self.retry_after_seconds = retry_after_seconds
		status = f" (HTTP {status_code})" if status_code is not None else ""
		super().__init__(f"{provider} {kind.replace('_', ' ')} error{status}: {self.detail}")


def provider_error_from_http(
	*,
	status_code: int,
	provider: str,
	body: Any = "",
	headers: Mapping[str, str] | None = None,
) -> ProviderError:
	"""Classify a native provider HTTP response."""
	detail = provider_error_detail(body) or f"HTTP {status_code}"
	return _classify_untyped(
		provider=provider,
		detail=detail,
		status_code=status_code,
		headers=headers,
	)


def normalize_provider_error(error: Exception, *, provider: str) -> ProviderError:
	"""Normalize native-provider and raw httpx failures."""
	status_code, headers, detail = _exception_context(error)
	if isinstance(error, httpx.TimeoutException):
		return _provider_error(
			kind="timeout",
			retryable=True,
			status_code=status_code,
			provider=provider,
			detail=detail,
			headers=headers,
		)
	if isinstance(error, httpx.RequestError):
		# Every RequestError means the request failed without a usable response
		# (transport, protocol, or body decoding); HTTPStatusError is not one.
		return _provider_error(
			kind="transport",
			retryable=True,
			status_code=status_code,
			provider=provider,
			detail=detail,
			headers=headers,
		)
	return _classify_untyped(
		provider=provider,
		detail=detail,
		status_code=status_code,
		headers=headers,
	)


def normalize_litellm_error(error: Exception, *, provider: str) -> ProviderError:
	"""Map LiteLLM's public exception hierarchy into Flow's error model."""
	from litellm import exceptions as litellm_exceptions

	status_code, headers, detail = _exception_context(error)
	kind: ProviderErrorKind
	retryable: bool

	if isinstance(error, litellm_exceptions.ContextWindowExceededError):
		kind, retryable = "context_overflow", False
	elif isinstance(error, litellm_exceptions.BudgetExceededError):
		kind, retryable = "rate_limit", False
	elif isinstance(error, litellm_exceptions.RateLimitError):
		kind = "rate_limit"
		limit_type = getattr(error, "rate_limit_type", None)
		retryable = limit_type not in {"budget", "max_iterations"} and not _has_non_transient_rate_limit(
			detail
		)
	elif isinstance(error, litellm_exceptions.Timeout):
		kind, retryable = "timeout", True
	elif isinstance(error, litellm_exceptions.APIConnectionError):
		kind, retryable = "transport", True
	elif isinstance(
		error,
		(
			litellm_exceptions.AuthenticationError,
			litellm_exceptions.PermissionDeniedError,
		),
	):
		kind, retryable = "auth", _is_expired_auth(detail)
	elif isinstance(error, litellm_exceptions.APIResponseValidationError):
		kind, retryable = "unknown", False
	else:
		return normalize_provider_error(error, provider=provider)

	return _provider_error(
		kind=kind,
		retryable=retryable,
		status_code=status_code,
		provider=provider,
		detail=detail,
		headers=headers,
	)


def credential_refresh_error(error: Exception, *, provider: str) -> ProviderError:
	"""Classify a failed credential refresh.

	Refresh is a one-shot recovery, so any failure — a rejected refresh token, a
	transport fault, or an unusable resolved credential — ends the run the same way
	an unrecoverable authentication failure does.
	"""
	status_code, _, detail = _exception_context(error)
	return ProviderError(
		kind="auth",
		retryable=False,
		status_code=status_code,
		provider=provider,
		detail=detail,
	)


def provider_error_detail(value: Any) -> str:
	"""Extract type/code/message from common HTTP and SSE error shapes."""
	if value is None:
		return ""
	if isinstance(value, bytes):
		value = value.decode(errors="replace")
	if isinstance(value, str):
		text = value.strip()
		if not text:
			return ""
		try:
			value = json.loads(text)
		except (json.JSONDecodeError, TypeError):
			return _truncate(text)
	if not isinstance(value, Mapping):
		return str(value)

	parts: list[str] = []
	sources: list[Mapping[str, Any]] = [value]
	for key in ("error", "response"):
		nested = value.get(key)
		if isinstance(nested, Mapping):
			sources.append(nested)
			nested_error = nested.get("error")
			if isinstance(nested_error, Mapping):
				sources.append(nested_error)
	for source in sources:
		# `detail` is the FastAPI convention, used by gateways in front of a provider
		# and by flow's own HTTP boundary.
		for key in ("type", "code", "message", "detail"):
			item = source.get(key)
			if isinstance(item, str) and item.strip():
				parts.append(item.strip())
	return ": ".join(dict.fromkeys(parts))


def _classify_untyped(
	*,
	provider: str,
	detail: str,
	status_code: int | None,
	headers: Mapping[str, str] | None,
) -> ProviderError:
	normalized = _normalized(detail)
	if any(marker in normalized for marker in _CONTEXT_OVERFLOW_MARKERS):
		kind: ProviderErrorKind = "context_overflow"
		retryable = False
	elif status_code == 429 or "rate limit" in normalized:
		kind = "rate_limit"
		retryable = not _has_non_transient_rate_limit(detail)
	elif status_code == 408 or "timeout" in normalized or "timed out" in normalized:
		kind = "timeout"
		retryable = True
	elif status_code in {401, 403} or "unauthorized" in normalized or "authentication failed" in normalized:
		kind = "auth"
		retryable = _is_expired_auth(detail)
	# 409 and 425 are transient by LLM-API convention rather than HTTP semantics.
	# An in-stream SSE failure arrives on a 200, so there the markers are the only
	# signal available.
	elif (
		(status_code is not None and status_code >= 500)
		or status_code in {409, 425}
		or any(marker in normalized for marker in _OVERLOADED_MARKERS)
	):
		kind = "overloaded"
		retryable = True
	elif status_code in {400, 404, 405, 413, 422}:
		kind = "invalid_request"
		retryable = False
	else:
		kind = "unknown"
		retryable = False
	return _provider_error(
		kind=kind,
		retryable=retryable,
		status_code=status_code,
		provider=provider,
		detail=detail,
		headers=headers,
	)


def _provider_error(
	*,
	kind: ProviderErrorKind,
	retryable: bool,
	status_code: int | None,
	provider: str,
	detail: str,
	headers: Mapping[str, str] | None,
) -> ProviderError:
	retry_after_seconds = _retry_after_seconds(headers)
	if retry_after_seconds is None and kind == "rate_limit":
		retry_after_seconds = _rate_limit_reset_seconds(detail)
	return ProviderError(
		kind=kind,
		retryable=retryable,
		status_code=status_code,
		provider=provider,
		detail=detail,
		retry_after_seconds=retry_after_seconds,
	)


def _exception_context(
	error: Exception,
) -> tuple[int | None, Mapping[str, str] | None, str]:
	response = getattr(error, "response", None)
	status_code = _status_code(error, response)
	headers: dict[str, str] = {}
	for source in (getattr(response, "headers", None), getattr(error, "headers", None)):
		if isinstance(source, Mapping):
			headers.update((str(key), str(value)) for key, value in source.items())
	detail = (
		provider_error_detail(getattr(error, "body", None))
		or provider_error_detail(getattr(error, "detail", None))
		or str(error)
		or type(error).__name__
	)
	return status_code, headers or None, detail


def _status_code(error: Exception, response: Any) -> int | None:
	for value in (getattr(error, "status_code", None), getattr(response, "status_code", None)):
		if isinstance(value, int) and not isinstance(value, bool):
			return value
	return None


def _normalized(detail: str) -> str:
	"""Lowercase and flatten separators so one marker matches prose and error codes
	(`service unavailable`, `service_unavailable`, `service-unavailable`)."""
	return detail.lower().replace("_", " ").replace("-", " ")


def _has_non_transient_rate_limit(detail: str) -> bool:
	normalized = _normalized(detail)
	return any(marker in normalized for marker in _NON_TRANSIENT_RATE_LIMIT_MARKERS)


def _is_expired_auth(detail: str) -> bool:
	normalized = _normalized(detail)
	return any(marker in normalized for marker in _EXPIRED_AUTH_MARKERS)


def _retry_after_seconds(headers: Mapping[str, str] | None) -> float | None:
	if headers is None:
		return None
	normalized = {str(key).lower(): str(value) for key, value in headers.items()}
	raw = normalized.get("retry-after-ms")
	if raw is not None:
		try:
			delay = float(raw) / 1000
		except ValueError:
			return None
		return delay if math.isfinite(delay) and delay >= 0 else None
	raw = normalized.get("retry-after")
	if raw is None:
		return None
	try:
		delay = float(raw)
	except ValueError:
		return None
	return max(0.0, delay) if math.isfinite(delay) else None


def _rate_limit_reset_seconds(detail: str) -> float | None:
	"""Seconds until the reset time OpenRouter gives in its rate limit error."""
	match = _RATE_LIMIT_RESET.search(detail)
	if match is None:
		return None
	wait = max(0.0, int(match[1]) / 1000 - time.time())
	# a second late, should our clock run ahead
	return wait if wait > 60 else min(wait + 1.0, 60.0)  # retry.py waits 60 s at most


def _truncate(value: str) -> str:
	return value[:_MAX_DETAIL_LENGTH]
