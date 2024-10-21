import textwrap
from collections import defaultdict
from collections.abc import Generator, Iterable, Mapping, Sequence
from datetime import date, datetime
from itertools import groupby
from operator import attrgetter
from typing import Any, NamedTuple, TypeAlias, TypeGuard, TypeVar, cast

from pypika import Column
from typing_extensions import Self, override

from frappe.model.document import DocRef

Doct: TypeAlias = str
Fld: TypeAlias = str
Op: TypeAlias = str
DateTime: TypeAlias = datetime | date
_Val: TypeAlias = str | int | None | DateTime | Column
_InVal: TypeAlias = _Val | DocRef | bool
Val: TypeAlias = _Val | Sequence[_Val]
InVal: TypeAlias = _InVal | Sequence[_InVal]


FilterTupleSpec: TypeAlias = tuple[Fld, InVal] | tuple[Fld, Op, InVal] | tuple[Doct, Fld, Op, InVal]
FilterMappingSpec: TypeAlias = Mapping[Fld, _InVal | tuple[Op, InVal]]


class Sentinel:
	def __bool__(self) -> bool:
		return False

	@override
	def __str__(self) -> str:
		return "UNSPECIFIED"


UNSPECIFIED = Sentinel()

T = TypeVar("T")


def is_not_unspecified(value: T | Sentinel) -> TypeGuard[T]:
	return value is not UNSPECIFIED


class _FilterTuple(NamedTuple):
	doctype: Doct
	fieldname: Fld
	operator: Op
	value: Val


def _type_narrow(v: _InVal) -> _Val:
	if isinstance(v, bool):  # beware: bool derives int in _Val
		return int(v)
	elif isinstance(v, _Val):
		return v
	elif isinstance(v, DocRef):  # type: ignore[redundant-expr]
		return v.__value__()
	else:
		raise ValueError(
			f"Value must be one of types: {', '.join(str(t.__name__) for t in _InVal.__args__)}; found {type(v)}"
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
		value: InVal | Sentinel = UNSPECIFIED,
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
				else:
					raise ValueError(f"Invalid sequence length: {len(s)}. Expected 2, 3, or 4 elements.")
			if not is_not_unspecified(doctype) or doctype is None:
				raise ValueError("doctype is required")
			if not is_not_unspecified(fieldname) or fieldname is None:
				raise ValueError("fieldname is required")
			if not is_not_unspecified(value):
				raise ValueError("value is required; can be None")

			# soundness
			if operator in ("in", "not in") and isinstance(value, str):
				value = value.split(",")

			_value: Val
			if isinstance(value, _InVal):
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
				f"Error creating Filters:\n"
				f"Input: {s}, doctype={doctype}\n"
				f"Error: {indented_error}\n"
				f"Usage: Filters( FilterTuple(...), ...                                    )\n"
				f"       Filters( (fieldnam, value), ...                        doctype=dt )\n"
				f"       Filters( (fieldname, operator, value), ...             doctype=dt )\n"
				f"       Filters( (doctype, fieldname, operator, value), ...               )\n"
				f"       Filters( {{'fieldname': value, ...}}, ...                doctype=dt )\n"
				f"       Filters( {{'fieldname': (operator, value), ...}}, ...    doctype=dt )"
			)
			raise ValueError(error_context) from e

		if self:  # only optimize non-empty; avoid infinit recursion
			self.optimize()

		if __debug__:
			print(self)

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
			if not is_not_unspecified(doctype) or doctype is None:
				raise ValueError("When initiated with a mapping, doctype keyword argument is required")
			self._init_from_mapping(value, doctype)
		elif isinstance(value, Sequence):  # type: ignore[redundant-expr]
			super().append(FilterTuple(value, doctype=doctype))
		else:
			raise TypeError(f"Expected FilterTruple, Mapping or Sequence, got {type(value).__name__}")

	def _init_from_mapping(self, s: FilterMappingSpec, doctype: Doct) -> None:
		for k, v in s.items():
			if isinstance(v, _InVal):
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

				def _values() -> Generator[_Val, None, None]:
					for f in filters:
						# f.value is already narrowed to Val when we optimize over fully initialized FilterTuple
						yield cast(_Val, f.value)  # = operator only is allowed to have _Val

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
