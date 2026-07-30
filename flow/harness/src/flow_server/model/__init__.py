"""Provider registry + the `get_model` factory.

`get_model` dispatches on the model name's prefix: a registered native provider wins;
everything else falls through to `LiteLLMModel`, the broad API-key path. Native
providers call `register_provider` at import time to claim a prefix.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flow_server.model.base import Model, ModelCancelled, ModelRequest, run_with_retries
from flow_server.model.errors import ProviderError
from flow_server.model.litellm import LiteLLMModel
from flow_server.model.mock import MockModel

ModelFactory = Callable[..., Model]

_REGISTRY: dict[str, ModelFactory] = {}


def register_provider(prefix: str, factory: ModelFactory) -> None:
	_REGISTRY[prefix] = factory


def get_model(
	name: str,
	*,
	api_key: str | None = None,
	api_base: str | None = None,
	headers: dict[str, str] | None = None,
	params: dict[str, Any] | None = None,
) -> Model:
	factory = _REGISTRY.get(name.split("/", 1)[0])
	if factory is not None:
		return factory(name, api_key=api_key, api_base=api_base, headers=headers, params=params)
	return LiteLLMModel(name, api_key=api_key, api_base=api_base, headers=headers, params=params)


register_provider("mock", lambda name, **kwargs: MockModel())

__all__ = [
	"LiteLLMModel",
	"MockModel",
	"Model",
	"ModelCancelled",
	"ModelFactory",
	"ModelRequest",
	"ProviderError",
	"get_model",
	"register_provider",
	"run_with_retries",
]
