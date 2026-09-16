from dataclasses import replace

from flow_harness.tools.builtins.bash import bash
from flow_harness.tools.builtins.edit import edit
from flow_harness.tools.builtins.read import read
from flow_harness.tools.builtins.write import write
from flow_harness.tools.tool import Tool

# Clients may already expose a `read` tool; this alias avoids duplicate tool names.
read_file = replace(read, name="read_file")

BUILTIN_TOOLS: dict[str, Tool] = {t.name: t for t in (bash, read, read_file, write, edit)}

__all__ = ["BUILTIN_TOOLS", "bash", "edit", "read", "read_file", "write"]
