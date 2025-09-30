import re
from functools import lru_cache
from typing import TYPE_CHECKING, Any

import sqlparse
from pypika.queries import QueryBuilder, Table
from pypika.terms import AggregateFunction, Term

import frappe
from frappe import _
from frappe.database.operator_map import NESTED_SET_OPERATORS, OPERATOR_MAP
from frappe.database.utils import DefaultOrderBy, FilterValue, convert_to_value, get_doctype_name
from frappe.model import get_permitted_fields
from frappe.query_builder import Criterion, Field, Order, functions
from frappe.query_builder.utils import PseudoColumnMapper
from frappe.utils.data import MARIADB_SPECIFIC_COMMENT

if TYPE_CHECKING:
	from frappe.query_builder import DocType

TAB_PATTERN = re.compile("^tab")
WORDS_PATTERN = re.compile(r"\w+")
COMMA_PATTERN = re.compile(r",\s*(?![^()]*\))")

# less restrictive version of frappe.core.doctype.doctype.doctype.START_WITH_LETTERS_PATTERN
# to allow table names like __Auth
TABLE_NAME_PATTERN = re.compile(r"^[\w -]*$", flags=re.ASCII)

# Pattern to validate field names in SELECT:
# Allows: name, `name`, name as alias, `name` as alias, `table name`.`name`, `table name`.`name` as alias, table.name, table.name as alias
ALLOWED_FIELD_PATTERN = re.compile(r"^(?:(`[\w\s-]+`|\w+)\.)?(`\w+`|\w+)(?:\s+as\s+\w+)?$", flags=re.ASCII)

# Regex to parse field names:
# Group 1: Optional quote for table name
# Group 2: Optional table name (e.g., `tabDocType` or tabDocType or `tabNote Seen By`)
# Group 3: Optional quote for field name
# Group 4: Field name (e.g., `field` or field)
FIELD_PARSE_REGEX = re.compile(r"^(?:([`\"]?)(tab[\w\s-]+)\1\.)?([`\"]?)(\w+)\3$")

# Direct mapping from uppercase function names to pypika function classes
FUNCTION_MAPPING = {
	"COUNT": functions.Count,
	"SUM": functions.Sum,
	"AVG": functions.Avg,
	"MAX": functions.Max,
	"MIN": functions.Min,
	"ABS": functions.Abs,
	"EXTRACT": functions.Extract,
	"LOCATE": functions.Locate,
	"TIMESTAMP": functions.Timestamp,
	"IFNULL": functions.IfNull,
	"CONCAT": functions.Concat,
	"NOW": functions.Now,
}


