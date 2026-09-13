import re
import sqlite3
from datetime import date, datetime, time, timedelta
from typing import NamedTuple

NAMED_PARAMETER_PATTERN = re.compile(r"%\((?P<name>\w+)\)s")


class ParameterPlaceholder(NamedTuple):
	start: int
	end: int
	name_or_position: str | int | None
	already_parenthesized: bool


class TranspilationParameter(NamedTuple):
	original_placeholder: str
	positional_index: int | None


def _find_end_of_quoted_sql(query: str, start: int) -> int:
	opening_quote = query[start]
	closing_quote = "]" if opening_quote == "[" else opening_quote
	index = start + 1
	while index < len(query):
		if opening_quote in "'\"" and query[index] == "\\":
			index += 2
			continue
		if query[index] == closing_quote:
			if index + 1 < len(query) and query[index + 1] == closing_quote:
				index += 2
				continue
			return index + 1
		index += 1
	return index


def _is_line_comment_start(query: str, index: int) -> bool:
	return query[index] == "#" or (
		query.startswith("--", index) and (index + 2 == len(query) or query[index + 2].isspace())
	)


def _find_next_sql_code_character(query: str, start: int) -> int:
	"""Skip whitespace and comments, returning the index of the next SQL character."""
	index = start
	while index < len(query):
		if query[index].isspace():
			index += 1
		elif query.startswith("/*", index):
			comment_end = query.find("*/", index + 2)
			index = len(query) if comment_end < 0 else comment_end + 2
		elif _is_line_comment_start(query, index):
			comment_end = query.find("\n", index + 1)
			index = len(query) if comment_end < 0 else comment_end + 1
		else:
			break
	return index


def _iter_parameter_placeholders(query: str, *, sqlite_qmark: bool = False):
	"""Find actual parameters without mistaking quoted text, comments, or modulo expressions for one."""
	index = 0
	previous_code_character = None
	while index < len(query):
		character = query[index]
		if character.isspace():
			index += 1
			continue
		if query.startswith("/*", index) or _is_line_comment_start(query, index):
			index = _find_next_sql_code_character(query, index)
			continue
		if character in "'\"`[":
			index = _find_end_of_quoted_sql(query, index)
			previous_code_character = character
			continue

		placeholder_end = None
		name_or_position = None
		if sqlite_qmark and character == "?":
			placeholder_end = index + 1
			while placeholder_end < len(query) and query[placeholder_end].isdigit():
				placeholder_end += 1
			if placeholder_end > index + 1:
				name_or_position = int(query[index + 1 : placeholder_end])
		elif not sqlite_qmark and query.startswith("%s", index):
			previous_character = query[index - 1] if index else ""
			next_character = query[index + 2] if index + 2 < len(query) else ""
			if not (
				(previous_character and (previous_character.isalnum() or previous_character in "_$"))
				or (next_character and (next_character.isalnum() or next_character in "_$"))
			):
				placeholder_end = index + 2
		elif (
			not sqlite_qmark
			and character == "%"
			and (named_match := NAMED_PARAMETER_PATTERN.match(query, index))
		):
			placeholder_end = named_match.end()
			name_or_position = named_match["name"]

		if placeholder_end is not None:
			next_code_index = _find_next_sql_code_character(query, placeholder_end)
			yield ParameterPlaceholder(
				start=index,
				end=placeholder_end,
				name_or_position=name_or_position,
				already_parenthesized=(
					previous_code_character == "("
					and next_code_index < len(query)
					and query[next_code_index] == ")"
				),
			)
			previous_code_character = "?"
			index = placeholder_end
			continue

		previous_code_character = character
		index += 1


def _create_sqlite_placeholders(value, *, already_parenthesized: bool) -> tuple[str, list]:
	if not isinstance(value, list | tuple):
		return "?", [value]
	placeholder_list = ",".join("?" for _ in value)
	return (placeholder_list if already_parenthesized else f"({placeholder_list})"), list(value)


