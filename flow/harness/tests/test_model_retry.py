"""The retry envelope: provider failures are retried inside the model stream, with
`Retry` progress events, bounded attempts, and one-shot auth refresh."""

import asyncio

import httpx
import pytest

from flow_harness.events import AssistantMessage, TextDelta, Usage
from flow_harness.model.cancellation import ModelCancelled
from flow_harness.model.errors import ProviderError
from flow_harness.model.retry import run_with_retries


def provider_error(kind="overloaded", *, retryable=True, detail="provider busy", retry_after=None):
	return ProviderError(
		kind=kind,
		retryable=retryable,
		status_code=503,
		provider="test",
		detail=detail,
		retry_after_seconds=retry_after,
	)


class Flaky:
	"""Attempt factory that fails with the scripted errors, then succeeds."""

	def __init__(self, failures, *, deltas=False):
		self.failures = list(failures)
		self.deltas = deltas
		self.attempts = 0

	def __call__(self):
		return self._attempt()

	async def _attempt(self):
		self.attempts += 1
		if self.deltas:
			yield TextDelta(text=f"partial-{self.attempts}")
		if self.failures:
			raise self.failures.pop(0)
		yield AssistantMessage(content="done")
		yield Usage(output_tokens=1)


async def _collect(gen):
	return [ev async for ev in gen]


def _no_delay(monkeypatch):
	monkeypatch.setattr("flow_harness.model.retry._retry_delay_seconds", lambda error, retry_index: 0)


async def test_transient_failure_retries_before_the_terminal_commits(monkeypatch):
	"""A failed attempt's live deltas are already out; `started` marks where a client
	drops them and the fresh attempt re-streams."""
	_no_delay(monkeypatch)
	flaky = Flaky([provider_error()], deltas=True)

	events = await _collect(run_with_retries(flaky))

	assert flaky.attempts == 2
	assert [e.type for e in events] == [
		"text_delta",
		"retry",
		"retry",
		"text_delta",
		"assistant_message",
		"usage",
	]
	retries = [e for e in events if e.type == "retry"]
	assert [(r.status, r.attempt) for r in retries] == [("scheduled", 2), ("started", 2)]
	assert retries[0].max_attempts == 3
	assert [e.text for e in events if e.type == "assistant_message"] == ["done"]


async def test_exhaustion_has_one_typed_lifecycle(monkeypatch):
	_no_delay(monkeypatch)

	async def refresh_auth():
		return None

	cases = [
		# the transient budget runs out
		(
			[provider_error(), provider_error(), provider_error()],
			None,
			[("scheduled", 2), ("started", 2), ("scheduled", 3), ("started", 3), ("exhausted", 3)],
			"overloaded",
		),
		# auth fails again once its one refresh is used
		(
			[
				provider_error("auth", detail="access token expired"),
				provider_error("auth", detail="access token expired"),
			],
			refresh_auth,
			[("scheduled", 2), ("started", 2), ("exhausted", 2)],
			"auth",
		),
	]
	for failures, refresh, statuses, kind in cases:
		flaky = Flaky(failures)

		events = []
		with pytest.raises(ProviderError) as raised:
			async for event in run_with_retries(flaky, refresh_auth=refresh):
				events.append(event)

		assert flaky.attempts == len(failures), kind
		assert [(e.status, e.attempt) for e in events if e.type == "retry"] == statuses, kind
		assert raised.value.kind == kind
		assert not any(e.type == "assistant_message" for e in events), kind


async def test_failures_that_cannot_retry_raise_immediately():
	cases = [
		provider_error("invalid_request", retryable=False),
		# a provider hint this long is not slept out
		provider_error("rate_limit", detail="daily limit reached", retry_after=3600),
		# auth with no refresh hook to recover it
		provider_error("auth", detail="access token expired"),
	]
	for error in cases:
		flaky = Flaky([error])

		events = []
		with pytest.raises(ProviderError) as raised:
			async for event in run_with_retries(flaky):
				events.append(event)

		assert flaky.attempts == 1, error.kind
		assert events == [], error.kind
		assert raised.value is error


async def test_abandoning_the_turn_closes_the_active_attempt():
	"""An abort or a dropped client must release the provider connection now, not
	whenever the event loop happens to shut down."""
	finalized = []

	async def attempt():
		try:
			yield TextDelta(text="streaming")
			yield AssistantMessage(content="done")
			yield Usage()
		finally:
			finalized.append(True)

	turn = run_with_retries(attempt)
	async for event in turn:
		if event.type == "text_delta":
			break
	await turn.aclose()

	assert finalized == [True]


async def test_no_retry_after_the_assistant_message_is_out():
	async def attempt():
		yield AssistantMessage(content="committed")
		raise provider_error()

	events = []
	with pytest.raises(ProviderError):
		async for event in run_with_retries(attempt):
			events.append(event)

	assert [e.type for e in events] == ["assistant_message"]


async def test_cancellation_interrupts_retry_backoff(monkeypatch):
	monkeypatch.setattr("flow_harness.model.retry._retry_delay_seconds", lambda error, retry_index: 60)
	cancellation = asyncio.Event()
	flaky = Flaky([provider_error()])

	async def cancel_soon():
		await asyncio.sleep(0.01)
		cancellation.set()

	async def consume():
		events = []
		with pytest.raises(ModelCancelled):
			async for event in run_with_retries(flaky, cancellation=cancellation):
				events.append(event)
		return events

	events, _ = await asyncio.wait_for(asyncio.gather(consume(), cancel_soon()), timeout=1)

	assert flaky.attempts == 1
	assert [(e.status) for e in events if e.type == "retry"] == ["scheduled"]


async def test_expired_auth_refreshes_once_and_succeeds():
	token = "expired"
	refreshes = []

	async def refresh_auth():
		nonlocal token
		refreshes.append(token)
		token = "fresh"

	class AuthModel:
		attempts = 0

		def __call__(self):
			return self._attempt()

		async def _attempt(self):
			AuthModel.attempts += 1
			if token == "expired":
				raise provider_error("auth", detail="access token expired")
			yield AssistantMessage(content="authenticated")
			yield Usage()

	events = await _collect(run_with_retries(AuthModel(), refresh_auth=refresh_auth))

	assert refreshes == ["expired"]
	retries = [e for e in events if e.type == "retry"]
	assert [(r.status, r.attempt) for r in retries] == [("scheduled", 2), ("started", 2)]
	assert retries[0].max_attempts == 4  # the refresh slot extends the budget
	assert retries[0].delay_seconds == 0
	assert [e.text for e in events if e.type == "assistant_message"] == ["authenticated"]


async def test_refresh_failure_is_typed_and_exhausts(monkeypatch):
	"""The token endpoint is a second provider call; its transport faults must not
	escape untyped."""

	async def refresh_auth():
		raise httpx.ConnectError("token endpoint unreachable")

	flaky = Flaky([provider_error("auth", detail="access token expired")])

	events = []
	with pytest.raises(ProviderError) as raised:
		async for event in run_with_retries(flaky, refresh_auth=refresh_auth):
			events.append(event)

	assert flaky.attempts == 1
	statuses = [(e.status, e.kind) for e in events if e.type == "retry"]
	assert statuses == [("scheduled", "auth"), ("exhausted", "auth")]
	assert (raised.value.kind, raised.value.retryable) == ("auth", False)
	assert "token endpoint unreachable" in raised.value.detail