class Engine:
	def get_query(
		self,
		table: str | Table,
		fields: str | list | tuple | None = None,
		filters: dict[str, FilterValue] | FilterValue | list[list | FilterValue] | None = None,
		order_by: str | None = None,
		group_by: str | None = None,
		limit: int | None = None,
		offset: int | None = None,
		distinct: bool = False,
		for_update: bool = False,
		update: bool = False,
		into: bool = False,
		delete: bool = False,
		*,
		validate_filters: bool = False,
		skip_locked: bool = False,
		wait: bool = True,
		ignore_permissions: bool = True,
		user: str | None = None,
		parent_doctype: str | None = None,
	) -> QueryBuilder:
		qb = frappe.local.qb
		db_type = frappe.local.db.db_type

		self.is_mariadb = db_type == "mariadb"
		self.is_postgres = db_type == "postgres"
		self.is_sqlite = db_type == "sqlite"
		self.validate_filters = validate_filters
		self.user = user or frappe.session.user
		self.parent_doctype = parent_doctype
		self.apply_permissions = not ignore_permissions

		if isinstance(table, Table):
			self.table = table
			self.doctype = get_doctype_name(table.get_sql())
		else:
			self.doctype = table
			self.validate_doctype()
			self.table = qb.DocType(table)

		if self.apply_permissions:
			self.check_read_permission()

		if update:
			self.query = qb.update(self.table, immutable=False)
		elif into:
			self.query = qb.into(self.table, immutable=False)
		elif delete:
			self.query = qb.from_(self.table, immutable=False).delete()
		else:
			self.query = qb.from_(self.table, immutable=False)
			self.apply_fields(fields)

		self.apply_filters(filters)

		if limit:
			if not isinstance(limit, int) or limit < 0:
				frappe.throw(_("Limit must be a non-negative integer"), TypeError)
			self.query = self.query.limit(limit)

		if offset:
			if not isinstance(offset, int) or offset < 0:
				frappe.throw(_("Offset must be a non-negative integer"), TypeError)
			self.query = self.query.offset(offset)

		if distinct:
			self.query = self.query.distinct()

		if for_update:
			self.query = self.query.for_update(skip_locked=skip_locked, nowait=not wait)

		if group_by:
			self.apply_group_by(group_by)

		if order_by:
			self.apply_order_by(order_by)

		if self.apply_permissions:
			self.add_permission_conditions()

		self.query.immutable = True
		return self.query

	def validate_doctype(self):
		if not TABLE_NAME_PATTERN.match(self.doctype):
			frappe.throw(_("Invalid DocType: {0}").format(self.doctype))

	def apply_fields(self, fields):
		self.fields = self.parse_fields(fields)
		if self.apply_permissions:
			self.fields = self.apply_field_permissions()

		if not self.fields:
			self.fields = [self.table.name]

		self.query._child_queries = []
		for field in self.fields:
			if isinstance(field, DynamicTableField):
				self.query = field.apply_select(self.query)
			elif isinstance(field, ChildQuery):
				self.query._child_queries.append(field)
			else:
				self.query = self.query.select(field)

	def apply_filters(
		self,
		filters: dict[str, FilterValue] | FilterValue | list[list | FilterValue] | None = None,
	):
		if filters is None:
			return

		if isinstance(filters, FilterValue):
			filters = {"name": convert_to_value(filters)}

		if isinstance(filters, Criterion):
			self.query = self.query.where(filters)
			return

		if isinstance(filters, dict):
			self.apply_dict_filters(filters)
			return

		if isinstance(filters, list | tuple):
			if not filters:
				return

			# 1. Handle special case: list of names -> name IN (...)
			if all(isinstance(d, FilterValue) for d in filters):
				self.apply_dict_filters({"name": ("in", tuple(convert_to_value(f) for f in filters))})
				return

			# 2. Check for nested logic format [cond, op, cond, ...] or [[cond, op, cond]]
			is_nested_structure = False
			potential_nested_list = filters
			is_single_group = False

			# Check for single grouped condition [[cond_a, op, cond_b]]
			if len(filters) == 1 and isinstance(filters[0], list | tuple):
				inner_list = filters[0]
				# Ensure inner list also looks like a nested structure
				# Check if the operator is a string, validation happens inside _parse_nested_filters
				if len(inner_list) >= 3 and isinstance(inner_list[1], str):
					is_nested_structure = True
					potential_nested_list = inner_list  # Use the inner list for validation and parsing
					is_single_group = True  # Flag that the original filters was wrapped

			# Check for standard nested structure [cond, op, cond, ...]
			# Check if it looks like it *might* be nested (even if malformed).
			# This allows lists starting with operators or containing invalid operators
			# to be passed to _parse_nested_filters for detailed validation.
			# Condition: Contains a string at an odd index OR starts with a string.
			elif any(isinstance(item, str) for i, item in enumerate(filters) if i % 2 != 0) or (
				len(filters) > 0 and isinstance(filters[0], str)
			):
				is_nested_structure = True
				# potential_nested_list remains filters

			if is_nested_structure:
				# If validation passes, proceed with parsing the identified nested list
				try:
					# If it's a single group like [[cond]], parse the inner list as one condition.
					# Otherwise, parse the list as a sequence [cond1, op, cond2, ...].
					if is_single_group:
						combined_criterion = self._condition_to_criterion(potential_nested_list)
					else:
						# _parse_nested_filters MUST validate the structure, including the first element and operators.
						combined_criterion = self._parse_nested_filters(potential_nested_list)
					if combined_criterion:
						self.query = self.query.where(combined_criterion)
				except Exception as e:
					# Log the original filters list for better debugging context
					frappe.log_error(f"Filter parsing error: {filters}", "Query Engine Error")
					frappe.throw(_("Error parsing nested filters: {0}").format(e), exc=e)

			else:  # Not a nested structure, assume it's a list of simple filters (implicitly ANDed)
				for filter_item in filters:
					if isinstance(filter_item, list | tuple):
						self.apply_list_filters(filter_item)  # Handles simple [field, op, value] lists
					elif isinstance(filter_item, dict | Criterion):
						self.apply_filters(filter_item)  # Recursive call for dict/criterion
					else:
						# Disallow single values (strings, numbers, etc.) directly in the list
						# unless it's the name IN (...) case handled above.
						raise ValueError(
							f"Invalid item type in filter list: {type(filter_item).__name__}. Expected list, tuple, dict, or Criterion."
						)
			return

		# If filters type is none of the above
		raise ValueError(f"Unsupported filters type: {type(filters).__name__}")

	def apply_list_filters(self, filter: list):
		if len(filter) == 2:
			field, value = filter
			self._apply_filter(field, value)
		elif len(filter) == 3:
			field, operator, value = filter
			self._apply_filter(field, value, operator)
		elif len(filter) == 4:
			doctype, field, operator, value = filter
			self._apply_filter(field, value, operator, doctype)
		else:
			raise ValueError(f"Unknown filter format: {filter}")

	def apply_dict_filters(self, filters: dict[str, FilterValue | list]):
		for field, value in filters.items():
			operator = "="
			if isinstance(value, list | tuple):
				operator, value = value

			self._apply_filter(field, value, operator)

	def _apply_filter(
		self,
		field: str | Field,
		value: FilterValue | list | set | None,
		operator: str = "=",
		doctype: str | None = None,
	):
		"""Applies a simple filter condition to the query."""
		criterion = self._build_criterion_for_simple_filter(field, value, operator, doctype)
		if criterion:
			self.query = self.query.where(criterion)

	def _build_criterion_for_simple_filter(
		self,
		field: str | Field,
		value: FilterValue | list | set | None,
		operator: str = "=",
		doctype: str | None = None,
	) -> "Criterion | None":
		"""Builds a pypika Criterion object for a simple filter condition."""
		_field = self._validate_and_prepare_filter_field(field, doctype)
		_value = convert_to_value(value)
		_operator = operator

		if not _value and isinstance(_value, list | tuple | set):
			_value = ("",)

		if _operator in NESTED_SET_OPERATORS:
			hierarchy = _operator
			docname = _value

			# Use the original field name string for get_field if _field was converted
			# If _field is from a dynamic field, its name might be just the target fieldname.
			# We need the original string ('link.target') or the fieldname from the main doctype.
			original_field_name = field if isinstance(field, str) else _field.name
			# Check if the original field name exists in the *main* doctype meta
			main_meta = frappe.get_meta(self.doctype)
			if main_meta.has_field(original_field_name):
				_df = main_meta.get_field(original_field_name)
				ref_doctype = _df.options if _df else self.doctype
			else:
				# If not in main doctype, assume it's a standard field like 'name' or refers to the main doctype itself
				# This part might need refinement if nested set operators are used with dynamic fields.
				ref_doctype = self.doctype

			nodes = get_nested_set_hierarchy_result(ref_doctype, docname, hierarchy)
			operator_fn = (
				OPERATOR_MAP["not in"]
				if hierarchy in ("not ancestors of", "not descendants of")
				else OPERATOR_MAP["in"]
			)
			return operator_fn(_field, nodes or ("",))

		operator_fn = OPERATOR_MAP[_operator.casefold()]
		if _value is None and isinstance(_field, Field):
			return _field.isnull()
		else:
			return operator_fn(_field, _value)

	def _parse_nested_filters(self, nested_list: list | tuple) -> "Criterion | None":
		"""Parses a nested filter list like [cond1, 'and', cond2, 'or', cond3, ...] into a pypika Criterion."""
		if not isinstance(nested_list, list | tuple):
			frappe.throw(_("Nested filters must be provided as a list or tuple."))

		if not nested_list:
			return None

		# First item must be a condition (list/tuple)
		if not isinstance(nested_list[0], list | tuple):
			frappe.throw(
				_("Invalid start for filter condition: {0}. Expected a list or tuple.").format(nested_list[0])
			)

		current_criterion = self._condition_to_criterion(nested_list[0])

		idx = 1
		while idx < len(nested_list):
			# Expect an operator ('and' or 'or')
			operator_str = nested_list[idx]
			if not isinstance(operator_str, str) or operator_str.lower() not in ("and", "or"):
				frappe.throw(
					_("Expected 'and' or 'or' operator, found: {0}").format(operator_str),
					frappe.ValidationError,
				)

			idx += 1
			if idx >= len(nested_list):
				frappe.throw(_("Filter condition missing after operator: {0}").format(operator_str))

			# Expect a condition (list/tuple)
			next_condition = nested_list[idx]
			if not isinstance(next_condition, list | tuple):
				frappe.throw(
					_("Invalid filter condition: {0}. Expected a list or tuple.").format(next_condition)
				)

			next_criterion = self._condition_to_criterion(next_condition)

			if operator_str.lower() == "and":
				current_criterion = current_criterion & next_criterion
			elif operator_str.lower() == "or":
				current_criterion = current_criterion | next_criterion

			idx += 1

		return current_criterion

	def _condition_to_criterion(self, condition: list | tuple) -> "Criterion":
		"""Converts a single condition (simple filter list or nested list) into a pypika Criterion."""
		if not isinstance(condition, list | tuple):
			frappe.throw(_("Invalid condition type in nested filters: {0}").format(type(condition)))

		# Check if it's a nested condition list [cond1, op, cond2, ...]
		is_nested = False
		# Broaden check here as well: length >= 3 and second element is string
		if len(condition) >= 3 and isinstance(condition[1], str):
			if isinstance(condition[0], list | tuple):  # First element must also be a condition
				is_nested = True

		if is_nested:
			# It's a nested sub-expression like [["assignee", "=", "A"], "or", ["assignee", "=", "B"]]
			# _parse_nested_filters will handle operator validation ('and'/'or')
			return self._parse_nested_filters(condition)
		else:
			# Assume it's a simple filter [field, op, value] etc.
			field, value, operator, doctype = None, None, None, None

			# Determine structure based on length and types
			if len(condition) == 3 and isinstance(condition[1], str) and condition[1] in OPERATOR_MAP:
				# [field, operator, value]
				field, operator, value = condition
			elif len(condition) == 4 and isinstance(condition[2], str) and condition[2] in OPERATOR_MAP:
				# [doctype, field, operator, value]
				doctype, field, operator, value = condition
			elif len(condition) == 2:
				# [field, value] -> implies '=' operator
				field, value = condition
				operator = "="
			else:
				frappe.throw(_("Invalid simple filter format: {0}").format(condition))

			# Use the helper method to build the criterion for the simple filter
			return self._build_criterion_for_simple_filter(field, value, operator, doctype)

	def _validate_and_prepare_filter_field(self, field: str | Field, doctype: str | None = None) -> Field:
		"""Validate field name for filters and return a pypika Field object. Handles dynamic fields."""

		if isinstance(field, Term):
			# return if field is already a pypika Term
			return field

		# Reject backticks
		if "`" in field:
			frappe.throw(
				_("Filter fields cannot contain backticks (`)."),
				frappe.ValidationError,
				title=_("Invalid Filter"),
			)

		# Handle dot notation (link_field.target_field or child_table_field.target_field)
		if "." in field:
			# Disallow tabDoc.field notation in filters.
			dynamic_field = DynamicTableField.parse(field, self.doctype, allow_tab_notation=False)
			if dynamic_field:
				# Parsed successfully as link/child field access
				target_doctype = dynamic_field.doctype
				target_fieldname = dynamic_field.fieldname
				parent_doctype_for_perm = (
					dynamic_field.parent_doctype if isinstance(dynamic_field, ChildTableField) else None
				)
				self._check_field_permission(target_doctype, target_fieldname, parent_doctype_for_perm)

				self.query = dynamic_field.apply_join(self.query)
				# Return the pypika Field object associated with the dynamic field
				return dynamic_field.field
			else:
				# Contains '.' but is not a valid link/child field access pattern
				# This rejects tabDoc.field and other invalid formats like a.b.c
				frappe.throw(
					_(
						"Invalid filter field format: {0}. Use 'fieldname' or 'link_fieldname.target_fieldname'."
					).format(field),
					frappe.ValidationError,
					title=_("Invalid Filter"),
				)
		else:
			# No '.' and no '`'. Check if it's a simple field name (alphanumeric + underscore).
			if not re.fullmatch(r"\w+", field):
				frappe.throw(
					_(
						"Invalid characters in fieldname: {0}. Only letters, numbers, and underscores are allowed."
					).format(field),
					frappe.ValidationError,
					title=_("Invalid Filter"),
				)
			# It's a simple, valid fieldname like 'name' or 'creation'
			target_doctype = doctype or self.doctype
			target_fieldname = field
			parent_doctype_for_perm = self.parent_doctype if doctype else None

			# If a specific doctype is provided and it's different from the main query doctype,
			# assume it's a child table and add the join using ChildTableField logic.
			if doctype and doctype != self.doctype:
				# Check if doctype is a valid child table of self.doctype
				parent_meta = frappe.get_meta(self.doctype)
				# Find the parent fieldname for this child doctype
				parent_fieldname = None
				for df in parent_meta.get_table_fields():
					if df.options == doctype:
						parent_fieldname = df.fieldname
						break

				if not parent_fieldname:
					frappe.throw(
						_("{0} is not a child table of {1}").format(doctype, self.doctype),
						frappe.ValidationError,
						title=_("Invalid Filter"),
					)

				# Create a ChildTableField instance to handle join and field access
				# Pass the identified parent_fieldname
				child_field_handler = ChildTableField(
					doctype=doctype,
					fieldname=target_fieldname,
					parent_doctype=self.doctype,
					parent_fieldname=parent_fieldname,
				)

				# For permission check, the parent is the main doctype
				parent_doctype_for_perm = self.doctype
				self._check_field_permission(target_doctype, target_fieldname, parent_doctype_for_perm)

				# Delegate join logic
				self.query = child_field_handler.apply_join(self.query)
				# Return the pypika Field object from the handler
				return child_field_handler.field
			else:
				# Field belongs to the main doctype or doctype wasn't specified differently
				self._check_field_permission(target_doctype, target_fieldname, parent_doctype_for_perm)
				# Convert string field name to pypika Field object for the specified/current doctype
				return frappe.qb.DocType(target_doctype)[target_fieldname]

	def _check_field_permission(self, doctype: str, fieldname: str, parent_doctype: str | None = None):
		"""Check if the user has permission to access the given field"""
		if not self.apply_permissions:
			return

		permission_type = self.get_permission_type(doctype)
		permitted_fields = get_permitted_fields(
			doctype=doctype,
			parenttype=parent_doctype,
			permission_type=permission_type,
			ignore_virtual=True,
			user=self.user,
		)

		if fieldname not in permitted_fields:
			frappe.throw(
				_("You do not have permission to access field: {0}").format(
					frappe.bold(f"{doctype}.{fieldname}")
				),
				frappe.PermissionError,
				title=_("Permission Error"),
			)

	def parse_string_field(self, field: str):
		"""
		Parses a field string into a pypika Field object.

		Handles:
		- *
		- simple_field
		- `quoted_field`
		- tabDocType.simple_field
		- `tabDocType`.`quoted_field`
		- `tabTable Name`.`quoted_field`
		- Aliases for all above formats (e.g., field as alias)
		"""
		if field == "*":
			return self.table.star

		alias = None
		field_part = field
		if " as " in field.lower():  # Case-insensitive check for ' as '
			# Find the last occurrence of ' as ' to handle potential aliases named 'as'
			parts = re.split(r"\s+as\s+", field, flags=re.IGNORECASE)
			if len(parts) > 1:
				field_part = parts[0].strip()
				alias = parts[1].strip().strip('`"')  # Remove potential quotes from alias

		match = FIELD_PARSE_REGEX.match(field_part)

		if not match:
			frappe.throw(_("Could not parse field: {0}").format(field))

		# Groups: 1: table_quote, 2: table_name_with_tab, 3: field_quote, 4: field_name
		groups = match.groups()
		table_name = groups[1]  # This will be None if no table part (e.g., just 'field')
		field_name = groups[3]  # This will be the field name (e.g., 'field')

		if table_name:
			# Table name specified (e.g., `tabX`.`y` or tabX.y or `tabX Y`.`y`)
			# Ensure the extracted table name is valid before creating DocType object
			if not TABLE_NAME_PATTERN.match(table_name.lstrip("tab")):
				frappe.throw(_("Invalid characters in table name: {0}").format(table_name))
			table_obj = frappe.qb.DocType(table_name)
			pypika_field = table_obj[field_name]
		else:
			# Simple field name (e.g., `y` or y) - use the main table
			pypika_field = self.table[field_name]

		if alias:
			return pypika_field.as_(alias)
		else:
			return pypika_field

	def parse_fields(
		self, fields: str | list | tuple | Field | AggregateFunction | None
	) -> "list[Field | AggregateFunction | Criterion | DynamicTableField | ChildQuery]":
		if not fields:
			return []

		# return if fields is already a pypika Term
		if isinstance(fields, Term):
			return [fields]

		initial_field_list = []
		if isinstance(fields, str):
			# Split comma-separated fields passed as a single string
			initial_field_list.extend(f.strip() for f in COMMA_PATTERN.split(fields) if f.strip())
		elif isinstance(fields, list | tuple):
			for item in fields:
				if isinstance(item, str) and "," in item:
					# Split comma-separated strings within the list
					initial_field_list.extend(f.strip() for f in COMMA_PATTERN.split(item) if f.strip())
				else:
					# Add non-comma-separated items directly
					initial_field_list.append(item)

		else:
			frappe.throw(_("Fields must be a string, list, tuple, pypika Field, or pypika Function"))

		_fields = []
		# Iterate through the list where each item could be a single field, criterion, or a comma-separated string
		for item in initial_field_list:
			if isinstance(item, str):
				# Sanitize and split potentially comma-separated strings within the list
				sanitized_item = _sanitize_field(item.strip(), self.is_mariadb).strip()
				if sanitized_item:
					parsed = self._parse_single_field_item(sanitized_item)
					if isinstance(parsed, list):  # Result from parsing a child query dict
						_fields.extend(parsed)
					elif parsed:
						_fields.append(parsed)
			else:
				# Handle non-string items (like dict for child query, or pre-parsed Field/Function)
				parsed = self._parse_single_field_item(item)
				if isinstance(parsed, list):
					_fields.extend(parsed)
				elif parsed:
					_fields.append(parsed)

		return _fields

	def _parse_single_field_item(
		self, field: str | Criterion | dict | Field
	) -> "list | Criterion | Field | DynamicTableField | ChildQuery | None":
		"""Parses a single item from the fields list/tuple. Assumes comma-separated strings have already been split."""
		if isinstance(field, Criterion | Field):
			return field
		elif isinstance(field, dict):
			# Check if it's a SQL function dictionary
			function_parser = SQLFunctionParser(engine=self)
			if function_parser.is_function_dict(field):
				return function_parser.parse_function(field)
			else:
				# Handle child queries defined as dicts {fieldname: [child_fields]}
				_parsed_fields = []
				for child_field, child_fields_list in field.items():
					# Skip uppercase keys as they might be unsupported SQL functions
					if child_field.isupper():
						frappe.throw(
							_("Unsupported function or invalid field name: {0}").format(child_field),
							frappe.ValidationError,
						)

					# Ensure child_fields_list is a list or tuple
					if not isinstance(child_fields_list, list | tuple):
						frappe.throw(
							_("Child query fields for '{0}' must be a list or tuple.").format(child_field)
						)
					_parsed_fields.append(ChildQuery(child_field, list(child_fields_list), self.doctype))
				# Return list as a dict entry might represent multiple child queries (though unlikely)
				return _parsed_fields

		# At this point, field must be a string (already validated and sanitized)
		if not isinstance(field, str):
			frappe.throw(_("Invalid field type: {0}").format(type(field)))

		# Try parsing as dynamic field (link/child table access)
		if parsed := DynamicTableField.parse(field, self.doctype):
			return parsed
		# Otherwise, parse as a standard field (simple, quoted, table-qualified, with/without alias)
		else:
			# Note: Comma handling is done in parse_fields before this method is called
			return self.parse_string_field(field)

	def apply_group_by(self, group_by: str | None = None):
		parsed_group_by_fields = self._validate_group_by(group_by)
		self.query = self.query.groupby(*parsed_group_by_fields)

	def apply_order_by(self, order_by: str | None):
		if not order_by or order_by == DefaultOrderBy:
			return

		parsed_order_fields = self._validate_order_by(order_by)
		for order_field, order_direction in parsed_order_fields:
			self.query = self.query.orderby(order_field, order=order_direction)

	def _validate_and_parse_field_for_clause(self, field_name: str, clause_name: str) -> Field:
		"""
		Common helper to validate and parse field names for GROUP BY and ORDER BY clauses.

		Args:
			field_name: The field name to validate and parse
			clause_name: Name of the SQL clause (for error messages) - 'Group By' or 'Order By'

		Returns:
			Parsed Field object ready for use in pypika query
		"""
		if field_name.isdigit():
			# For numeric field references, return as-is (will be handled by caller)
			return field_name

		# Reject backticks
		if "`" in field_name:
			frappe.throw(
				_("{0} fields cannot contain backticks (`): {1}").format(clause_name, field_name),
				frappe.ValidationError,
			)

		# Try parsing as dynamic field (link_field.field or child_table.field)
		dynamic_field = DynamicTableField.parse(field_name, self.doctype, allow_tab_notation=False)
		if dynamic_field:
			# Check permissions for dynamic field
			if self.apply_permissions:
				if isinstance(dynamic_field, ChildTableField):
					self._check_field_permission(
						dynamic_field.doctype, dynamic_field.fieldname, dynamic_field.parent_doctype
					)
				elif isinstance(dynamic_field, LinkTableField):
					# Check permission for the link field in parent doctype
					self._check_field_permission(self.doctype, dynamic_field.link_fieldname)
					# Check permission for the target field in linked doctype
					self._check_field_permission(dynamic_field.doctype, dynamic_field.fieldname)

			# Apply join for the dynamic field
			self.query = dynamic_field.apply_join(self.query)
			return dynamic_field.field
		else:
			# Validate as simple field name (alphanumeric + underscore only)
			if not re.fullmatch(r"\w+", field_name):
				frappe.throw(
					_(
						"Invalid field format in {0}: {1}. Use 'field', 'link_field.field', or 'child_table.field'."
					).format(clause_name, field_name),
					frappe.ValidationError,
				)

			# Check permissions for simple field
			if self.apply_permissions:
				self._check_field_permission(self.doctype, field_name)

			# Create Field object for simple field
			return self.table[field_name]

	def _validate_group_by(self, group_by: str) -> list[Field]:
		"""Validate the group_by string argument, apply joins for dynamic fields, and return parsed Field objects."""
		if not isinstance(group_by, str):
			frappe.throw(_("Group By must be a string"), TypeError)

		parsed_fields = []
		parts = COMMA_PATTERN.split(group_by)
		for part in parts:
			field_name = part.strip()
			if not field_name:
				continue

			parsed_field = self._validate_and_parse_field_for_clause(field_name, "Group By")
			parsed_fields.append(parsed_field)

		return parsed_fields

	def _validate_order_by(self, order_by: str) -> list[tuple[Field | str, Order]]:
		"""Validate the order_by string argument, apply joins for dynamic fields, and return parsed Field objects with directions."""
		if not isinstance(order_by, str):
			frappe.throw(_("Order By must be a string"), TypeError)

		valid_directions = {"asc", "desc"}
		parsed_order_fields = []

		for declaration in order_by.split(","):
			if _order_by := declaration.strip():
				parts = _order_by.split()
				field_name = parts[0]
				direction = None
				if len(parts) > 1:
					direction = parts[1].lower()

				order_direction = Order.asc if direction == "asc" else Order.desc

				parsed_field = self._validate_and_parse_field_for_clause(field_name, "Order By")
				parsed_order_fields.append((parsed_field, order_direction))

				if direction and direction not in valid_directions:
					frappe.throw(
						_("Invalid direction in Order By: {0}. Must be 'ASC' or 'DESC'.").format(parts[1]),
						ValueError,
					)

		return parsed_order_fields

	def check_read_permission(self):
		"""Check if user has read permission on the doctype"""

		def has_permission(ptype):
			return frappe.has_permission(
				self.doctype,
				ptype,
				user=self.user,
				parent_doctype=self.parent_doctype,
			)

		if not has_permission("select") and not has_permission("read"):
			frappe.throw(
				_("Insufficient Permission for {0}").format(frappe.bold(self.doctype)), frappe.PermissionError
			)

	def apply_field_permissions(self):
		"""Filter the list of fields based on permlevel."""
		allowed_fields = []
		parent_permission_type = self.get_permission_type(self.doctype)
		permitted_fields_cache = {}

		def get_cached_permitted_fields(doctype, parenttype, permission_type):
			cache_key = (doctype, parenttype, permission_type)
			if cache_key not in permitted_fields_cache:
				permitted_fields_cache[cache_key] = set(
					get_permitted_fields(
						doctype=doctype,
						parenttype=parenttype,
						permission_type=permission_type,
						ignore_virtual=True,
					)
				)
			return permitted_fields_cache[cache_key]

		permitted_fields_set = get_cached_permitted_fields(
			self.doctype, self.parent_doctype, parent_permission_type
		)

		for field in self.fields:
			if isinstance(field, ChildTableField):
				if parent_permission_type == "select":
					# Skip child table fields if parent permission is only 'select'
					continue

				# Cache permitted fields for child doctypes if accessed multiple times
				permitted_child_fields_set = get_cached_permitted_fields(
					field.doctype, field.parent_doctype, self.get_permission_type(field.doctype)
				)
				# Check permission for the specific field in the child table
				if field.fieldname in permitted_child_fields_set:
					allowed_fields.append(field)
			elif isinstance(field, LinkTableField):
				# Check permission for the link field *in the parent doctype*
				if field.link_fieldname in permitted_fields_set:
					# Also check if user has permission to read/select the target doctype
					target_doctype = field.doctype
					has_target_perm = frappe.has_permission(
						target_doctype, "select", user=self.user
					) or frappe.has_permission(target_doctype, "read", user=self.user)

					if has_target_perm:
						# Finally, check if the specific field *in the target doctype* is permitted
						permitted_target_fields_set = get_cached_permitted_fields(
							target_doctype, None, self.get_permission_type(target_doctype)
						)
						if field.fieldname in permitted_target_fields_set:
							allowed_fields.append(field)
			elif isinstance(field, ChildQuery):
				if parent_permission_type == "select":
					# Skip child queries if parent permission is only 'select'
					continue

				# Cache permitted fields for the child doctype of the query
				permitted_child_fields_set = get_cached_permitted_fields(
					field.doctype, field.parent_doctype, self.get_permission_type(field.doctype)
				)
				# Filter the fields *within* the ChildQuery object based on permissions
				field.fields = [f for f in field.fields if f in permitted_child_fields_set]
				# Only add the child query if it still has fields after filtering
				if field.fields:
					allowed_fields.append(field)
			elif isinstance(field, Field):
				if field.name == "*":
					# Expand '*' to include all permitted fields
					# Avoid reparsing '*' recursively by passing the actual list
					allowed_fields.extend(self.parse_fields(list(permitted_fields_set)))
				# Check if the field name (without alias) is permitted
				elif field.name in permitted_fields_set:
					allowed_fields.append(field)
				# Handle cases where the field might be aliased but the base name is permitted
				elif hasattr(field, "alias") and field.alias and field.name in permitted_fields_set:
					allowed_fields.append(field)

			elif isinstance(field, PseudoColumnMapper):
				# Typically functions or complex terms
				allowed_fields.append(field)

		return allowed_fields

	def get_user_permission_conditions(self, role_permissions):
		"""Build conditions for user permissions and return tuple of (conditions, fetch_shared_docs)"""
		conditions = []
		fetch_shared_docs = False

		# add user permission only if role has read perm
		if not (role_permissions.get("read") or role_permissions.get("select")):
			return conditions, fetch_shared_docs

		user_permissions = frappe.permissions.get_user_permissions(self.user)

		if not user_permissions:
			return conditions, fetch_shared_docs

		fetch_shared_docs = True

		doctype_link_fields = self.get_doctype_link_fields()
		for df in doctype_link_fields:
			if df.get("ignore_user_permissions"):
				continue

			user_permission_values = user_permissions.get(df.get("options"), {})
			if user_permission_values:
				docs = []
				for permission in user_permission_values:
					if not permission.get("applicable_for"):
						docs.append(permission.get("doc"))
					# append docs based on user permission applicable on reference doctype
					# this is useful when getting list of docs from a link field
					# in this case parent doctype of the link
					# will be the reference doctype
					elif df.get("fieldname") == "name" and self.reference_doctype:
						if permission.get("applicable_for") == self.reference_doctype:
							docs.append(permission.get("doc"))
					elif permission.get("applicable_for") == self.doctype:
						docs.append(permission.get("doc"))

				if docs:
					field_name = df.get("fieldname")
					strict_user_permissions = frappe.get_system_settings("apply_strict_user_permissions")
					if strict_user_permissions:
						conditions.append(self.table[field_name].isin(docs))
					else:
						empty_value_condition = self.table[field_name].isnull()
						value_condition = self.table[field_name].isin(docs)
						conditions.append(empty_value_condition | value_condition)

		return conditions, fetch_shared_docs

	def get_doctype_link_fields(self):
		meta = frappe.get_meta(self.doctype)
		# append current doctype with fieldname as 'name' as first link field
		doctype_link_fields = [{"options": self.doctype, "fieldname": "name"}]
		# append other link fields
		doctype_link_fields.extend(meta.get_link_fields())
		return doctype_link_fields

	def add_permission_conditions(self):
		conditions = []
		role_permissions = frappe.permissions.get_role_permissions(self.doctype, user=self.user)
		fetch_shared_docs = False

		if self.requires_owner_constraint(role_permissions):
			fetch_shared_docs = True
			conditions.append(self.table.owner == self.user)
		# skip user perm check if owner constraint is required
		elif role_permissions.get("read") or role_permissions.get("select"):
			user_perm_conditions, fetch_shared = self.get_user_permission_conditions(role_permissions)
			conditions.extend(user_perm_conditions)
			fetch_shared_docs = fetch_shared_docs or fetch_shared

		permission_query_conditions = self.get_permission_query_conditions()
		if permission_query_conditions:
			conditions.extend(permission_query_conditions)

		shared_docs = []
		if fetch_shared_docs:
			shared_docs = frappe.share.get_shared(self.doctype, self.user)

		if shared_docs:
			shared_condition = self.table.name.isin(shared_docs)
			if conditions:
				# (permission conditions) OR (shared condition)
				self.query = self.query.where(Criterion.all(conditions) | shared_condition)
			else:
				self.query = self.query.where(shared_condition)
		elif conditions:
			# AND all permission conditions
			self.query = self.query.where(Criterion.all(conditions))

	def get_permission_query_conditions(self):
		"""Add permission query conditions from hooks and server scripts"""
		from frappe.core.doctype.server_script.server_script_utils import get_server_script_map

		conditions = []
		hooks = frappe.get_hooks("permission_query_conditions", {})
		condition_methods = hooks.get(self.doctype, []) + hooks.get("*", [])

		for method in condition_methods:
			if c := frappe.call(frappe.get_attr(method), self.user, doctype=self.doctype):
				conditions.append(RawCriterion(c))

		# Get conditions from server scripts
		if permission_script_name := get_server_script_map().get("permission_query", {}).get(self.doctype):
			script = frappe.get_doc("Server Script", permission_script_name)
			if condition := script.get_permission_query_conditions(self.user):
				conditions.append(RawCriterion(condition))

		return conditions

	def get_permission_type(self, doctype) -> str:
		"""Get permission type (select/read) based on user permissions"""
		if frappe.only_has_select_perm(doctype, user=self.user):
			return "select"
		return "read"

	def requires_owner_constraint(self, role_permissions):
		"""Return True if "select" or "read" isn't available without being creator."""
		if not role_permissions.get("has_if_owner_enabled"):
			return

		if_owner_perms = role_permissions.get("if_owner")
		if not if_owner_perms:
			return

		# has select or read without if owner, no need for constraint
		for perm_type in ("select", "read"):
			if role_permissions.get(perm_type) and perm_type not in if_owner_perms:
				return

		# not checking if either select or read if present in if_owner_perms
		# because either of those is required to perform a query
		return True


