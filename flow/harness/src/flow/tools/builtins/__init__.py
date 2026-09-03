from flow.tools.builtins.bash import bash
from flow.tools.builtins.edit import edit
from flow.tools.builtins.grep import grep
from flow.tools.builtins.read import read
from flow.tools.builtins.write import write
from flow.tools.tool import Tool

BUILTIN_TOOLS: dict[str, Tool] = {t.name: t for t in (bash, read, write, edit, grep)}

__all__ = ["BUILTIN_TOOLS", "bash", "edit", "grep", "read", "write"]
