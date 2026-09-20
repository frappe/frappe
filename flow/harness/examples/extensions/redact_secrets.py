"""Keep credential-shaped strings out of what the model sees.

Run with:

    flow -e examples/extensions/redact_secrets.py
"""

import re

from flow_harness.extensions import ExtensionAPI, PostToolUseEvent, PostToolUseOverride

SECRET = re.compile(r"\b(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,})")


def redact(event: PostToolUseEvent) -> PostToolUseOverride | None:
	cleaned = SECRET.sub("[redacted]", event.result.content)
	if cleaned == event.result.content:
		return None
	# details replaces the whole dict, so keep the tool's own keys
	return PostToolUseOverride(content=cleaned, details={**event.result.details, "redacted": True})


def setup(flow: ExtensionAPI) -> None:
	flow.on("tool_result", redact)
