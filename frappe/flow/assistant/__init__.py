# Re-exported so the after_migrate hook stays reachable at flow.assistant.<name>.
from flow.assistant.assistant import (
	ASSISTANT_AGENT_TITLE,
	ASSISTANT_INSTRUCTIONS,
	sync_builtin_assistant,
)

__all__ = ["ASSISTANT_AGENT_TITLE", "ASSISTANT_INSTRUCTIONS", "sync_builtin_assistant"]
