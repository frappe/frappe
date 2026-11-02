"""Rewrite interpreted page scripts as `setup(context)` modules, so every Studio app authors
one dialect.

A database app used to run its page script as a bare body: free identifiers resolved against a
live context that carried Vue's reactivity APIs, the page's variables and resources, and a few
globals. Its files now compile in the browser the way a repository app's do, so the script is a
real module — it imports what it uses and returns what the page binds to.

The rewrite keeps the body verbatim and wraps it:

        import { ref } from "vue"

        export default function setup(context) {
                const { todos } = context

                const count = ref(0)

                return { count }
        }

What the body referenced through the old context now arrives through an import (Vue, VueUse and
frappe-ui APIs) or through `context` (the page's own variables and resources, plus route, router
and socket) — the same values, named the same way.
"""

import json

import frappe
from frappe.studio.files import write_store_file

# The names the interpreted context injected, and where the module dialect gets them from.
VUE_APIS = (
	"ref",
	"reactive",
	"computed",
	"watch",
	"watchEffect",
	"toRef",
	"toRefs",
	"unref",
	"isRef",
	"isReactive",
	"shallowRef",
	"readonly",
	"markRaw",
	"nextTick",
)
IMPORTED_APIS = {
	"vue": VUE_APIS,
	"@vueuse/core": ("watchDebounced",),
	"frappe-ui": ("call", "toast"),
}
# Context members that are not the page's own variables or resources.
CONTEXT_EXTRAS = ("route", "router", "socket")

DECLARATION_KEYWORDS = {"const", "let", "var", "function", "class", "async"}
# Tokens after which a newline ends the statement (ASI), so the next token starts a new one.
STATEMENT_END_PUNCTUATION = {")", "]", "}"}
# Punctuation that can only continue an expression, so it never starts a statement however it is
# spaced — `}` ends a destructuring pattern as often as it ends a block.
CONTINUATION_PUNCTUATION = {"=", ".", ",", ":", "?", ")", "]", "}", "*", "/", "%", "<", ">", "&", "|", "^"}


def execute():
	pages = frappe.get_all(
		"Studio Page",
		filters={"is_standard": 0, "script": ("is", "set")},
		fields=["name", "script"],
	)
	for page in pages:
		convert_page_script(page.name, page.script)

	# this release drops the field, and frappe leaves the column behind rather than dropping it;
	# a site that never had it has nothing to move
	if frappe.db.has_column("Studio App", "router_script"):
		for app in frappe.get_all("Studio App", filters={"is_standard": 0}, fields=["name", "router_script"]):
			move_router_script_to_file(app.name, app.router_script)


def convert_page_script(page_name: str, script: str) -> None:
	"""Rewrite one page's script, unless it is already a module."""
	if not script or not script.strip() or is_module(script):
		return
	context_names = get_context_names(page_name)
	frappe.db.set_value(
		"Studio Page", page_name, "script", to_setup_module(script, context_names), update_modified=False
	)


def move_router_script_to_file(app_name: str, router_script: str | None) -> None:
	"""A database app's router config moves from the `router_script` field into router.ts, where
	every app keeps it. The field is dropped by this release."""
	if not router_script or not router_script.strip():
		return
	write_store_file(app_name, "router.ts", f"export default {router_script.strip()}\n")


def is_module(script: str) -> bool:
	"""A bare script cannot contain a top-level `import`/`export` — it is a function body, not a
	module — so either one marks a script this patch has already rewritten."""
	return any(
		token.value in ("import", "export") and token.statement_start and token.depth == 0
		for token in tokenize(script)
	)


def get_context_names(page_name: str) -> list[str]:
	"""The page's variables and resources, which the script used to read as free identifiers."""
	page = frappe.get_doc("Studio Page", page_name)
	variables = [row.variable_name for row in page.variables if row.variable_name]
	resources = [row.resource_name for row in page.resources if row.resource_name]
	return [*variables, *resources, *CONTEXT_EXTRAS]


def to_setup_module(script: str, context_names: list[str]) -> str:
	"""The script as a `setup(context)` module: imports for the APIs it used, a destructure for
	the context members it used, the body unchanged, and a return of its top-level bindings."""
	tokens = list(tokenize(script))
	bindings = get_top_level_bindings(tokens)
	used = get_referenced_names(tokens)

	# a binding of the same name shadows what the context used to inject, exactly as it did before
	declared = set(bindings)
	from_context = [name for name in dict.fromkeys(context_names) if name in used and name not in declared]
	taken = declared | set(from_context)

	lines = []
	for module, names in IMPORTED_APIS.items():
		imported = [name for name in names if name in used and name not in taken]
		if imported:
			lines.append(f"import {{ {', '.join(imported)} }} from {json.dumps(module)}")
	if lines:
		lines.append("")

	lines.append("export default function setup(context) {")
	if from_context:
		lines.append(f"\tconst {{ {', '.join(from_context)} }} = context")
		lines.append("")
	lines.append(indent_code(script.strip("\n")))
	lines.append("")
	lines.append(f"\treturn {{ {', '.join(bindings)} }}")
	lines.append("}")
	return "\n".join(lines) + "\n"