class Permission:
	@classmethod
	def check_permissions(cls, query, **kwargs):
		if not isinstance(query, str):
			query = query.get_sql()

		doctype = cls.get_tables_from_query(query)
		if isinstance(doctype, str):
			doctype = [doctype]

		for dt in doctype:
			dt = TAB_PATTERN.sub("", dt)
			if not frappe.has_permission(
				dt,
				"select",
				user=kwargs.get("user"),
				parent_doctype=kwargs.get("parent_doctype"),
			) and not frappe.has_permission(
				dt,
				"read",
				user=kwargs.get("user"),
				parent_doctype=kwargs.get("parent_doctype"),
			):
				frappe.throw(
					_("Insufficient Permission for {0}").format(frappe.bold(dt)), frappe.PermissionError
				)

	@staticmethod
	def get_tables_from_query(query: str):
		return [table for table in WORDS_PATTERN.findall(query) if table.startswith("tab")]


class DynamicTableField:
	def __init__(
		self,
		doctype: str,
		fieldname: str,
		parent_doctype: str,
		alias: str | None = None,
	) -> None:
		self.doctype = doctype
		self.fieldname = fieldname
		self.alias = alias
		self.parent_doctype = parent_doctype

	def __str__(self) -> str:
		table_name = f"`tab{self.doctype}`"
		fieldname = f"`{self.fieldname}`"
		if frappe.db.db_type == "postgres":
			table_name = table_name.replace("`", '"')
			fieldname = fieldname.replace("`", '"')
		alias = f"AS {self.alias}" if self.alias else ""
		return f"{table_name}.{fieldname} {alias}".strip()

	@staticmethod
	def parse(field: str, doctype: str, allow_tab_notation: bool = True):
		if "." in field:
			alias = None
			# Handle 'as' alias, case-insensitive, taking the last occurrence
			if " as " in field.lower():
				parts = re.split(r"\s+as\s+", field, flags=re.IGNORECASE)
				if len(parts) > 1:
					field_part = parts[0].strip()
					alias = parts[-1].strip().strip('`"')  # Get last part as alias
					field = field_part  # Use the part before alias for further parsing

			child_match = None
			if allow_tab_notation:
				# Regex to match `tabDoc`.`field`, "tabDoc"."field", tabDoc.field
				# Group 1: Doctype name (without 'tab')
				# Group 2: Optional quote for fieldname
				# Group 3: Fieldname
				# Ensures quotes are consistent or absent on fieldname using backreference \2
				# Uses re.match to ensure the pattern matches the *entire* field string
				# Allow spaces in doctype name (Group 1) and field name (Group 3)
				child_match = re.match(r'[`"]?tab([\w\s]+)[`"]?\.([`"]?)([\w\s]+)\2$', field)

			if child_match:
				child_doctype_name = child_match.group(1)
				child_field = child_match.group(3)

				if child_doctype_name == doctype:
					# Referencing a field in the main doctype using `tabDoctype.field` notation.
					# This should be handled by the standard field parser, not as a DynamicTableField.
					return None
				# Found a child table reference like tabChildDoc.child_field
				# Note: parent_fieldname is None here as it's directly specified via tab notation
				return ChildTableField(child_doctype_name, child_field, doctype, alias=alias)
			else:
				# Try parsing as LinkTableField (link_field.target_field) or ChildTableField (child_field.target_field)
				# This handles patterns not starting with 'tab' prefix
				if "." not in field:  # Should not happen due to outer check, but safety
					return None

				parts = field.split(".", 1)
				if len(parts) != 2:  # Ensure it splits into exactly two parts
					return None
				potential_parent_fieldname, target_fieldname = parts

				# Basic validation for the parts to avoid unnecessary metadata lookups on invalid input
				# We expect simple identifiers here. Quoted/complex names are handled elsewhere or by child_match.
				if (
					not potential_parent_fieldname.replace("_", "").isalnum()
					or not target_fieldname.replace("_", "").isalnum()
				):
					return None

				try:
					meta = frappe.get_meta(doctype)  # Get meta of the *parent* doctype
					# Check if the first part is a valid fieldname in the parent doctype
					if not meta.has_field(potential_parent_fieldname):
						return None  # Not a field in the parent, so not link/child access pattern

					linked_field = meta.get_field(potential_parent_fieldname)
				except Exception:
					# Handle cases where doctype doesn't exist, etc.
					print(f"Error getting metadata for {doctype} while parsing field {field}")
					return None

				if linked_field:
					linked_doctype = linked_field.options
					if linked_field.fieldtype == "Link":
						# It's a Link field access: parent_doctype.link_fieldname.target_fieldname
						return LinkTableField(
							linked_doctype, target_fieldname, doctype, potential_parent_fieldname, alias=alias
						)
					elif linked_field.fieldtype in frappe.model.table_fields:
						# It's a Child Table field access: parent_doctype.child_table_fieldname.target_fieldname
						return ChildTableField(
							linked_doctype, target_fieldname, doctype, potential_parent_fieldname, alias=alias
						)

		return None

	def apply_select(self, query: QueryBuilder) -> QueryBuilder:
		raise NotImplementedError


