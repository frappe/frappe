from flow_server.tools.builtins.bash import bash
from flow_server.tools.builtins.edit import edit
from flow_server.tools.builtins.grep import grep
from flow_server.tools.builtins.read_file import read_file
from flow_server.tools.builtins.write import write
from flow_server.tools.tool import Tool

BUILTIN_TOOLS: dict[str, Tool] = {t.name: t for t in (bash, read_file, write, edit, grep)}

__all__ = ["BUILTIN_TOOLS", "bash", "edit", "grep", "read_file", "write"]
