import json
import time

import httpx

from flow_harness.model.errors import (
	normalize_litellm_error,
	normalize_provider_error,
	provider_error_from_http,
)


def test_http_error_classification():
	overflow = {
		"error": {
			"code": "context_length_exceeded",
			"message": "Your input exceeds the context window of this model.",
		}
	}
	cases = [
		(429, {"error": {"message": "slow down"}}, "rate_limit", True),
		(503, {"error": {"message": "overloaded"}}, "overloaded", True),
		(400, {"error": {"message": "bad parameter"}}, "invalid_request", False),
		(400, overflow, "context_overflow", False),
		(401, {"error": {"message": "invalid API key"}}, "auth", False),
		(401, {"error": {"message": "access token expired"}}, "auth", True),
		# transient by LLM-API convention rather than HTTP semantics
		(409, "", "overloaded", True),
		(425, "", "overloaded", True),
	]
	for status, body, kind, retryable in cases:
		error = provider_error_from_http(status_code=status, provider="test", body=body)
		assert (error.kind, error.retryable, error.status_code) == (kind, retryable, status), body
	error = provider_error_from_http(status_code=400, provider="openai", body=overflow)
	assert "context_length_exceeded" in error.detail

	# quota and subscription usage limits are not transient rate limits
	for body in (
		{"error": {"code": "insufficient_quota", "message": "billing quota exceeded"}},
		{"detail": "You've hit your usage limit. Try again after your quota resets."},
		{"error": {"type": "GoUsageLimitError", "message": "Monthly usage limit reached"}},
		{"error": {"message": "Enable available balance usage to continue."}},
	):
		error = provider_error_from_http(status_code=429, provider="opencode-go", body=body)
		assert (error.kind, error.retryable) == ("rate_limit", False), body

	seconds = provider_error_from_http(
		status_code=429, provider="test", headers=httpx.Headers({"Retry-After": "2.5"})
	)
	milliseconds = provider_error_from_http(
		status_code=503, provider="test", headers=httpx.Headers({"retry-after-ms": "750"})
	)
	assert (seconds.retry_after_seconds, milliseconds.retry_after_seconds) == (2.5, 0.75)


def test_raised_failures_are_typed():
	request = httpx.Request("POST", "https://provider.test")
	cases = [
		(httpx.ReadTimeout("slow", request=request), "timeout"),
		(httpx.ConnectError("refused", request=request), "transport"),
		(httpx.RemoteProtocolError("disconnected", request=request), "transport"),
		(httpx.DecodingError("bad gzip", request=request), "transport"),
		# Codex reports transient failures as snake_case codes on a 200 SSE frame, so
		# there is no status to fall back on and the marker must match either spelling
		*[
			(RuntimeError(f"error: {code}: upstream"), "overloaded")
			for code in ("service_unavailable", "temporarily_unavailable", "internal_error", "server_error")
		],
		(RuntimeError("503 Service Unavailable"), "overloaded"),
	]
	for raised, kind in cases:
		error = normalize_provider_error(raised, provider="codex")
		assert (error.kind, error.retryable) == (kind, True), raised


def test_litellm_exception_types_are_the_primary_classification_boundary():
	from litellm import exceptions as litellm_exceptions

	request = httpx.Request("POST", "https://provider.test")
	source = {"model": "test", "llm_provider": "anthropic"}
	cases = [
		(
			litellm_exceptions.ContextWindowExceededError(
				message="Context Window exceeded for given call", **source
			),
			"context_overflow",
			False,
			None,
		),
		(litellm_exceptions.Timeout(message="request stalled", **source), "timeout", True, None),
		(
			litellm_exceptions.APIConnectionError(message="connection closed", **source),
			"transport",
			True,
			None,
		),
		(
			litellm_exceptions.PermissionDeniedError(
				message="not permitted", response=httpx.Response(403, request=request), **source
			),
			"auth",
			False,
			None,
		),
		(
			litellm_exceptions.ServiceUnavailableError(message="provider busy", **source),
			"overloaded",
			True,
			None,
		),
		(
			litellm_exceptions.BadRequestError(message="invalid tool schema", **source),
			"invalid_request",
			False,
			None,
		),
		(
			litellm_exceptions.APIResponseValidationError(message="invalid provider response", **source),
			"unknown",
			False,
			None,
		),
		# structured rate-limit fields override message guessing
		(
			litellm_exceptions.RateLimitError(
				message="request capacity exhausted",
				response=httpx.Response(429, headers={"retry-after": "4"}, request=request),
				rate_limit_type="requests",
				**source,
			),
			"rate_limit",
			True,
			4,
		),
		(
			litellm_exceptions.RateLimitError(
				message="request capacity exhausted", rate_limit_type="budget", **source
			),
			"rate_limit",
			False,
			None,
		),
		(
			litellm_exceptions.BudgetExceededError(current_cost=11, max_budget=10, llm_provider="anthropic"),
			"rate_limit",
			False,
			None,
		),
	]

	for native, kind, retryable, retry_after in cases:
		error = normalize_litellm_error(native, provider="anthropic")
		assert (error.kind, error.retryable) == (kind, retryable), native
		assert error.retry_after_seconds == retry_after, native


def test_openrouter_rate_limit_waits_until_its_reset(monkeypatch):
	"""OpenRouter gives its reset time only in the error body, in epoch milliseconds."""
	from litellm import exceptions as litellm_exceptions

	body = {
		"error": {
			"message": "Rate limit exceeded: new-account-rpm/openai/gpt-6-luna-pro-20260922.",
			"code": 429,
			"metadata": {
				"headers": {
					"X-RateLimit-Limit": "20",
					"X-RateLimit-Remaining": "0",
					"X-RateLimit-Reset": "1790586900000",
				}
			},
		}
	}
	native = litellm_exceptions.RateLimitError(
		message=f"OpenrouterException - {json.dumps(body, separators=(',', ':'))}",
		model="openai/gpt-6-luna-pro",
		llm_provider="openrouter",
	)
	cases = [
		(4.5, 5.5),  # a second more, should our clock run ahead
		(59.5, 60.0),  # but no more than the retry waits
		(3600.0, 3600.0),  # too long to retry anyway
	]
	for to_reset, wait in cases:
		monkeypatch.setattr(time, "time", lambda: 1790586900 - to_reset)

		error = normalize_litellm_error(native, provider="openrouter")

		assert (error.kind, error.retryable) == ("rate_limit", True)
		assert error.retry_after_seconds == wait