class ChildTableField(DynamicTableField):
	def __init__(
		self,
		doctype: str,
		fieldname: str,
		parent_doctype: str,
		parent_fieldname: str | None = None,
		alias: str | None = None,
	) -> None:
		self.doctype = doctype
		self.fieldname = fieldname
		self.alias = alias
		self.parent_doctype = parent_doctype
		self.parent_fieldname = parent_fieldname
		self.table = frappe.qb.DocType(self.doctype)
		self.field = self.table[self.fieldname]

	def apply_select(self, query: QueryBuilder) -> QueryBuilder:
		table = frappe.qb.DocType(self.doctype)
		query = self.apply_join(query)
		return query.select(getattr(table, self.fieldname).as_(self.alias or None))

	def apply_join(self, query: QueryBuilder) -> QueryBuilder:
		main_table = frappe.qb.DocType(self.parent_doctype)
		if not query.is_joined(self.table):
			join_conditions = (self.table.parent == main_table.name) & (
				self.table.parenttype == self.parent_doctype
			)
			if self.parent_fieldname:
				join_conditions &= self.table.parentfield == self.parent_fieldname
			query = query.left_join(self.table).on(join_conditions)
		return query


class LinkTableField(DynamicTableField):
	def __init__(
		self,
		doctype: str,
		fieldname: str,
		parent_doctype: str,
		link_fieldname: str,
		alias: str | None = None,
	) -> None:
		super().__init__(doctype, fieldname, parent_doctype, alias=alias)
		self.link_fieldname = link_fieldname
		self.table = frappe.qb.DocType(self.doctype)
		self.field = self.table[self.fieldname]

	def apply_select(self, query: QueryBuilder) -> QueryBuilder:
		table = frappe.qb.DocType(self.doctype)
		query = self.apply_join(query)
		return query.select(getattr(table, self.fieldname).as_(self.alias or None))

	def apply_join(self, query: QueryBuilder) -> QueryBuilder:
		table = frappe.qb.DocType(self.doctype)
		main_table = frappe.qb.DocType(self.parent_doctype)
		if not query.is_joined(table):
			query = query.left_join(table).on(table.name == getattr(main_table, self.link_fieldname))
		return query


