import frappe

from studio.utils import has_page_write_perm


class ModelRegistry:
	AVAILABLE = [
		{
			"id": "openrouter/anthropic/claude-sonnet-4-6",
			"label": "Claude Sonnet 4.6",
			"vision_capable": True,
		},
		{"id": "openrouter/anthropic/claude-opus-4.6", "label": "Claude Opus 4.6", "vision_capable": True},
		{"id": "openrouter/anthropic/claude-haiku-4-6", "label": "Claude Haiku 4.6", "vision_capable": True},
		{"id": "openrouter/google/gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro", "vision_capable": True},
		{"id": "openrouter/google/gemini-3-flash-preview", "label": "Gemini 3 Flash", "vision_capable": True},
		{"id": "openrouter/openai/gpt-5-mini", "label": "GPT-5 Mini", "vision_capable": True},
		{"id": "openrouter/qwen/qwen3.7-max", "label": "Qwen 3.7 Max", "vision_capable": False},
		{"id": "openrouter/moonshotai/kimi-k2.6", "label": "Kimi K2.6", "vision_capable": True},
	]

	DEFAULT = "openrouter/anthropic/claude-sonnet-4-6"
	SIMPLE = "openrouter/google/gemini-3-flash-preview"

	@classmethod
	def get_default(cls) -> str:
		return cls.DEFAULT

	@classmethod
	def get_simple(cls) -> str:
		return cls.SIMPLE

	@classmethod
	def get_label(cls, model_id: str) -> str:
		for m in cls.AVAILABLE:
			if m["id"] == model_id:
				return m["label"]
		return model_id

	@classmethod
	def list_all(cls) -> list:
		return cls.AVAILABLE


@frappe.whitelist()
@has_page_write_perm()
def get_ai_models() -> list:
	return ModelRegistry.list_all()
