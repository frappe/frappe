"""Provider registry + the `get_model` factory.

`get_model` dispatches on the model name's prefix: a registered native provider (the
mock, or a Phase 3 OAuth provider) wins; everything else falls through to
`LiteLLMModel`, the broad API-key path. Native providers call `register_provider` at
import time to claim a prefix.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flow_server.model.mock import MockModel
from flow_server.model.model import LiteLLMModel, Model

ModelFactory = Callable[..., Model]

_REGISTRY: dict[str, ModelFactory] = {}


def register_provider(prefix: str, factory: ModelFactory) -> None:
	_REGISTRY[prefix] = factory


def get_model(
	name: str,
	*,
	api_key: str | None = None,
	api_base: str | None = None,
	params: dict[str, Any] | None = None,
) -> Model:
	factory = _REGISTRY.get(name.split("/", 1)[0])
	if factory is not None:
		return factory(name, api_key=api_key, api_base=api_base, params=params)
	return LiteLLMModel(name, api_key=api_key, api_base=api_base, params=params)


register_provider("mock", lambda name, **kwargs: MockModel())

__all__ = ["Model", "LiteLLMModel", "MockModel", "get_model", "register_provider"]
