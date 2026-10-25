from flow_harness.tools.bundled.grep import grep
from flow_harness.tools.bundled.suggest_replies import suggest_replies
from flow_harness.tools.tool import Tool

# Shipped with the harness but off by default: a session opts in by naming one in `tools`.
BUNDLED_TOOLS: dict[str, Tool] = {t.name: t for t in (grep, suggest_replies)}

__all__ = ["BUNDLED_TOOLS", "grep", "suggest_replies"]