class ChildQuery:
	def __init__(
		self,
		fieldname: str,
		fields: list,
		parent_doctype: str,
	) -> None:
		field = frappe.get_meta(parent_doctype).get_field(fieldname)
		if field.fieldtype not in frappe.model.table_fields:
			return
		self.fieldname = fieldname
		self.fields = fields
		self.parent_doctype = parent_doctype
		self.doctype = field.options

	def get_query(self, parent_names=None) -> QueryBuilder:
		filters = {
			"parenttype": self.parent_doctype,
			"parentfield": self.fieldname,
			"parent": ["in", parent_names],
		}
		return frappe.qb.get_query(
			self.doctype,
			fields=[*self.fields, "parent", "parentfield"],
			filters=filters,
			order_by="idx asc",
		)


def get_nested_set_hierarchy_result(doctype: str, name: str, hierarchy: str) -> list[str]:
	"""Get matching nodes based on operator."""
	table = frappe.qb.DocType(doctype)
	try:
		lft, rgt = frappe.qb.from_(table).select("lft", "rgt").where(table.name == name).run()[0]
	except IndexError:
		lft, rgt = None, None

	if hierarchy in ("descendants of", "not descendants of", "descendants of (inclusive)"):
		result = (
			frappe.qb.from_(table)
			.select(table.name)
			.where(table.lft > lft)
			.where(table.rgt < rgt)
			.orderby(table.lft, order=Order.asc)
			.run(pluck=True)
		)
		if hierarchy == "descendants of (inclusive)":
			result += [name]
	else:
		# Get ancestor elements of a DocType with a tree structure
		result = (
			frappe.qb.from_(table)
			.select(table.name)
			.where(table.lft < lft)
			.where(table.rgt > rgt)
			.orderby(table.lft, order=Order.desc)
			.run(pluck=True)
		)
	return result


