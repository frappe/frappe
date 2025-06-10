import textwrap
from collections import defaultdict
from collections.abc import Generator, Iterable, Mapping, Sequence
from datetime import date, datetime
from itertools import groupby
from operator import attrgetter
from typing import Any, NamedTuple, TypeAlias, TypeGuard, TypeVar, cast

from pypika import Column
from typing_extensions import Self, override

Doct: TypeAlias = str
Fld: TypeAlias = str
Op: TypeAlias = str
DateTime: TypeAlias = datetime | date
_Value: TypeAlias = str | int | float | None | DateTime | Column
_InputValue: TypeAlias = _Value | bool
Value: TypeAlias = _Value | Sequence[_Value]
InputValue: TypeAlias = _InputValue | Sequence[_InputValue]


FilterTupleSpec: TypeAlias = (
	tuple[Fld, InputValue] | tuple[Fld, Op, InputValue] | tuple[Doct, Fld, Op, InputValue]
)
FilterMappingSpec: TypeAlias = Mapping[Fld, _InputValue | tuple[Op, InputValue]]


class Sentinel:
	def __bool__(self) -> bool:
		return False

	@override
	def __str__(self) -> str:
		return "UNSPECIFIED"


UNSPECIFIED = Sentinel()

T = TypeVar("T")


def is_unspecified(value: T | Sentinel) -> TypeGuard[Sentinel]:
	return value is UNSPECIFIED


class _FilterTuple(NamedTuple):
	doctype: Doct
	fieldname: Fld
	operator: Op
	value: Value


def _type_narrow(v: _InputValue) -> _Value:
	if isinstance(v, bool):  # beware: bool derives int in _Value
		return int(v)
	elif isinstance(v, _Value):  # type: ignore[redundant-expr]
		return v
	else:
		raise ValueError(
			f"Value must be one of types: {', '.join(str(t.__name__) for t in _InputValue.__args__)}; found {type(v)}"
		)


class FilterTuple(_FilterTuple):
	"""A named tuple representing a filter condition."""

	def __new__(
		cls,
		s: FilterTupleSpec | None = None,
		/,
		*,
		doctype: Doct | Sentinel = UNSPECIFIED,
		fieldname: Fld | Sentinel = UNSPECIFIED,
		operator: Op = "=",
		value: InputValue | Sentinel = UNSPECIFIED,
	) -> Self:
		"""
		Create a new FilterTuple instance.
		Args:
		        s: A sequence representing the filter tuple.
		        doctype: The document type.
		        fieldname: The field name.
		        operator: The comparison operator.
		        value: The value to compare against.
		Returns:
		        A new FilterTuple instance.
		"""
		try:
			if isinstance(s, Sequence):
				if len(s) == 2:
					fieldname, value = s
				elif len(s) == 3:
					fieldname, operator, value = s
				elif len(s) == 4:  # type: ignore[redundant-expr]
					doctype, fieldname, operator, value = s
				elif len(s) == 5:  # type: ignore[unreachable]
					from frappe.deprecation_dumpster import deprecation_warning

					deprecation_warning(
						"2024-12-05",
						"v16",
						f"List type filters now should have 2, 3 or 4 elements: got 5 (Input: {s!r}). Hint: you probably need to remove the last filter element, a no-op from history.",
					)
					doctype, fieldname, operator, value, _noop = s
				else:
					raise ValueError(f"Invalid sequence length: {len(s)}. Expected 2, 3, or 4 elements.")
			if is_unspecified(doctype) or doctype is None:
				raise ValueError("doctype is required")
			if is_unspecified(fieldname) or fieldname is None:
				raise ValueError("fieldname is required")
			if is_unspecified(value):
				raise ValueError("value is required; can be None")

			# soundness
			if operator in ("in", "not in") and isinstance(value, str):
				value = value.split(",")

			_value: Value
			if isinstance(value, _InputValue):
				_value = _type_narrow(value)
			else:
				_value = tuple(_type_narrow(v) for v in value)

			return super().__new__(
				cls,
				doctype=doctype,
				fieldname=fieldname,
				operator=operator,
				value=_value,
			)

		except Exception as e:
			error_context = (
				f"Error creating FilterTuple:\n"
				f"Input: {s}, doctype={doctype}, fieldname={fieldname}, operator={operator}, value={value}\n"
				f"Error: {e!s}\n"
				f"Usage: FilterTuple( (fieldname, value),                  doctype=dt )\n"
				f"       FilterTuple( (fieldname, operator, value),        doctype=dt )\n"
				f"       FilterTuple( (doctype, fieldname, operator, value)           )\n"
				f"       FilterTuple( doctype=doctype, fieldname=fieldname, operator=operator, value=value )"
			)
			raise ValueError(error_context) from e

	@override
	def __str__(self) -> str:
		value_repr = f"'{self.value}'" if isinstance(self.value, str) else repr(self.value)
		return f"<{self.doctype}>.{self.fieldname} {self.operator} {value_repr}"


