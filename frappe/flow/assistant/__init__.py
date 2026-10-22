# Re-exported so the hooks stay reachable at flow.assistant.<name>.
from flow.assistant.assistant import (
	ASSISTANT_AGENT_TITLE,
	ASSISTANT_INSTRUCTIONS,
	ensure_builtin_assistant,
	sync_assistant_skills,
	sync_builtin_assistant,
)

__all__ = [
	"ASSISTANT_AGENT_TITLE",
	"ASSISTANT_INSTRUCTIONS",
	"ensure_builtin_assistant",
	"sync_assistant_skills",
	"sync_builtin_assistant",
]
