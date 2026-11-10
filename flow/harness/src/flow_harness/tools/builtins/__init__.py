from flow_harness.tools.builtins.bash import bash
from flow_harness.tools.builtins.edit import edit
from flow_harness.tools.builtins.read import read
from flow_harness.tools.builtins.subagent import subagent
from flow_harness.tools.builtins.write import write
from flow_harness.tools.tool import Tool

BUILTIN_TOOLS: dict[str, Tool] = {t.name: t for t in (bash, read, write, edit, subagent)}

__all__ = ["BUILTIN_TOOLS", "bash", "edit", "read", "subagent", "write"]
