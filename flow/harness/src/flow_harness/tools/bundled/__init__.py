from flow_harness.tools.bundled.grep import grep
from flow_harness.tools.tool import Tool

# Shipped with the harness but off by default: a session opts in by naming one in `tools`.
BUNDLED_TOOLS: dict[str, Tool] = {t.name: t for t in (grep,)}

__all__ = ["BUNDLED_TOOLS", "grep"]
