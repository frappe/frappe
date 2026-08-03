import pypika.terms
from pypika import *
from pypika import Field
from pypika.utils import ignore_copy

from frappe.query_builder.terms import (
	BasicCriterionPatched,
	ComplexCriterionPatched,
	FieldPatched,
	ParameterizedFunction,
	ParameterizedValueWrapper,
	format_quotes_patched,
)
from frappe.query_builder.utils import (
	Column,
	DocType,
	get_query,
	get_query_builder,
	patch_all,
)

pypika.terms.ValueWrapper = ParameterizedValueWrapper
pypika.terms.Function.get_sql = ParameterizedFunction.get_sql
pypika.terms.Function = ParameterizedFunction

# * Overrides the field() method and replaces it with the a `PseudoColumn` 'field' for consistency
pypika.queries.Selectable.__getattr__ = ignore_copy(lambda table, x: FieldPatched(x, table=table))
pypika.queries.Selectable.__getitem__ = ignore_copy(lambda table, x: FieldPatched(x, table=table))
pypika.queries.Selectable.field = pypika.terms.PseudoColumn("field")

# ===========================================================
# Overrides anywhere `format_quotes` may already have been looked up. (as part of utils!)
pypika.utils.format_quotes = format_quotes_patched
pypika.terms.format_quotes = format_quotes_patched
pypika.queries.format_quotes = format_quotes_patched
pypika.dialects.format_quotes = format_quotes_patched

pypika.terms.Field = FieldPatched
pypika.terms.ComplexCriterion = ComplexCriterionPatched
pypika.terms.BasicCriterion = BasicCriterionPatched
pypika.queries.Field = FieldPatched
pypika.Field = FieldPatched
# =============================================================

# run monkey patches
patch_all()