def get_top_level_bindings(tokens: list["Token"]) -> list[str]:
	"""Names the body declares at the top level — what the interpreted dialect returned to the
	page. Matches `getTopLevelBindings` in the editor: declarations only, in source order."""
	names: list[str] = []
	index = 0
	while index < len(tokens):
		token = tokens[index]
		if not (token.depth == 0 and token.statement_start and token.value in DECLARATION_KEYWORDS):
			index += 1
			continue
		if token.value == "async":
			if index + 1 >= len(tokens) or tokens[index + 1].value != "function":
				index += 1
				continue
			index += 1
			token = tokens[index]
		if token.value in ("function", "class"):
			index = read_declaration_name(tokens, index + 1, names)
		else:
			index = read_declarator_names(tokens, index + 1, names)
	return list(dict.fromkeys(names))


def read_declaration_name(tokens: list["Token"], index: int, names: list[str]) -> int:
	"""The name of a `function`/`class` declaration. A `function`/`class` *expression* is skipped:
	it is not a declaration, so its name never reached the page."""
	if index < len(tokens) and tokens[index].value == "*":
		index += 1
	if index < len(tokens) and tokens[index].kind == "identifier":
		names.append(tokens[index].value)
		return index + 1
	return index


def read_declarator_names(tokens: list["Token"], index: int, names: list[str]) -> int:
	"""Every name bound by a `const`/`let`/`var` statement, destructuring patterns included."""
	base_depth = tokens[index - 1].depth
	while index < len(tokens):
		token = tokens[index]
		if token.kind == "identifier":
			names.append(token.value)
			index += 1
		elif token.value in ("{", "["):
			index = read_pattern_names(tokens, index, names)
		else:
			break
		index = skip_to_next_declarator(tokens, index, base_depth)
		if index is None:
			return len(tokens)
		if tokens[index - 1].value != ",":
			return index
	return index


def read_pattern_names(tokens: list["Token"], index: int, names: list[str]) -> int:
	"""Names bound by a destructuring pattern, skipping object keys and default values."""
	open_depth = tokens[index].depth + 1
	index += 1
	while index < len(tokens):
		token = tokens[index]
		if token.depth < open_depth:
			return index
		if token.depth > open_depth:
			index += 1
			continue
		if token.value == "=":
			index = skip_default_value(tokens, index + 1, open_depth)
			continue
		if token.value in ("{", "["):
			index = read_pattern_names(tokens, index, names)
			continue
		if token.kind == "identifier":
			# `key: binding` binds the right-hand side, so a name before `:` is only a key
			if index + 1 < len(tokens) and tokens[index + 1].value == ":":
				index += 2
				continue
			names.append(token.value)
		index += 1
	return index


def skip_default_value(tokens: list["Token"], index: int, pattern_depth: int) -> int:
	"""Past a `= <expression>` inside a pattern, to its `,` or the pattern's close."""
	while index < len(tokens):
		token = tokens[index]
		if token.depth < pattern_depth or (token.depth == pattern_depth and token.value == ","):
			return index
		index += 1
	return index


def skip_to_next_declarator(tokens: list["Token"], index: int, base_depth: int) -> int | None:
	"""Past one declarator's initialiser. Returns the index after the `,` that starts the next
	declarator, the index of the token that ends the statement, or None at end of input."""
	while index < len(tokens):
		token = tokens[index]
		if token.depth < base_depth:
			return index
		if token.depth == base_depth:
			if token.value == ",":
				return index + 1
			if token.value == ";" or (token.statement_start and index > 0):
				return index
		index += 1
	return None


def get_referenced_names(tokens: list["Token"]) -> set[str]:
	"""Identifiers the body reads. Property names (`doc.ref`) and object keys are left out, so a
	name here is one that had to resolve from the enclosing scope."""
	referenced = set()
	for index, token in enumerate(tokens):
		if token.kind != "identifier":
			continue
		if index and tokens[index - 1].value in (".", "?."):
			continue
		referenced.add(token.value)
	return referenced


def indent_code(source: str) -> str:
	"""Indent the body by one tab. A line that continues a template literal keeps its indentation:
	a tab there would change the string, not the code."""
	spans = [(token.start, token.end) for token in tokenize(source) if token.kind == "template"]
	lines = []
	position = 0
	for line in source.split("\n"):
		continues_template = any(start < position < end for start, end in spans)
		lines.append(line if continues_template or not line.strip() else "\t" + line)
		position += len(line) + 1
	return "\n".join(lines)


