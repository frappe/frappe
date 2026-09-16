from dataclasses import replace

from flow_harness.tools.builtins.bash import bash
from flow_harness.tools.builtins.edit import edit
from flow_harness.tools.builtins.read import read
from flow_harness.tools.builtins.write import write
from flow_harness.tools.tool import Tool

BUILTIN_TOOLS: dict[str, Tool] = {t.name: t for t in (bash, read, write, edit)}

# Clients may already expose a `read` tool; this alias avoids duplicate tool names.
# Selectable by name like a built-in, but never listed: it is the same tool as `read`.
read_file = replace(read, name="read_file")
BUILTIN_ALIASES: dict[str, Tool] = {read_file.name: read_file}

__all__ = ["BUILTIN_ALIASES", "BUILTIN_TOOLS", "bash", "edit", "read", "read_file", "write"]