@lru_cache(maxsize=1024)
def _validate_select_field(field: str):
	"""Validate a field string intended for use in a SELECT clause."""
	if field == "*":
		return

	if field.isdigit():
		return

	if ALLOWED_FIELD_PATTERN.match(field):
		return

	frappe.throw(
		_(
			"Invalid field format for SELECT: {0}. Field names must be simple, backticked, table-qualified, aliased, or '*'."
		).format(field),
		frappe.PermissionError,
	)


@lru_cache(maxsize=1024)
def _sanitize_field(field: str, is_mariadb):
	"""Validate and sanitize a field string for SELECT clause by stripping comments."""
	_validate_select_field(field)

	stripped_field = sqlparse.format(field, strip_comments=True, keyword_case="lower")

	if is_mariadb:
		stripped_field = MARIADB_SPECIFIC_COMMENT.sub("", stripped_field)

	return stripped_field.strip()


class RawCriterion(Term):
	"""A class to represent raw SQL string as a criterion.

	Allows using raw SQL strings in pypika queries:
		frappe.qb.from_("DocType").where(RawCriterion("name like 'a%'"))
	"""

	def __init__(self, sql_string: str):
		self.sql_string = sql_string
		super().__init__()

	def get_sql(self, **kwargs: Any) -> str:
		return self.sql_string

	def __and__(self, other):
		return CombinedRawCriterion(self, other, "AND")

	def __or__(self, other):
		return CombinedRawCriterion(self, other, "OR")

	def __invert__(self):
		return RawCriterion(f"NOT ({self.sql_string})")


