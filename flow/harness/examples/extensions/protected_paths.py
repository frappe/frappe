"""Block `write` and `edit` on a few sensitive filenames.

A hook is a guardrail, not a sandbox: `bash` is not covered and can still touch these
files. Run with:

    flow -e examples/extensions/protected_paths.py
"""

import os

from flow_harness.extensions import ExtensionAPI, PreToolUseDecision, PreToolUseEvent

PROTECTED = frozenset({".env", "credentials.json", "id_rsa"})


def guard(event: PreToolUseEvent) -> PreToolUseDecision | None:
	if event.tool_name not in ("write", "edit"):
		return None
	path = str(event.arguments.get("path", ""))
	# realpath follows a symlink alias to the file it names
	target = os.path.realpath(os.path.join(event.cwd, path))
	if os.path.basename(target) in PROTECTED:
		return PreToolUseDecision(block=True, reason=f"{path} is protected; ask the user to edit it by hand")
	return None


def setup(flow: ExtensionAPI) -> None:
	flow.on("tool_call", guard)