class Filters(list[FilterTuple]):
	"""A sequence of filter tuples representing multiple filter conditions."""

	def __init__(
		self,
		/,
		*s: FilterTuple
		| FilterTupleSpec
		| FilterMappingSpec
		| Sequence[FilterTuple | FilterTupleSpec | FilterMappingSpec],
		doctype: Doct | Sentinel = UNSPECIFIED,
	) -> None:
		"""
		Create a new Filters instance.

		Args:
		        s: A sequence of FilterTuple or FilterTupleSpec, or a FilterMappingSpec.
		        doctype: The document type for the filters.

		Returns:
		        A new Filters instance.
		"""
		super().__init__()
		try:
			# only one argument
			if len(s) == 1:
				# and that is an empty sequence
				if len(s[0]) == 0:
					return
				# compat: unpack if first argument was Sequence of Sequences
				if (
					not isinstance(s[0], FilterTuple)
					and isinstance(s[0], Sequence)
					and not isinstance(s[0][0], str)  # it's a FilterTupleSpec
					and isinstance(s[0][0], Sequence | Mapping)
				):
					self.extend(
						cast(Iterable[FilterTuple | FilterTupleSpec | FilterMappingSpec], s[0]), doctype
					)
				else:
					self.extend(cast(Iterable[FilterTuple | FilterTupleSpec | FilterMappingSpec], s), doctype)
			else:
				self.extend(cast(Iterable[FilterTuple | FilterTupleSpec | FilterMappingSpec], s), doctype)
		except Exception as e:
			error_lines = str(e).split("\n")
			indented_error = error_lines[0] + "\n" + textwrap.indent("\n".join(error_lines[1:]), "       ")
			error_context = (
				f"\nError creating Filters:\n"
				f"Input: {s}, doctype={doctype}\n"
				f"Usage: Filters( FilterTuple(...), ...                                    )\n"
				f"       Filters( (fieldnam, value), ...                        doctype=dt )\n"
				f"       Filters( (fieldname, operator, value), ...             doctype=dt )\n"
				f"       Filters( (doctype, fieldname, operator, value), ...               )\n"
				f"       Filters( {{'fieldname': value, ...}}, ...                doctype=dt )\n"
				f"       Filters( {{'fieldname': (operator, value), ...}}, ...    doctype=dt )\n\n"
				f"Cause:\n{indented_error}"
			)
			raise ValueError(error_context) from e

		if self:  # only optimize non-empty; avoid infinit recursion
			self.optimize()

	@override
	def extend(
		self,
		values: Iterable[FilterTuple | FilterTupleSpec | FilterMappingSpec],
		doctype: Doct | Sentinel = UNSPECIFIED,
	) -> None:
		for item in values:
			self.append(item, doctype)

	@override
	def append(
		self, value: FilterTuple | FilterTupleSpec | FilterMappingSpec, doctype: Doct | Sentinel = UNSPECIFIED
	) -> None:
		if isinstance(value, FilterTuple):
			super().append(value)
		elif isinstance(value, Mapping):
			if is_unspecified(doctype) or doctype is None:
				raise ValueError("When initiated with a mapping, doctype keyword argument is required")
			self._init_from_mapping(value, doctype)
		elif isinstance(value, Sequence):  # type: ignore[redundant-expr]
			super().append(FilterTuple(value, doctype=doctype))
		else:
			raise TypeError(f"Expected FilterTruple, Mapping or Sequence, got {type(value).__name__}")

	def _init_from_mapping(self, s: FilterMappingSpec, doctype: Doct) -> None:
		for k, v in s.items():
			if isinstance(v, _InputValue):
				self.append(FilterTuple(doctype=doctype, fieldname=k, value=v))
			elif isinstance(v, Sequence):  # type: ignore[redundant-expr]
				self.append(FilterTuple(doctype=doctype, fieldname=k, operator=v[0], value=v[1]))
			else:
				raise ValueError(f"Invalid value for key '{k}': expected value or (operator, value[s]) tuple")

	def optimize(self) -> None:
		"""Optimize the filters by grouping '=' operators into 'in' operators where possible."""

		def group_key(f: FilterTuple) -> tuple[str, str, bool]:
			return (f.doctype, f.fieldname, f.operator == "=")

		optimized = Filters()
		for (doctype, fieldname, collatable), filters in groupby(sorted(self, key=group_key), key=group_key):
			if not collatable:
				optimized.extend(filters)
			else:

				def _values() -> Generator[_Value, None, None]:
					for f in filters:
						# f.value is already narrowed to Val when we optimize over fully initialized FilterTuple
						yield cast(_Value, f.value)  # = operator only is allowed to have _Value

				values = tuple(_values())

				_op = "in" if len(values) > 1 else "="
				optimized.append(
					FilterTuple(
						doctype=doctype,
						fieldname=fieldname,
						operator=_op,
						value=values if _op == "in" else values[0],
					)
				)
		self[:] = optimized

	@override
	def __str__(self) -> str:
		if not self:
			return "Filters()"

		filters_str = "\n".join(f"  {filter}" for filter in self)
		return f"Filters(\n{filters_str}\n)"


FilterSignature: TypeAlias = Filters | FilterTuple | FilterMappingSpec | FilterTupleSpec
