"""Where a model name becomes a `Model`.

`get_model` dispatches on the model name's prefix: a registered native provider (the
mock, Codex, or OpenCode Go provider) wins; everything else falls through to
`LiteLLMModel`, the broad API-key path. This module is the one place providers are
registered, so provider modules stay import-order free.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flow_harness.model.auth import RefreshAuth, register_auth_provider
from flow_harness.model.base import Model, ModelRequest
from flow_harness.model.cancellation import ModelCancelled
from flow_harness.model.errors import ProviderError
from flow_harness.model.litellm import LiteLLMModel
from flow_harness.model.mock import MockModel
from flow_harness.model.providers.codex import CodexAuthProvider, CodexModel
from flow_harness.model.providers.opencode import opencode_go_model
from flow_harness.model.retry import run_with_retries

BuildModel = Callable[..., Model]

# Keyed by the model-name prefix a provider claims (`codex` in `codex/gpt-5`).
_NATIVE_PROVIDERS: dict[str, BuildModel] = {}


def register_provider(model_prefix: str, build_model: BuildModel) -> None:
	_NATIVE_PROVIDERS[model_prefix] = build_model


def get_model(
	name: str,
	*,
	api_key: str | None = None,
	api_base: str | None = None,
	headers: dict[str, str] | None = None,
	params: dict[str, Any] | None = None,
	refresh_auth: RefreshAuth | None = None,
) -> Model:
	kwargs: dict[str, Any] = {"api_key": api_key, "api_base": api_base, "headers": headers, "params": params}
	if refresh_auth is not None:
		kwargs["refresh_auth"] = refresh_auth
	build_model = _NATIVE_PROVIDERS.get(name.split("/", 1)[0])
	if build_model is not None:
		return build_model(name, **kwargs)
	return LiteLLMModel(name, **kwargs)


register_provider("mock", lambda name, **kwargs: MockModel())
register_provider("codex", CodexModel)
register_provider("opencode-go", opencode_go_model)
register_auth_provider(CodexAuthProvider())

__all__ = [
	"BuildModel",
	"LiteLLMModel",
	"MockModel",
	"Model",
	"ModelCancelled",
	"ModelRequest",
	"ProviderError",
	"get_model",
	"register_provider",
	"run_with_retries",
]