class Token:
	__slots__ = ("depth", "end", "kind", "start", "statement_start", "value")

	def __init__(self, kind, value, depth, statement_start, start, end):
		self.kind = kind
		self.value = value
		self.depth = depth
		self.statement_start = statement_start
		self.start = start
		self.end = end

	def __repr__(self):
		return f"Token({self.kind}, {self.value!r}, depth={self.depth})"


IDENTIFIER_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_$")
IDENTIFIER_REST = IDENTIFIER_START | set("0123456789")
DIGITS = set("0123456789")
# A `/` right after one of these starts a regular expression, not a division.
REGEX_PRECEDING_KEYWORDS = {
	"return",
	"typeof",
	"instanceof",
	"in",
	"of",
	"new",
	"delete",
	"void",
	"throw",
	"case",
	"do",
	"else",
	"yield",
	"await",
}


def tokenize(source: str):
	"""JavaScript tokens, enough of them to find declarations and references: identifiers,
	numbers, strings, templates (with their `${}` expressions tokenized), regular expressions,
	comments and punctuation. Each token carries its bracket depth and whether it starts a
	statement."""
	index = 0
	length = len(source)
	depth = 0
	# open brackets of the template substitutions currently being tokenized
	template_stack: list[int] = []
	previous: Token | None = None
	newline_before = True

	while index < length:
		char = source[index]
		if char in " \t\r":
			index += 1
			continue
		if char == "\n":
			newline_before = True
			index += 1
			continue
		if char == "/" and source.startswith("//", index):
			index = source.find("\n", index)
			index = length if index == -1 else index
			continue
		if char == "/" and source.startswith("/*", index):
			end = source.find("*/", index + 2)
			index = length if end == -1 else end + 2
			continue

		start = index
		if char in IDENTIFIER_START:
			while index < length and source[index] in IDENTIFIER_REST:
				index += 1
			kind = "identifier"
		elif char in DIGITS:
			while index < length and (source[index] in IDENTIFIER_REST or source[index] == "."):
				index += 1
			kind = "number"
		elif char in "'\"":
			index = read_quoted(source, index)
			kind = "string"
		elif char == "`":
			index = read_template(source, index)
			kind = "template"
		elif char == "}" and template_stack and depth == template_stack[-1]:
			template_stack.pop()
			depth -= 1
			index = read_template(source, index, resuming=True)
			kind = "template"
		elif char == "/" and starts_regex(previous):
			index = read_regex(source, index)
			kind = "regex"
		else:
			index += 1
			kind = "punctuation"
			if char in "([{":
				depth += 1
			elif char in ")]}":
				depth = max(depth - 1, 0)

		value = source[start:index]
		statement_start = is_statement_start(previous, newline_before, kind, value)
		token_depth = depth - 1 if kind == "punctuation" and value in "([{" else depth
		token = Token(kind, value, token_depth, statement_start, start, index)

		# `${` inside a template: its expression is tokenized at one level deeper
		if kind == "template" and value.endswith("${"):
			depth += 1
			template_stack.append(depth)

		yield token
		previous = token
		newline_before = False


def is_statement_start(previous: Token | None, newline_before: bool, kind: str, value: str) -> bool:
	if kind == "punctuation" and value in CONTINUATION_PUNCTUATION:
		return False
	if previous is None:
		return True
	if previous.kind == "punctuation" and previous.value in (";", "{", "}"):
		return True
	if not newline_before:
		return False
	# ASI: a newline after something a statement can end with starts the next one
	return previous.kind in ("identifier", "number", "string", "template", "regex") or (
		previous.value in STATEMENT_END_PUNCTUATION
	)


def starts_regex(previous: Token | None) -> bool:
	if previous is None:
		return True
	if previous.kind in ("number", "string", "template", "regex"):
		return False
	if previous.kind == "identifier":
		return previous.value in REGEX_PRECEDING_KEYWORDS
	return previous.value not in (")", "]", "}", "++", "--")


def read_quoted(source: str, index: int) -> int:
	quote = source[index]
	index += 1
	while index < len(source):
		if source[index] == "\\":
			index += 2
			continue
		if source[index] == quote:
			return index + 1
		if source[index] == "\n":
			return index
		index += 1
	return index


def read_template(source: str, index: int, resuming: bool = False) -> int:
	"""Up to the end of a template literal, or to the `${` that opens a substitution. `resuming`
	continues a template after its substitution's closing brace."""
	index += 1
	while index < len(source):
		if source[index] == "\\":
			index += 2
			continue
		if source.startswith("${", index):
			return index + 2
		if source[index] == "`":
			return index + 1
		index += 1
	del resuming
	return index


def read_regex(source: str, index: int) -> int:
	index += 1
	in_class = False
	while index < len(source):
		char = source[index]
		if char == "\\":
			index += 2
			continue
		if char == "\n":
			return index
		if char == "[":
			in_class = True
		elif char == "]":
			in_class = False
		elif char == "/" and not in_class:
			index += 1
			while index < len(source) and source[index] in IDENTIFIER_REST:
				index += 1
			return index
		index += 1
	return index
