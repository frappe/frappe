"""Prove a comment-only change left the code identical."""

import io
import subprocess
import sys
import tokenize

SOURCE_SUFFIXES = (".py", ".ts", ".js", ".vue", ".mjs")
JS_STRING_QUOTES = "\"'`"
REGEX_CANNOT_FOLLOW = ")]}abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$"


def main(base, head):
	differing = [path for path in changed_sources(base, head) if not is_equivalent(path, base, head)]
	for path in differing:
		print(f"code changed: {path}")
	if differing:
		print(f"\n{len(differing)} file(s) are not comment-only.")
		return 1
	print("every changed file is comment-only.")
	return 0


def changed_sources(base, head):
	names = run(["git", "diff", "--name-only", f"{base}...{head}"]).split("\n")
	return [name for name in names if name.endswith(SOURCE_SUFFIXES)]


def is_equivalent(path, base, head):
	return strip(path, read(base, path)) == strip(path, read(head, path))


def read(ref, path):
	try:
		return run(["git", "show", f"{ref}:{path}"])
	except subprocess.CalledProcessError:
		return ""


def strip(path, source):
	lines, protected = strip_python(source) if path.endswith(".py") else strip_curly(source, path)
	return "\n".join(normalised(lines, protected))


def normalised(lines, protected):
	"""Blank lines and trailing space are inert outside a string literal, and content inside one."""
	for index, line in enumerate(lines):
		if index in protected:
			yield line
		elif line.strip():
			yield line.rstrip()


def strip_python(source):
	"""Blanks comment spans; a docstring is a runtime value and survives as code."""
	lines = source.split("\n")
	try:
		tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
	except (tokenize.TokenError, IndentationError):
		return lines, set(range(len(lines)))
	protected = set()
	for token in tokens:
		if token.type == tokenize.COMMENT:
			row = token.start[0] - 1
			lines[row] = lines[row][: token.start[1]] + lines[row][token.end[1] :]
		elif token.type == tokenize.STRING and token.end[0] > token.start[0]:
			protected.update(range(token.start[0] - 1, token.end[0]))
	return lines, protected


def strip_curly(source, path=""):
	return CurlySource(source, template_span(source) if path.endswith(".vue") else None).without_comments()


def template_span(source):
	"""The outer `<template>` block of a Vue file, where only `"` delimits a string."""
	start = source.find("<template")
	end = source.rfind("</template>")
	return (start, end) if 0 <= start < end else None


class CurlySource:
	"""Comment removal for JS, TS and Vue templates, aware of strings, template literals and regexes."""

	def __init__(self, source, template=None):
		self.source = source
		self.template = template
		self.position = 0
		self.line = 0
		self.output = []
		self.protected = set()

	def without_comments(self):
		while self.position < len(self.source):
			character = self.source[self.position]
			if character in self.quotes():
				self.copy_string(character)
			elif self.starts("//"):
				self.skip_to("\n")
			elif self.starts("/*"):
				self.skip_past("*/")
			elif self.starts("<!--"):
				self.skip_past("-->")
			elif character == "/" and self.regex_may_start():
				self.copy_regex()
			else:
				self.emit(character)
		return "".join(self.output).split("\n"), self.protected

	def quotes(self):
		"""An apostrophe in template text is not a string; only `"` delimits one there."""
		if self.template and self.template[0] <= self.position < self.template[1]:
			return '"'
		return JS_STRING_QUOTES

	def starts(self, text):
		return self.source.startswith(text, self.position)

	def emit(self, text):
		self.output.append(text)
		self.position += len(text)
		self.line += text.count("\n")

	def copy_string(self, quote):
		opened_at = self.line
		self.emit(quote)
		while self.position < len(self.source):
			character = self.source[self.position]
			if character == "\\":
				self.emit(self.source[self.position : self.position + 2])
				continue
			self.emit(character)
			if character == quote:
				break
		if self.line > opened_at:
			self.protected.update(range(opened_at, self.line + 1))

	def copy_regex(self):
		self.emit("/")
		while self.position < len(self.source):
			character = self.source[self.position]
			if character == "\\":
				self.emit(self.source[self.position : self.position + 2])
				continue
			self.emit(character)
			if character in "/\n":
				return

	def skip_to(self, terminator):
		end = self.source.find(terminator, self.position)
		self.position = len(self.source) if end == -1 else end

	def skip_past(self, terminator):
		end = self.source.find(terminator, self.position)
		self.position = len(self.source) if end == -1 else end + len(terminator)
		self.output.append(" ")

	def regex_may_start(self):
		previous = "".join(self.output).rstrip()
		return not previous or previous[-1] not in REGEX_CANNOT_FOLLOW