class CombinedRawCriterion(RawCriterion):
	def __init__(self, left, right, operator):
		self.left = left
		self.right = right
		self.operator = operator
		super(RawCriterion, self).__init__()

	def get_sql(self, **kwargs: Any) -> str:
		left_sql = self.left.get_sql(**kwargs) if hasattr(self.left, "get_sql") else str(self.left)
		right_sql = self.right.get_sql(**kwargs) if hasattr(self.right, "get_sql") else str(self.right)
		return f"({left_sql}) {self.operator} ({right_sql})"


class SQLFunctionParser:
	"""Parser for SQL function dictionaries in query builder fields."""

	def __init__(self, engine):
		self.engine = engine

	def is_function_dict(self, field_dict: dict) -> bool:
		"""Check if a dictionary represents a SQL function definition."""
		function_keys = [k for k in field_dict.keys() if k != "as"]
		return len(function_keys) == 1 and function_keys[0] in FUNCTION_MAPPING

	def parse_function(self, function_dict: dict) -> Field:
		"""Parse a SQL function dictionary into a pypika function call."""
		function_name = None
		alias = None
		function_args = None

		for key, value in function_dict.items():
			if key == "as":
				alias = value
			else:
				function_name = key
				function_args = value

		if not function_name:
			frappe.throw(_("Invalid function dictionary format"), frappe.ValidationError)

		if function_name not in FUNCTION_MAPPING:
			frappe.throw(
				_("Unsupported function or invalid field name: {0}").format(function_name),
				frappe.ValidationError,
			)

		if alias:
			self._validate_alias(alias)

		func_class = FUNCTION_MAPPING.get(function_name)
		if not func_class:
			frappe.throw(
				_("Unsupported function or invalid field name: {0}").format(function_name),
				frappe.ValidationError,
			)

		if isinstance(function_args, str):
			parsed_arg = self._parse_and_validate_argument(function_args)
			function_call = func_class(parsed_arg)
		elif isinstance(function_args, list):
			parsed_args = []
			for arg in function_args:
				parsed_arg = self._parse_and_validate_argument(arg)
				parsed_args.append(parsed_arg)
			function_call = func_class(*parsed_args)
		elif isinstance(function_args, (int | float)):
			function_call = func_class(function_args)
		elif function_args is None:
			try:
				function_call = func_class()
			except TypeError:
				frappe.throw(
					_("Function {0} requires arguments but none were provided").format(function_name),
					frappe.ValidationError,
				)
		else:
			frappe.throw(
				_(
					"Invalid function argument type: {0}. Only strings, numbers, lists, and None are allowed."
				).format(type(function_args).__name__),
				frappe.ValidationError,
			)

		if alias:
			return function_call.as_(alias)
		else:
			return function_call

	def _parse_and_validate_argument(self, arg):
		"""Parse and validate a single function argument against SQL injection."""
		if isinstance(arg, (int | float)):
			return arg
		elif isinstance(arg, str):
			return self._validate_string_argument(arg)
		elif arg is None:
			# None is allowed for some functions
			return arg
		else:
			frappe.throw(
				_("Invalid argument type: {0}. Only strings, numbers, and None are allowed.").format(
					type(arg).__name__
				),
				frappe.ValidationError,
			)

	def _validate_string_argument(self, arg: str):
		"""Validate string arguments to prevent SQL injection."""
		arg = arg.strip()

		if not arg:
			frappe.throw(_("Empty string arguments are not allowed"), frappe.ValidationError)

		# Check for string literals (quoted strings)
		if self._is_string_literal(arg):
			return self._validate_string_literal(arg)

		elif self._is_valid_field_name(arg):
			# Validate field name and check permissions
			self._validate_function_field_arg(arg)
			return self.engine.table[arg]

		else:
			frappe.throw(
				_(
					"Invalid argument format: {0}. Only quoted string literals or simple field names are allowed."
				).format(arg),
				frappe.ValidationError,
			)

	def _is_string_literal(self, arg: str) -> bool:
		"""Check if argument is a properly quoted string literal."""
		return (arg.startswith("'") and arg.endswith("'") and len(arg) >= 2) or (
			arg.startswith('"') and arg.endswith('"') and len(arg) >= 2
		)

	def _validate_string_literal(self, literal: str):
		"""Validate a string literal for SQL injection attacks."""
		if literal.startswith("'") and literal.endswith("'"):
			quote_char = "'"
			content = literal[1:-1]
		elif literal.startswith('"') and literal.endswith('"'):
			quote_char = '"'
			content = literal[1:-1]
		else:
			frappe.throw(_("Invalid string literal format: {0}").format(literal), frappe.ValidationError)

		if quote_char in content:
			escaped_content = content.replace(quote_char + quote_char, "")
			if quote_char in escaped_content:
				frappe.throw(
					_("Unescaped quotes in string literal: {0}").format(literal),
					frappe.ValidationError,
				)

		# Reject dangerous SQL keywords and patterns
		dangerous_patterns = [
			# SQL injection keywords
			r"\b(?:union|select|insert|update|delete|drop|create|alter|exec|execute)\b",
			# Comment patterns
			r"--",
			r"/\*",
			r"\*/",
			# Semicolon (statement terminator)
			r";",
			# Backslash escape sequences that could be dangerous
			r"\\x[0-9a-fA-F]{2}",  # Hex escape sequences
			r"\\[0-7]{1,3}",  # Octal escape sequences
		]

		content_lower = content.lower()
		for pattern in dangerous_patterns:
			if re.search(pattern, content_lower, re.IGNORECASE):
				frappe.throw(
					_("Potentially dangerous content in string literal: {0}").format(literal),
					frappe.ValidationError,
				)

		# Return just the content without quotes - pypika will handle proper escaping
		return content

	def _is_valid_field_name(self, name: str) -> bool:
		"""Check if a string is a valid field name."""
		# Field names should only contain alphanumeric characters and underscores
		return re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name) is not None

	def _validate_alias(self, alias: str):
		"""Validate alias name for SQL injection."""
		if not isinstance(alias, str):
			frappe.throw(_("Alias must be a string"), frappe.ValidationError)

		alias = alias.strip()
		if not alias:
			frappe.throw(_("Empty alias is not allowed"), frappe.ValidationError)

		# Alias should be a simple identifier
		if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", alias):
			frappe.throw(
				_("Invalid alias format: {0}. Alias must be a simple identifier.").format(alias),
				frappe.ValidationError,
			)

		# Check for SQL keywords that shouldn't be used as aliases
		sql_keywords = {
			"select",
			"from",
			"where",
			"join",
			"inner",
			"left",
			"right",
			"outer",
			"union",
			"group",
			"order",
			"by",
			"having",
			"limit",
			"offset",
			"insert",
			"update",
			"delete",
			"create",
			"drop",
			"alter",
			"table",
			"index",
			"view",
			"database",
			"schema",
			"grant",
			"revoke",
			"commit",
			"rollback",
			"transaction",
			"begin",
			"end",
			"if",
			"else",
			"case",
			"when",
			"then",
			"null",
			"not",
			"and",
			"or",
			"in",
			"exists",
			"between",
			"like",
			"is",
			"as",
			"on",
			"using",
			"distinct",
			"all",
			"any",
			"some",
			"true",
			"false",
		}

		if alias.lower() in sql_keywords:
			frappe.throw(
				_("Alias cannot be a SQL keyword: {0}").format(alias),
				frappe.ValidationError,
			)

	def _validate_function_field_arg(self, field_name: str):
		"""Validate a field name used as a function argument."""
		if not isinstance(field_name, str):
			return  # Non-string arguments are allowed (literals)

		# Basic validation - should be a simple field name
		if not self._is_valid_field_name(field_name):
			frappe.throw(
				_("Invalid field name in function: {0}. Only simple field names are allowed.").format(
					field_name
				),
				frappe.ValidationError,
			)

		# Check field permission if permissions are being applied
		if self.engine.apply_permissions and self.engine.doctype:
			self.engine._check_field_permission(self.engine.doctype, field_name)
