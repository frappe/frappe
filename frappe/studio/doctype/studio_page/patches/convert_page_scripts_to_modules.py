"""Convert database page scripts to the `setup(context)` format used by repository apps.

Older scripts could use Vue APIs, page variables and resources without declaring
where those names came from. A module must import library APIs and read page data
from `context`. It returns the values and functions used by page bindings.

The conversion adds imports and a setup function around the existing script body:

        import { ref } from "vue"

        export default function setup(context) {
                const { todos } = context

                const count = ref(0)

                return { count }
        }

Vue and frappe-ui APIs come from imports. Page variables, resources, route, router and
socket come from `context`. Existing references keep their names. A VueUse API becomes a
`@vueuse/core` import, which a database app cannot resolve, so the page reports the line
to rewrite.

What a site owner has to review afterwards is in
`studio/frontend/docs/migrate-custom-db-apps-to-modules.md`.
"""

import json

import frappe
from frappe.studio.files import write_store_file

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
CONTEXT_EXTRAS = ("route", "router", "socket")

DECLARATION_KEYWORDS = {"const", "let", "var", "function", "class", "async"}
# A newline after these tokens can start a statement through automatic semicolon insertion.
STATEMENT_END_PUNCTUATION = {")", "]", "}"}
# These tokens continue an expression even after a newline.
# A closing brace can end a destructuring pattern as well as a code block.
CONTINUATION_PUNCTUATION = {"=", ".", ",", ":", "?", ")", "]", "}", "*", "/", "%", "<", ">", "&", "|", "^"}


def execute():
	pages = frappe.get_all(
		"Studio Page",
		filters={"is_standard": 0, "script": ("is", "set")},
		fields=["name", "script"],
	)
	for page in pages:
		convert_page_script(page.name, page.script)

	# Frappe keeps columns for removed fields. Migrate the old router field only if it exists.
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
	"""Move the removed `router_script` field to the app's `router.js` source file."""
	if not router_script or not router_script.strip():
		return
	used = get_referenced_names(list(tokenize(router_script)))
	names = [name for name in IMPORTED_APIS["frappe-ui"] if name in used]
	imports = f'import {{ {", ".join(names)} }} from "frappe-ui"\n\n' if names else ""
	write_store_file(app_name, "router.js", f"{imports}export default {router_script.strip()}\n")


def is_module(script: str) -> bool:
	"""Detect top-level import or export syntax so a module is not wrapped again."""
	return any(
		token.value in ("import", "export") and token.statement_start and token.depth == 0
		for token in tokenize(script)
	)


def get_context_names(page_name: str) -> list[str]:
	"""Return names that older scripts could read from the page's execution context."""
	page = frappe.get_doc("Studio Page", page_name)
	variables = [row.variable_name for row in page.variables if row.variable_name]
	resources = [row.resource_name for row in page.resources if row.resource_name]
	return [*variables, *resources, *CONTEXT_EXTRAS]


def to_setup_module(script: str, context_names: list[str]) -> str:
	"""Wrap the script in a setup module without rewriting its statements.

	Import library APIs, read required values from `context` and return top-level
	declarations for use by page bindings.
	"""
	tokens = list(tokenize(script))
	bindings = get_top_level_bindings(tokens)
	used = get_referenced_names(tokens)

	declared = set(bindings)
	from_context = [name for name in dict.fromkeys(context_names) if name in used and name not in declared]
	taken = declared | set(from_context)
	# A script can declare `context`, or read a page variable with that name.
	parameter = "context"
	while parameter in taken:
		parameter = "_" + parameter

	lines = []
	for module, names in IMPORTED_APIS.items():
		imported = [name for name in names if name in used and name not in taken]
		if imported:
			lines.append(f"import {{ {', '.join(imported)} }} from {json.dumps(module)}")
	if lines:
		lines.append("")

	lines.append(f"export default function setup({parameter}) {{")
	if from_context:
		lines.append(f"\tconst {{ {', '.join(from_context)} }} = {parameter}")
		lines.append("")
	lines.append(indent_code(script.strip("\n")))
	lines.append("")
	lines.append(f"\treturn {{ {', '.join(bindings)} }}")
	lines.append("}")
	return "\n".join(lines) + "\n"


def get_top_level_bindings(tokens: list["Token"]) -> list[str]:
	"""Find top-level declarations to return from setup, in source order."""
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
	"""Read a function or class declaration's name. Expression names are not page bindings."""
	if index < len(tokens) and tokens[index].value == "*":
		index += 1
	if index < len(tokens) and tokens[index].kind == "identifier":
		names.append(tokens[index].value)
		return index + 1
	return index


def read_declarator_names(tokens: list["Token"], index: int, names: list[str]) -> int:
	"""Read names declared by const, let or var, including destructured names."""
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
	"""Read declared names from a destructuring pattern, excluding keys and default values."""
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
			# In `key: binding`, only the name after the colon declares a variable.
			if index + 1 < len(tokens) and tokens[index + 1].value == ":":
				index += 2
				continue
			names.append(token.value)
		index += 1
	return index


def skip_default_value(tokens: list["Token"], index: int, pattern_depth: int) -> int:
	"""Skip a default value and return the index of the next comma or closing bracket."""
	while index < len(tokens):
		token = tokens[index]
		if token.depth < pattern_depth or (token.depth == pattern_depth and token.value == ","):
			return index
		index += 1
	return index


def skip_to_next_declarator(tokens: list["Token"], index: int, base_depth: int) -> int | None:
	"""Skip one variable's initial value.

	Return the index after a separating comma, the index of the statement's ending
	token, or None at the end of the input.
	"""
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
	"""Collect possible identifier references, excluding property names after `.` or `?.`."""
	referenced = set()
	for index, token in enumerate(tokens):
		if token.kind != "identifier":
			continue
		if index and tokens[index - 1].value in (".", "?."):
			continue
		referenced.add(token.value)
	return referenced


def indent_code(source: str) -> str:
	"""Indent code by one tab. Preserve indentation inside multiline template strings."""
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


IDENTIFIER_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_$")
IDENTIFIER_REST = IDENTIFIER_START | set("0123456789")
DIGITS = set("0123456789")
# After these keywords, `/` starts a regular expression rather than division.
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
	"""Read the JavaScript tokens needed to find declarations and references for this migration.

	Handle identifiers, numbers, strings, templates, regular expressions and punctuation.
	Skip comments and tokenize expressions inside `${}`. Each token records its bracket
	depth and whether it starts a statement.
	"""
	index = 0
	length = len(source)
	depth = 0
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
			index = read_template(source, index)
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

		# Read a template's `${}` expression at one additional bracket level.
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
	# These tokens can end a statement when followed by a newline.
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


def read_template(source: str, index: int) -> int:
	"""Read through a closing backtick or the `${` that starts an expression.

	When resuming a template, `index` points to the expression's closing brace.
	"""
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
