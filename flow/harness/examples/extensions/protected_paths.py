"""Block edits to sensitive files, whichever tool makes them.

Run with:

    flow -e examples/extensions/protected_paths.py
"""

from flow_harness.extensions import ExtensionAPI, PreToolUseDecision, PreToolUseEvent

PROTECTED = (".env", "credentials.json", "id_rsa")


def guard(event: PreToolUseEvent) -> PreToolUseDecision | None:
	if event.tool_name not in ("write", "edit"):
		return None
	path = str(event.arguments.get("path", ""))
	if any(path.endswith(name) for name in PROTECTED):
		return PreToolUseDecision(block=True, reason=f"{path} is protected; ask the user to edit it by hand")
	return None


def setup(flow: ExtensionAPI) -> None:
	flow.on("tool_call", guard)