def run(command):
	return subprocess.run(command, capture_output=True, check=True, text=True).stdout


JS_TEMPLATE = "const t = `line one\n\nline two   \n`\n"
PY_DOCSTRING = '# header\ndef f():\n\t"""Doc.\n\n\tBody   \n\t"""\n\treturn 1  # trailing\n'

SELF_TEST_CASES = [
	(
		"js comments only",
		True,
		"x.ts",
		"// h\nconst a = 1 // t\n/* b\n c */\nconst b = 2\n",
		"const a = 1\nconst b = 2\n",
	),
	("js code change", False, "x.ts", "const b = 2\n", "const b = 3\n"),
	(
		"vue apostrophe in template text",
		True,
		"x.vue",
		"<template>\n\t<p>the app's home</p>\n\t<!-- a -->\n</template>\n<script>\nconst a = 1 // t\n</script>\n",
		"<template>\n\t<p>the app's home</p>\n</template>\n<script>\nconst a = 1\n</script>\n",
	),
	(
		"vue template comment only",
		True,
		"x.vue",
		"<template>\n\t<!-- a\n\t\tb -->\n\t<p>x</p>\n</template>\n",
		"<template>\n\t<!-- c -->\n\t<p>x</p>\n</template>\n",
	),
	("js trailing space outside a string", True, "x.ts", "const a = 1\n", "const a = 1   \n"),
	(
		"js blank line in a template literal",
		False,
		"x.ts",
		JS_TEMPLATE,
		"const t = `line one\nline two   \n`\n",
	),
	(
		"js trailing space in a template literal",
		False,
		"x.ts",
		JS_TEMPLATE,
		"const t = `line one\n\nline two\n`\n",
	),
	("py comments only", True, "x.py", PY_DOCSTRING, 'def f():\n\t"""Doc.\n\n\tBody   \n\t"""\n\treturn 1\n'),
	(
		"py blank line in a docstring",
		False,
		"x.py",
		PY_DOCSTRING,
		'def f():\n\t"""Doc.\n\tBody   \n\t"""\n\treturn 1  # trailing\n',
	),
	(
		"py trailing space in a docstring",
		False,
		"x.py",
		PY_DOCSTRING,
		'def f():\n\t"""Doc.\n\n\tBody\n\t"""\n\treturn 1  # trailing\n',
	),
	(
		"py indentation change",
		False,
		"x.py",
		"def f():\n\tif a:\n\t\treturn 1\n",
		"def f():\n\tif a:\n\t\t\treturn 1\n",
	),
	("py hash inside a string", False, "x.py", 'a = "# not a comment"\n', 'a = ""\n'),
]


def self_test():
	failures = 0
	for name, equivalent, path, before, after in SELF_TEST_CASES:
		if (strip(path, before) == strip(path, after)) != equivalent:
			print(f"self-test failed: {name}")
			failures += 1
	print(f"{len(SELF_TEST_CASES) - failures} of {len(SELF_TEST_CASES)} self-test cases pass.")
	return 1 if failures else 0


if __name__ == "__main__":
	if sys.argv[1:] == ["--self-test"]:
		sys.exit(self_test())
	if len(sys.argv) != 3:
		sys.exit("usage: comment_equivalence.py <base-ref> <head-ref> | --self-test")
	sys.exit(main(sys.argv[1], sys.argv[2]))
