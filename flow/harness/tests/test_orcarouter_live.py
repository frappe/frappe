"""A real request through the OrcaRouter provider.

Needs a real key, so it skips unless ``ORCAROUTER_API_KEY`` is set. The key never
leaves the process: it is written to a temporary credential store and only the
model's answer is asserted on.
"""

import os

import pytest

from flow_harness.events import TextDelta, UserMessage
from flow_harness.model import get_model
from flow_harness.model.auth import resolve_model_auth
from flow_harness.model.base import ModelRequest
from flow_harness.model.credentials import CredentialStore
from flow_harness.model.discovery import available_models

pytestmark = pytest.mark.skipif(
	not os.environ.get("ORCAROUTER_API_KEY"),
	reason="needs a real OrcaRouter key in ORCAROUTER_API_KEY",
)


async def test_a_real_answer_comes_back_through_the_adapter(tmp_path):
	store = CredentialStore(str(tmp_path / "credentials.json"))
	store.set_api_key("orcarouter", os.environ["ORCAROUTER_API_KEY"])

	catalog = await available_models(store)
	assert catalog.models, catalog.errors
	assert not catalog.errors

	text_models = [info.name for info in catalog.models if info.supports_images is not True]
	name = next((candidate for candidate in text_models if "flash" in candidate), text_models[0])
	auth = await resolve_model_auth(name, store)
	assert auth.source == "stored API key"

	model = get_model(name, api_key=auth.api_key, api_base=auth.base_url, headers=auth.headers)
	assert model.provider == "orcarouter"

	request = ModelRequest(
		messages=[UserMessage(content="Reply with exactly the word OK and nothing else.")],
		system_prompt="You are a terse assistant.",
		stream=True,
		max_output_tokens=32,
	)
	text = [event.text async for event in model.run(request) if isinstance(event, TextDelta)]
	assert "".join(text).strip()
