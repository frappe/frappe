import textwrap
from collections import defaultdict
from collections.abc import Generator, Mapping, Sequence
from itertools import groupby
from operator import attrgetter
from typing import Any, NamedTuple, TypeAlias

from typing_extensions import Self, override

from .docref import DocRef

Doct: TypeAlias = str
Fld: TypeAlias = str
Op: TypeAlias = str
_Val: TypeAlias = str | int | DocRef
Val: TypeAlias = _Val | Sequence[_Val]

FilterTupleSpec: TypeAlias = tuple[Fld, Val] | tuple[Fld, Op, Val] | tuple[Doct, Fld, Op, Val]
FilterMappingSpec: TypeAlias = Mapping[Fld, _Val | tuple[Op, Val]]


class _FilterTuple(NamedTuple):
	doctype: Doct
	fieldname: Fld
	operator: Op
	value: Val


class FilterTuple(_FilterTuple):
	"""A named tuple representing a filter condition."""

	def __new__(
		cls,
		s: FilterTupleSpec | None = None,
		/,
		*,
		doctype: Doct | None = None,
		fieldname: Fld | None = None,
		operator: Op = "=",
		value: Val | None = None,
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
			if not doctype:
				raise ValueError("doctype is required")
			if not fieldname:
				raise ValueError("fieldname is required")
			if not operator:
				raise ValueError("operator is required")
			if not value:
				raise ValueError("value is required")
			return super().__new__(cls, doctype=doctype, fieldname=fieldname, operator=operator, value=value)
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
		s: Sequence[FilterTuple | FilterTupleSpec] | FilterMappingSpec | FilterTuple,
		/,
		*,
		doctype: Doct | None = None,
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
			if isinstance(s, FilterTuple):
				self.append(s)
			elif isinstance(s, Mapping):
				if doctype is None:
					raise ValueError("When initiated with a mapping, doctype keyword argument is required")
				self._init_from_mapping(s, doctype)
			elif isinstance(s, Sequence):  # type: ignore[redundant-expr]
				assert not isinstance(s, FilterTuple)  # type narrowing
				self._init_from_sequence(s, doctype)
			else:
				raise TypeError(f"Expected Mapping or Sequence, got {type(s).__name__}")
		except Exception as e:
			error_lines = str(e).split("\n")
			indented_error = error_lines[0] + "\n" + textwrap.indent("\n".join(error_lines[1:]), "       ")
			error_context = (
				f"Error creating Filters:\n"
				f"Input: {s}, doctype={doctype}\n"
				f"Error: {indented_error}\n"
				f"Usage: Filters( [ FilterTuple(...), ... ]                            )\n"
				f"       Filters( [ (fieldnam, value), ... ],                  doctype=dt )\n"
				f"       Filters( [ (fieldname, operator, value), ... ],        doctype=dt )\n"
				f"       Filters( [ (doctype, fieldname, operator, value), ... ]           )\n"
				f"       Filters( {{'fieldname': value, ...}},                    doctype=dt )\n"
				f"       Filters( {{'fieldname': (operator, value), ...}},        doctype=dt )"
			)
			raise ValueError(error_context) from e

		self.optimize()

	def _init_from_mapping(self, s: FilterMappingSpec, doctype: Doct) -> None:
		for k, v in s.items():
			if isinstance(v, _Val):
				self.append(FilterTuple(doctype=doctype, fieldname=k, value=v))
			elif isinstance(v, Sequence):  # type: ignore[redundant-expr]
				self.append(FilterTuple(doctype=doctype, fieldname=k, operator=v[0], value=v[1]))
			else:
				raise ValueError(f"Invalid value for key '{k}': expected value or (operator, value[s]) tuple")

	def _init_from_sequence(self, s: Sequence[FilterTuple | FilterTupleSpec], doctype: Doct | None) -> None:
		for i in s:
			if isinstance(i, FilterTuple):
				self.append(i)
			elif isinstance(i, Sequence):  # type: ignore[redundant-expr]
				self.append(FilterTuple(i, doctype=doctype))
			else:
				raise TypeError(f"Expected FilterTuple or Sequence, got {type(i).__name__}")

	def optimize(self) -> None:
		"""Optimize the filters by grouping '=' operators into 'in' operators where possible."""

		def group_key(f: FilterTuple) -> tuple[str, str, str]:
			return (f.doctype, f.fieldname, f.operator)

		optimized = Filters([])
		for (doctype, fieldname, operator), filters in groupby(sorted(self, key=group_key), key=group_key):
			if operator != "=":
				optimized.extend(filters)
			else:

				def _values() -> Generator[_Val, None, None]:
					for f in filters:
						if isinstance(f.value, Sequence):
							yield from f.value
						else:
							yield f.value

				optimized.append(
					FilterTuple(doctype=doctype, fieldname=fieldname, operator="in", value=tuple(_values()))
				)
		self[:] = optimized

	@override
	def __str__(self) -> str:
		if not self:
			return "Filters()"

		filters_str = "\n".join(f"  {filter}" for filter in self)
		return f"Filters(\n{filters_str}\n)"


FilterSignature: TypeAlias = Filters | FilterTuple | FilterMappingSpec | FilterTupleSpec
