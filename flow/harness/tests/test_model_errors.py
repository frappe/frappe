import httpx

from flow_harness.model.errors import (
	normalize_litellm_error,
	normalize_provider_error,
	provider_error_from_http,
)


def test_http_error_classification():
	cases = [
		(429, {"error": {"message": "slow down"}}, "rate_limit", True),
		(503, {"error": {"message": "overloaded"}}, "overloaded", True),
		(400, {"error": {"message": "bad parameter"}}, "invalid_request", False),
		(401, {"error": {"message": "invalid API key"}}, "auth", False),
		(401, {"error": {"message": "access token expired"}}, "auth", True),
	]
	for status, body, kind, retryable in cases:
		error = provider_error_from_http(status_code=status, provider="test", body=body)
		assert error.kind == kind
		assert error.retryable is retryable
		assert error.status_code == status


def test_context_overflow_is_distinct_from_invalid_request():
	error = provider_error_from_http(
		status_code=400,
		provider="openai",
		body={
			"error": {
				"code": "context_length_exceeded",
				"message": "Your input exceeds the context window of this model.",
			}
		},
	)

	assert error.kind == "context_overflow"
	assert error.retryable is False
	assert "context_length_exceeded" in error.detail


def test_provider_codes_match_regardless_of_separator():
	"""Codex reports transient failures as snake_case codes on a 200 SSE frame, so
	there is no status to fall back on and the marker must match either spelling."""
	for code in ("service_unavailable", "temporarily_unavailable", "internal_error", "server_error"):
		error = normalize_provider_error(RuntimeError(f"error: {code}: upstream"), provider="codex")
		assert (error.kind, error.retryable) == ("overloaded", True), code

	spaced = normalize_provider_error(RuntimeError("503 Service Unavailable"), provider="codex")
	assert (spaced.kind, spaced.retryable) == ("overloaded", True)


def test_conflict_and_too_early_are_transient():
	"""409/425 are transient by LLM-API convention rather than HTTP semantics."""
	for status in (409, 425):
		error = provider_error_from_http(status_code=status, provider="codex")
		assert (error.kind, error.retryable) == ("overloaded", True), status


def test_subscription_usage_limits_are_not_transient_rate_limits():
	cases = [
		{"detail": "You've hit your usage limit. Try again after your quota resets."},
		{"error": {"type": "GoUsageLimitError", "message": "Monthly usage limit reached"}},
		{"error": {"message": "Enable available balance usage to continue."}},
	]
	for body in cases:
		error = provider_error_from_http(status_code=429, provider="opencode-go", body=body)
		assert (error.kind, error.retryable) == ("rate_limit", False), body


def test_body_decoding_failure_is_a_transport_fault():
	request = httpx.Request("POST", "https://provider.test")
	error = normalize_provider_error(httpx.DecodingError("bad gzip", request=request), provider="codex")

	assert (error.kind, error.retryable) == ("transport", True)


def test_quota_exhaustion_is_not_a_transient_rate_limit():
	error = provider_error_from_http(
		status_code=429,
		provider="openai",
		body={"error": {"code": "insufficient_quota", "message": "billing quota exceeded"}},
	)

	assert error.kind == "rate_limit"
	assert error.retryable is False


def test_retry_after_seconds_and_milliseconds_are_normalized():
	seconds = provider_error_from_http(
		status_code=429,
		provider="test",
		headers=httpx.Headers({"Retry-After": "2.5"}),
	)
	milliseconds = provider_error_from_http(
		status_code=503,
		provider="test",
		headers=httpx.Headers({"retry-after-ms": "750"}),
	)

	assert seconds.retry_after_seconds == 2.5
	assert milliseconds.retry_after_seconds == 0.75


def test_transport_and_timeout_exceptions_are_typed():
	request = httpx.Request("POST", "https://provider.test")
	timeout = normalize_provider_error(httpx.ReadTimeout("slow", request=request), provider="test")
	transport = normalize_provider_error(httpx.ConnectError("refused", request=request), provider="test")
	protocol = normalize_provider_error(
		httpx.RemoteProtocolError("disconnected", request=request),
		provider="test",
	)

	assert (timeout.kind, timeout.retryable) == ("timeout", True)
	assert (transport.kind, transport.retryable) == ("transport", True)
	assert (protocol.kind, protocol.retryable) == ("transport", True)


def test_litellm_exception_types_are_the_primary_classification_boundary():
	from litellm import exceptions as litellm_exceptions

	request = httpx.Request("POST", "https://provider.test")
	response_403 = httpx.Response(403, request=request)
	cases = [
		(
			litellm_exceptions.ContextWindowExceededError(
				message="Context Window exceeded for given call",
				model="test",
				llm_provider="anthropic",
			),
			"context_overflow",
			False,
		),
		(
			litellm_exceptions.Timeout(
				message="request stalled",
				model="test",
				llm_provider="anthropic",
			),
			"timeout",
			True,
		),
		(
			litellm_exceptions.APIConnectionError(
				message="connection closed",
				model="test",
				llm_provider="anthropic",
			),
			"transport",
			True,
		),
		(
			litellm_exceptions.PermissionDeniedError(
				message="not permitted",
				model="test",
				llm_provider="anthropic",
				response=response_403,
			),
			"auth",
			False,
		),
		(
			litellm_exceptions.ServiceUnavailableError(
				message="provider busy",
				model="test",
				llm_provider="anthropic",
			),
			"overloaded",
			True,
		),
		(
			litellm_exceptions.BadRequestError(
				message="invalid tool schema",
				model="test",
				llm_provider="anthropic",
			),
			"invalid_request",
			False,
		),
		(
			litellm_exceptions.APIResponseValidationError(
				message="invalid provider response",
				model="test",
				llm_provider="anthropic",
			),
			"unknown",
			False,
		),
	]

	for native, kind, retryable in cases:
		error = normalize_litellm_error(native, provider="anthropic")
		assert (error.kind, error.retryable) == (kind, retryable)


def test_litellm_structured_rate_limit_fields_override_message_guessing():
	from litellm import exceptions as litellm_exceptions

	request = httpx.Request("POST", "https://provider.test")
	response = httpx.Response(429, headers={"retry-after": "4"}, request=request)
	transient = normalize_litellm_error(
		litellm_exceptions.RateLimitError(
			message="request capacity exhausted",
			model="test",
			llm_provider="anthropic",
			response=response,
			rate_limit_type="requests",
		),
		provider="anthropic",
	)
	budget = normalize_litellm_error(
		litellm_exceptions.RateLimitError(
			message="request capacity exhausted",
			model="test",
			llm_provider="anthropic",
			rate_limit_type="budget",
		),
		provider="anthropic",
	)
	explicit_budget = normalize_litellm_error(
		litellm_exceptions.BudgetExceededError(
			current_cost=11,
			max_budget=10,
			llm_provider="anthropic",
		),
		provider="anthropic",
	)

	assert (transient.kind, transient.retryable, transient.retry_after_seconds) == (
		"rate_limit",
		True,
		4,
	)
	assert (budget.kind, budget.retryable) == ("rate_limit", False)
	assert (explicit_budget.kind, explicit_budget.retryable) == ("rate_limit", False)
