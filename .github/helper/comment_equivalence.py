"""Prove a comment-only change left the code byte-identical."""

import io
import subprocess
import sys
import tokenize

SOURCE_SUFFIXES = (".py", ".ts", ".js", ".vue", ".mjs")
JS_STRING_QUOTES = "\"'`"
REGEX_CANNOT_FOLLOW = ")]}" + "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$"


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
	stripped = strip_python(source) if path.endswith(".py") else strip_curly(source)
	return "\n".join(line.rstrip() for line in stripped.split("\n") if line.strip())


def strip_python(source):
	"""Drops comment tokens; docstrings are runtime values and survive as code."""
	try:
		tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
	except (tokenize.TokenError, IndentationError):
		return source
	kept = [token for token in tokens if token.type != tokenize.COMMENT]
	return tokenize.untokenize(kept)


def strip_curly(source):
	reader = CurlySource(source)
	return reader.without_comments()


class CurlySource:
	"""Line and block comment removal for JS, TS and Vue, string- and regex-aware."""

	def __init__(self, source):
		self.source = source
		self.position = 0
		self.output = []

	def without_comments(self):
		while self.position < len(self.source):
			character = self.source[self.position]
			if character in JS_STRING_QUOTES:
				self.copy_string(character)
			elif self.starts("//"):
				self.skip_to("\n")
			elif self.starts("/*"):
				self.skip_past("*/")
			elif character == "/" and self.regex_may_start():
				self.copy_regex()
			else:
				self.emit(character)
		return "".join(self.output)

	def starts(self, text):
		return self.source.startswith(text, self.position)

	def emit(self, text):
		self.output.append(text)
		self.position += len(text)

	def copy_string(self, quote):
		self.emit(quote)
		while self.position < len(self.source):
			character = self.source[self.position]
			if character == "\\":
				self.emit(self.source[self.position : self.position + 2])
				continue
			self.emit(character)
			if character == quote:
				return

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


if __name__ == "__main__":
	if len(sys.argv) != 3:
		sys.exit("usage: comment_equivalence.py <base-ref> <head-ref>")
	sys.exit(main(sys.argv[1], sys.argv[2]))