def convert_frappe_query_parameters(query: str, values) -> tuple[str, object]:
	"""Convert Frappe's pyformat parameters to SQLite placeholders and bound values."""
	if values is None:
		return query, ()
	if "%" not in query:
		return query, values

	query_parts = []
	bound_values = []
	previous_end = 0
	placeholder_found = False

	if isinstance(values, dict):
		for placeholder in _iter_parameter_placeholders(query):
			placeholder_found = True
			query_parts.append(query[previous_end : placeholder.start])
			parameter_name = placeholder.name_or_position
			if parameter_name is None:
				raise sqlite3.ProgrammingError("Positional %s placeholder used with mapping parameters")
			if parameter_name not in values:
				raise sqlite3.ProgrammingError(f"Missing query parameter: {parameter_name}")
			replacement, expanded_values = _create_sqlite_placeholders(
				values[parameter_name], already_parenthesized=placeholder.already_parenthesized
			)
			query_parts.append(replacement)
			bound_values.extend(expanded_values)
			previous_end = placeholder.end
	else:
		positional_values = tuple(values) if isinstance(values, list | tuple) else (values,)
		position = 0
		for placeholder in _iter_parameter_placeholders(query):
			placeholder_found = True
			query_parts.append(query[previous_end : placeholder.start])
			if placeholder.name_or_position is not None:
				raise sqlite3.ProgrammingError("Named placeholder used with positional parameters")
			if position >= len(positional_values):
				raise sqlite3.ProgrammingError("Not enough query parameters")
			replacement, expanded_values = _create_sqlite_placeholders(
				positional_values[position], already_parenthesized=placeholder.already_parenthesized
			)
			query_parts.append(replacement)
			bound_values.extend(expanded_values)
			position += 1
			previous_end = placeholder.end
		if position != len(positional_values):
			raise sqlite3.ProgrammingError("Too many query parameters")

	if not placeholder_found:
		return query, values
	query_parts.append(query[previous_end:])
	return "".join(query_parts), tuple(bound_values)


def _format_parameter_for_query_log(value) -> str:
	if value is None:
		return "NULL"
	if isinstance(value, bool):
		return "1" if value else "0"
	if isinstance(value, bytes):
		return f"X'{value.hex()}'"
	if isinstance(value, datetime | date | time):
		value = value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
	elif isinstance(value, timedelta):
		value = str(value)
	if isinstance(value, str):
		return "'" + value.replace("'", "''") + "'"
	return str(value)


def render_query_with_bound_values(query: str, values) -> str:
	"""Render bound SQLite values for diagnostics only; never use the result for execution."""
	if not values or isinstance(values, dict):
		return query

	highest_parameter_position = 0
	previous_end = 0
	query_parts = []
	for placeholder in _iter_parameter_placeholders(query, sqlite_qmark=True):
		explicit_position = placeholder.name_or_position
		if explicit_position is None:
			highest_parameter_position += 1
			parameter_position = highest_parameter_position
		elif explicit_position > 0:
			highest_parameter_position = max(highest_parameter_position, explicit_position)
			parameter_position = explicit_position
		else:
			raise sqlite3.ProgrammingError("SQLite parameter numbers start at 1")

		if parameter_position > len(values):
			raise sqlite3.ProgrammingError("Query placeholder count does not match bound values")
		query_parts.extend(
			(
				query[previous_end : placeholder.start],
				_format_parameter_for_query_log(values[parameter_position - 1]),
			)
		)
		previous_end = placeholder.end

	if highest_parameter_position != len(values):
		raise sqlite3.ProgrammingError("Query placeholder count does not match bound values")
	query_parts.append(query[previous_end:])
	return "".join(query_parts)


def mask_query_parameters(query: str) -> tuple[str, dict[str, TranspilationParameter]]:
	"""Replace parameters with unique SQLGlot-safe markers before parsing."""
	parameters = {}
	query_parts = []
	marker_prefix = "__frappe_sql_parameter_"
	while marker_prefix in query:
		marker_prefix = f"_{marker_prefix}"
	positional_index = 0
	previous_end = 0

	for placeholder in _iter_parameter_placeholders(query):
		original_placeholder = query[placeholder.start : placeholder.end]
		marker = f":{marker_prefix}{len(parameters)}__"
		parameter_position = positional_index if original_placeholder == "%s" else None
		parameters[marker] = TranspilationParameter(original_placeholder, parameter_position)
		query_parts.extend((query[previous_end : placeholder.start], marker))
		previous_end = placeholder.end
		if parameter_position is not None:
			positional_index += 1

	query_parts.append(query[previous_end:])
	return "".join(query_parts), parameters


def restore_transpiled_query_parameters(
	query: str, parameters: dict[str, TranspilationParameter]
) -> tuple[str, tuple[int, ...]]:
	"""Restore masked parameters and report positional parameters in translated SQL order."""
	marker_positions = {}
	for marker in parameters:
		if query.count(marker) != 1:
			raise ValueError("SQLGlot changed a query placeholder")
		marker_positions[marker] = query.index(marker)

	positional_parameter_order = tuple(
		parameters[marker].positional_index
		for marker in sorted(marker_positions, key=marker_positions.__getitem__)
		if parameters[marker].positional_index is not None
	)
	for marker, parameter in parameters.items():
		query = query.replace(marker, parameter.original_placeholder)
	return query, positional_parameter_order
